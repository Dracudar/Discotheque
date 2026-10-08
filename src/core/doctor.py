"""
doctor.py - Diagnostic de l'environnement

Description:
    Diagnostic de l'environnement (« disco doctor »).

    Ne modifie rien : vérifie Python, les modules, SQLite, les outils externes,
    les chemins longs Windows et les chemins de la configuration. Chaque vérification
    renvoie un ou plusieurs `Resultat` de statut `OK`, `ATTENTION` (le programme
    fonctionne, mais un point mérite un coup d'œil) ou `ERREUR` (à corriger).

Auteur :
    Dracudar

Version :
    1.1

Date de création :
    2026.10.06

Date de modification :
    2026.10.08
"""

from __future__ import annotations

import importlib
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.backend.config import Config, ErreurConfig, RacineIntrouvable

OK, ATTENTION, ERREUR = "ok", "attention", "erreur"
MARQUES = {OK: "[OK]", ATTENTION: "[!!]", ERREUR: "[XX]"}


@dataclass
class Resultat:
    """Résultat d'une vérification.

    Attributes:
        nom: Ce qui est vérifié (« Python », « ffmpeg »…).
        statut: `OK`, `ATTENTION` ou `ERREUR`.
        detail: Version trouvée, chemin, ou ce qu'il faut corriger.
    """

    nom: str
    statut: str
    detail: str


# --------------------------------------------------------------------- Python
def verifier_python() -> Resultat:
    """Vérifie la version de Python (3.13 minimum) et indique l'interpréteur utilisé."""
    v = sys.version_info
    texte = f"{v.major}.{v.minor}.{v.micro} ({platform.python_implementation()}, {sys.executable})"
    if (v.major, v.minor) < (3, 13):
        return Resultat("Python", ERREUR, texte + " : 3.13 minimum")
    return Resultat("Python", OK, texte)


def verifier_modules() -> list[Resultat]:
    """Vérifie que les dépendances (numpy, scipy, mutagen) s'importent ; donne leur version."""
    res = []
    for nom in ("numpy", "scipy", "mutagen"):
        try:
            m = importlib.import_module(nom)
            version = getattr(m, "__version__", None) or getattr(m, "version_string", "?")
            res.append(Resultat(f"Module {nom}", OK, str(version)))
        except ImportError as e:
            res.append(Resultat(f"Module {nom}", ERREUR, f"absent ({e}) : pip install -e .[dev]"))
    return res


# --------------------------------------------------------------------- SQLite
def fonctions_sqlite() -> dict[str, bool]:
    """Fonctions SQLite utiles au projet, testées sur une base en mémoire."""
    con = sqlite3.connect(":memory:")
    dispo = {}
    essais = {
        "FTS5": "CREATE VIRTUAL TABLE t USING fts5(x)",
        "JSON": "SELECT json_extract('{\"a\":1}', '$.a')",
        "UPSERT": "CREATE TABLE u(k PRIMARY KEY, v); "
        "INSERT INTO u VALUES (1, 1) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
        "RETURNING": "CREATE TABLE r(x); INSERT INTO r VALUES (1) RETURNING x",
        "STRICT": "CREATE TABLE s(x INTEGER) STRICT",
    }
    for nom, sql in essais.items():
        try:
            con.executescript(sql) if ";" in sql else con.execute(sql)
            dispo[nom] = True
        except sqlite3.Error:
            dispo[nom] = False
    con.close()
    return dispo


def verifier_sqlite() -> Resultat:
    """Vérifie la version de SQLite et ses fonctions utiles au projet.

    FTS5 manquant est une erreur ; une autre fonction
    manquante n'est qu'un point d'attention.
    """
    dispo = fonctions_sqlite()
    manque = [k for k, v in dispo.items() if not v]
    detail = f"SQLite {sqlite3.sqlite_version} : " + ", ".join(
        f"{k} {'oui' if v else 'NON'}" for k, v in dispo.items()
    )
    if manque:
        return Resultat("SQLite", ERREUR if "FTS5" in manque else ATTENTION, detail)
    return Resultat("SQLite", OK, detail)


# ---------------------------------------------------------------- Outils externes
def localiser(commande: str) -> str | None:
    """Chemin complet d'un exécutable (nom dans le PATH ou chemin direct)."""
    p = Path(commande)
    if p.is_file():
        return str(p)
    return shutil.which(commande)


def version_outil(chemin: str, option: str = "-version") -> str:
    """Première ligne affichée par un outil appelé avec son option de version.

    Args:
        chemin: Exécutable à lancer.
        option: Option qui affiche la version.

    Returns:
        La première ligne de la sortie standard (sinon de la sortie d'erreur), ou « ? ».
    """
    r = subprocess.run([chemin, option], capture_output=True, text=True, timeout=30)
    sortie = (r.stdout or r.stderr).strip().splitlines()
    return sortie[0] if sortie else "?"


