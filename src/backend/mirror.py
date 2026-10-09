"""
mirror.py - Moteur de copie miroir

Description:
    Moteur de copie miroir, sans robocopy.

    - **Plan** : on liste la source et la destination, puis on compare taille et date de
      modification (tolérance de 2 s, comme robocopy /FFT, pour les cartes en FAT/exFAT).
    - **Copie atomique** : chaque fichier est copié sous un nom temporaire, vérifié
      (taille), puis renommé. Une interruption ne laisse jamais un fichier tronqué à sa
      place définitive ; relancer l'opération reprend là où elle s'était arrêtée.
    - **Ce qui disparaît** de la destination est supprimé, ou déplacé dans une corbeille
      quand la destination doit rester récupérable (discothèque, sauvegarde).
    - **Exclusions** : uniquement des dossiers et fichiers de **premier niveau**
      (ex. `_log`), jamais un motif appliqué à toute la profondeur.

    Les chemins relatifs manipulés sont toujours écrits avec « / » (« a/b.flac »),
    quel que soit le système.

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

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

DATE_TOLERANCE = 2.0  # secondes
TEMP_SUFFIX = ".disco-tmp"
IGNORED_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}


@dataclass
class Plan:
    """Ce qu'un miroir doit faire, calculé par `make_plan` avant toute écriture.

    Attributes:
        new: Fichiers absents de la destination (chemins relatifs, triés).
        modified: Fichiers présents des deux côtés, mais de taille ou de date différente.
        extra: Fichiers de la destination absents de la source.
        total_bytes: Volume total à copier (nouveaux et modifiés).
    """

    new: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)
    total_bytes: int = 0

    @property
    def to_copy(self) -> list[str]:
        """Fichiers à copier : les nouveaux, puis les modifiés."""
        return self.new + self.modified

    def is_empty(self) -> bool:
        """Vrai si source et destination sont déjà identiques."""
        return not (self.new or self.modified or self.extra)


@dataclass
class Outcome:
    """Ce qu'une copie a réellement fait (reste vide en simulation).

    Attributes:
        copied: Fichiers copiés.
        total_bytes: Volume copié.
        deleted: Fichiers supprimés de la destination (miroir sans corbeille).
        trashed: Fichiers déplacés dans la corbeille (en trop ou remplacés).
        moved: Arrivées retirées du baladeur (copiées, ou déjà présentes).
        errors: Messages « chemin : erreur » des fichiers qui n'ont pas pu être traités.
    """

    copied: int = 0
    total_bytes: int = 0
    deleted: int = 0
    trashed: int = 0
    moved: int = 0
    errors: list[str] = field(default_factory=list)


def list_files(root: Path, excluded: set[str] | None = None, ignored: set[Path] | None = None) -> dict[str, tuple[int, float]]:
    """Fichiers sous `root` : {chemin relatif « a/b.flac » : (taille, date)}.

    Les fichiers temporaires (`TEMP_SUFFIX`) et système (`IGNORED_FILES`) sont
    toujours ignorés.

    Args:
        root: Dossier à parcourir ; s'il n'existe pas, le résultat est vide.
        excluded: Noms de dossiers ou de fichiers ignorés **au premier niveau seulement**
            (comparaison insensible à la casse).
        ignored: Fichiers ignorés, en chemins absolus (ex. le journal en cours
            d'écriture).

    Returns:
        Un dictionnaire {chemin relatif : (taille en octets, date de modification)}.
    """
    root = Path(root)
    excluded = {e.lower() for e in (excluded or set())}
    ignored = {Path(i).resolve() for i in (ignored or set())}
    res: dict[str, tuple[int, float]] = {}
    if not root.is_dir():
        return res
    for folder, subfolders, files in os.walk(root):
        rel_folder = Path(folder).relative_to(root)
        if rel_folder == Path("."):
            subfolders[:] = [s for s in subfolders if s.lower() not in excluded]
            files = [f for f in files if f.lower() not in excluded]
        for f in files:
            if f.lower() in IGNORED_FILES or f.endswith(TEMP_SUFFIX):
                continue
            if ignored and (Path(folder) / f).resolve() in ignored:
                continue
            st = (Path(folder) / f).stat()
            res[(rel_folder / f).as_posix()] = (st.st_size, st.st_mtime)
    return res


def system_exclusions(*roots: Path, prefix: str = "_") -> set[str]:
    """Noms des dossiers système (« _… ») présents au premier niveau des racines données."""
    names: set[str] = set()
    for r in roots:
        if r and Path(r).is_dir():
            names |= {p.name for p in Path(r).iterdir() if p.is_dir() and p.name.startswith(prefix)}
    return names


def make_plan(source: dict, destination: dict) -> Plan:
    """Compare deux listes de fichiers (résultats de `list_files`) et en tire le plan.

    Un fichier est « modifié » si sa taille diffère ou si sa date s'écarte de plus de
    `DATE_TOLERANCE` secondes. Le contenu n'est pas relu : c'est le compromis de
    robocopy, suffisant pour une copie de sécurité et bien plus rapide.

    Args:
        source: Fichiers de la source.
        destination: Fichiers de la destination.

    Returns:
        Le plan du miroir source → destination.
    """
    plan = Plan()
    for rel, (size, date) in sorted(source.items()):
        if rel not in destination:
            plan.new.append(rel)
        else:
            size2, date2 = destination[rel]
            if size2 != size or abs(date2 - date) > DATE_TOLERANCE:
                plan.modified.append(rel)
            else:
                continue
        plan.total_bytes += size
    plan.extra = sorted(set(destination) - set(source))
    return plan


def copy_file(src: Path, dst: Path) -> int:
    """Copie atomique : nom temporaire, vérification de la taille, puis renommage.

    La date de modification est conservée (`shutil.copy2`), sans quoi le fichier
    paraîtrait modifié au miroir suivant. Les dossiers manquants sont créés.

    Args:
        src: Fichier à copier.
        dst: Chemin final de la copie ; remplacé s'il existe.

    Returns:
        La taille copiée, en octets.

    Raises:
        OSError: Copie impossible, ou taille différente après copie (le fichier
            temporaire est alors retiré).
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + TEMP_SUFFIX)
    shutil.copy2(src, tmp)
    size = src.stat().st_size
    if tmp.stat().st_size != size:
        tmp.unlink(missing_ok=True)
        raise OSError(f"taille différente après copie : {dst}")
    os.replace(tmp, dst)
    return size


