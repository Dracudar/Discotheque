"""
test_audio_hash.py - Tests de l'empreinte audio

Description:
    Tests de `src.backend.audio_hash` sur des fichiers synthétiques générés par ffmpeg
    (MP3, FLAC, M4A, Opus, Vorbis) : l'empreinte ne bouge pas quand mutagen réécrit les
    tags (ajout, suppression, agrandissement au-delà du remplissage, ID3v1, APEv2),
    elle change si un octet audio change, elle reste stable sur des trames abîmées, et
    un fichier inconnu, vide ou sans audio lève une erreur au lieu d'une empreinte vide.

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.19

Date de modification :
    2026.10.19
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
from mutagen.apev2 import APEv2
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, ID3, TIT2, TXXX
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from src.backend import audio_hash, config
from src.backend.audio_hash import AudioHashError, compute


def _ffmpeg() -> str:
    """ffmpeg tel que la configuration le trouve, sinon par son nom (cas de la CI)."""
    try:
        return config.load().ffmpeg
    except config.ConfigError:
        return "ffmpeg"


FFMPEG = _ffmpeg()
HAS_FFMPEG = shutil.which(FFMPEG) is not None

# En CI, ffmpeg doit être présent : les tests ne peuvent pas être sautés.
pytestmark = pytest.mark.skipif(not os.environ.get("CI") and not HAS_FFMPEG, reason="ffmpeg absent")

BIG = 300_000  # octets : bien au-delà du remplissage laissé par ffmpeg et mutagen

# Format -> (extension, options d'encodage ffmpeg)
FORMATS = {
    "mp3": (".mp3", ["-c:a", "libmp3lame", "-b:a", "128k"]),
    "flac": (".flac", ["-c:a", "flac"]),
    "m4a": (".m4a", ["-c:a", "aac", "-b:a", "128k"]),
    "m4a_faststart": (".m4a", ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]),
    "opus": (".opus", ["-c:a", "libopus", "-b:a", "96k"]),
    "vorbis": (".ogg", ["-c:a", "libvorbis", "-q:a", "3"]),
}


def _encoders() -> str:
    """Liste des encodeurs de ffmpeg (texte brut), vide si ffmpeg est absent."""
    if not HAS_FFMPEG:
        return ""
    return subprocess.run([FFMPEG, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout


ENCODERS = _encoders()


@pytest.fixture(scope="module")
def originals(tmp_path_factory) -> dict[str, Path]:
    """Un fichier de 8 s par format, généré une seule fois (sinus et bruit, stéréo)."""
    d = tmp_path_factory.mktemp("originaux")
    files = {}
    for name, (ext, codec) in FORMATS.items():
        if codec[1] not in ENCODERS:
            continue
        f = d / f"{name}{ext}"
        subprocess.run(
            [FFMPEG, "-nostdin", "-v", "error", "-f", "lavfi", "-i", "sine=f=440:d=8", "-f", "lavfi", "-i", "anoisesrc=d=8:a=0.1:seed=1"]
            + ["-filter_complex", "amix=inputs=2", "-ar", "48000", "-ac", "2", *codec, str(f)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        files[name] = f
    return files


@pytest.fixture
def copy(originals, tmp_path):
    """Copie de travail d'un original : les réécritures ne touchent jamais l'original."""

    def _copy(name: str) -> Path:
        if name not in originals:
            pytest.skip(f"encodeur absent de ffmpeg pour {name}")
        return Path(shutil.copy(originals[name], tmp_path / originals[name].name))

    return _copy


def h(path: Path) -> audio_hash.AudioHash:
    """Empreinte avec le ffmpeg des tests."""
    return compute(path, FFMPEG)


def _flip_byte(path: Path, offset: int) -> None:
    """Inverse les bits d'un octet du fichier."""
    with path.open("r+b") as f:
        f.seek(offset)
        b = f.read(1)
        f.seek(offset)
        f.write(bytes([b[0] ^ 0xFF]))


# --------------------------------------------------------------------- MP3
def test_mp3_tags_rewritten(copy):
    f = copy("mp3")
    ref = h(f)
    assert ref.method == "mp3" and ref.version == audio_hash.VERSIONS["mp3"]

    tags = ID3()
    tags.add(TIT2(encoding=3, text="Titre inventé"))
    tags.save(f, padding=lambda info: 0)  # aucun remplissage : la suite devra agrandir
    assert h(f).same_audio(ref)

    tags = ID3(f)
    tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=b"\x00" * BIG))
    tags.add(TXXX(encoding=3, desc="note", text="x" * 5000))
    tags.save(f)
    assert h(f).same_audio(ref)

    tags = ID3(f)
    tags.save(f, v1=2)  # ID3v1 en fin de fichier
    assert f.read_bytes()[-128:-125] == b"TAG"
    assert h(f).same_audio(ref)

    ape = APEv2()
    ape["Title"] = "Titre inventé"
    ape.save(f)  # APEv2, placé avant l'ID3v1
    assert b"APETAGEX" in f.read_bytes()[-1024:]
    assert h(f).same_audio(ref)

    APEv2(f).delete()
    ID3(f).delete(f)
    assert f.read_bytes()[:3] != b"ID3"
    assert h(f).same_audio(ref)


