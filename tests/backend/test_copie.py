"""
test_copie.py - Tests du moteur de copie miroir

Description:
    Tests de `src.backend.copie` sur des arborescences fictives : miroir avec ou sans
    corbeille, simulation, fichier modifié, exclusions de premier niveau, arrivées en
    double. Reprend les cas couverts par les anciens tests du baladeur (legacy/dap), le
    moteur restant en service pour les copies à venir.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.08
"""

import os
from pathlib import Path

import pytest

from src.backend import copie


def ecrire(p: Path, contenu: str = "x", age: float = 0) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenu, encoding="utf-8")
    if age:
        t = p.stat().st_mtime - age
        os.utime(p, (t, t))
    return p


def fichiers(d: Path) -> set[str]:
    return {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()}


@pytest.fixture
def source(tmp_path) -> Path:
    """Une discothèque fictive, avec ses dossiers système."""
    racine = tmp_path / "Musique"
    ecrire(racine / "Artists" / "Les Exemples" / "Album" / "01 - Titre.flac", "audio1")
    ecrire(racine / "Artists" / "Les Exemples" / "Album" / "_bonus" / "02 - Caché.flac", "audio2")
    ecrire(racine / "Bulk" / "piste.opus", "audio3")
    ecrire(racine / "_data" / "index.html", "page")
    ecrire(racine / "Bulk" / "desktop.ini", "système")
    return racine


def test_miroir_exclusions_premier_niveau(source, tmp_path):
    dest = tmp_path / "DAP"
    exclus = copie.exclusions_systeme(source)
    assert exclus == {"_data"}
    plan, bilan = copie.miroir(source, dest, exclus, lambda m: None)
    # « _bonus » n'est pas au premier niveau : il est copié ; desktop.ini est ignoré
    assert fichiers(dest) == {
        "Artists/Les Exemples/Album/01 - Titre.flac",
        "Artists/Les Exemples/Album/_bonus/02 - Caché.flac",
        "Bulk/piste.opus",
    }
    assert bilan.copies == 3 and not bilan.erreurs
    assert copie.miroir(source, dest, exclus, lambda m: None)[0].vide()


def test_simulation_ne_modifie_rien(source, tmp_path):
    dest = tmp_path / "DAP"
    lignes: list[str] = []
    plan, bilan = copie.miroir(source, dest, set(), lignes.append, simulation=True)
    assert len(plan.nouveaux) == 4 and bilan.copies == 0
    assert not dest.exists()
    assert any(ligne.startswith("[simulation]") for ligne in lignes)


def test_fichier_modifie_recopie(source, tmp_path):
    dest = tmp_path / "DAP"
    copie.miroir(source, dest, set(), lambda m: None)
    ecrire(source / "Bulk" / "piste.opus", "audio3 retagué")
    plan, _ = copie.miroir(source, dest, set(), lambda m: None)
    assert plan.modifies == ["Bulk/piste.opus"] and not plan.nouveaux
    assert copie.lister(dest)["Bulk/piste.opus"][0] == len("audio3 retagué".encode())


def test_en_trop_supprime_sans_corbeille(source, tmp_path):
    dest = tmp_path / "DAP"
    copie.miroir(source, dest, set(), lambda m: None)
    (source / "Bulk" / "piste.opus").unlink()
    _, bilan = copie.miroir(source, dest, set(), lambda m: None)
    assert bilan.supprimes == 1 and not (dest / "Bulk").exists()


def test_corbeille_garde_les_anciennes_versions(source, tmp_path):
    dest, corbeille = tmp_path / "Froid", tmp_path / "Froid_corbeille"
    copie.miroir(source, dest, set(), lambda m: None, corbeille=corbeille)
    ecrire(source / "Bulk" / "piste.opus", "version 2")
    (source / "Artists" / "Les Exemples" / "Album" / "01 - Titre.flac").unlink()
    _, bilan = copie.miroir(source, dest, set(), lambda m: None, corbeille=corbeille)
    assert (dest / "Bulk" / "piste.opus").read_text(encoding="utf-8") == "version 2"
    assert bilan.mis_en_corbeille == 2 and bilan.supprimes == 0
    assert fichiers(corbeille) == {"Bulk/piste.opus", "Artists/Les Exemples/Album/01 - Titre.flac"}


def test_arrivee_en_double(tmp_path):
    arrivees, sort = tmp_path / "DAP" / "_sort", tmp_path / "Musique" / "_sort"
    ecrire(sort / "a.flac", "ancien")
    ecrire(arrivees / "a.flac", "nouveau", age=100)
    ecrire(arrivees / "b.flac", "b")
    bilan = copie.deplacer_arrivees(arrivees, sort, lambda m: None)
    assert (sort / "a.flac").read_text(encoding="utf-8") == "ancien"
    assert (sort / "a (2).flac").read_text(encoding="utf-8") == "nouveau"
    assert (sort / "b.flac").exists() and fichiers(arrivees) == set()
    assert bilan.deplaces == 2
