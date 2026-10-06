"""Point d'entrée en ligne de commande : « disco <commande> »."""

from __future__ import annotations

import argparse
import sys

from disco import __version__
from disco.config import ErreurConfig, charger


def _doctor(args: argparse.Namespace) -> int:
    from disco import doctor

    try:
        cfg, erreur = charger(args.config), None
    except ErreurConfig as e:
        cfg, erreur = None, str(e)
    return doctor.afficher(doctor.diagnostic(cfg, erreur))


def _config(args: argparse.Namespace) -> int:
    try:
        cfg = charger(args.config)
    except ErreurConfig as e:
        print(e, file=sys.stderr)
        return 2
    print(f"Fichier   : {cfg.source}")
    print(f"Musique   : {cfg.musique}")
    print(f"Sortie    : {cfg.sortie}")
    print(f"Données   : {cfg.donnees}")
    print(f"Journaux  : {cfg.journaux}")
    print(f"Corbeille : {cfg.corbeille or '(non définie)'}")
    print(f"DAP       : {cfg.dap.destination or '(non défini)'} (arrivées : {cfg.dap.arrivees})")
    print(f"Références: audit={cfg.references.audit} fiches={cfg.references.fiches_achat}")
    print(f"Outils    : ffmpeg={cfg.ffmpeg} ffprobe={cfg.ffprobe} fpcalc={cfg.fpcalc}")
    print(
        f"Analyse   : référence {cfg.reference_lufs} LUFS, "
        f"crête vraie x{cfg.surechantillonnage_crete}"
    )
    print("Catégories :")
    for c in cfg.categories.values():
        print(
            f"  {c.nom:<26} {c.type:<12} pages={'oui' if c.pages else 'non':<3} "
            f"RG album={'oui' if c.rg_album else 'non'}"
        )
    return 0


def _dap(args: argparse.Namespace) -> int:
    from disco import dap

    try:
        cfg = charger(args.config)
        construire = dap.commande_envoi if args.sens == "envoyer" else dap.commande_recuperation
        commande = construire(cfg, simulation=args.simulation)
    except ErreurConfig as e:
        print(e, file=sys.stderr)
        return 2
    print(" ".join(f'"{a}"' if " " in a else a for a in commande))
    if sys.platform != "win32":
        print("robocopy n'existe que sous Windows : commande affichée, non lancée.")
        return 0
    return dap.executer(commande, cfg.journaux)


def construire_parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="disco", description="Outils de la discothèque.")
    p.add_argument("--version", action="version", version=f"disco {__version__}")
    p.add_argument("--config", help="chemin de config.toml (sinon DISCO_CONFIG ou ./config.toml)")
    sous = p.add_subparsers(dest="commande", required=True)
    sous.add_parser("doctor", help="vérifie l'environnement (ne modifie rien)").set_defaults(
        fonction=_doctor
    )
    sous.add_parser("config", help="affiche la configuration chargée").set_defaults(
        fonction=_config
    )
    d = sous.add_parser("dap", help="synchronise la discothèque avec le baladeur (robocopy)")
    d.add_argument(
        "sens",
        choices=["envoyer", "recuperer"],
        help="envoyer : discothèque → DAP (miroir) ; recuperer : arrivées du DAP → discothèque",
    )
    d.add_argument(
        "--simulation", action="store_true", help="liste ce qui serait copié, sans rien copier"
    )
    d.set_defaults(fonction=_dap)
    return p


def main(argv: list[str] | None = None) -> int:
    # Sortie console en UTF-8, y compris dans un terminal Windows
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    args = construire_parseur().parse_args(argv)
    return args.fonction(args)