def move_to_trash(file: Path, root: Path, trash: Path) -> Path:
    """Déplace `file` (sous `root`) vers `trash`, en gardant son chemin relatif.

    Si la corbeille contient déjà ce chemin, le nom reçoit un suffixe
    (« titre (1234).flac ») plutôt que d'écraser l'ancien.

    Args:
        file: Fichier à retirer.
        root: Dossier de référence du chemin relatif.
        trash: Dossier de corbeille de l'opération.

    Returns:
        Le chemin du fichier dans la corbeille.
    """
    target = trash / file.relative_to(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target = target.with_name(f"{target.stem} ({os.getpid()}){target.suffix}")
    shutil.move(file, target)
    return target


def remove_empty_dirs(root: Path, excluded: set[str] | None = None) -> None:
    """Supprime les dossiers devenus vides sous `root` (jamais la racine elle-même).

    Args:
        root: Dossier à nettoyer.
        excluded: Dossiers de premier niveau à ne pas toucher, ni eux ni leur contenu.
    """
    excluded = {e.lower() for e in (excluded or set())}
    for folder, _subfolders, _files in os.walk(root, topdown=False):
        p = Path(folder)
        if p == Path(root):
            continue
        rel = p.relative_to(root)
        if rel.parts[0].lower() in excluded:
            continue
        try:
            p.rmdir()
        except OSError:
            pass


def mirror(
    source: Path,
    destination: Path,
    excluded: set[str],
    log: Callable[[str], None],
    trash: Path | None = None,
    dry_run: bool = False,
    ignored: set[Path] | None = None,
) -> tuple[Plan, Outcome]:
    """Rend `destination` identique à `source`, hors exclusions de premier niveau.

    Les fichiers en trop (et l'ancienne version des fichiers remplacés) vont dans
    `trash` si elle est donnée ; sinon ils sont supprimés. Une erreur sur un fichier
    est notée dans le bilan et n'arrête pas la copie des autres.

    Args:
        source: Dossier de référence.
        destination: Dossier à mettre à jour.
        excluded: Noms de premier niveau exclus, des deux côtés.
        log: Appelable qui reçoit chaque ligne du journal.
        trash: Corbeille de l'opération ; None pour supprimer directement.
        dry_run: Simulation : journalise le plan sans rien modifier (le bilan reste vide).
        ignored: Fichiers de la source à ne pas copier (chemins absolus).

    Returns:
        Le couple (plan, bilan).
    """
    source, destination = Path(source), Path(destination)
    plan = make_plan(list_files(source, excluded, ignored), list_files(destination, excluded))
    outcome = Outcome()
    log(f"Plan : {len(plan.new)} nouveaux, {len(plan.modified)} modifiés, {len(plan.extra)} en trop, {plan.total_bytes / 1e9:.2f} Go à copier")
    if dry_run:
        for rel in plan.new:
            log(f"[simulation] nouveau   {rel}")
        for rel in plan.modified:
            log(f"[simulation] modifié   {rel}")
        for rel in plan.extra:
            log(f"[simulation] en trop   {rel}")
        return plan, outcome

    total = len(plan.to_copy)
    for i, rel in enumerate(plan.to_copy, 1):
        target = destination / rel
        try:
            if trash and target.exists():
                move_to_trash(target, destination, trash)
                outcome.trashed += 1
            outcome.total_bytes += copy_file(source / rel, target)
            outcome.copied += 1
            log(f"[{i}/{total}] copié     {rel}")
        except OSError as e:
            outcome.errors.append(f"{rel} : {e}")
            log(f"[{i}/{total}] ERREUR    {rel} : {e}")
    for rel in plan.extra:
        target = destination / rel
        try:
            if trash:
                move_to_trash(target, destination, trash)
                outcome.trashed += 1
                log(f"corbeille  {rel}")
            else:
                target.unlink()
                outcome.deleted += 1
                log(f"supprimé   {rel}")
        except OSError as e:
            outcome.errors.append(f"{rel} : {e}")
            log(f"ERREUR     {rel} : {e}")
    remove_empty_dirs(destination, excluded)
    return plan, outcome


def move_incoming(
    source: Path,
    destination: Path,
    log: Callable[[str], None],
    dry_run: bool = False,
) -> Outcome:
    """Déplace le contenu de `source` vers `destination` (arrivées du baladeur).

    Chaque fichier est copié puis vérifié avant d'être retiré de la source. Un fichier
    déjà présent à l'identique côté destination est seulement retiré de la source ; s'il
    diffère, le nouveau est gardé à côté, sous un autre nom (« titre (2).flac »).
    Rien n'est donc jamais écrasé dans la discothèque.

    Args:
        source: Dossier d'arrivées du baladeur.
        destination: Dossier d'arrivées de la discothèque (`paths.incoming`).
        log: Appelable qui reçoit chaque ligne du journal.
        dry_run: Simulation : journalise ce qui serait déplacé, sans rien modifier.

    Returns:
        Le bilan du déplacement.
    """
    source, destination = Path(source), Path(destination)
    outcome = Outcome()
    files = list_files(source)
    log(f"Arrivées : {len(files)} fichier(s) dans {source}")
    for rel, (size, date) in sorted(files.items()):
        target = destination / rel
        if dry_run:
            log(f"[simulation] déplacé   {rel}")
            continue
        try:
            if target.exists():
                st = target.stat()
                if st.st_size == size and abs(st.st_mtime - date) <= DATE_TOLERANCE:
                    (source / rel).unlink()
                    log(f"déjà présent, retiré du baladeur : {rel}")
                    outcome.moved += 1
                    continue
                n = 2
                while target.exists():
                    target = destination / Path(rel).with_name(f"{Path(rel).stem} ({n}){Path(rel).suffix}")
                    n += 1
            outcome.total_bytes += copy_file(source / rel, target)
            (source / rel).unlink()
            outcome.moved += 1
            log(f"déplacé    {rel}")
        except OSError as e:
            outcome.errors.append(f"{rel} : {e}")
            log(f"ERREUR     {rel} : {e}")
    if not dry_run:
        remove_empty_dirs(source)
    return outcome
