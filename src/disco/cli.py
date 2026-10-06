"""Point d'entrée en ligne de commande : « disco <commande> »."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    print(f"Rapports  : {cfg.rapports}")
    print(f"Corbeille : {cfg.corbeille}")
    print(f"Bot       : {cfg.bot}")
    print(f"Arrivées  : {cfg.arrivees}")
    print(f"DAP       : {cfg.dap or '(non défini)'}")
    print(f"Sauvegarde: {cfg.sauvegarde or '(non définie)'}")
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
        if args.sens == "lanceur":
            chemin = dap.poser_lanceur(Path(args.dap) if args.dap else cfg.dap)
            print(f"Lanceur posé : {chemin}")
            return 0
        return dap.operation_dap(
            cfg,
            args.sens,
            dap=Path(args.dap) if args.dap else None,
            simulation=args.simulation,
            confirmer=args.confirmer,
        )
    except ErreurConfig as e:
        print(e, file=sys.stderr)
        return 2


def _sauvegarde(args: argparse.Namespace) -> int:
    from disco import dap

    try:
        cfg = charger(args.config)
        return dap.operation_sauvegarde(
            cfg, args.sens, simulation=args.simulation, confirmer=args.confirmer
        )
    except ErreurConfig as e:
        print(e, file=sys.stderr)
        return 2


def _options_copie(sp: argparse.ArgumentParser) -> None:
    sp.add_argument(
        "--simulation", action="store_true", help="affiche ce qui serait fait, sans rien modifier"
    )
    sp.add_argument(
        "--confirmer",
        action="store_true",
        help="obligatoire pour « restaurer » (sinon simulation)",
    )


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
    d = sous.add_parser("dap", help="synchronise la discothèque avec le baladeur")
    d.add_argument(
        "sens",
        choices=["synchro", "envoyer", "recuperer", "restaurer", "lanceur"],
        help=(
            "synchro : arrivées du DAP → discothèque, puis discothèque → DAP ; "
            "envoyer / recuperer : une seule des deux étapes ; "
            "restaurer : DAP → discothèque ; lanceur : pose le lanceur sur le DAP"
        ),
    )
    d.add_argument("--dap", help="dossier de musique du baladeur (sinon [dap] destination)")
    _options_copie(d)
    d.set_defaults(fonction=_dap)
    s = sous.add_parser("sauvegarde", help="copie froide de la discothèque sur un autre disque")
    s.add_argument("sens", choices=["envoyer", "restaurer"])
    _options_copie(s)
    s.set_defaults(fonction=_sauvegarde)
    return p


def main(argv: list[str] | None = None) -> int:
    # Sortie console en UTF-8, y compris dans un terminal Windows
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    args = construire_parseur().parse_args(argv)
    return args.fonction(args)
