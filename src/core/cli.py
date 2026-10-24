"""
cli.py - Ligne de commande « disco »

Description:
    Point d'entrée en ligne de commande : « disco <commande> ». Construit le parseur
    d'arguments et relie chaque sous-commande (doctor, config, purge, lot, review,
    reject) à sa fonction. Chaque sous-commande renvoie le code de retour du processus :
    0 si tout va bien, 1 en cas d'erreur pendant l'opération, 2 si la configuration
    est absente ou invalide.

Auteur :
    Claude (Anthropic)

Version :
    2.2

Date de création :
    2026.10.06

Date de modification :
    2026.10.24
"""

from __future__ import annotations

import argparse
import sys

from src.__versions__ import __version__
from src.backend.config import ConfigError, load


def _doctor(args: argparse.Namespace) -> int:
    """« disco doctor » : diagnostic de l'environnement.

    Une configuration illisible n'arrête pas le diagnostic : elle y figure comme un
    résultat parmi les autres.
    """
    from src.core import doctor

    try:
        cfg, error = load(args.config), None
    except ConfigError as e:
        cfg, error = None, e
    return doctor.show(doctor.diagnose(cfg, error))


def _config(args: argparse.Namespace) -> int:
    """« disco config » : affiche la configuration chargée et l'origine de chaque valeur."""
    try:
        cfg = load(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2

    def line(title: str, value: object, key: str) -> None:
        """Affiche une valeur, suivie de son origine entre crochets (défaut, _bot…)."""
        print(f"{title:<10}: {value}  [{cfg.origin(key)}]")

    files = " + ".join(str(s) for s in cfg.sources) or "aucun (configuration par défaut)"
    print(f"Fichiers  : {files}")
    line("Racine", cfg.root, "paths.root")
    line("Sortie", cfg.output, "paths.output")
    line("Base", cfg.db, "paths.db")
    line("Cache", cfg.cache, "paths.cache")
    line("Journaux", cfg.logs, "paths.logs")
    line("Rapports", cfg.reports, "paths.reports")
    line("Corbeille", cfg.trash, "paths.trash")
    line("Bot", cfg.bot, "paths.bot")
    line("Arrivées", cfg.incoming, "paths.incoming")
    line("Playlists", cfg.playlists, "paths.playlists")
    line("Travail", cfg.workspace, "paths.workspace")
    line("En cours", cfg.process, "paths.process")
    line("À valider", cfg.in_review, "paths.in_review")
    line("En attente", cfg.pending, "paths.pending")
    line("Rétention", f"{cfg.retention_days} jours" if cfg.retention_days else "jamais de purge", "trash.retention_days")
    line("Audit", cfg.references.audit or "(non défini)", "references.audit")
    line(
        "Fiches",
        cfg.references.purchase_sheets or "(non défini)",
        "references.purchase_sheets",
    )
    line("ffmpeg", cfg.ffmpeg, "tools.ffmpeg")
    line("ffprobe", cfg.ffprobe, "tools.ffprobe")
    line("fpcalc", cfg.fpcalc, "tools.fpcalc")
    line("Référence", f"{cfg.reference_lufs} LUFS", "analysis.reference_lufs")
    line("Crête", f"vraie x{cfg.true_peak_oversampling}", "analysis.true_peak_oversampling")
    line("Processus", cfg.workers or "auto", "analysis.workers")
    print("Catégories :")
    for c in cfg.categories.values():
        print(
            f"  {c.name:<26} {c.type:<12} pages={'oui' if c.pages else 'non':<3} "
            f"RG album={'oui' if c.rg_album else 'non':<3}  [{cfg.origin('categories.' + c.name)}]"
        )
    return 0


def _purge(args: argparse.Namespace) -> int:
    """« disco purge » : supprime les lots de la corbeille plus vieux que la rétention.

    Écrit un journal et un rapport, qui annonce aussi les lots purgés dans les jours
    suivants et signale ceux qui ne le seront jamais (voir `src.backend.trash`).
    """
    from src.backend import oplog, trash

    try:
        cfg = load(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    with oplog.OpLog(cfg.logs, "purge") as log:
        retention = f"{cfg.retention_days} jours" if cfg.retention_days else "purge désactivée (trash.retention_days = 0)"
        log(f"Purge de la corbeille {cfg.trash} (rétention : {retention})")
        outcome = trash.purge(cfg.trash, cfg.logs, cfg.retention_days, log)
        notes = [f"Lot {lot.name} purgé le {date:%d/%m/%Y} : le récupérer avant si besoin" for lot, date in outcome.upcoming]
        report = oplog.write_report(
            cfg.reports,
            log,
            "Purge de la corbeille",
            [("Corbeille", str(cfg.trash)), ("Rétention", retention)],
            [
                ("Lots purgés", str(len(outcome.purged))),
                ("Fichiers supprimés", str(sum(len(lot.files) for lot in outcome.purged))),
                ("Lots gardés", str(outcome.kept)),
                ("Lots purgés dans les 7 jours", str(len(outcome.upcoming))),
                ("Lots signalés", str(len(outcome.flagged))),
            ],
            [f"Lot {name} jamais purgé : {reason}" for name, reason in outcome.flagged],
            notes,
        )
        log(f"Rapport : {report}")
    return 1 if outcome.flagged else 0


def _lots(args: argparse.Namespace) -> int:
    """« disco lot », « disco review » et « disco reject » : lots validés par l'opérateur.

    Voir `src.core.lots`.
    """
    from src.core import lots

    try:
        cfg = load(args.config)
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    if args.command == "lot":
        return lots.run(args.folder, cfg)
    if args.command == "reject":
        return lots.reject(args.lot, cfg)
    return lots.review(cfg)


def build_parser() -> argparse.ArgumentParser:
    """Construit le parseur de « disco » et de ses sous-commandes.

    Returns:
        Le parseur ; chaque sous-commande range sa fonction dans l'attribut `func`
        des arguments analysés.
    """
    p = argparse.ArgumentParser(prog="disco", description="Outils de la discothèque.")
    p.add_argument("--version", action="version", version=f"disco {__version__}")
    p.add_argument(
        "--config",
        help="chemin de config.toml (sinon DISCO_CONFIG, celui de _bot ou du clone ; facultatif)",
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="vérifie l'environnement (ne modifie rien)").set_defaults(func=_doctor)
    sub.add_parser("config", help="affiche la configuration chargée").set_defaults(func=_config)
    sub.add_parser("purge", help="supprime les lots de la corbeille plus vieux que trash.retention_days (désactivé par défaut)").set_defaults(
        func=_purge
    )
    p_lot = sub.add_parser("lot", help="applique les décisions d'un lot (_decisions.csv), après confirmation")
    p_lot.add_argument("folder", help="dossier du lot (dans _in_review ou _pending), ou son nom")
    p_lot.set_defaults(func=_lots)
    sub.add_parser("review", help="liste les lots à valider et en attente").set_defaults(func=_lots)
    p_reject = sub.add_parser("reject", help="refuse toutes les lignes restantes d'un lot, après confirmation")
    p_reject.add_argument("lot", help="nom ou dossier du lot")
    p_reject.set_defaults(func=_lots)
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
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    return args.func(args)
