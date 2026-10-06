"""Baladeur et sauvegarde froide, sur des arborescences temporaires fictives."""

import os
from pathlib import Path

import pytest

from disco import config, dap


def ecrire(p: Path, contenu: str = "x", age: float = 0) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenu, encoding="utf-8")
    if age:
        t = p.stat().st_mtime - age
        os.utime(p, (t, t))
    return p


@pytest.fixture
def monde(tmp_path):
    """Une discothèque fictive, un baladeur et un disque de sauvegarde."""
    racine, baladeur, sauvegarde = tmp_path / "Musique", tmp_path / "DAP", tmp_path / "Froid"
    ecrire(racine / "Artists" / "Les Exemples" / "Album" / "01 - Titre.flac", "audio1")
    ecrire(racine / "Artists" / "Les Exemples" / "Album" / "_bonus" / "02 - Caché.flac", "audio2")
    ecrire(racine / "Bulk" / "piste.opus", "audio3")
    ecrire(racine / "_data" / "index.html", "page")
    ecrire(racine / "_bot" / "config.toml", "cfg")
    (racine / "_sort").mkdir()
    for d in (baladeur, sauvegarde):
        d.mkdir()
    cfg = config.depuis_dict(
        {
            "chemins": {"racine": str(racine)},
            "dap": {"destination": str(baladeur)},
            "sauvegarde": {"destination": str(sauvegarde)},
            "categories": {"Artists": {"type": "artistes"}, "Bulk": {"type": "vrac"}},
        }
    )
    return cfg, racine, baladeur, sauvegarde


def fichiers(d: Path) -> set[str]:
    return {p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file()}


def test_racine_et_dossiers_deduits(monde):
    cfg, racine, *_ = monde
    assert cfg.journaux == racine / "_log" and cfg.rapports == racine / "_reports"
    assert cfg.corbeille == racine / "_to_delete" and cfg.arrivees == racine / "_sort"
    assert cfg.categorie("_log").type == "ignore"


def test_synchro(monde):
    cfg, racine, baladeur, _ = monde
    ecrire(baladeur / "_sort" / "Nouvel album" / "01.flac", "rip")
    ecrire(baladeur / "Ancien" / "vieux.mp3", "à retirer")
    dap.poser_lanceur(baladeur)
    assert dap.operation_dap(cfg, "synchro", console=False) == 0

    # 1. les arrivées sont déplacées vers la discothèque
    assert (racine / "_sort" / "Nouvel album" / "01.flac").read_text(encoding="utf-8") == "rip"
    assert not list((baladeur / "_sort").rglob("*.flac"))
    # 2. le miroir copie la musique, y compris un sous-dossier « _… » profond
    assert fichiers(baladeur) == {
        "Artists/Les Exemples/Album/01 - Titre.flac",
        "Artists/Les Exemples/Album/_bonus/02 - Caché.flac",
        "Bulk/piste.opus",
        dap.NOM_LANCEUR,
    }
    # 3. journal et rapport
    assert len(list(cfg.journaux.glob("*_dap_synchro.log"))) == 1
    rapport = next(cfg.rapports.glob("*_dap_synchro.md")).read_text(encoding="utf-8")
    assert "Synchronisation du baladeur" in rapport and "../_log/" in rapport


def test_simulation_ne_modifie_rien(monde):
    cfg, racine, baladeur, _ = monde
    assert dap.operation_dap(cfg, "envoyer", simulation=True, console=False) == 0
    assert fichiers(baladeur) == set()
    assert "simulation" in next(cfg.rapports.glob("*.md")).read_text(encoding="utf-8")


def test_fichier_modifie_recopie(monde):
    cfg, racine, baladeur, _ = monde
    dap.operation_dap(cfg, "envoyer", console=False)
    ecrire(racine / "Bulk" / "piste.opus", "audio3 retagué")
    from disco import copie

    plan, _ = dap.envoyer(cfg, baladeur, lambda m: None)
    assert plan.modifies == ["Bulk/piste.opus"] and not plan.nouveaux
    assert copie.lister(baladeur)["Bulk/piste.opus"][0] == len("audio3 retagué".encode())


def test_restauration_exige_confirmation(monde):
    cfg, racine, baladeur, _ = monde
    dap.operation_dap(cfg, "envoyer", console=False)
    (racine / "Bulk" / "piste.opus").unlink()  # perte côté discothèque
    ecrire(racine / "Bulk" / "orphelin.mp3", "absent du DAP")

    dap.operation_dap(cfg, "restaurer", console=False)  # sans --confirmer : simulation
    assert not (racine / "Bulk" / "piste.opus").exists()

    assert dap.operation_dap(cfg, "restaurer", confirmer=True, console=False) == 0
    assert (racine / "Bulk" / "piste.opus").read_text(encoding="utf-8") == "audio3"
    # le fichier absent du DAP n'est pas supprimé : il part dans la corbeille
    assert not (racine / "Bulk" / "orphelin.mp3").exists()
    assert list(cfg.corbeille.rglob("orphelin.mp3"))
    # les dossiers système ne sont pas touchés
    assert (racine / "_bot" / "config.toml").exists()


def test_sauvegarde_garde_les_anciennes_versions(monde):
    cfg, racine, _, froid = monde
    assert dap.operation_sauvegarde(cfg, "envoyer", console=False) == 0
    assert "_data/index.html" in fichiers(froid) and "_bot/config.toml" in fichiers(froid)

    ecrire(racine / "Bulk" / "piste.opus", "version 2")
    (racine / "Artists" / "Les Exemples" / "Album" / "01 - Titre.flac").unlink()
    dap.operation_sauvegarde(cfg, "envoyer", console=False)
    assert (froid / "Bulk" / "piste.opus").read_text(encoding="utf-8") == "version 2"
    corbeille = froid / "_to_delete"
    assert {p.name for p in corbeille.rglob("*") if p.is_file()} == {
        "piste.opus",
        "01 - Titre.flac",
    }


def test_arrivee_en_double(monde):
    cfg, racine, baladeur, _ = monde
    ecrire(racine / "_sort" / "a.flac", "ancien")
    ecrire(baladeur / "_sort" / "a.flac", "nouveau", age=100)
    dap.operation_dap(cfg, "recuperer", console=False)
    assert (racine / "_sort" / "a.flac").read_text(encoding="utf-8") == "ancien"
    assert (racine / "_sort" / "a (2).flac").read_text(encoding="utf-8") == "nouveau"


def test_baladeur_absent(monde):
    cfg, *_ = monde
    with pytest.raises(config.ErreurConfig, match="introuvable"):
        dap.operation_dap(cfg, "synchro", dap=Path("/chemin/inexistant"), console=False)


def test_lanceur():
    texte = dap.texte_lanceur()
    assert "\r\n" in texte and "_bot\\config.toml" in texte
    assert "dap %SENS% --dap" in texte
