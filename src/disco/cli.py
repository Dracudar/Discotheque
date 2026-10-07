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

    def ligne(titre: str, valeur: object, cle: str) -> None:
        # Entre crochets : d'où vient la valeur (défaut, _bot, clone, déduit)
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
