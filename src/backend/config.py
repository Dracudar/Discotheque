"""
config.py - Configuration de la discothèque

Description:
    Chargement et validation de la configuration locale (config.toml).

    Tout part de la racine de la discothèque (`paths.root`). Les dossiers système
    vivent à la racine et commencent par « _ » ; chacun peut être déplacé dans la config :

        <racine>/_data          pages générées (miroir de la discothèque), base et caches
        <racine>/_data/_base    index SQLite : coûteux à reconstruire, jamais effacé
        <racine>/_data/_cache   réponses des services en ligne
        <racine>/_bot           installation de production (environnement, config)
        <racine>/_bot/tools     outils externes (ffmpeg, ffprobe, fpcalc)
        <racine>/_sort          arrivées depuis le baladeur
        <racine>/_log           journaux détaillés
        <racine>/_reports       rapports lisibles des résultats
        <racine>/_to_delete     corbeille des opérations (jamais de suppression directe)

    La configuration se superpose en trois couches, la plus haute l'emportant clé par clé :

    1. la configuration par défaut, intégrée au programme (`assets/config_default.toml`) ;
    2. `<racine>/_bot/config.toml`, facultatif : seulement ce qui diffère (catégories en
       plus, outils) ;
    3. le `config.toml` trouvé ailleurs (le clone, en développement) : `root`, les
       références et toute surcharge.

    Sans `root` écrite, la racine se déduit de `_bot` : le dossier parent de `_bot` quand
    la config y est rangée, ou, sans aucun fichier, quand le programme tourne depuis `_bot`.

    Les anciens noms français des sections et des clés (`[chemins] racine`…) et les
    sections retirées (`[dap]`, `[sauvegarde]`) sont refusés avec un message qui donne
    le nouveau nom.

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

import os
import sys
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

CATEGORY_TYPES = {
    "artists",
    "classical",
    "compilations",
    "projects",
    "bulk",
    "incoming",
    "ignore",
}

# Préfixe des dossiers système à la racine de la discothèque
SYSTEM_PREFIX = "_"

# Racine du dépôt : src/backend/config.py -> ../../
REPO_ROOT = Path(__file__).resolve().parents[2]

CONFIG_NAME = "config.toml"
DEFAULT_NAME = "config_default.toml"

# Origine d'une valeur, affichée par « disco config »
ORIGIN_DEFAULT = "défaut"  # configuration intégrée au programme
ORIGIN_BOT = "_bot"  # <racine>/_bot/config.toml
ORIGIN_CLONE = "clone"  # config.toml trouvé ailleurs (clone de développement, --config)
ORIGIN_DERIVED = "déduit"  # calculé (chemins déduits de la racine, outils trouvés)

# Anciens noms français : section -> (nouvelle section, {ancienne clé : nouvelle clé})
RENAMED_SECTIONS = {
    "chemins": (
        "paths",
        {
            "racine": "root",
            "sortie": "output",
            "base": "db",
            "journaux": "logs",
            "rapports": "reports",
            "corbeille": "trash",
            "arrivees": "incoming",
        },
    ),
    "outils": ("tools", {}),
    "analyse": (
        "analysis",
        {"surechantillonnage_crete": "true_peak_oversampling", "processus": "workers"},
    ),
}
# Clés renommées dans une section qui a gardé son nom
RENAMED_KEYS = {"references": {"fiches_achat": "purchase_sheets"}}
# Sections qui ne sont plus lues
REMOVED_SECTIONS = {
    "dap": "les copies vers le baladeur sont refaites dans l'issue #54",
    "sauvegarde": "les copies de sauvegarde sont refaites dans l'issue #54",
}
RENAMED_TYPES = {
    "artistes": "artists",
    "classique": "classical",
    "projets": "projects",
    "vrac": "bulk",
    "arrivees": "incoming",
}


class ConfigError(Exception):
    """Configuration absente ou invalide."""


class RootNotFound(ConfigError):
    """Aucune racine écrite ni déductible : un réglage manque, la config n'est pas cassée."""


@dataclass(frozen=True)
class Category:
    """Un dossier de premier niveau de la discothèque et son traitement.

    Attributes:
        name: Nom du dossier.
        type: Type de la catégorie (voir `CATEGORY_TYPES`).
        pages: Génère des pages (album, artiste, projet, compositeur).
        rg_album: Calcule et écrit le ReplayGain album (sinon piste seulement).
    """

    name: str
    type: str
    pages: bool
    rg_album: bool


@dataclass(frozen=True)
class References:
    """Données de référence hors dépôt (jamais versionnées), utiles au développement.

    Attributes:
        audit: Résultats et scripts de l'audit de septembre 2026.
        purchase_sheets: Fiches d'achat réalisées à la main (référence du jalon 4.1).
    """

    audit: Path | None
    purchase_sheets: Path | None


