"""Moteur de copie miroir, sans robocopy.

- **Plan** : on liste la source et la destination, puis on compare taille et date de
  modification (tolérance de 2 s, comme robocopy /FFT, pour les cartes en FAT/exFAT).
- **Copie atomique** : chaque fichier est copié sous un nom temporaire, vérifié (taille),
  puis renommé. Une interruption ne laisse jamais un fichier tronqué à sa place définitive ;
  relancer l'opération reprend là où elle s'était arrêtée.
- **Ce qui disparaît** de la destination est supprimé, ou déplacé dans une corbeille quand
  la destination doit rester récupérable (discothèque, sauvegarde).
- **Exclusions** : uniquement des dossiers et fichiers de **premier niveau** (ex. `_log`),
  jamais un motif appliqué à toute la profondeur.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

TOLERANCE_DATE = 2.0  # secondes
SUFFIXE_TEMP = ".disco-tmp"
FICHIERS_IGNORES = {"desktop.ini", "thumbs.db", ".ds_store"}


@dataclass
class Plan:
    nouveaux: list[str] = field(default_factory=list)
    modifies: list[str] = field(default_factory=list)
    en_trop: list[str] = field(default_factory=list)
    octets: int = 0

    @property
    def a_copier(self) -> list[str]:
        return self.nouveaux + self.modifies

    def vide(self) -> bool:
        return not (self.nouveaux or self.modifies or self.en_trop)


@dataclass
class Bilan:
    copies: int = 0
    octets: int = 0
    supprimes: int = 0
    mis_en_corbeille: int = 0
    deplaces: int = 0
    erreurs: list[str] = field(default_factory=list)


def lister(
    racine: Path, exclus: set[str] | None = None, ignores: set[Path] | None = None
) -> dict[str, tuple[int, float]]:
    """Fichiers sous `racine` : {chemin relatif « a/b.flac » : (taille, date)}.

    `exclus` : noms de dossiers ou de fichiers ignorés **au premier niveau seulement**
    (comparaison insensible à la casse). Les fichiers temporaires et système sont ignorés,
    ainsi que les fichiers `ignores` (chemins absolus, ex. le journal en cours d'écriture).
    """
    racine = Path(racine)
    exclus = {e.lower() for e in (exclus or set())}
    ignores = {Path(i).resolve() for i in (ignores or set())}
    res: dict[str, tuple[int, float]] = {}
    if not racine.is_dir():
        return res
    for dossier, sous, fichiers in os.walk(racine):
        rel_dossier = Path(dossier).relative_to(racine)
        if rel_dossier == Path("."):
            sous[:] = [s for s in sous if s.lower() not in exclus]
            fichiers = [f for f in fichiers if f.lower() not in exclus]
        for f in fichiers:
            if f.lower() in FICHIERS_IGNORES or f.endswith(SUFFIXE_TEMP):
                continue
            if ignores and (Path(dossier) / f).resolve() in ignores:
                continue
            st = (Path(dossier) / f).stat()
            res[(rel_dossier / f).as_posix()] = (st.st_size, st.st_mtime)
    return res


def exclusions_systeme(*racines: Path, prefixe: str = "_") -> set[str]:
    """Noms des dossiers système (« _… ») présents au premier niveau des racines données."""
    noms: set[str] = set()
    for r in racines:
        if r and Path(r).is_dir():
            noms |= {p.name for p in Path(r).iterdir() if p.is_dir() and p.name.startswith(prefixe)}
    return noms


def planifier(source: dict, destination: dict) -> Plan:
    plan = Plan()
    for rel, (taille, date) in sorted(source.items()):
        if rel not in destination:
            plan.nouveaux.append(rel)
        else:
            t2, d2 = destination[rel]
            if t2 != taille or abs(d2 - date) > TOLERANCE_DATE:
                plan.modifies.append(rel)
            else:
                continue
        plan.octets += taille
    plan.en_trop = sorted(set(destination) - set(source))
    return plan


def copier_fichier(src: Path, dst: Path) -> int:
    """Copie atomique : nom temporaire, vérification de la taille, puis renommage."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + SUFFIXE_TEMP)
    shutil.copy2(src, tmp)
    taille = src.stat().st_size
    if tmp.stat().st_size != taille:
        tmp.unlink(missing_ok=True)
        raise OSError(f"taille différente après copie : {dst}")
    os.replace(tmp, dst)
    return taille


def mettre_en_corbeille(fichier: Path, racine: Path, corbeille: Path) -> Path:
    """Déplace `fichier` (sous `racine`) vers `corbeille`, en gardant son chemin relatif."""
    cible = corbeille / fichier.relative_to(racine)
    cible.parent.mkdir(parents=True, exist_ok=True)
    if cible.exists():
        cible = cible.with_name(f"{cible.stem} ({os.getpid()}){cible.suffix}")
    shutil.move(fichier, cible)
    return cible


def supprimer_dossiers_vides(racine: Path, exclus: set[str] | None = None) -> None:
    """Supprime les dossiers devenus vides sous `racine` (jamais la racine elle-même)."""
    exclus = {e.lower() for e in (exclus or set())}
    for dossier, _sous, _fichiers in os.walk(racine, topdown=False):
        p = Path(dossier)
        if p == Path(racine):
            continue
        rel = p.relative_to(racine)
        if rel.parts[0].lower() in exclus:
            continue
        try:
            p.rmdir()
        except OSError:
            pass


def miroir(
    source: Path,
    destination: Path,
    exclus: set[str],
    journal: Callable[[str], None],
    corbeille: Path | None = None,
    simulation: bool = False,
    ignores: set[Path] | None = None,
) -> tuple[Plan, Bilan]:
    """Rend `destination` identique à `source`, hors exclusions de premier niveau.

    Les fichiers en trop (et l'ancienne version des fichiers remplacés) vont dans
    `corbeille` si elle est donnée ; sinon ils sont supprimés.
    """
    source, destination = Path(source), Path(destination)
    plan = planifier(lister(source, exclus, ignores), lister(destination, exclus))
    bilan = Bilan()
    journal(
        f"Plan : {len(plan.nouveaux)} nouveaux, {len(plan.modifies)} modifiés, "
        f"{len(plan.en_trop)} en trop, {plan.octets / 1e9:.2f} Go à copier"
    )
    if simulation:
        for rel in plan.nouveaux:
            journal(f"[simulation] nouveau   {rel}")
        for rel in plan.modifies:
            journal(f"[simulation] modifié   {rel}")
        for rel in plan.en_trop:
            journal(f"[simulation] en trop   {rel}")
        return plan, bilan

    total = len(plan.a_copier)
    for i, rel in enumerate(plan.a_copier, 1):
        cible = destination / rel
        try:
            if corbeille and cible.exists():
                mettre_en_corbeille(cible, destination, corbeille)
                bilan.mis_en_corbeille += 1
            bilan.octets += copier_fichier(source / rel, cible)
            bilan.copies += 1
            journal(f"[{i}/{total}] copié     {rel}")
        except OSError as e:
            bilan.erreurs.append(f"{rel} : {e}")
            journal(f"[{i}/{total}] ERREUR    {rel} : {e}")
    for rel in plan.en_trop:
        cible = destination / rel
        try:
            if corbeille:
                mettre_en_corbeille(cible, destination, corbeille)
                bilan.mis_en_corbeille += 1
                journal(f"corbeille  {rel}")
            else:
                cible.unlink()
                bilan.supprimes += 1
                journal(f"supprimé   {rel}")
        except OSError as e:
            bilan.erreurs.append(f"{rel} : {e}")
            journal(f"ERREUR     {rel} : {e}")
    supprimer_dossiers_vides(destination, exclus)
    return plan, bilan


def deplacer_arrivees(
    source: Path,
    destination: Path,
    journal: Callable[[str], None],
    simulation: bool = False,
) -> Bilan:
    """Déplace le contenu de `source` vers `destination` (arrivées du baladeur).

    Chaque fichier est copié puis vérifié avant d'être retiré de la source. Un fichier
    déjà présent à l'identique côté destination est seulement retiré de la source ; s'il
    diffère, le nouveau est gardé à côté, sous un autre nom.
    """
    source, destination = Path(source), Path(destination)
    bilan = Bilan()
    fichiers = lister(source)
    journal(f"Arrivées : {len(fichiers)} fichier(s) dans {source}")
    for rel, (taille, date) in sorted(fichiers.items()):
        cible = destination / rel
        if simulation:
            journal(f"[simulation] déplacé   {rel}")
            continue
        try:
            if cible.exists():
                st = cible.stat()
                if st.st_size == taille and abs(st.st_mtime - date) <= TOLERANCE_DATE:
                    (source / rel).unlink()
                    journal(f"déjà présent, retiré du baladeur : {rel}")
                    bilan.deplaces += 1
                    continue
                n = 2
                while cible.exists():
                    cible = destination / Path(rel).with_name(
                        f"{Path(rel).stem} ({n}){Path(rel).suffix}"
                    )
                    n += 1
            bilan.octets += copier_fichier(source / rel, cible)
            (source / rel).unlink()
            bilan.deplaces += 1
            journal(f"déplacé    {rel}")
        except OSError as e:
            bilan.erreurs.append(f"{rel} : {e}")
            journal(f"ERREUR     {rel} : {e}")
    if not simulation:
        supprimer_dossiers_vides(source)
    return bilan