def test_mp3_lyrics3_and_trailing_id3v2(copy):
    f = copy("mp3")
    ref = h(f)
    body = b"IND0000210" + b"LYR00005hello"
    lyrics = b"LYRICSBEGIN" + body + f"{len(b'LYRICSBEGIN' + body):06d}".encode() + b"LYRICS200"
    id3v1 = b"TAG" + b"\x00" * 125
    # ID3v2.4 en fin de fichier, avec pied (« 3DI ») : 10 octets de corps
    trailing = b"ID3\x04\x00\x10\x00\x00\x00\x0a" + b"\x00" * 10 + b"3DI\x04\x00\x10\x00\x00\x00\x0a"
    with f.open("ab") as out:
        out.write(trailing + lyrics + id3v1)
    assert h(f).same_audio(ref)


def test_mp3_audio_byte_changed(copy):
    f = copy("mp3")
    ref = h(f)
    _flip_byte(f, f.stat().st_size // 2)
    assert not h(f).same_audio(ref)


def test_mp3_damaged_frames(copy):
    """Trames abîmées (« Header missing ») : l'empreinte se calcule et reste stable."""
    f = copy("mp3")
    data = bytearray(f.read_bytes())
    # Efface quelques en-têtes de trame au milieu du fichier
    middle = len(data) // 2
    for _ in range(3):
        i = data.find(b"\xff\xfb", middle)
        assert i > 0
        data[i : i + 4] = b"\x00\x00\x00\x00"
        middle = i + 200
    f.write_bytes(bytes(data))
    ref = h(f)
    assert h(f) == ref

    tags = ID3(f)
    tags.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="", data=b"\x00" * BIG))
    tags.save(f, v1=2)
    assert h(f).same_audio(ref)


def test_mp3_without_id3_damaged_start(copy, tmp_path):
    """Un MP3 sans tag dont le début est abîmé est reconnu à son extension."""
    f = copy("mp3")
    ID3(f).delete(f)
    data = bytearray(f.read_bytes())
    data[:4] = b"\x00\x00\x00\x00"
    f.write_bytes(bytes(data))
    assert h(f).method == "mp3"
    other = tmp_path / "sans_extension.bin"
    other.write_bytes(bytes(data))
    with pytest.raises(AudioHashError, match="format inconnu"):
        h(other)


# --------------------------------------------------------------------- FLAC
def test_flac_tags_rewritten(copy):
    f = copy("flac")
    ref = h(f)
    assert ref.method == "flac"
    assert ref.streaminfo_md5 and len(ref.streaminfo_md5) == 32

    tags = FLAC(f)
    tags["title"] = "Titre inventé"
    tags.save()
    assert h(f).same_audio(ref)

    tags = FLAC(f)
    pic = Picture()
    pic.type, pic.mime, pic.data = 3, "image/jpeg", b"\x00" * BIG
    tags.add_picture(pic)
    tags["comment"] = "x" * 5000
    tags.save()
    assert h(f).same_audio(ref)

    ape = APEv2()
    ape["Title"] = "Titre inventé"
    ape.save(f)
    tags = ID3()
    tags.add(TIT2(encoding=3, text="Titre inventé"))
    tags.save(f, v1=2, v2_version=3)  # ID3v2 devant « fLaC » et ID3v1 en fin
    assert f.read_bytes()[:3] == b"ID3"
    assert h(f).same_audio(ref)

    tags = FLAC(f)
    tags.clear_pictures()
    tags.delete()
    tags.save(deleteid3=True)
    APEv2(f).delete()
    assert f.read_bytes()[:4] == b"fLaC"
    assert h(f).same_audio(ref)