@dataclass(frozen=True)
class Config:
    """Configuration chargée et validée, telle qu'utilisée par tout le programme.

    Tous les chemins sont résolus : ceux qui ne sont pas écrits dans un fichier sont
    déduits de la racine (voir l'en-tête du module). Les noms des attributs suivent
    les clés du TOML (`db` = `paths.db`, `workers` = `analysis.workers`…).

    Attributes:
        root: Racine de la discothèque (la sandbox en développement).
        output: Pages générées (`_data`).
        db: Dossier de l'index SQLite (`_data/_base`), jamais effacé.
        cache: Réponses des services en ligne (`_data/_cache`).
        logs: Journaux détaillés (`_log`).
        reports: Rapports lisibles (`_reports`).
        trash: Corbeille des opérations (`_to_delete`).
        bot: Installation de production (`_bot`).
        incoming: Arrivées depuis le baladeur (`_sort`).
        ffmpeg: Commande de ffmpeg (chemin complet ou nom cherché dans le PATH).
        ffprobe: Commande de ffprobe.
        fpcalc: Commande de fpcalc (Chromaprint).
        reference_lufs: Sonie de référence du ReplayGain 2 (−18 LUFS par défaut).
        true_peak_oversampling: Facteur de suréchantillonnage de la crête vraie.
        workers: Pistes analysées en parallèle (0 : nombre de cœurs − 2).
        categories: Catégories déclarées, par nom de dossier.
        references: Données de référence hors dépôt.
        sources: Fichiers lus, du dessous vers le dessus.
        origins: Couche qui a écrit chaque clé.
    """

    root: Path
    output: Path
    db: Path
    cache: Path
    logs: Path
    reports: Path
    trash: Path
    bot: Path
    incoming: Path
    ffmpeg: str
    ffprobe: str
    fpcalc: str
    reference_lufs: float
    true_peak_oversampling: int
    workers: int
    categories: dict[str, Category]
    references: References
    # Fichiers lus, du dessous vers le dessus (vide : configuration par défaut seule)
    sources: tuple[Path, ...] = ()
    # Couche d'où vient chaque clé écrite (« categories.Bulk.pages » -> « _bot »)
    origins: dict[str, str] = field(default_factory=dict)

    def origin(self, key: str) -> str:
        """Origine d'une clé pointée (« paths.db », « categories.Bulk »…).

        Une clé écrite dans aucun fichier vient de la configuration par défaut, sauf les
        chemins et les outils, calculés à partir de la racine.
        """
        if key in self.origins:
            return self.origins[key]
        if key.startswith(("paths.", "tools.")):
            return ORIGIN_DERIVED
        return ORIGIN_DEFAULT

    def category(self, folder: str) -> Category | None:
        """Catégorie d'un dossier de premier niveau.

        Un dossier système (« _… ») non déclaré est ignoré ; un autre dossier non
        déclaré renvoie None.
        """
        if folder in self.categories:
            return self.categories[folder]
        if folder.startswith(SYSTEM_PREFIX):
            return Category(name=folder, type="ignore", pages=False, rg_album=False)
        return None


def environment_dir() -> Path | None:
    """Dossier qui contient l'environnement Python en cours (venv), s'il y en a un.

    En production, `disco` tourne depuis `<racine>/_bot/.venv` : ce dossier est `_bot`.
    En développement, c'est le clone (`<clone>/.venv`).
    """
    if sys.prefix == sys.base_prefix:
        return None
    return Path(sys.prefix).resolve().parent


def program_dir() -> Path | None:
    """Dossier d'où tourne le programme : celui de l'exécutable pour la version compilée
    (`<racine>/_bot/disco.exe`), sinon celui qui contient l'environnement Python."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return environment_dir()


def find(explicit: str | os.PathLike | None = None) -> Path | None:
    """Chemin du fichier de configuration, ou None s'il n'y en a pas (configuration
    par défaut seule).

    Ordre : argument explicite, variable DISCO_CONFIG, config.toml à côté du programme
    (`_bot` en production, le clone en développement), ./config.toml, config.toml du
    dépôt. Un fichier demandé explicitement (argument ou variable) doit exister.
    """
    requested = explicit or os.environ.get("DISCO_CONFIG")
    if requested:
        path = Path(requested)
        if not path.is_file():
            raise ConfigError(f"Configuration introuvable : {path}")
        return path
    candidates: list[Path] = []
    program = program_dir()
    if program is not None:
        candidates.append(program / CONFIG_NAME)
    candidates += [Path.cwd() / CONFIG_NAME, REPO_ROOT / CONFIG_NAME]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _require(table: dict, key: str, where: str):
    """Valeur d'une clé obligatoire de `table`.

    Args:
        table: Table TOML lue.
        key: Clé demandée.
        where: Nom de la table, pour le message d'erreur (« analysis »).

    Raises:
        ConfigError: La clé est absente.
    """
    if key not in table:
        raise ConfigError(f"Clé manquante : [{where}] {key}")
    return table[key]


def _path(table: dict, key: str) -> Path | None:
    """Chemin écrit sous `key`, ou None si la clé est absente ou vide."""
    v = table.get(key)
    return Path(v) if v else None


TOOLS_DIR = "tools"


def _tool(tools: dict, name: str, bot: Path) -> str:
    """Commande d'un outil externe.

    Ordre : chemin donné dans [tools], puis `<bot>/tools/`, sinon le nom seul (PATH).
    """
    if tools.get(name):
        return str(tools[name])
    local = bot / TOOLS_DIR / (name + ".exe" if os.name == "nt" else name)
    return str(local) if local.is_file() else name


def _root_from_bot(folder: Path | None) -> Path | None:
    """Racine déduite d'un dossier système (`<racine>/_bot`) : son dossier parent."""
    if folder is not None and folder.name.startswith(SYSTEM_PREFIX):
        return folder.parent
    return None


