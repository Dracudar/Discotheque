"""
journal.py - Journal et rapport d'une opération

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
    1.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.07
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path


def horodatage(maintenant: dt.datetime | None = None) -> str:
    """Horodatage des noms de fichiers d'une opération (« 2026-10-06_143005 »).

    Args:
        maintenant: Instant à formater ; l'heure courante par défaut.

    Returns:
        L'horodatage, triable dans l'ordre chronologique et sans caractère interdit
        dans un nom de fichier Windows.
    """
    return f"{(maintenant or dt.datetime.now()):%Y-%m-%d_%H%M%S}"


class Journal:
    """Écrit chaque ligne dans le fichier journal et dans la console.

    S'appelle comme une fonction (`journal("message")`) : les fonctions qui écrivent
    dans le journal reçoivent donc indifféremment un `Journal` ou un simple appelable,
    `print` par exemple. S'utilise de préférence dans un bloc `with`, qui ferme le
    fichier à la sortie.

    Attributes:
        operation: Nom court de l'opération (« dap_synchro »), repris dans les noms
            du journal et du rapport.
        debut: Instant de début de l'opération.
        chemin: Chemin du fichier journal.
        console: Si vrai, chaque ligne est aussi affichée sur la sortie standard.
    """

    def __init__(self, dossier: Path, operation: str, maintenant=None, console=True):
        """Ouvre le fichier journal (en ajout) dans `dossier`, créé au besoin.

        Args:
            dossier: Dossier des journaux (`chemins.journaux`).
            operation: Nom court de l'opération.
            maintenant: Instant de début ; l'heure courante par défaut (utile aux tests).
            console: Affiche aussi chaque ligne dans la console.
        """
        self.operation = operation
        self.debut = maintenant or dt.datetime.now()
        dossier = Path(dossier)
        dossier.mkdir(parents=True, exist_ok=True)
        self.chemin = dossier / f"{horodatage(self.debut)}_{operation}.log"
        self._f = open(self.chemin, "a", encoding="utf-8")
        self.console = console

    def __call__(self, message: str) -> None:
        """Écrit `message`, précédé de l'heure, et vide le tampon aussitôt.

        L'écriture immédiate garde un journal exploitable même si l'opération est
        interrompue brutalement.
        """
        ligne = f"{dt.datetime.now():%H:%M:%S}  {message}"
        self._f.write(ligne + "\n")
        self._f.flush()
        if self.console:
            print(ligne, file=sys.stdout, flush=True)

    def fermer(self) -> None:
        """Ferme le fichier journal."""
        self._f.close()

    def __enter__(self):
        """Renvoie le journal lui-même, pour `with Journal(...) as j`."""
        return self

    def __exit__(self, *exc):
        """Ferme le journal, y compris après une exception (qui n'est pas absorbée)."""
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
    """Écrit le rapport Markdown d'une opération et renvoie son chemin.

    Le rapport donne la date, la durée et le statut, puis le contexte, le tableau des
    chiffres, les remarques et les erreurs (les 50 premières : le reste est dans le
    journal), et finit par un lien relatif vers le journal.

    Args:
        dossier: Dossier des rapports (`chemins.rapports`), créé au besoin.
        journal: Journal de l'opération : fournit le nom, le début et le lien.
        titre: Titre du rapport.
        contexte: Couples (libellé, valeur) affichés en liste (dossiers concernés…).
        chiffres: Couples (résultat, nombre) affichés en tableau.
        erreurs: Messages d'erreur ; s'il y en a, le statut l'indique.
        remarques: Lignes à signaler en plus (corbeille utilisée, mode simulation…).

    Returns:
        Le chemin du rapport écrit.
    """
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
