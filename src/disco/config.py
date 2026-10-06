"""Chargement et validation de la configuration locale (config.toml).

Tout part de la racine de la discothèque (`chemins.musique`). Les dossiers système
vivent à la racine et commencent par « _ » ; chacun peut être déplacé dans la config :

    <racine>/_discotheque   pages, index et caches (sortie)
    <racine>/_bot           installation de production (environnement, config)
    <racine>/_sort          arrivées depuis le baladeur
    <racine>/_log           journaux détaillés
    <racine>/_reports       rapports lisibles des résultats
    <racine>/_to_delete     corbeille des opérations (jamais de suppression directe)
"""

from __future__ import annotations

import os
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
    musique: Path
    sortie: Path
    donnees: Path
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


def trouver(explicite: str | os.PathLike | None = None) -> Path:
    """Chemin du fichier de configuration.

    Ordre : argument explicite, variable DISCO_CONFIG, ./config.toml, config.toml du dépôt.
    """
    candidats: list[Path] = []
    if explicite:
        candidats.append(Path(explicite))
    elif os.environ.get("DISCO_CONFIG"):
        candidats.append(Path(os.environ["DISCO_CONFIG"]))
    else:
        candidats += [Path.cwd() / "config.toml", RACINE_DEPOT / "config.toml"]
    for c in candidats:
        if c.is_file():
            return c
    essais = ", ".join(str(c) for c in candidats)
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


def depuis_dict(d: dict, source: Path | None = None) -> Config:
    """Construit et valide une Config à partir du contenu TOML déjà lu."""
    chemins = _exiger(d, "chemins", "racine")
    outils = d.get("outils", {})
    analyse = d.get("analyse", {})
    refs = d.get("references", {})

    musique = Path(_exiger(chemins, "musique", "chemins"))
    sortie = _chemin(chemins, "sortie") or musique / "_discotheque"
    donnees = _chemin(chemins, "donnees") or sortie / "_data"

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
        musique=musique,
        sortie=sortie,
        donnees=donnees,
        journaux=_chemin(chemins, "journaux") or musique / "_log",
        rapports=_chemin(chemins, "rapports") or musique / "_reports",
        corbeille=_chemin(chemins, "corbeille") or musique / "_to_delete",
        bot=_chemin(chemins, "bot") or musique / "_bot",
        arrivees=_chemin(chemins, "arrivees") or musique / "_sort",
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


def charger(explicite: str | os.PathLike | None = None) -> Config:
    """Trouve, lit et valide la configuration."""
    chemin = trouver(explicite)
    try:
        with open(chemin, "rb") as f:
            contenu = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ErreurConfig(f"{chemin} : TOML invalide ({e})") from e
    return depuis_dict(contenu, source=chemin)
