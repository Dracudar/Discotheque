"""
audio_hash.py - Empreinte de l'audio, indépendante des tags

Description:
    Empreinte de l'audio d'un fichier, qui ne change pas quand on réécrit ses tags. Elle
    sert à vérifier qu'un lot de tags n'a pas touché l'audio, à savoir sans décoder si
    l'audio d'une piste a changé (« l'index d'abord ») et à contrôler les copies.

    | Format     | Empreinte (SHA-1)                                               |
    |------------|-----------------------------------------------------------------|
    | MP3        | octets entre les tags ID3v2 du début et les tags de fin         |
    |            | (APEv2, Lyrics3v2, ID3v1, ID3v2 de fin)                         |
    | FLAC       | octets des trames, après les blocs de métadonnées ; le MD5 de   |
    |            | `STREAMINFO` (flux décodé) est gardé comme second contrôle      |
    | M4A / MP4  | contenu des atomes `mdat` (une réécriture peut les déplacer)    |
    | Ogg / Opus | MD5 des paquets audio par `ffmpeg -c:a copy -f md5` (une        |
    |            | réécriture des tags peut redécouper les pages Ogg)              |

    MP3, FLAC et MP4 sont lus sans décodage ni outil externe : on ne lit que la
    structure du conteneur. Le format est reconnu au contenu du fichier, pas à son
    extension (sauf un MP3 sans tag dont le début est abîmé, reconnu à « .mp3 »).

    Chaque empreinte porte le nom de sa méthode et la version de son algorithme, comme
    les autres mesures : changer l'algorithme d'un format ne fait recalculer que les
    fichiers de ce format. Un format inconnu, un fichier illisible ou sans audio lève
    `AudioHashError` : il n'y a jamais d'empreinte vide, et deux fichiers sans audio
    ne peuvent pas passer pour identiques.

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.19

Date de modification :
    2026.10.19
"""

from __future__ import annotations

import hashlib
import struct
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from src.backend import config

# Version de l'algorithme de chaque méthode : à augmenter quand le calcul change.
VERSIONS = {"mp3": 1, "flac": 1, "mp4": 1, "ogg": 1}

CHUNK = 1 << 20  # lecture par blocs de 1 Mio
FFMPEG_TIMEOUT = 600  # secondes, large pour les longues pistes sur disque lent
EMPTY_MD5 = hashlib.md5(b"").hexdigest()

ID3V2_HEADER = 10
ID3V1_SIZE = 128
APE_FOOTER = 32
LYRICS3_END = b"LYRICS200"


class AudioHashError(Exception):
    """L'empreinte n'a pas pu être calculée (format inconnu, fichier illisible, abîmé
    ou sans audio). Le message dit pourquoi, en français."""


@dataclass(frozen=True)
class AudioHash:
    """Empreinte de l'audio d'un fichier.

    Attributes:
        method: Méthode de calcul (« mp3 », « flac », « mp4 », « ogg »).
        version: Version de l'algorithme de cette méthode.
        digest: Empreinte en hexadécimal (SHA-1, ou MD5 de ffmpeg pour « ogg »).
        size: Nombre d'octets audio pris en compte (0 pour « ogg », calculé par ffmpeg).
        streaminfo_md5: FLAC seulement : MD5 du flux décodé écrit dans `STREAMINFO`
            par l'encodeur, ou None s'il est absent (zéros).
    """

    method: str
    version: int
    digest: str
    size: int = 0
    streaminfo_md5: str | None = None

    @property
    def key(self) -> str:
        """Forme courte à stocker ou comparer (« mp3:1:<empreinte> »)."""
        return f"{self.method}:{self.version}:{self.digest}"

    def same_audio(self, other: AudioHash) -> bool:
        """Vrai si les deux empreintes désignent le même audio.

        Il faut la même méthode, la même version et la même empreinte ; pour un FLAC,
        le MD5 de `STREAMINFO` doit aussi être le même. Deux empreintes calculées par
        des versions différentes ne sont pas comparables : il faut recalculer.

        Args:
            other: L'autre empreinte.
        """
        return self.key == other.key and self.streaminfo_md5 == other.streaminfo_md5


# --------------------------------------------------------------------- lecture
def _read_at(f: BinaryIO, offset: int, n: int) -> bytes:
    """Lit `n` octets à la position `offset` (moins si la fin du fichier est atteinte)."""
    f.seek(offset)
    return f.read(n)


def _ranges_sha1(f: BinaryIO, ranges: list[tuple[int, int]]) -> tuple[str, int]:
    """SHA-1 des octets des plages `(début, fin)` mises bout à bout.

    Returns:
        L'empreinte en hexadécimal et le nombre d'octets lus.

    Raises:
        AudioHashError: Le fichier est plus court que prévu, ou les plages sont vides.
    """
    h = hashlib.sha1()
    total = 0
    for start, end in ranges:
        f.seek(start)
        left = end - start
        while left > 0:
            block = f.read(min(CHUNK, left))
            if not block:
                raise AudioHashError(f"fichier tronqué : {left} octets audio manquants")
            h.update(block)
            left -= len(block)
            total += len(block)
    if total == 0:
        raise AudioHashError("aucune donnée audio")
    return h.hexdigest(), total


