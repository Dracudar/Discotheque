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
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
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
