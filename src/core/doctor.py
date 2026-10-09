"""
doctor.py - Diagnostic de l'environnement

Description:
    Diagnostic de l'environnement (« disco doctor »).

    Ne modifie rien : vérifie Python, les modules, SQLite, les outils externes,
    les chemins longs Windows et les chemins de la configuration. Chaque vérification
    renvoie un ou plusieurs `Result` de statut `OK`, `WARNING` (le programme
    fonctionne, mais un point mérite un coup d'œil) ou `ERROR` (à corriger).

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
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

from src.backend.config import Config, ConfigError, RootNotFound

OK, WARNING, ERROR = "ok", "warning", "error"
MARKS = {OK: "[OK]", WARNING: "[!!]", ERROR: "[XX]"}


@dataclass
class Result:
    """Résultat d'une vérification.

    Attributes:
        name: Ce qui est vérifié (« Python », « ffmpeg »…), affiché tel quel.
        status: `OK`, `WARNING` ou `ERROR`.
        detail: Version trouvée, chemin, ou ce qu'il faut corriger.
    """

    name: str
    status: str
    detail: str


# --------------------------------------------------------------------- Python
def check_python() -> Result:
    """Vérifie la version de Python (3.13 minimum) et indique l'interpréteur utilisé."""
    v = sys.version_info
    text = f"{v.major}.{v.minor}.{v.micro} ({platform.python_implementation()}, {sys.executable})"
    if (v.major, v.minor) < (3, 13):
        return Result("Python", ERROR, text + " : 3.13 minimum")
    return Result("Python", OK, text)


def check_modules() -> list[Result]:
    """Vérifie que les dépendances (numpy, scipy, mutagen) s'importent ; donne leur version."""
    res = []
    for name in ("numpy", "scipy", "mutagen"):
        try:
            m = importlib.import_module(name)
            version = getattr(m, "__version__", None) or getattr(m, "version_string", "?")
            res.append(Result(f"Module {name}", OK, str(version)))
        except ImportError as e:
            res.append(Result(f"Module {name}", ERROR, f"absent ({e}) : pip install -e .[dev]"))
    return res


# --------------------------------------------------------------------- SQLite
def sqlite_features() -> dict[str, bool]:
    """Fonctions SQLite utiles au projet, testées sur une base en mémoire."""
    con = sqlite3.connect(":memory:")
    available = {}
    trials = {
        "FTS5": "CREATE VIRTUAL TABLE t USING fts5(x)",
        "JSON": "SELECT json_extract('{\"a\":1}', '$.a')",
        "UPSERT": "CREATE TABLE u(k PRIMARY KEY, v); INSERT INTO u VALUES (1, 1) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
        "RETURNING": "CREATE TABLE r(x); INSERT INTO r VALUES (1) RETURNING x",
        "STRICT": "CREATE TABLE s(x INTEGER) STRICT",
    }
    for name, sql in trials.items():
        try:
            con.executescript(sql) if ";" in sql else con.execute(sql)
            available[name] = True
        except sqlite3.Error:
            available[name] = False
    con.close()
    return available


def check_sqlite() -> Result:
    """Vérifie la version de SQLite et ses fonctions utiles au projet.

    FTS5 manquant est une erreur ; une autre fonction
    manquante n'est qu'un point d'attention.
    """
    available = sqlite_features()
    missing = [k for k, v in available.items() if not v]
    detail = f"SQLite {sqlite3.sqlite_version} : " + ", ".join(f"{k} {'oui' if v else 'NON'}" for k, v in available.items())
    if missing:
        return Result("SQLite", ERROR if "FTS5" in missing else WARNING, detail)
    return Result("SQLite", OK, detail)


# ---------------------------------------------------------------- Outils externes
def locate(command: str) -> str | None:
    """Chemin complet d'un exécutable (nom dans le PATH ou chemin direct)."""
    p = Path(command)
    if p.is_file():
        return str(p)
    return shutil.which(command)


