"""
config.py - Configuration de la discothèque

Description:
    Chargement et validation de la configuration locale (config.toml).

    Tout part de la racine de la discothèque (`chemins.racine`). Les dossiers système
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

    1. la configuration par défaut, intégrée au programme (`assets/config_defaut.toml`) ;
    2. `<racine>/_bot/config.toml`, facultatif : seulement ce qui diffère (baladeur,
       sauvegarde, références, catégories en plus) ;
    3. le `config.toml` trouvé ailleurs (le clone, en développement) : `racine` et toute
       surcharge.

    Sans `racine` écrite, elle se déduit de `_bot` : le dossier parent de `_bot` quand la
    config y est rangée, ou, sans aucun fichier, quand le programme tourne depuis `_bot`.

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

import os
import sys
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

TYPES_CATEGORIE = {
    "artistes",
    "classique",
    "compilations",
    "projets",
    "vrac",
    "arrivees",
    "ignore",
}

# Préfixe des dossiers système à la racine de la discothèque
PREFIXE_SYSTEME = "_"

# Racine du dépôt : src/backend/config.py -> ../../
RACINE_DEPOT = Path(__file__).resolve().parents[2]

NOM_CONFIG = "config.toml"
NOM_DEFAUT = "config_defaut.toml"

# Origine d'une valeur, affichée par « disco config »
DEFAUT = "défaut"  # configuration intégrée au programme
BOT = "_bot"  # <racine>/_bot/config.toml
CLONE = "clone"  # config.toml trouvé ailleurs (clone de développement, --config)
DEDUIT = "déduit"  # calculé (chemins déduits de la racine, outils trouvés)


class ErreurConfig(Exception):
    """Configuration absente ou invalide."""


class RacineIntrouvable(ErreurConfig):
    """Aucune racine écrite ni déductible : un réglage manque, la config n'est pas cassée."""


@dataclass(frozen=True)
class Categorie:
    """Un dossier de premier niveau de la discothèque et son traitement."""

    nom: str
    type: str
    pages: bool
    rg_album: bool


@dataclass(frozen=True)
class References:
    """Données de référence hors dépôt (jamais versionnées)."""

    audit: Path | None
    fiches_achat: Path | None


@dataclass(frozen=True)
class Config:
    """Configuration chargée et validée, telle qu'utilisée par tout le programme.

    Tous les chemins sont résolus : ceux qui ne sont pas écrits dans un fichier sont
    déduits de la racine (voir l'en-tête du module). Les noms des attributs suivent
    les clés du TOML (`base` = `chemins.base`, `dap` = `dap.destination`…).

    Attributes:
        racine: Racine de la discothèque (la sandbox en développement).
        sortie: Pages générées (`_data`).
        base: Index SQLite (`_data/_base`), jamais effacé.
        cache: Réponses des services en ligne (`_data/_cache`).
        journaux: Journaux détaillés (`_log`).
        rapports: Rapports lisibles (`_reports`).
        corbeille: Corbeille des opérations (`_to_delete`).
        bot: Installation de production (`_bot`).
        arrivees: Arrivées depuis le baladeur (`_sort`).
        dap: Dossier de musique du baladeur, s'il est configuré.
        sauvegarde: Destination de la copie froide, si elle est configurée.
        ffmpeg: Commande de ffmpeg (chemin complet ou nom cherché dans le PATH).
        ffprobe: Commande de ffprobe.
        fpcalc: Commande de fpcalc (Chromaprint).
        reference_lufs: Sonie de référence du ReplayGain 2 (−18 LUFS par défaut).
        surechantillonnage_crete: Facteur de suréchantillonnage de la crête vraie.
        processus: Pistes analysées en parallèle (0 : nombre de cœurs − 2).
        categories: Catégories déclarées, par nom de dossier.
        references: Données de référence hors dépôt.
        sources: Fichiers lus, du dessous vers le dessus.
        origines: Couche qui a écrit chaque clé.
    """

    racine: Path
    sortie: Path
    base: Path
    cache: Path
    journaux: Path
    rapports: Path
    corbeille: Path
    bot: Path
    arrivees: Path
    dap: Path | None
    sauvegarde: Path | None
    ffmpeg: str
    ffprobe: str
    fpcalc: str
    reference_lufs: float
    surechantillonnage_crete: int
    processus: int
    categories: dict[str, Categorie]
    references: References
    # Fichiers lus, du dessous vers le dessus (vide : configuration par défaut seule)
    sources: tuple[Path, ...] = ()
    # Couche d'où vient chaque clé écrite (« categories.Bulk.pages » -> « _bot »)
    origines: dict[str, str] = field(default_factory=dict)

    def origine(self, cle: str) -> str:
        """Origine d'une clé pointée (« chemins.base », « categories.Bulk »…).

        Une clé écrite dans aucun fichier vient de la configuration par défaut, sauf les
        chemins et les outils, calculés à partir de la racine.
        """
        if cle in self.origines:
            return self.origines[cle]
        if cle.startswith(("chemins.", "outils.")):
            return DEDUIT
        return DEFAUT

    def categorie(self, dossier: str) -> Categorie | None:
        """Catégorie d'un dossier de premier niveau.

        Un dossier système (« _… ») non déclaré est ignoré ; un autre dossier non
        déclaré renvoie None.
        """
        if dossier in self.categories:
            return self.categories[dossier]
        if dossier.startswith(PREFIXE_SYSTEME):
            return Categorie(nom=dossier, type="ignore", pages=False, rg_album=False)
        return None


