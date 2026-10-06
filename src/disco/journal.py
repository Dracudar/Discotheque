"""Journal d'une opération (dans `_log`) et rapport lisible des résultats (dans `_reports`).

- Le **journal** garde chaque action, horodatée, et l'affiche en même temps dans la console.
- Le **rapport** ne garde que le résultat : chiffres, erreurs, et un lien vers le journal.
  Il est écrit en Markdown pour être lu tel quel, puis intégré plus tard à l'interface.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path


def horodatage(maintenant: dt.datetime | None = None) -> str:
    return f"{(maintenant or dt.datetime.now()):%Y-%m-%d_%H%M%S}"


class Journal:
    """Écrit chaque ligne dans le fichier journal et dans la console."""

    def __init__(self, dossier: Path, operation: str, maintenant=None, console=True):
        self.operation = operation
        self.debut = maintenant or dt.datetime.now()
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        self.chemin = dossier / f"{horodatage(self.debut)}_{operation}.log"
        self._f = open(self.chemin, "a", encoding="utf-8")
        self.console = console

    def __call__(self, message: str) -> None:
        ligne = f"{dt.datetime.now():%H:%M:%S}  {message}"
        self._f.write(ligne + "\n")
        self._f.flush()
        if self.console:
            print(ligne, file=sys.stdout, flush=True)

    def fermer(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.fermer()


def ecrire_rapport(
    dossier: Path,
    journal: Journal,
    titre: str,
    contexte: list[tuple[str, str]],
    chiffres: list[tuple[str, str]],
    erreurs: list[str],
    remarques: list[str] | None = None,
) -> Path:
    """Écrit le rapport Markdown d'une opération et renvoie son chemin."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemin = dossier / f"{horodatage(journal.debut)}_{journal.operation}.md"
    lien = os.path.relpath(journal.chemin, dossier).replace("\\", "/")
    duree = dt.datetime.now() - journal.debut
    statut = "⚠️ terminé avec des erreurs" if erreurs else "✅ terminé sans erreur"
    lignes = [
        f"# {titre}",
        "",
        f"{journal.debut:%d/%m/%Y à %H:%M} · durée {str(duree).split('.')[0]} · {statut}",
        "",
    ]
    lignes += [f"- **{k} :** {v}" for k, v in contexte]
    lignes += ["", "| Résultat | Nombre |", "|---|---|"]
    lignes += [f"| {k} | {v} |" for k, v in chiffres]
    if remarques:
        lignes += ["", "## Remarques", *[f"- {r}" for r in remarques]]
    if erreurs:
        lignes += ["", f"## Erreurs ({len(erreurs)})", *[f"- {e}" for e in erreurs[:50]]]
        if len(erreurs) > 50:
            lignes.append(f"- … et {len(erreurs) - 50} autres : voir le journal")
    lignes += ["", f"Journal détaillé : [{journal.chemin.name}]({lien})", ""]
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return chemin
