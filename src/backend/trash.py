"""
trash.py - Corbeille des opérations et sa purge

Description:
    Corbeille des opérations (`paths.trash`, `_workspace/_bin` par défaut) : rien n'est
    supprimé directement, ce qui doit disparaître y est déplacé par lot
    (`<corbeille>/<lot>/`). Il y reste jusqu'à ce que l'opérateur vide la corbeille, sauf
    si la purge est activée (`trash.retention_days`, 0 par défaut : jamais) : chaque lot
    est alors supprimé définitivement ce nombre de jours après son entrée. Son lancement
    automatique viendra avec la surveillance des données (jalon 4) ; d'ici là,
    `disco purge` la lance à la main.

    Chaque lot laisse deux traces :

    - **le journal de la corbeille**, `bin_journal.jsonl` dans `paths.logs` : il fait
      foi. Une ligne JSON par événement (entrée d'un lot, purge), jamais réécrite ni
      touchée par la purge. L'opération qui remplit ou purge la corbeille note aussi
      chaque fichier dans son propre journal (`OpLog`) ;
    - **le manifeste `_lot.json`** dans le dossier du lot : la même liste, pour lire ou
      annuler un lot sans chercher dans les journaux. Il disparaît avec le lot.

    Garde-fous de la purge :

    - l'âge se compte depuis la date d'entrée notée dans le journal, jamais depuis la
      date des fichiers (un fichier déplacé garde sa date de modification d'origine) ;
    - un lot entier à la fois, jamais une partie ;
    - un lot absent du journal, sans manifeste, dont le manifeste ne correspond pas au
      journal ou qui contient d'autres fichiers que ceux du manifeste n'est jamais
      purgé : il est signalé.

    Les chemins des fichiers dans un lot sont écrits avec « / » (« a/b.flac »), quel
    que soit le système.

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.24

Date de modification :
    2026.10.24
"""

from __future__ import annotations

import datetime as dt
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

JOURNAL_NAME = "bin_journal.jsonl"
MANIFEST_NAME = "_lot.json"
# Les lots purgés dans ce délai sont annoncés dans le rapport de la purge
NOTICE_DAYS = 7

ENTRY, PURGE = "entry", "purge"


class TrashError(Exception):
    """Lot impossible à créer (nom invalide, lot déjà connu, fichier hors racine)."""


@dataclass(frozen=True)
class Lot:
    """Un lot de la corbeille, tel que noté dans le journal et le manifeste.

    Attributes:
        name: Nom du lot, qui est aussi celui de son dossier dans la corbeille.
        entered: Date d'entrée dans la corbeille : l'âge du lot se compte à partir d'elle.
        operation: Opération qui a rempli le lot (« replaygain », « sort »…).
        files: Pour chaque fichier : `path` (chemin dans le lot), `original` (chemin
            d'origine) et `size` (taille en octets).
    """

    name: str
    entered: dt.datetime
    operation: str
    files: tuple[dict, ...]

    def to_json(self) -> dict:
        """Contenu du manifeste (et de l'entrée du journal, sans l'événement)."""
        return {
            "lot": self.name,
            "entered": self.entered.isoformat(timespec="seconds"),
            "operation": self.operation,
            "files": list(self.files),
        }

    @classmethod
    def from_json(cls, d: dict) -> Lot:
        """Lot relu d'un manifeste ou d'une entrée du journal.

        Raises:
            KeyError, ValueError, TypeError: Contenu incomplet ou mal formé.
        """
        return cls(
            name=str(d["lot"]),
            entered=dt.datetime.fromisoformat(d["entered"]),
            operation=str(d["operation"]),
            files=tuple(dict(f) for f in d["files"]),
        )