def dossier_environnement() -> Path | None:
    """Dossier qui contient l'environnement Python en cours (venv), s'il y en a un.

    En production, `disco` tourne depuis `<racine>/_bot/.venv` : ce dossier est `_bot`.
    En développement, c'est le clone (`<clone>/.venv`).
    """
    if sys.prefix == sys.base_prefix:
        return None
    return Path(sys.prefix).resolve().parent


def dossier_programme() -> Path | None:
    """Dossier d'où tourne le programme : celui de l'exécutable pour la version compilée
    (`<racine>/_bot/disco.exe`), sinon celui qui contient l'environnement Python."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return dossier_environnement()


def trouver(explicite: str | os.PathLike | None = None) -> Path | None:
    """Chemin du fichier de configuration, ou None s'il n'y en a pas (configuration
    par défaut seule).

    Ordre : argument explicite, variable DISCO_CONFIG, config.toml à côté du programme
    (`_bot` en production, le clone en développement), ./config.toml, config.toml du
    dépôt. Un fichier demandé explicitement (argument ou variable) doit exister.
    """
    demande = explicite or os.environ.get("DISCO_CONFIG")
    if demande:
        chemin = Path(demande)
        if not chemin.is_file():
            raise ErreurConfig(f"Configuration introuvable : {chemin}")
        return chemin
    candidats: list[Path] = []
    programme = dossier_programme()
    if programme is not None:
        candidats.append(programme / NOM_CONFIG)
    candidats += [Path.cwd() / NOM_CONFIG, RACINE_DEPOT / NOM_CONFIG]
    for c in candidats:
        if c.is_file():
            return c
    return None


def _exiger(table: dict, cle: str, ou: str):
    """Valeur d'une clé obligatoire de `table`.

    Args:
        table: Table TOML lue.
        cle: Clé demandée.
        ou: Nom de la table, pour le message d'erreur (« analyse »).

    Raises:
        ErreurConfig: La clé est absente.
    """
    if cle not in table:
        raise ErreurConfig(f"Clé manquante : [{ou}] {cle}")
    return table[cle]


def _chemin(table: dict, cle: str) -> Path | None:
    """Chemin écrit sous `cle`, ou None si la clé est absente ou vide."""
    v = table.get(cle)
    return Path(v) if v else None


DOSSIER_OUTILS = "tools"


def _outil(outils: dict, nom: str, bot: Path) -> str:
    """Commande d'un outil externe.

    Ordre : chemin donné dans [outils], puis `<bot>/tools/`, sinon le nom seul (PATH).
    """
    if outils.get(nom):
        return str(outils[nom])
    local = bot / DOSSIER_OUTILS / (nom + ".exe" if os.name == "nt" else nom)
    return str(local) if local.is_file() else nom


def _racine_de_bot(dossier: Path | None) -> Path | None:
    """Racine déduite d'un dossier système (`<racine>/_bot`) : son dossier parent."""
    if dossier is not None and dossier.name.startswith(PREFIXE_SYSTEME):
        return dossier.parent
    return None