def verifier_outil(nom: str, commande: str) -> Resultat:
    """Vérifie qu'un outil externe est présent et répond.

    Args:
        nom: Nom affiché.
        commande: Commande configurée (chemin complet ou nom cherché dans le PATH).
    """
    chemin = localiser(commande)
    if not chemin:
        return Resultat(
            nom, ERREUR, f"introuvable ({commande!r}) : voir README, section Installation"
        )
    try:
        return Resultat(nom, OK, f"{version_outil(chemin)} ({chemin})")
    except (OSError, subprocess.SubprocessError) as e:
        return Resultat(nom, ERREUR, f"{chemin} ne répond pas : {e}")


def empreinte_fichier(fpcalc: str, fichier: Path) -> str:
    """Empreinte Chromaprint calculée par fpcalc en lisant lui-même le fichier.

    Returns:
        L'empreinte brute (`-plain`), ou une chaîne vide si fpcalc échoue.
    """
    r = subprocess.run([fpcalc, "-plain", str(fichier)], capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def empreinte_flux(ffmpeg: str, fpcalc: str, fichier: Path) -> str:
    """Empreinte calculée par fpcalc à partir de PCM envoyé sur l'entrée standard.

    C'est le mode prévu pour l'analyse en un seul décodage : ffmpeg décode en PCM
    16 bits stéréo 44,1 kHz, et fpcalc lit ce flux au lieu de relire le fichier.

    Returns:
        L'empreinte brute (`-plain`), ou une chaîne vide si fpcalc échoue.
    """
    dec = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(fichier),
            "-f",
            "s16le",
            "-ac",
            "2",
            "-ar",
            "44100",
            "-",
        ],
        capture_output=True,
        timeout=60,
    )
    r = subprocess.run(
        [fpcalc, "-format", "s16le", "-rate", "44100", "-channels", "2", "-plain", "-"],
        input=dec.stdout,
        capture_output=True,
        timeout=60,
    )
    return r.stdout.decode(errors="replace").strip()


def verifier_fpcalc_entree_standard(ffmpeg_cmd: str, fpcalc_cmd: str) -> Resultat:
    """Vérifie que fpcalc lit le PCM sur l'entrée standard.

    Génère un court FLAC synthétique (sinus et bruit) dans un dossier temporaire,
    puis compare l'empreinte calculée depuis le fichier à celle calculée depuis le flux.

    Args:
        ffmpeg_cmd: Commande de ffmpeg.
        fpcalc_cmd: Commande de fpcalc.
    """
    nom = "fpcalc par l'entrée standard"
    ffmpeg, fpcalc = localiser(ffmpeg_cmd), localiser(fpcalc_cmd)
    if not (ffmpeg and fpcalc):
        return Resultat(nom, ATTENTION, "non testé (ffmpeg ou fpcalc absent)")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "essai.flac"
        subprocess.run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=f=440:d=15",
                "-f",
                "lavfi",
                "-i",
                "anoisesrc=d=15:a=0.1:seed=1",
                "-filter_complex",
                "amix=inputs=2",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "flac",
                str(f),
            ],
            capture_output=True,
            timeout=60,
            check=True,
        )
        a = empreinte_fichier(fpcalc, f)
        b = empreinte_flux(ffmpeg, fpcalc, f)
    if a and a == b:
        return Resultat(nom, OK, "empreinte identique à celle du fichier")
    if b:
        return Resultat(nom, ATTENTION, "fonctionne, mais empreinte différente de celle du fichier")
    return Resultat(nom, ERREUR, "fpcalc ne lit pas l'entrée standard : il relira les fichiers")


# --------------------------------------------------------------------- Windows
def verifier_chemins_longs() -> Resultat:
    """Vérifie que Windows accepte les chemins de plus de 260 caractères.

    Lit `LongPathsEnabled` dans le registre ; sans objet hors Windows.
    """
    nom = "Chemins longs Windows"
    if sys.platform != "win32":
        return Resultat(nom, OK, "sans objet hors Windows")
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem"
        ) as k:
            valeur, _ = winreg.QueryValueEx(k, "LongPathsEnabled")
    except OSError:
        valeur = 0
    if valeur == 1:
        return Resultat(nom, OK, "LongPathsEnabled = 1")
    return Resultat(
        nom,
        ATTENTION,
        "LongPathsEnabled = 0 : chemins de plus de 260 caractères refusés (voir README)",
    )