@dataclass
class PurgeOutcome:
    """Ce qu'une purge a fait et ce qu'elle annonce.

    Attributes:
        purged: Lots supprimés définitivement.
        upcoming: Lots purgés dans les `NOTICE_DAYS` jours, avec leur date de purge.
        flagged: Lots jamais purgés, avec la raison (absent du journal, manifeste…).
        kept: Nombre de lots gardés parce qu'ils sont encore récents.
    """

    purged: list[Lot] = field(default_factory=list)
    upcoming: list[tuple[Lot, dt.datetime]] = field(default_factory=list)
    flagged: list[tuple[str, str]] = field(default_factory=list)
    kept: int = 0


def _check_name(name: str) -> None:
    """Refuse un nom de lot qui ne serait pas un simple nom de dossier.

    Raises:
        TrashError: Nom vide, avec séparateur, « . », « .. » ou commençant par « _ ».
    """
    if not name or name in {".", ".."} or "/" in name or "\\" in name or name.startswith("_"):
        raise TrashError(f"Nom de lot invalide : {name!r}")


def journal_path(logs: Path) -> Path:
    """Chemin du journal de la corbeille dans le dossier des journaux (`paths.logs`)."""
    return Path(logs) / JOURNAL_NAME


def _append(logs: Path, event: str, content: dict) -> None:
    """Ajoute un événement au journal de la corbeille, créé au besoin, écrit aussitôt."""
    path = journal_path(logs)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"event": event, **content}, ensure_ascii=False) + "\n")
        f.flush()


def read_journal(logs: Path) -> tuple[dict[str, Lot], set[str]]:
    """Relit le journal de la corbeille.

    Une ligne illisible est ignorée : le lot qu'elle décrivait passe alors pour absent
    du journal, et n'est donc jamais purgé.

    Args:
        logs: Dossier des journaux (`paths.logs`).

    Returns:
        Les lots entrés, par nom, et les noms des lots déjà purgés.
    """
    lots: dict[str, Lot] = {}
    purged: set[str] = set()
    path = journal_path(logs)
    if not path.is_file():
        return lots, purged
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
            if d.get("event") == ENTRY:
                lot = Lot.from_json(d)
                lots[lot.name] = lot
            elif d.get("event") == PURGE:
                purged.add(str(d["lot"]))
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
    return lots, purged


