"""
test_mirror.py - Tests du moteur de copie miroir

Description:
    Tests de `src.backend.mirror` sur des arborescences fictives : miroir avec ou sans
    trash, simulation, fichier modifié, excludedions de premier niveau, arrivées en
    double. Reprend les cas couverts par les anciens tests du baladeur (legacy/dap), le
    moteur restant en service pour les copies à venir.

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.09
"""

import os
from pathlib import Path

import pytest

from src.backend import mirror


def write(p: Path, content: str = "x", age: float = 0) -> Path:
    """Écrit un fichier fictif, vieilli de `age` secondes."""
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if age:
        t = p.stat().st_mtime - age
        os.utime(p, (t, t))
    return p


def files(d: Path) -> set[str]:
    """Fichiers sous `d`, en chemins relatifs."""
    return {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()}


@pytest.fixture
def source(tmp_path) -> Path:
    """Une discothèque fictive, avec ses dossiers système."""
    root = tmp_path / "Musique"
    write(root / "Artists" / "Les Exemples" / "Album" / "01 - Titre.flac", "audio1")
    write(root / "Artists" / "Les Exemples" / "Album" / "_bonus" / "02 - Caché.flac", "audio2")
    write(root / "Bulk" / "piste.opus", "audio3")
    write(root / "_data" / "index.html", "page")
    write(root / "Bulk" / "desktop.ini", "système")
    return root


def test_mirror_first_level_exclusions(source, tmp_path):
    dest = tmp_path / "DAP"
    excluded = mirror.system_exclusions(source)
    assert excluded == {"_data"}
    plan, outcome = mirror.mirror(source, dest, excluded, lambda m: None)
    # « _bonus » n'est pas au premier niveau : il est copié ; desktop.ini est ignoré
    assert files(dest) == {
        "Artists/Les Exemples/Album/01 - Titre.flac",
        "Artists/Les Exemples/Album/_bonus/02 - Caché.flac",
        "Bulk/piste.opus",
    }
    assert outcome.copied == 3 and not outcome.errors
    assert mirror.mirror(source, dest, excluded, lambda m: None)[0].is_empty()


def test_dry_run_changes_nothing(source, tmp_path):
    dest = tmp_path / "DAP"
    lines: list[str] = []
    plan, outcome = mirror.mirror(source, dest, set(), lines.append, dry_run=True)
    assert len(plan.new) == 4 and outcome.copied == 0
    assert not dest.exists()
    assert any(line.startswith("[simulation]") for line in lines)


def test_modified_file_copied_again(source, tmp_path):
    dest = tmp_path / "DAP"
    mirror.mirror(source, dest, set(), lambda m: None)
    write(source / "Bulk" / "piste.opus", "audio3 retagué")
    plan, _ = mirror.mirror(source, dest, set(), lambda m: None)
    assert plan.modified == ["Bulk/piste.opus"] and not plan.new
    assert mirror.list_files(dest)["Bulk/piste.opus"][0] == len("audio3 retagué".encode())


def test_extra_deleted_without_trash(source, tmp_path):
    dest = tmp_path / "DAP"
    mirror.mirror(source, dest, set(), lambda m: None)
    (source / "Bulk" / "piste.opus").unlink()
    _, outcome = mirror.mirror(source, dest, set(), lambda m: None)
    assert outcome.deleted == 1 and not (dest / "Bulk").exists()


def test_trash_keeps_old_versions(source, tmp_path):
    dest, trash = tmp_path / "Froid", tmp_path / "Froid_corbeille"
    mirror.mirror(source, dest, set(), lambda m: None, trash=trash)
    write(source / "Bulk" / "piste.opus", "version 2")
    (source / "Artists" / "Les Exemples" / "Album" / "01 - Titre.flac").unlink()
    _, outcome = mirror.mirror(source, dest, set(), lambda m: None, trash=trash)
    assert (dest / "Bulk" / "piste.opus").read_text(encoding="utf-8") == "version 2"
    assert outcome.trashed == 2 and outcome.deleted == 0
    assert files(trash) == {"Bulk/piste.opus", "Artists/Les Exemples/Album/01 - Titre.flac"}


def test_duplicate_incoming(tmp_path):
    incoming, sort = tmp_path / "DAP" / "_sort", tmp_path / "Musique" / "_sort"
    write(sort / "a.flac", "ancien")
    write(incoming / "a.flac", "nouveau", age=100)
    write(incoming / "b.flac", "b")
    outcome = mirror.move_incoming(incoming, sort, lambda m: None)
    assert (sort / "a.flac").read_text(encoding="utf-8") == "ancien"
    assert (sort / "a (2).flac").read_text(encoding="utf-8") == "nouveau"
    assert (sort / "b.flac").exists() and files(incoming) == set()
    assert outcome.moved == 2