def _syncsafe(b: bytes) -> int:
    """Entier « syncsafe » des tags ID3v2 (7 bits utiles par octet)."""
    return (b[0] << 21) | (b[1] << 14) | (b[2] << 7) | b[3]


def _skip_id3v2(f: BinaryIO, offset: int, end: int) -> int:
    """Position après le ou les tags ID3v2 qui commencent à `offset` (pied compris)."""
    while offset + ID3V2_HEADER <= end:
        head = _read_at(f, offset, ID3V2_HEADER)
        if head[:3] != b"ID3" or head[3] == 0xFF or any(x & 0x80 for x in head[6:10]):
            break
        size = ID3V2_HEADER + _syncsafe(head[6:10])
        if head[5] & 0x10:  # pied présent
            size += ID3V2_HEADER
        offset += size
    return min(offset, end)


def _strip_trailing_tags(f: BinaryIO, start: int, end: int) -> int:
    """Fin de l'audio, avant les tags de fin (ID3v1, APEv2, Lyrics3v2, ID3v2 de fin).

    Ces tags peuvent s'empiler dans n'importe quel ordre : on les retire tant qu'on en
    reconnaît un à la fin de la plage.
    """
    while True:
        if end - start >= ID3V1_SIZE and _read_at(f, end - ID3V1_SIZE, 3) == b"TAG":
            end -= ID3V1_SIZE
            continue
        if end - start >= APE_FOOTER:
            foot = _read_at(f, end - APE_FOOTER, APE_FOOTER)
            if foot[:8] == b"APETAGEX":
                size, flags = struct.unpack("<I4xI", foot[12:24])
                if flags & 0x80000000:  # en-tête présent
                    size += APE_FOOTER
                if APE_FOOTER <= size <= end - start:
                    end -= size
                    continue
            if foot[-10:-7] == b"3DI":  # pied d'un ID3v2 placé en fin de fichier
                d = foot[-10:]
                size = 2 * ID3V2_HEADER + _syncsafe(d[6:10])
                if size <= end - start:
                    end -= size
                    continue
        if end - start >= 15 and _read_at(f, end - 9, 9) == LYRICS3_END:
            digits = _read_at(f, end - 15, 6)
            if digits.isdigit():
                size = int(digits) + 15
                if size <= end - start and _read_at(f, end - size, 11) == b"LYRICSBEGIN":
                    end -= size
                    continue
        return end


def _file_size(f: BinaryIO) -> int:
    """Taille du fichier ouvert."""
    return f.seek(0, 2)


# --------------------------------------------------------------------- formats
def _mp3(f: BinaryIO) -> AudioHash:
    """Empreinte d'un MP3 : octets entre les tags du début et ceux de la fin.

    On ne cherche pas la première trame : des octets parasites entre le tag et l'audio
    font partie de l'audio (une réécriture des tags ne les touche pas), et un MP3 aux
    trames abîmées garde ainsi une empreinte stable.
    """
    size = _file_size(f)
    start = _skip_id3v2(f, 0, size)
    end = _strip_trailing_tags(f, start, size)
    digest, n = _ranges_sha1(f, [(start, end)])
    return AudioHash("mp3", VERSIONS["mp3"], digest, n)


def _flac(f: BinaryIO, start: int) -> AudioHash:
    """Empreinte d'un FLAC : octets des trames, après les blocs de métadonnées.

    Args:
        f: Fichier ouvert.
        start: Position du marqueur « fLaC » (après un éventuel ID3v2).
    """
    size = _file_size(f)
    pos = start + 4
    streaminfo: bytes | None = None
    first = True
    while True:
        head = _read_at(f, pos, 4)
        if len(head) < 4:
            raise AudioHashError("FLAC tronqué dans les blocs de métadonnées")
        last, kind = head[0] & 0x80, head[0] & 0x7F
        length = int.from_bytes(head[1:4], "big")
        if first:
            if kind != 0 or length < 34:
                raise AudioHashError("FLAC invalide : STREAMINFO absent en tête")
            streaminfo = _read_at(f, pos + 4, 34)
            first = False
        pos += 4 + length
        if pos > size:
            raise AudioHashError("FLAC tronqué dans les blocs de métadonnées")
        if last:
            break
    end = _strip_trailing_tags(f, pos, size)
    digest, n = _ranges_sha1(f, [(pos, end)])
    md5 = streaminfo[18:34].hex() if streaminfo and len(streaminfo) == 34 else None
    if md5 and int(md5, 16) == 0:
        md5 = None
    return AudioHash("flac", VERSIONS["flac"], digest, n, md5)