def test_flac_audio_byte_changed(copy):
    f = copy("flac")
    ref = h(f)
    _flip_byte(f, f.stat().st_size // 2)
    after = h(f)
    assert not after.same_audio(ref)
    # Le MD5 de STREAMINFO ne bouge pas : il décrit l'audio attendu, pas les octets
    assert after.streaminfo_md5 == ref.streaminfo_md5


def test_flac_streaminfo_compared(copy):
    """Même trames, MD5 de STREAMINFO différent : pas le même audio."""
    a = h(copy("flac"))
    b = audio_hash.AudioHash(a.method, a.version, a.digest, a.size, "0" * 31 + "1")
    assert not a.same_audio(b)


def test_flac_damaged_frames(copy):
    f = copy("flac")
    data = bytearray(f.read_bytes())
    middle = len(data) // 2
    data[middle : middle + 64] = b"\x00" * 64
    f.write_bytes(bytes(data))
    ref = h(f)
    tags = FLAC(f)
    tags["title"] = "y" * BIG
    tags.save()
    assert h(f).same_audio(ref)


def test_flac_metadata_only(copy):
    f = copy("flac")
    tags = FLAC(f)
    audio_start = f.read_bytes().find(b"\xff\xf8")  # première trame
    assert tags and audio_start > 0
    with f.open("r+b") as out:
        out.truncate(audio_start)
    with pytest.raises(AudioHashError, match="aucune donnée audio"):
        h(f)


# --------------------------------------------------------------------- MP4
@pytest.mark.parametrize("name", ["m4a", "m4a_faststart"])
def test_mp4_tags_rewritten(copy, name):
    f = copy(name)
    ref = h(f)
    assert ref.method == "mp4"

    tags = MP4(f)
    tags["\xa9nam"] = ["Titre inventé"]
    tags.save()
    assert h(f).same_audio(ref)

    tags = MP4(f)
    tags["covr"] = [MP4Cover(b"\x00" * BIG, imageformat=MP4Cover.FORMAT_JPEG)]
    tags["\xa9cmt"] = ["x" * 5000]
    tags.save()
    assert h(f).same_audio(ref)

    MP4(f).delete()
    assert h(f).same_audio(ref)


def test_mp4_audio_byte_changed(copy):
    f = copy("m4a")  # moov en fin : le milieu du fichier est dans mdat
    ref = h(f)
    _flip_byte(f, f.stat().st_size // 2)
    assert not h(f).same_audio(ref)


def test_mp4_truncated(copy):
    f = copy("m4a")
    with f.open("r+b") as out:
        out.truncate(f.stat().st_size // 2)
    with pytest.raises(AudioHashError, match="MP4"):
        h(f)


def test_mp4_without_mdat(tmp_path):
    f = tmp_path / "vide.m4a"
    f.write_bytes(b"\x00\x00\x00\x10ftypM4A \x00\x00\x00\x00")
    with pytest.raises(AudioHashError, match="mdat"):
        h(f)


# --------------------------------------------------------------------- Ogg
@pytest.mark.parametrize("name,kind", [("opus", OggOpus), ("vorbis", OggVorbis)])
def test_ogg_tags_rewritten(copy, name, kind):
    f = copy(name)
    ref = h(f)
    assert ref.method == "ogg" and len(ref.digest) == 32

    tags = kind(f)
    tags["title"] = "Titre inventé"
    tags.save()
    assert h(f).same_audio(ref)

    tags = kind(f)
    tags["comment"] = "x" * BIG  # plusieurs pages Ogg : les pages sont redécoupées
    tags.save()
    assert h(f).same_audio(ref)

    kind(f).delete()
    assert h(f).same_audio(ref)


def test_ogg_audio_byte_changed(copy):
    f = copy("opus")
    ref = h(f)
    # Le CRC de la page devient faux : ffmpeg le signale et écarte la page, l'empreinte
    # change sans erreur (l'intégrité est une autre mesure).
    _flip_byte(f, f.stat().st_size // 2)
    assert not h(f).same_audio(ref)


def test_ogg_ffmpeg_from_config(copy):
    """Sans ffmpeg donné, celui de la configuration est utilisé."""
    f = copy("opus")
    assert compute(f).same_audio(h(f))


def test_ogg_ffmpeg_missing(copy):
    with pytest.raises(AudioHashError, match="ffmpeg introuvable"):
        compute(copy("opus"), "ffmpeg-qui-n-existe-pas-12345")


def test_ogg_not_audio(tmp_path):
    f = tmp_path / "faux.ogg"
    f.write_bytes(b"OggS" + b"\x00" * 200)
    with pytest.raises(AudioHashError, match="ffmpeg"):
        h(f)


# --------------------------------------------------------------------- erreurs
def test_unknown_format(tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("ceci n'est pas de l'audio", encoding="utf-8")
    with pytest.raises(AudioHashError, match="format inconnu"):
        h(f)


def test_empty_file(tmp_path):
    f = tmp_path / "vide.mp3"
    f.write_bytes(b"")
    with pytest.raises(AudioHashError, match="fichier vide"):
        h(f)


def test_missing_file(tmp_path):
    with pytest.raises(AudioHashError, match="lecture impossible"):
        h(tmp_path / "absent.flac")


def test_tags_only_is_never_identical(tmp_path):
    """Deux fichiers sans audio ne passent jamais pour identiques : ils lèvent une erreur."""
    for i, title in enumerate(["un", "deux"]):
        f = tmp_path / f"tags_seuls_{i}.mp3"
        tags = ID3()
        tags.add(TIT2(encoding=3, text=title))
        tags.save(f, v1=2)
        with pytest.raises(AudioHashError, match="aucune donnée audio"):
            h(f)


def test_key_format(copy):
    r = h(copy("mp3"))
    assert r.key == f"mp3:{r.version}:{r.digest}"
    assert len(r.digest) == 40 and r.size > 0