def defaut() -> dict:
    """Configuration par défaut, intégrée au programme."""
    texte = resources.files("src").joinpath("assets", NOM_DEFAUT).read_text("utf-8")
    return tomllib.loads(texte)


def depuis_dict(
    d: dict, sources: tuple[Path, ...] = (), origines: dict[str, str] | None = None
) -> Config:
    """Construit et valide une Config à partir du contenu TOML déjà lu.

    `d` est posé sur la configuration par défaut ; `chemins.racine` y est obligatoire
    (`charger` la déduit de `_bot` au besoin).

    Args:
        d: Contenu TOML, déjà fusionné s'il vient de plusieurs fichiers.
        sources: Fichiers lus, gardés pour `disco config`.
        origines: Couche qui a écrit chaque clé (voir `Config.origine`).

    Returns:
        La configuration validée.

    Raises:
        RacineIntrouvable: `chemins.racine` absente.
        ErreurConfig: Ancienne clé renommée, catégorie de type inconnu, clé
            obligatoire manquante ou valeur hors limites.
    """
    d = fusionner(defaut(), d)
    chemins = d.get("chemins", {})
    outils = d.get("outils", {})
    analyse = d.get("analyse", {})
    refs = d.get("references", {})

    if "musique" in chemins:
        raise ErreurConfig("La clé [chemins] musique s'appelle désormais racine.")
    if "donnees" in chemins:
        raise ErreurConfig("La clé [chemins] donnees s'appelle désormais base.")
    racine = _chemin(chemins, "racine")
    if racine is None:
        raise RacineIntrouvable(
            "Racine introuvable : lancer le programme depuis <racine>/_bot, ou indiquer "
            "[chemins] racine dans config.toml."
        )
    sortie = _chemin(chemins, "sortie") or racine / "_data"
    bot = _chemin(chemins, "bot") or racine / "_bot"

    categories: dict[str, Categorie] = {}
    for nom, c in d.get("categories", {}).items():
        type_ = _exiger(c, "type", f"categories.{nom}")
        if type_ not in TYPES_CATEGORIE:
            permis = ", ".join(sorted(TYPES_CATEGORIE))
            raise ErreurConfig(
                f"Type inconnu pour [categories.{nom}] : {type_!r} (permis : {permis})"
            )
        # Une catégorie par défaut retirée (type = "ignore") garde ses autres clés à la
        # fusion : on les neutralise
        actif = type_ != "ignore"
        categories[nom] = Categorie(
            nom=nom,
            type=type_,
            pages=actif and bool(c.get("pages", False)),
            rg_album=actif and bool(c.get("rg_album", False)),
        )

    surech = int(_exiger(analyse, "surechantillonnage_crete", "analyse"))
    if surech < 1:
        raise ErreurConfig("analyse.surechantillonnage_crete doit valoir au moins 1")

    return Config(
        racine=racine,
        sortie=sortie,
        base=_chemin(chemins, "base") or sortie / "_base",
        cache=_chemin(chemins, "cache") or sortie / "_cache",
        journaux=_chemin(chemins, "journaux") or racine / "_log",
        rapports=_chemin(chemins, "rapports") or racine / "_reports",
        corbeille=_chemin(chemins, "corbeille") or racine / "_to_delete",
        bot=bot,
        arrivees=_chemin(chemins, "arrivees") or racine / "_sort",
        dap=_chemin(d.get("dap", {}), "destination"),
        sauvegarde=_chemin(d.get("sauvegarde", {}), "destination"),
        ffmpeg=_outil(outils, "ffmpeg", bot),
        ffprobe=_outil(outils, "ffprobe", bot),
        fpcalc=_outil(outils, "fpcalc", bot),
        reference_lufs=float(_exiger(analyse, "reference_lufs", "analyse")),
        surechantillonnage_crete=surech,
        processus=int(_exiger(analyse, "processus", "analyse")),
        categories=categories,
        references=References(
            audit=_chemin(refs, "audit"), fiches_achat=_chemin(refs, "fiches_achat")
        ),
        sources=sources,
        origines=origines or {},
    )