# --------------------------------------------------------------- Configuration
def verifier_config(cfg: Config) -> list[Resultat]:
    """Vérifie les chemins de la configuration.

    - la racine doit exister ; un dossier de premier niveau non déclaré dans
      `[categories]` est signalé ;
    - sortie, base et cache peuvent manquer s'ils peuvent être créés ;
    - les chemins facultatifs (baladeur, sauvegarde, références) absents ne sont
      qu'un point d'attention : un baladeur peut simplement ne pas être branché.
    """
    fichiers = " + ".join(str(s) for s in cfg.sources)
    res = [Resultat("Configuration", OK, fichiers or "aucun fichier : configuration par défaut")]
    if cfg.racine.is_dir():
        presents = sorted(p.name for p in cfg.racine.iterdir() if p.is_dir())
        inconnus = [n for n in presents if cfg.categorie(n) is None]  # « _… » : système
        detail = f"{cfg.racine} ({len(presents)} dossiers)"
        if inconnus:
            res.append(
                Resultat(
                    "Racine",
                    ATTENTION,
                    detail + " ; non déclarés dans [categories] : " + ", ".join(inconnus),
                )
            )
        else:
            res.append(Resultat("Racine", OK, detail))
    else:
        res.append(Resultat("Racine", ERREUR, f"{cfg.racine} introuvable"))
    for nom, chemin in (
        ("Dossier de sortie", cfg.sortie),
        ("Base", cfg.base),
        ("Cache", cfg.cache),
    ):
        if chemin.is_dir():
            res.append(Resultat(nom, OK, str(chemin)))
        elif chemin.parent.is_dir() or chemin.parent.parent.is_dir():
            res.append(Resultat(nom, OK, f"{chemin} (sera créé)"))
        else:
            res.append(Resultat(nom, ATTENTION, f"{chemin} : dossier parent introuvable"))
    facultatifs = (
        ("DAP", cfg.dap),
        ("Sauvegarde froide", cfg.sauvegarde),
        ("Référence : audit", cfg.references.audit),
        ("Référence : fiches d'achat", cfg.references.fiches_achat),
    )
    for nom, chemin in facultatifs:
        if chemin is None:
            res.append(Resultat(nom, OK, "non configuré"))
        elif chemin.is_dir():
            res.append(Resultat(nom, OK, str(chemin)))
        else:
            # Le DAP peut simplement ne pas être branché : simple point d'attention
            res.append(Resultat(nom, ATTENTION, f"{chemin} introuvable"))
    return res


# --------------------------------------------------------------------- Ensemble
def diagnostic(cfg: Config | None, erreur_config: ErreurConfig | None = None) -> list[Resultat]:
    """Lance toutes les vérifications.

    Args:
        cfg: Configuration chargée, ou None si elle n'a pas pu l'être : les outils
            sont alors cherchés dans le PATH.
        erreur_config: Erreur de chargement de la configuration, affichée comme
            résultat quand `cfg` vaut None.

    Returns:
        Les résultats, dans l'ordre d'affichage.
    """
    res = [verifier_python(), *verifier_modules(), verifier_sqlite()]
    ffmpeg = cfg.ffmpeg if cfg else "ffmpeg"
    ffprobe = cfg.ffprobe if cfg else "ffprobe"
    fpcalc = cfg.fpcalc if cfg else "fpcalc"
    res += [
        verifier_outil("ffmpeg", ffmpeg),
        verifier_outil("ffprobe", ffprobe),
        verifier_outil("fpcalc", fpcalc),
        verifier_fpcalc_entree_standard(ffmpeg, fpcalc),
        verifier_chemins_longs(),
    ]
    if cfg:
        res += verifier_config(cfg)
    else:
        # Racine introuvable (clone neuf, CI) : un réglage manque, simple point d'attention.
        # Le reste (TOML invalide, valeur refusée) est une config cassée : erreur.
        statut = ATTENTION if isinstance(erreur_config, RacineIntrouvable) else ERREUR
        res.append(Resultat("Configuration", statut, str(erreur_config or "illisible")))
    return res


def afficher(resultats: list[Resultat]) -> int:
    """Affiche le diagnostic ; renvoie 1 s'il y a au moins une erreur."""
    largeur = max(len(r.nom) for r in resultats)
    for r in resultats:
        print(f"{MARQUES[r.statut]} {r.nom.ljust(largeur)}  {r.detail}")
    n_err = sum(r.statut == ERREUR for r in resultats)
    n_att = sum(r.statut == ATTENTION for r in resultats)
    print()
    print(f"{n_err} erreur(s), {n_att} point(s) d'attention.")
    return 1 if n_err else 0