def tool_version(path: str, option: str = "-version") -> str:
    """Première ligne affichée par un outil appelé avec son option de version.

    Args:
        path: Exécutable à lancer.
        option: Option qui affiche la version.

    Returns:
        La première ligne de la sortie standard (sinon de la sortie d'erreur), ou « ? ».
    """
    r = subprocess.run([path, option], capture_output=True, text=True, timeout=30)
    output = (r.stdout or r.stderr).strip().splitlines()
    return output[0] if output else "?"


def check_tool(name: str, command: str) -> Result:
    """Vérifie qu'un outil externe est présent et répond.

    Args:
        name: Nom affiché.
        command: Commande configurée (chemin complet ou nom cherché dans le PATH).
    """
    path = locate(command)
    if not path:
        return Result(name, ERROR, f"introuvable ({command!r}) : voir README, section Installation")
    try:
        return Result(name, OK, f"{tool_version(path)} ({path})")
    except (OSError, subprocess.SubprocessError) as e:
        return Result(name, ERROR, f"{path} ne répond pas : {e}")


def file_fingerprint(fpcalc: str, file: Path) -> str:
    """Empreinte Chromaprint calculée par fpcalc en lisant lui-même le fichier.

    Returns:
        L'empreinte brute (`-plain`), ou une chaîne vide si fpcalc échoue.
    """
    r = subprocess.run([fpcalc, "-plain", str(file)], capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


def stream_fingerprint(ffmpeg: str, fpcalc: str, file: Path) -> str:
    """Empreinte calculée par fpcalc à partir de PCM envoyé sur l'entrée standard.

    C'est le mode prévu pour l'analyse en un seul décodage : ffmpeg décode en PCM
    16 bits stéréo 44,1 kHz, et fpcalc lit ce flux au lieu de relire le fichier.

    Returns:
        L'empreinte brute (`-plain`), ou une chaîne vide si fpcalc échoue.
    """
    decoded = subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(file),
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
        input=decoded.stdout,
        capture_output=True,
        timeout=60,
    )
    return r.stdout.decode(errors="replace").strip()


def check_fpcalc_stdin(ffmpeg_cmd: str, fpcalc_cmd: str) -> Result:
    """Vérifie que fpcalc lit le PCM sur l'entrée standard.

    Génère un court FLAC synthétique (sinus et bruit) dans un dossier temporaire,
    puis compare l'empreinte calculée depuis le fichier à celle calculée depuis le flux.

    Args:
        ffmpeg_cmd: Commande de ffmpeg.
        fpcalc_cmd: Commande de fpcalc.
    """
    name = "fpcalc par l'entrée standard"
    ffmpeg, fpcalc = locate(ffmpeg_cmd), locate(fpcalc_cmd)
    if not (ffmpeg and fpcalc):
        return Result(name, WARNING, "non testé (ffmpeg ou fpcalc absent)")
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
        a = file_fingerprint(fpcalc, f)
        b = stream_fingerprint(ffmpeg, fpcalc, f)
    if a and a == b:
        return Result(name, OK, "empreinte identique à celle du fichier")
    if b:
        return Result(name, WARNING, "fonctionne, mais empreinte différente de celle du fichier")
    return Result(name, ERROR, "fpcalc ne lit pas l'entrée standard : il relira les fichiers")


# --------------------------------------------------------------------- Windows
def check_long_paths() -> Result:
    """Vérifie que Windows accepte les chemins de plus de 260 caractères.

    Lit `LongPathsEnabled` dans le registre ; sans objet hors Windows.
    """
    name = "Chemins longs Windows"
    if sys.platform != "win32":
        return Result(name, OK, "sans objet hors Windows")
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as k:
            value, _ = winreg.QueryValueEx(k, "LongPathsEnabled")
    except OSError:
        value = 0
    if value == 1:
        return Result(name, OK, "LongPathsEnabled = 1")
    return Result(
        name,
        WARNING,
        "LongPathsEnabled = 0 : chemins de plus de 260 caractères refusés (voir README)",
    )