def _lire(chemin: Path) -> dict:
    """Lit un fichier TOML.

    Raises:
        ErreurConfig: Le fichier n'est pas du TOML valide.
    """
    try:
        with open(chemin, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ErreurConfig(f"{chemin} : TOML invalide ({e})") from e


def fusionner(dessous: dict, dessus: dict) -> dict:
    """Fusionne deux contenus TOML : les valeurs de `dessus` l'emportent, table par table."""
    res = dict(dessous)
    for cle, valeur in dessus.items():
        if isinstance(valeur, dict) and isinstance(res.get(cle), dict):
            res[cle] = fusionner(res[cle], valeur)
        else:
            res[cle] = valeur
    return res


def _noter(origines: dict[str, str], contenu: dict, etiquette: str, prefixe: str = "") -> None:
    """Note la couche qui écrit chaque clé de `contenu`, tables comprises."""
    for cle, valeur in contenu.items():
        nom = prefixe + cle
        origines[nom] = etiquette
        if isinstance(valeur, dict):
            _noter(origines, valeur, etiquette, nom + ".")


def charger(explicite: str | os.PathLike | None = None) -> Config:
    """Trouve, lit, superpose et valide la configuration.

    Couches, du dessous vers le dessus : la configuration par défaut (posée par
    `depuis_dict`), `<racine>/_bot/config.toml` s'il existe, puis le fichier trouvé
    s'il est ailleurs (clone de développement). Aucun fichier n'est obligatoire.

    Args:
        explicite: Fichier demandé par `--config` ; sinon, recherche par `trouver`.

    Returns:
        La configuration validée, avec ses fichiers sources et l'origine de chaque clé.

    Raises:
        RacineIntrouvable: Aucune racine écrite ni déductible.
        ErreurConfig: Fichier demandé introuvable, TOML invalide ou valeur refusée.
    """
    chemin = trouver(explicite)
    contenu = _lire(chemin) if chemin else {}
    racine_ecrite = _chemin(contenu.get("chemins", {}), "racine")
    racine = racine_ecrite
    if racine is None:
        # <racine>/_bot/config.toml, ou, sans fichier, programme lancé depuis <racine>/_bot
        racine = _racine_de_bot(chemin.parent if chemin else dossier_programme())

    config_bot = None
    if racine is not None:
        config_bot = (_chemin(contenu.get("chemins", {}), "bot") or racine / "_bot") / NOM_CONFIG
    est_bot = (
        chemin is not None and config_bot is not None and chemin.resolve() == config_bot.resolve()
    )

    couches: list[tuple[str, Path, dict]] = []
    if config_bot is not None and config_bot.is_file() and not est_bot:
        couches.append((BOT, config_bot, _lire(config_bot)))
    if chemin is not None:
        couches.append((BOT if est_bot else CLONE, chemin, contenu))

    fusion: dict = {}
    origines: dict[str, str] = {}
    for etiquette, _, c in couches:
        fusion = fusionner(fusion, c)
        _noter(origines, c, etiquette)
    if racine is not None:
        # La racine du fichier trouvé (ou déduite) l'emporte toujours sur celle de _bot
        fusion = fusionner(fusion, {"chemins": {"racine": str(racine)}})
        origines["chemins.racine"] = couches[-1][0] if racine_ecrite else DEDUIT
    return depuis_dict(fusion, sources=tuple(p for _, p, _ in couches), origines=origines)
