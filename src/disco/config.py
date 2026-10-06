"""Chargement et validation de la configuration locale (config.toml).

Tout part de la racine de la discothèque (`chemins.racine`). Les dossiers système
vivent à la racine et commencent par « _ » ; chacun peut être déplacé dans la config :

    <racine>/_data          pages générées (miroir de la discothèque), base et caches
    <racine>/_data/_base    index SQLite : coûteux à reconstruire, jamais effacé
    <racine>/_data/_cache   réponses des services en ligne
    <racine>/_bot           installation de production (environnement, config, outils)
    <racine>/_sort          arrivées depuis le baladeur
    <racine>/_log           journaux détaillés
    <racine>/_reports       rapports lisibles des résultats
    <racine>/_to_delete     corbeille des opérations (jamais de suppression directe)

La configuration se trouve d'elle-même (voir `trouver`). En production, c'est
`<racine>/_bot/config.toml`, et la racine s'en déduit : le dossier parent de `_bot`.
En développement, le `config.toml` du clone peut se limiter à `racine` (la sandbox) :
le reste est lu dans le `_bot/config.toml` de cette racine, et le clone peut le surcharger.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
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

# Racine du dépôt : src/disco/config.py -> ../../
RACINE_DEPOT = Path(__file__).resolve().parents[2]

NOM_CONFIG = "config.toml"


class ErreurConfig(Exception):
    """Configuration absente ou invalide."""


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
    source: Path | None = None

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


def trouver(explicite: str | os.PathLike | None = None) -> Path:
    """Chemin du fichier de configuration.

    Ordre : argument explicite, variable DISCO_CONFIG, config.toml à côté de
    l'environnement Python (`_bot` en production, le clone en développement),
    ./config.toml, config.toml du dépôt.
    """
    candidats: list[Path] = []
    if explicite:
        candidats.append(Path(explicite))
    elif os.environ.get("DISCO_CONFIG"):
        candidats.append(Path(os.environ["DISCO_CONFIG"]))
    else:
        env = dossier_environnement()
        if env is not None:
            candidats.append(env / NOM_CONFIG)
        candidats += [Path.cwd() / NOM_CONFIG, RACINE_DEPOT / NOM_CONFIG]
    for c in candidats:
        if c.is_file():
            return c
    essais = ", ".join(str(c) for c in dict.fromkeys(candidats))
    raise ErreurConfig(
        f"Configuration introuvable (essayé : {essais}). "
        "Copier config.example.toml en config.toml et adapter les chemins."
    )


def _exiger(table: dict, cle: str, ou: str):
    if cle not in table:
        raise ErreurConfig(f"Clé manquante : [{ou}] {cle}")
    return table[cle]


def _chemin(table: dict, cle: str) -> Path | None:
    v = table.get(cle)
    return Path(v) if v else None


def _racine_deduite(source: Path | None) -> Path | None:
    """Racine déduite de l'emplacement de la config : `<racine>/_bot/config.toml`."""
    if source is not None and source.parent.name.startswith(PREFIXE_SYSTEME):
        return source.parent.parent
    return None


def depuis_dict(d: dict, source: Path | None = None) -> Config:
    """Construit et valide une Config à partir du contenu TOML déjà lu.

    Sans `chemins.racine`, la racine est déduite de l'emplacement de la config, si elle
    est rangée dans un dossier système (`<racine>/_bot/config.toml`).
    """
    chemins = d.get("chemins", {})
    outils = d.get("outils", {})
    analyse = d.get("analyse", {})
    refs = d.get("references", {})

    if "musique" in chemins:
        raise ErreurConfig("La clé [chemins] musique s'appelle désormais racine.")
    if "donnees" in chemins:
        raise ErreurConfig("La clé [chemins] donnees s'appelle désormais base.")
    racine = _chemin(chemins, "racine") or _racine_deduite(source)
    if racine is None:
        raise ErreurConfig(
            "Clé manquante : [chemins] racine (obligatoire quand config.toml "
            "n'est pas rangé dans <racine>/_bot)."
        )
    sortie = _chemin(chemins, "sortie") or racine / "_data"

    categories: dict[str, Categorie] = {}
    for nom, c in d.get("categories", {}).items():
        type_ = _exiger(c, "type", f"categories.{nom}")
        if type_ not in TYPES_CATEGORIE:
            permis = ", ".join(sorted(TYPES_CATEGORIE))
            raise ErreurConfig(
                f"Type inconnu pour [categories.{nom}] : {type_!r} (permis : {permis})"
            )
        categories[nom] = Categorie(
            nom=nom,
            type=type_,
            pages=bool(c.get("pages", False)),
            rg_album=bool(c.get("rg_album", False)),
        )
    if not categories:
        raise ErreurConfig('Aucune catégorie déclarée : section [categories."<dossier>"] attendue.')

    surech = int(analyse.get("surechantillonnage_crete", 8))
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
        bot=_chemin(chemins, "bot") or racine / "_bot",
        arrivees=_chemin(chemins, "arrivees") or racine / "_sort",
        dap=_chemin(d.get("dap", {}), "destination"),
        sauvegarde=_chemin(d.get("sauvegarde", {}), "destination"),
        ffmpeg=str(outils.get("ffmpeg", "ffmpeg")),
        ffprobe=str(outils.get("ffprobe", "ffprobe")),
        fpcalc=str(outils.get("fpcalc", "fpcalc")),
        reference_lufs=float(analyse.get("reference_lufs", -18.0)),
        surechantillonnage_crete=surech,
        processus=int(analyse.get("processus", 0)),
        categories=categories,
        references=References(
            audit=_chemin(refs, "audit"), fiches_achat=_chemin(refs, "fiches_achat")
        ),
        source=source,
    )


def _lire(chemin: Path) -> dict:
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


def charger(explicite: str | os.PathLike | None = None) -> Config:
    """Trouve, lit et valide la configuration.

    Si la config trouvée n'est pas celle de `<racine>/_bot` (cas du clone de
    développement), la config de `<racine>/_bot` est lue d'abord, puis surchargée.
    """
    chemin = trouver(explicite)
    contenu = _lire(chemin)
    chemins = contenu.get("chemins", {})
    racine = _chemin(chemins, "racine") or _racine_deduite(chemin)
    if racine is not None:
        bot = _chemin(chemins, "bot") or racine / "_bot"
        config_bot = bot / NOM_CONFIG
        if config_bot.is_file() and config_bot.resolve() != chemin.resolve():
            contenu = fusionner(_lire(config_bot), contenu)
            # La racine de la config du clone l'emporte toujours
            contenu.setdefault("chemins", {})["racine"] = str(racine)
    return depuis_dict(contenu, source=chemin)