# --------------------------------------------------------------- Configuration
def check_config(cfg: Config) -> list[Result]:
    """Vérifie les chemins de la configuration.

    - la racine doit exister ; un dossier de premier niveau non déclaré dans
      `[categories]` est signalé ;
    - sortie, base et cache peuvent manquer s'ils peuvent être créés ;
    - les références hors dépôt absentes ne sont qu'un point d'attention : elles ne
      servent qu'au développement.
    """
    files = " + ".join(str(s) for s in cfg.sources)
    res = [Result("Configuration", OK, files or "aucun fichier : configuration par défaut")]
    if cfg.root.is_dir():
        present = sorted(p.name for p in cfg.root.iterdir() if p.is_dir())
        unknown = [n for n in present if cfg.category(n) is None]  # « _… » : système
        detail = f"{cfg.root} ({len(present)} dossiers)"
        if unknown:
            res.append(
                Result(
                    "Racine",
                    WARNING,
                    detail + " ; non déclarés dans [categories] : " + ", ".join(unknown),
                )
            )
        else:
            res.append(Result("Racine", OK, detail))
    else:
        res.append(Result("Racine", ERROR, f"{cfg.root} introuvable"))
    for name, path in (
        ("Dossier de sortie", cfg.output),
        ("Base", cfg.db),
        ("Cache", cfg.cache),
    ):
        if path.is_dir():
            res.append(Result(name, OK, str(path)))
        elif path.parent.is_dir() or path.parent.parent.is_dir():
            res.append(Result(name, OK, f"{path} (sera créé)"))
        else:
            res.append(Result(name, WARNING, f"{path} : dossier parent introuvable"))
    optional = (
        ("Référence : audit", cfg.references.audit),
        ("Référence : fiches d'achat", cfg.references.purchase_sheets),
    )
    for name, path in optional:
        if path is None:
            res.append(Result(name, OK, "non configuré"))
        elif path.is_dir():
            res.append(Result(name, OK, str(path)))
        else:
            res.append(Result(name, WARNING, f"{path} introuvable"))
    return res


# --------------------------------------------------------------------- Ensemble
def diagnose(cfg: Config | None, config_error: ConfigError | None = None) -> list[Result]:
    """Lance toutes les vérifications.

    Args:
        cfg: Configuration chargée, ou None si elle n'a pas pu l'être : les outils
            sont alors cherchés dans le PATH.
        config_error: Erreur de chargement de la configuration, affichée comme
            résultat quand `cfg` vaut None.

    Returns:
        Les résultats, dans l'ordre d'affichage.
    """
    res = [check_python(), *check_modules(), check_sqlite()]
    ffmpeg = cfg.ffmpeg if cfg else "ffmpeg"
    ffprobe = cfg.ffprobe if cfg else "ffprobe"
    fpcalc = cfg.fpcalc if cfg else "fpcalc"
    res += [
        check_tool("ffmpeg", ffmpeg),
        check_tool("ffprobe", ffprobe),
        check_tool("fpcalc", fpcalc),
        check_fpcalc_stdin(ffmpeg, fpcalc),
        check_long_paths(),
    ]
    if cfg:
        res += check_config(cfg)
    else:
        # Racine introuvable (clone neuf, CI) : un réglage manque, simple point d'attention.
        # Le reste (TOML invalide, valeur refusée) est une config cassée : erreur.
        status = WARNING if isinstance(config_error, RootNotFound) else ERROR
        res.append(Result("Configuration", status, str(config_error or "illisible")))
    return res


def show(results: list[Result]) -> int:
    """Affiche le diagnostic ; renvoie 1 s'il y a au moins une erreur."""
    width = max(len(r.name) for r in results)
    for r in results:
        print(f"{MARKS[r.status]} {r.name.ljust(width)}  {r.detail}")
    n_errors = sum(r.status == ERROR for r in results)
    n_warnings = sum(r.status == WARNING for r in results)
    print()
    print(f"{n_errors} erreur(s), {n_warnings} point(s) d'attention.")
    return 1 if n_errors else 0
