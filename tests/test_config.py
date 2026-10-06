import pytest

from disco import config


def test_exemple_valide(config_exemple):
    cfg = config.charger(config_exemple)
    assert cfg.source == config_exemple
    # Les apostrophes TOML gardent les « \ » de Windows tels quels
    assert str(cfg.racine) == r"X:\Musique"
    assert cfg.surechantillonnage_crete == 8
    assert str(cfg.dap).startswith("X:") and str(cfg.sauvegarde).startswith("X:")
    assert cfg.references.fiches_achat is not None
    # Dossiers système déduits de la racine
    assert cfg.sortie.name == "_data" and cfg.journaux.name == "_log"
    assert cfg.base.name == "_base" and cfg.base.parent == cfg.sortie
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
    assert cfg.categorie("_data").type == "ignore"  # dossier système implicite
    assert cfg.categorie("Inconnu") is None


def test_base_et_cache_par_defaut():
    cfg = config.depuis_dict(
        {
            "chemins": {"racine": "M", "sortie": "S"},
            "categories": {"Artists": {"type": "artistes"}},
        }
    )
    assert cfg.base.as_posix() == "S/_base" and cfg.cache.as_posix() == "S/_cache"
    assert cfg.journaux.as_posix() == "M/_log"
    assert cfg.dap is None and cfg.sauvegarde is None and cfg.references.audit is None
    assert cfg.ffmpeg == "ffmpeg"


def test_type_inconnu_refuse():
    with pytest.raises(config.ErreurConfig, match="Type inconnu"):
        config.depuis_dict(
            {
                "chemins": {"racine": "M", "sortie": "S"},
                "categories": {"X": {"type": "nimporte"}},
            }
        )


def test_racine_manquante():
    with pytest.raises(config.ErreurConfig, match="racine"):
        config.depuis_dict({"chemins": {"sortie": "S"}, "categories": {}})


@pytest.mark.parametrize(("ancienne", "nouvelle"), [("musique", "racine"), ("donnees", "base")])
def test_anciennes_cles_signalees(ancienne, nouvelle):
    with pytest.raises(config.ErreurConfig, match=nouvelle):
        config.depuis_dict({"chemins": {ancienne: "M"}, "categories": {}})


CATEGORIES = '[categories.Artists]\ntype = "artistes"\n'


def test_racine_deduite_de_bot(tmp_path):
    """Production : <racine>/_bot/config.toml, sans clé racine."""
    bot = tmp_path / "Musique" / "_bot"
    bot.mkdir(parents=True)
    (bot / "config.toml").write_text(CATEGORIES, encoding="utf-8")
    cfg = config.charger(bot / "config.toml")
    assert cfg.racine == tmp_path / "Musique" and cfg.bot == bot
    assert cfg.sortie == tmp_path / "Musique" / "_data"


def test_config_du_clone_surcharge_celle_de_bot(tmp_path):
    """Développement : le clone ne donne que la racine, le reste vient de _bot."""
    sandbox = tmp_path / "Sandbox"
    (sandbox / "_bot").mkdir(parents=True)
    (sandbox / "_bot" / "config.toml").write_text(
        CATEGORIES + '[dap]\ndestination = "D"\n[outils]\nfpcalc = "F"\n', encoding="utf-8"
    )
    clone = tmp_path / "clone" / "config.toml"
    clone.parent.mkdir()
    clone.write_text(f"[chemins]\nracine = '{sandbox}'\n[outils]\nfpcalc = 'G'\n", encoding="utf-8")
    cfg = config.charger(clone)
    assert cfg.racine == sandbox and cfg.source == clone
    assert str(cfg.dap) == "D"  # lu dans _bot
    assert cfg.fpcalc == "G"  # le clone l'emporte
    assert "Artists" in cfg.categories


def test_config_a_cote_de_l_environnement(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    bot = tmp_path / "_bot"
    bot.mkdir()
    (bot / "config.toml").write_text(CATEGORIES, encoding="utf-8")
    monkeypatch.setattr(config, "dossier_environnement", lambda: bot)
    assert config.trouver() == bot / "config.toml"


def test_introuvable(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "RACINE_DEPOT", tmp_path)
    monkeypatch.setattr(config, "dossier_environnement", lambda: None)
    with pytest.raises(config.ErreurConfig, match="introuvable"):
        config.trouver()


def test_variable_environnement(config_exemple, monkeypatch):
    monkeypatch.setenv("DISCO_CONFIG", str(config_exemple))
    assert config.trouver() == config_exemple