def _renamed(old_to_new: dict[str, str]) -> str:
    """Liste lisible des renommages (« racine → root, sortie → output »)."""
    return ", ".join(f"{a} → {b}" for a, b in old_to_new.items())


def reject_old_names(d: dict) -> None:
    """Refuse les anciens noms français et les sections retirées, en donnant le nouveau nom.

    Sans ce contrôle, une ancienne clé serait ignorée en silence : la valeur par défaut
    s'appliquerait à la place de celle écrite, sans que rien ne le signale.

    Args:
        d: Contenu TOML écrit par l'utilisateur (avant la fusion avec le défaut).

    Raises:
        ConfigError: Une ancienne section, clé ou valeur de type est utilisée.
    """
    for old, (new, keys) in RENAMED_SECTIONS.items():
        if old in d:
            detail = f" ; clés renommées : {_renamed(keys)}" if keys else ""
            raise ConfigError(f"La section [{old}] s'appelle désormais [{new}]{detail}.")
    for old, reason in REMOVED_SECTIONS.items():
        if old in d:
            raise ConfigError(f"La section [{old}] n'est plus lue ({reason}) : la retirer.")
    sections = {new: keys for new, keys in RENAMED_SECTIONS.values()} | RENAMED_KEYS
    for section, keys in sections.items():
        for old, new in keys.items():
            if old in d.get(section, {}):
                raise ConfigError(f"La clé [{section}] {old} s'appelle désormais {new}.")
    for name, c in d.get("categories", {}).items():
        type_ = c.get("type") if isinstance(c, dict) else None
        if type_ in RENAMED_TYPES:
            raise ConfigError(
                f"[categories.{name}] : le type {type_!r} s'appelle désormais "
                f"{RENAMED_TYPES[type_]!r}."
            )


def default() -> dict:
    """Configuration par défaut, intégrée au programme."""
    text = resources.files("src").joinpath("assets", DEFAULT_NAME).read_text("utf-8")
    return tomllib.loads(text)


def from_dict(
    d: dict, sources: tuple[Path, ...] = (), origins: dict[str, str] | None = None
) -> Config:
    """Construit et valide une Config à partir du contenu TOML déjà lu.

    `d` est posé sur la configuration par défaut ; `paths.root` y est obligatoire
    (`load` la déduit de `_bot` au besoin).

    Args:
        d: Contenu TOML, déjà fusionné s'il vient de plusieurs fichiers.
        sources: Fichiers lus, gardés pour `disco config`.
        origins: Couche qui a écrit chaque clé (voir `Config.origin`).

    Returns:
        La configuration validée.

    Raises:
        RootNotFound: `paths.root` absente.
        ConfigError: Ancien nom, catégorie de type inconnu, clé obligatoire manquante
            ou valeur hors limites.
    """
    reject_old_names(d)
    d = merge(default(), d)
    paths = d.get("paths", {})
    tools = d.get("tools", {})
    analysis = d.get("analysis", {})
    refs = d.get("references", {})

    root = _path(paths, "root")
    if root is None:
        raise RootNotFound(
            "Racine introuvable : lancer le programme depuis <racine>/_bot, ou indiquer "
            "[paths] root dans config.toml."
        )
    output = _path(paths, "output") or root / "_data"
    bot = _path(paths, "bot") or root / "_bot"

    categories: dict[str, Category] = {}
    for name, c in d.get("categories", {}).items():
        type_ = _require(c, "type", f"categories.{name}")
        if type_ not in CATEGORY_TYPES:
            allowed = ", ".join(sorted(CATEGORY_TYPES))
            raise ConfigError(
                f"Type inconnu pour [categories.{name}] : {type_!r} (permis : {allowed})"
            )
        # Une catégorie par défaut retirée (type = "ignore") garde ses autres clés à la
        # fusion : on les neutralise
        active = type_ != "ignore"
        categories[name] = Category(
            name=name,
            type=type_,
            pages=active and bool(c.get("pages", False)),
            rg_album=active and bool(c.get("rg_album", False)),
        )

    oversampling = int(_require(analysis, "true_peak_oversampling", "analysis"))
    if oversampling < 1:
        raise ConfigError("analysis.true_peak_oversampling doit valoir au moins 1")

    return Config(
        root=root,
        output=output,
        db=_path(paths, "db") or output / "_base",
        cache=_path(paths, "cache") or output / "_cache",
        logs=_path(paths, "logs") or root / "_log",
        reports=_path(paths, "reports") or root / "_reports",
        trash=_path(paths, "trash") or root / "_to_delete",
        bot=bot,
        incoming=_path(paths, "incoming") or root / "_sort",
        ffmpeg=_tool(tools, "ffmpeg", bot),
        ffprobe=_tool(tools, "ffprobe", bot),
        fpcalc=_tool(tools, "fpcalc", bot),
        reference_lufs=float(_require(analysis, "reference_lufs", "analysis")),
        true_peak_oversampling=oversampling,
        workers=int(_require(analysis, "workers", "analysis")),
        categories=categories,
        references=References(
            audit=_path(refs, "audit"), purchase_sheets=_path(refs, "purchase_sheets")
        ),
        sources=sources,
        origins=origins or {},
    )