def _mp4_atoms(f: BinaryIO, size: int) -> Iterator[tuple[bytes, int, int]]:
    """Atomes de premier niveau d'un MP4 : (type, début du contenu, fin du contenu).

    Raises:
        AudioHashError: Un atome est mal formé ou dépasse la fin du fichier.
    """
    pos = 0
    while pos < size:
        head = _read_at(f, pos, 8)
        if len(head) < 8:
            raise AudioHashError("MP4 tronqué : en-tête d'atome incomplet")
        length, kind = struct.unpack(">I4s", head)
        body = pos + 8
        if length == 1:  # taille sur 64 bits
            ext = _read_at(f, body, 8)
            if len(ext) < 8:
                raise AudioHashError("MP4 tronqué : en-tête d'atome incomplet")
            length = struct.unpack(">Q", ext)[0]
            body += 8
        elif length == 0:  # jusqu'à la fin du fichier
            length = size - pos
        if length < body - pos or pos + length > size:
            raise AudioHashError(f"MP4 abîmé ou tronqué : atome {kind!r} de taille invalide")
        yield kind, body, pos + length
        pos += length


def _mp4(f: BinaryIO) -> AudioHash:
    """Empreinte d'un M4A / MP4 : contenu des atomes `mdat`, dans l'ordre du fichier."""
    ranges = [(start, end) for kind, start, end in _mp4_atoms(f, _file_size(f)) if kind == b"mdat"]
    if not ranges:
        raise AudioHashError("MP4 sans atome mdat : aucune donnée audio")
    digest, n = _ranges_sha1(f, ranges)
    return AudioHash("mp4", VERSIONS["mp4"], digest, n)


def _ogg(path: Path, ffmpeg: str | None) -> AudioHash:
    """Empreinte d'un Ogg (Opus, Vorbis, FLAC) : MD5 des paquets audio, par ffmpeg.

    Les en-têtes (dont les commentaires) ne sont pas des paquets audio pour ffmpeg :
    ils n'entrent pas dans l'empreinte.

    Args:
        path: Fichier.
        ffmpeg: Commande de ffmpeg ; None : celle de la configuration, ou « ffmpeg »
            cherché dans le PATH s'il n'y a pas de configuration (comme `disco doctor`).
    """
    if ffmpeg is None:
        try:
            ffmpeg = config.load().ffmpeg
        except config.ConfigError:
            ffmpeg = "ffmpeg"
    cmd = [ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a", "-c:a", "copy", "-f", "md5", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
    except FileNotFoundError as e:
        raise AudioHashError(f"ffmpeg introuvable ({ffmpeg})") from e
    except subprocess.TimeoutExpired as e:
        raise AudioHashError(f"ffmpeg n'a pas fini en {FFMPEG_TIMEOUT} s") from e
    out = r.stdout.strip()
    if r.returncode != 0 or not out.startswith("MD5="):
        detail = r.stderr.strip().splitlines()[-1:] or [f"code {r.returncode}"]
        raise AudioHashError(f"ffmpeg n'a pas pu lire l'audio : {detail[0]}")
    digest = out[4:].strip().lower()
    if len(digest) != 32 or digest == EMPTY_MD5:
        raise AudioHashError("aucun paquet audio")
    return AudioHash("ogg", VERSIONS["ogg"], digest)


# --------------------------------------------------------------------- entrée
def _is_mpeg_sync(b: bytes) -> bool:
    """Vrai si `b` commence par une synchro de trame MPEG audio (11 bits à 1)."""
    return len(b) >= 2 and b[0] == 0xFF and (b[1] & 0xE0) == 0xE0


def compute(path: Path | str, ffmpeg: str | None = None) -> AudioHash:
    """Empreinte de l'audio d'un fichier, indépendante de ses tags.

    Args:
        path: Fichier audio (MP3, FLAC, M4A / MP4, Ogg / Opus).
        ffmpeg: Commande de ffmpeg (`Config.ffmpeg`), utilisée pour les Ogg seulement ;
            None : lue dans la configuration au besoin (« ffmpeg » du PATH sans
            configuration).

    Returns:
        L'empreinte, avec sa méthode et la version de l'algorithme.

    Raises:
        AudioHashError: Format inconnu, fichier illisible, abîmé au point de ne pas
            trouver l'audio, ou sans aucune donnée audio.
    """
    path = Path(path)
    try:
        with path.open("rb") as f:
            size = _file_size(f)
            if size == 0:
                raise AudioHashError("fichier vide")
            head = _read_at(f, 0, 12)
            if head[4:8] == b"ftyp":
                return _mp4(f)
            if head[:4] != b"OggS":
                # Un FLAC ou un MP3 peut commencer par un ID3v2
                start = _skip_id3v2(f, 0, size) if head[:3] == b"ID3" else 0
                after = _read_at(f, start, 4)
                if after == b"fLaC":
                    return _flac(f, start)
                if head[:3] == b"ID3" or _is_mpeg_sync(after) or path.suffix.lower() == ".mp3":
                    return _mp3(f)
                raise AudioHashError("format inconnu")
    except OSError as e:
        raise AudioHashError(f"lecture impossible : {e.strerror or e}") from e
    # Ogg : le fichier est refermé, ffmpeg le relit lui-même
    return _ogg(path, ffmpeg)
