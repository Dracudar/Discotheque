"""
oplog.py - Journal et rapport d'une opération

Description:
    Journal d'une opération (dans `_log`) et rapport lisible des résultats (dans `_reports`).

    - Le **journal** garde chaque action, horodatée, et l'affiche en même temps dans la
      console.
    - Le **rapport** ne garde que le résultat : chiffres, erreurs, et un lien vers le
      journal. Il est écrit en Markdown pour être lu tel quel, puis intégré plus tard à
      l'interface.

    Les deux fichiers d'une même opération portent le même nom
    (`<aaaa-mm-jj_hhmmss>_<operation>`), avec l'extension `.log` ou `.md`.

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

import datetime as dt
import os
import sys
from pathlib import Path


def timestamp(now: dt.datetime | None = None) -> str:
    """Horodatage des noms de fichiers d'une opération (« 2026-10-06_143005 »).

    Args:
        now: Instant à formater ; l'heure courante par défaut.

    Returns:
        L'horodatage, triable dans l'ordre chronologique et sans caractère interdit
        dans un nom de fichier Windows.
    """
    return f"{(now or dt.datetime.now()):%Y-%m-%d_%H%M%S}"


class OpLog:
    """Écrit chaque ligne dans le fichier journal et dans la console.

    S'appelle comme une fonction (`log("message")`) : les fonctions qui écrivent
    dans le journal reçoivent donc indifféremment un `OpLog` ou un simple appelable,
    `print` par exemple. S'utilise de préférence dans un bloc `with`, qui ferme le
    fichier à la sortie.

    Attributes:
        operation: Nom court de l'opération (« dap_sync »), repris dans les noms
            du journal et du rapport.
        start: Instant de début de l'opération.
        path: Chemin du fichier journal.
        console: Si vrai, chaque ligne est aussi affichée sur la sortie standard.
    """

    def __init__(self, folder: Path, operation: str, now=None, console=True):
        """Ouvre le fichier journal (en ajout) dans `folder`, créé au besoin.

        Args:
            folder: Dossier des journaux (`paths.logs`).
            operation: Nom court de l'opération.
            now: Instant de début ; l'heure courante par défaut (utile aux tests).
            console: Affiche aussi chaque ligne dans la console.
        """
        self.operation = operation
        self.start = now or dt.datetime.now()
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / f"{timestamp(self.start)}_{operation}.log"
        self._f = open(self.path, "a", encoding="utf-8")
        self.console = console

    def __call__(self, message: str) -> None:
        """Écrit `message`, précédé de l'heure, et vide le tampon aussitôt.

        L'écriture immédiate garde un journal exploitable même si l'opération est
        interrompue brutalement.
        """
        line = f"{dt.datetime.now():%H:%M:%S}  {message}"
        self._f.write(line + "\n")
        self._f.flush()
        if self.console:
            print(line, file=sys.stdout, flush=True)

    def close(self) -> None:
        """Ferme le fichier journal."""
        self._f.close()

    def __enter__(self):
        """Renvoie le journal lui-même, pour `with OpLog(...) as log`."""
        return self

    def __exit__(self, *exc):
        """Ferme le journal, y compris après une exception (qui n'est pas absorbée)."""
        self.close()


def write_report(
    folder: Path,
    log: OpLog,
    title: str,
    context: list[tuple[str, str]],
    figures: list[tuple[str, str]],
    errors: list[str],
    notes: list[str] | None = None,
) -> Path:
    """Écrit le rapport Markdown d'une opération et renvoie son chemin.

    Le rapport donne la date, la durée et le statut, puis le contexte, le tableau des
    chiffres, les remarques et les erreurs (les 50 premières : le reste est dans le
    journal), et finit par un lien relatif vers le journal.

    Args:
        folder: Dossier des rapports (`paths.reports`), créé au besoin.
        log: Journal de l'opération : fournit le nom, le début et le lien.
        title: Titre du rapport.
        context: Couples (libellé, valeur) affichés en liste (dossiers concernés…).
        figures: Couples (résultat, nombre) affichés en tableau.
        errors: Messages d'erreur ; s'il y en a, le statut l'indique.
        notes: Lignes à signaler en plus (corbeille utilisée, mode simulation…).

    Returns:
        Le chemin du rapport écrit.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{timestamp(log.start)}_{log.operation}.md"
    link = os.path.relpath(log.path, folder).replace("\\", "/")
    duration = dt.datetime.now() - log.start
    status = "⚠️ terminé avec des erreurs" if errors else "✅ terminé sans erreur"
    lines = [
        f"# {title}",
        "",
        f"{log.start:%d/%m/%Y à %H:%M} · durée {str(duration).split('.')[0]} · {status}",
        "",
    ]
    lines += [f"- **{k} :** {v}" for k, v in context]
    lines += ["", "| Résultat | Nombre |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in figures]
    if notes:
        lines += ["", "## Remarques", *[f"- {r}" for r in notes]]
    if errors:
        lines += ["", f"## Erreurs ({len(errors)})", *[f"- {e}" for e in errors[:50]]]
        if len(errors) > 50:
            lines.append(f"- … et {len(errors) - 50} autres : voir le journal")
    lines += ["", f"Journal détaillé : [{log.path.name}]({link})", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