def _read(path: Path) -> dict:
    """Lit un fichier TOML.

    Raises:
        ConfigError: Le fichier n'est pas du TOML valide.
    """
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"{path} : TOML invalide ({e})") from e


def merge(below: dict, above: dict) -> dict:
    """Fusionne deux contenus TOML : les valeurs de `above` l'emportent, table par table."""
    res = dict(below)
    for key, value in above.items():
        if isinstance(value, dict) and isinstance(res.get(key), dict):
            res[key] = merge(res[key], value)
        else:
            res[key] = value
    return res


def _record(origins: dict[str, str], content: dict, label: str, prefix: str = "") -> None:
    """Note la couche qui écrit chaque clé de `content`, tables comprises."""
    for key, value in content.items():
        name = prefix + key
        origins[name] = label
        if isinstance(value, dict):
            _record(origins, value, label, name + ".")


def load(explicit: str | os.PathLike | None = None) -> Config:
    """Trouve, lit, superpose et valide la configuration.

    Couches, du dessous vers le dessus : la configuration par défaut (posée par
    `from_dict`), `<racine>/_bot/config.toml` s'il existe, puis le fichier trouvé
    s'il est ailleurs (clone de développement). Aucun fichier n'est obligatoire.

    Args:
        explicit: Fichier demandé par `--config` ; sinon, recherche par `find`.

    Returns:
        La configuration validée, avec ses fichiers sources et l'origine de chaque clé.

    Raises:
        RootNotFound: Aucune racine écrite ni déductible.
        ConfigError: Fichier demandé introuvable, TOML invalide, ancien nom ou valeur
            refusée.
    """
    path = find(explicit)
    content = _read(path) if path else {}
    # Un ancien nom est signalé avant tout : sinon la racine écrite sous [chemins]
    # passerait inaperçue, et l'erreur annoncée serait « Racine introuvable »
    reject_old_names(content)
    written_root = _path(content.get("paths", {}), "root")
    root = written_root
    if root is None:
        # <racine>/_bot/config.toml, ou, sans fichier, programme lancé depuis <racine>/_bot
        root = _root_from_bot(path.parent if path else program_dir())

    bot_config = None
    if root is not None:
        bot_config = (_path(content.get("paths", {}), "bot") or root / "_bot") / CONFIG_NAME
    is_bot = path is not None and bot_config is not None and path.resolve() == bot_config.resolve()

    layers: list[tuple[str, Path, dict]] = []
    if bot_config is not None and bot_config.is_file() and not is_bot:
        layers.append((ORIGIN_BOT, bot_config, _read(bot_config)))
    if path is not None:
        layers.append((ORIGIN_BOT if is_bot else ORIGIN_CLONE, path, content))

    merged: dict = {}
    origins: dict[str, str] = {}
    for label, _, c in layers:
        reject_old_names(c)
        merged = merge(merged, c)
        _record(origins, c, label)
    if root is not None:
        # La racine du fichier trouvé (ou déduite) l'emporte toujours sur celle de _bot
        merged = merge(merged, {"paths": {"root": str(root)}})
        origins["paths.root"] = layers[-1][0] if written_root else ORIGIN_DERIVED
    return from_dict(merged, sources=tuple(p for _, p, _ in layers), origins=origins)
