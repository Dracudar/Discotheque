"""
cli.py - Ligne de commande « disco »

Description:
    Point d'entrée en ligne de commande : « disco <commande> ». Construit le parseur
    d'arguments et relie chaque sous-commande (doctor, config) à sa
    fonction. Chaque sous-commande renvoie le code de retour du processus :
    0 si tout va bien, 1 en cas d'erreur pendant l'opération, 2 si la configuration
    est absente ou invalide.

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

import argparse
import sys

from src.backend.config import ErreurConfig, charger
from src.core.version import __version__


def _doctor(args: argparse.Namespace) -> int:
    """« disco doctor » : diagnostic de l'environnement.

    Une configuration illisible n'arrête pas le diagnostic : elle y figure comme un
    résultat parmi les autres.
    """
    from src.core import doctor

    try:
        cfg, erreur = charger(args.config), None
    except ErreurConfig as e:
        cfg, erreur = None, e
    return doctor.afficher(doctor.diagnostic(cfg, erreur))


def _config(args: argparse.Namespace) -> int:
    """« disco config » : affiche la configuration chargée et l'origine de chaque valeur."""
    try:
        cfg = charger(args.config)
    except ErreurConfig as e:
        print(e, file=sys.stderr)
        return 2

    def ligne(titre: str, valeur: object, cle: str) -> None:
        """Affiche une valeur, suivie de son origine entre crochets (défaut, _bot…)."""
        print(f"{titre:<10}: {valeur}  [{cfg.origine(cle)}]")

    fichiers = " + ".join(str(s) for s in cfg.sources) or "aucun (configuration par défaut)"
    print(f"Fichiers  : {fichiers}")
    ligne("Racine", cfg.racine, "chemins.racine")
    ligne("Sortie", cfg.sortie, "chemins.sortie")
    ligne("Base", cfg.base, "chemins.base")
    ligne("Cache", cfg.cache, "chemins.cache")
    ligne("Journaux", cfg.journaux, "chemins.journaux")
    ligne("Rapports", cfg.rapports, "chemins.rapports")
    ligne("Corbeille", cfg.corbeille, "chemins.corbeille")
    ligne("Bot", cfg.bot, "chemins.bot")
    ligne("Arrivées", cfg.arrivees, "chemins.arrivees")
    ligne("DAP", cfg.dap or "(non défini)", "dap.destination")
    ligne("Sauvegarde", cfg.sauvegarde or "(non définie)", "sauvegarde.destination")
    ligne("Audit", cfg.references.audit or "(non défini)", "references.audit")
    ligne("Fiches", cfg.references.fiches_achat or "(non défini)", "references.fiches_achat")
    ligne("ffmpeg", cfg.ffmpeg, "outils.ffmpeg")
    ligne("ffprobe", cfg.ffprobe, "outils.ffprobe")
    ligne("fpcalc", cfg.fpcalc, "outils.fpcalc")
    ligne("Référence", f"{cfg.reference_lufs} LUFS", "analyse.reference_lufs")
    ligne("Crête", f"vraie x{cfg.surechantillonnage_crete}", "analyse.surechantillonnage_crete")
    ligne("Processus", cfg.processus or "auto", "analyse.processus")
    print("Catégories :")
    for c in cfg.categories.values():
        print(
            f"  {c.nom:<26} {c.type:<12} pages={'oui' if c.pages else 'non':<3} "
            f"RG album={'oui' if c.rg_album else 'non':<3}  [{cfg.origine('categories.' + c.nom)}]"
        )
    return 0


def construire_parseur() -> argparse.ArgumentParser:
    """Construit le parseur de « disco » et de ses sous-commandes.

    Returns:
        Le parseur ; chaque sous-commande range sa fonction dans l'attribut `fonction`
        des arguments analysés.
    """
    p = argparse.ArgumentParser(prog="disco", description="Outils de la discothèque.")
    p.add_argument("--version", action="version", version=f"disco {__version__}")
    p.add_argument(
        "--config",
        help="chemin de config.toml (sinon DISCO_CONFIG, celui de _bot ou du clone ; facultatif)",
    )
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("doctor", help="vérifie l'environnement (ne modifie rien)").set_defaults(
        fonction=_doctor
    )
    sous.add_parser("config", help="affiche la configuration chargée").set_defaults(
        fonction=_config
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Lance la commande demandée.

    Args:
        argv: Arguments de la ligne de commande, sans le nom du programme ;
            ceux de `sys.argv` par défaut (les tests passent leur propre liste).

    Returns:
        Le code de retour du processus.
    """
    # Sortie console en UTF-8, y compris dans un terminal Windows
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    args = construire_parseur().parse_args(argv)
    return args.fonction(args)
