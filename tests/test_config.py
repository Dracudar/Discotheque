import pytest

from disco import config


def test_exemple_valide(config_exemple):
    cfg = config.charger(config_exemple)
    assert cfg.source == config_exemple
    # Les apostrophes TOML gardent les « \ » de Windows tels quels
    assert str(cfg.musique) == r"X:\Musique"
    assert cfg.surechantillonnage_crete == 8
    assert str(cfg.dap).startswith("X:") and str(cfg.sauvegarde).startswith("X:")
    assert cfg.references.fiches_achat is not None
    # Dossiers système déduits de la racine
    assert cfg.sortie.name == "_discotheque" and cfg.journaux.name == "_log"
    assert cfg.rapports.name == "_reports" and cfg.corbeille.name == "_to_delete"
    assert cfg.bot.name == "_bot" and cfg.arrivees.name == "_sort"
    assert cfg.reference_lufs == -18.0
    assert len(cfg.categories) == 9


def test_categories_exemple(config_exemple):
    cfg = config.charger(config_exemple)
    assert cfg.categorie("Artists").pages and cfg.categorie("Artists").rg_album
    # Bulk et Night : pas de pages, ReplayGain piste seulement
    for nom in ("Bulk", "Night"):
        c = cfg.categorie(nom)
        assert c.type == "vrac" and not c.pages and not c.rg_album
    assert cfg.categorie("_discotheque").type == "ignore"  # dossier système implicite
    assert cfg.categorie("Inconnu") is None


def test_donnees_par_defaut():
    cfg = config.depuis_dict(
        {
            "chemins": {"musique": "M", "sortie": "S"},
            "categories": {"Artists": {"type": "artistes"}},
        }
    )
    assert cfg.donnees.name == "_data" and cfg.donnees.parent.name == "S"
    assert cfg.journaux.as_posix() == "M/_log"
    assert cfg.dap is None and cfg.sauvegarde is None and cfg.references.audit is None
    assert cfg.ffmpeg == "ffmpeg"


def test_type_inconnu_refuse():
    with pytest.raises(config.ErreurConfig, match="Type inconnu"):
        config.depuis_dict(
            {
                "chemins": {"musique": "M", "sortie": "S"},
                "categories": {"X": {"type": "nimporte"}},
            }
        )


def test_cle_manquante():
    with pytest.raises(config.ErreurConfig, match="musique"):
        config.depuis_dict({"chemins": {"sortie": "S"}, "categories": {}})


def test_introuvable(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "RACINE_DEPOT", tmp_path)
    with pytest.raises(config.ErreurConfig, match="introuvable"):
        config.trouver()


def test_variable_environnement(config_exemple, monkeypatch):
    monkeypatch.setenv("DISCO_CONFIG", str(config_exemple))
    assert config.trouver() == config_exemple