def put(
    files: list[Path],
    root: Path,
    trash: Path,
    logs: Path,
    lot: str,
    operation: str,
    log: Callable[[str], None],
    now: dt.datetime | None = None,
) -> Lot:
    """Déplace des fichiers dans un nouveau lot de la corbeille.

    Chaque fichier garde son chemin relatif à `root` dans `<corbeille>/<lot>/`. Le lot
    est noté dans le journal de la corbeille avant le premier déplacement (un lot
    interrompu reste donc connu du journal ; son manifeste ne correspond plus, et il
    est signalé au lieu d'être purgé), puis le manifeste est écrit.

    Args:
        files: Fichiers à retirer, tous sous `root`.
        root: Dossier de référence des chemins relatifs (la racine de la discothèque).
        trash: Corbeille (`paths.trash`).
        logs: Dossier des journaux (`paths.logs`).
        lot: Nom du lot, nouveau.
        operation: Opération qui retire les fichiers.
        log: Journal de l'opération (`OpLog` ou tout appelable).
        now: Date d'entrée ; l'heure courante par défaut (utile aux tests).

    Returns:
        Le lot créé.

    Raises:
        TrashError: Nom invalide, lot déjà connu (journal ou dossier), fichier hors de
            `root` ou absent.
    """
    _check_name(lot)
    folder = Path(trash) / lot
    known, _ = read_journal(logs)
    if lot in known or folder.exists():
        raise TrashError(f"Le lot {lot} existe déjà dans la corbeille ou son journal")
    root = Path(root)
    entries = []
    for f in files:
        f = Path(f)
        try:
            rel = f.relative_to(root).as_posix()
        except ValueError as e:
            raise TrashError(f"{f} n'est pas sous {root}") from e
        if not f.is_file():
            raise TrashError(f"{f} introuvable")
        entries.append({"path": rel, "original": str(f), "size": f.stat().st_size})
    result = Lot(name=lot, entered=(now or dt.datetime.now()).replace(microsecond=0), operation=operation, files=tuple(entries))
    _append(logs, ENTRY, result.to_json())
    log(f"Corbeille : lot {lot} ({len(entries)} fichiers, opération {operation})")
    folder.mkdir(parents=True)
    for f, e in zip(files, entries, strict=True):
        target = folder / e["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(f, target)
        log(f"  -> corbeille : {e['original']} ({e['size']} octets)")
    (folder / MANIFEST_NAME).write_text(json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _content(folder: Path) -> set[str]:
    """Fichiers d'un dossier de lot, en chemins relatifs, sans le manifeste."""
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()} - {MANIFEST_NAME}


def _problem(folder: Path, known: Lot | None) -> str | None:
    """Raison de ne jamais purger un dossier de la corbeille, ou None s'il peut l'être."""
    if known is None:
        return "absent du journal de la corbeille"
    manifest = folder / MANIFEST_NAME
    if not manifest.is_file():
        return "manifeste absent"
    try:
        written = Lot.from_json(json.loads(manifest.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, AttributeError):
        return "manifeste illisible"
    if written != known:
        return "le manifeste ne correspond pas au journal"
    extra = _content(folder) - {f["path"] for f in known.files}
    if extra:
        return f"{len(extra)} fichier(s) hors du manifeste (ex. {sorted(extra)[0]})"
    return None


def purge(
    trash: Path,
    logs: Path,
    retention_days: int,
    log: Callable[[str], None],
    now: dt.datetime | None = None,
) -> PurgeOutcome:
    """Supprime définitivement les lots entrés depuis au moins `retention_days` jours.

    Un lot est purgé en entier (son dossier, manifeste compris), et la purge est notée
    dans le journal de la corbeille avec la liste des fichiers supprimés. Avec
    `retention_days` à 0, rien n'est purgé, mais les lots suspects sont signalés.

    Args:
        trash: Corbeille (`paths.trash`).
        logs: Dossier des journaux (`paths.logs`).
        retention_days: Jours de conservation (0 : jamais de purge automatique).
        log: Journal de l'opération (`OpLog` ou tout appelable).
        now: Instant de la purge ; l'heure courante par défaut (utile aux tests).

    Returns:
        Les lots purgés, ceux purgés bientôt et ceux signalés.
    """
    now = now or dt.datetime.now()
    outcome = PurgeOutcome()
    trash = Path(trash)
    if not trash.is_dir():
        return outcome
    known, already = read_journal(logs)
    for folder in sorted(p for p in trash.iterdir() if p.is_dir()):
        lot = known.get(folder.name)
        problem = "déjà purgé selon le journal" if folder.name in already else _problem(folder, lot)
        if problem:
            outcome.flagged.append((folder.name, problem))
            log(f"Corbeille : lot {folder.name} jamais purgé : {problem}")
            continue
        if retention_days == 0:
            outcome.kept += 1
            continue
        expiry = lot.entered + dt.timedelta(days=retention_days)
        if now < expiry:
            outcome.kept += 1
            if expiry - now <= dt.timedelta(days=NOTICE_DAYS):
                outcome.upcoming.append((lot, expiry))
            continue
        try:
            shutil.rmtree(folder)
        except OSError as e:
            # Lot en partie supprimé : son manifeste peut manquer, il sera signalé ensuite
            outcome.flagged.append((lot.name, f"purge interrompue : {e}"))
            log(f"Corbeille : purge du lot {lot.name} interrompue : {e}")
            continue
        _append(
            logs,
            PURGE,
            {"lot": lot.name, "purged": now.isoformat(timespec="seconds"), "files": [f["original"] for f in lot.files]},
        )
        log(f"Corbeille : lot {lot.name} purgé (entré le {lot.entered:%d/%m/%Y}, {len(lot.files)} fichiers)")
        for f in lot.files:
            log(f"  supprimé : {f['original']}")
        outcome.purged.append(lot)
    return outcome
