import os

import pytest

from disco import config


def test_exemple_valide(config_exemple):
    cfg = config.charger(config_exemple)
    assert cfg.sources == (config_exemple,)
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
    # L'exemple n'ajoute aucune catégorie active : celles par défaut seulement
    assert len(cfg.categories) == 7


def test_categories_exemple(config_exemple):
    cfg = config.charger(config_exemple)
    assert cfg.categorie("Artists").pages and cfg.categorie("Artists").rg_album
    # Bulk : pas de pages, ReplayGain piste seulement
    c = cfg.categorie("Bulk")
    assert c.type == "vrac" and not c.pages and not c.rg_album
    assert cfg.categorie("_data").type == "ignore"  # dossier système implicite
    assert cfg.categorie("Inconnu") is None


def test_base_et_cache_par_defaut():
    cfg = config.depuis_dict({"chemins": {"racine": "M", "sortie": "S"}})
    assert cfg.base.as_posix() == "S/_base" and cfg.cache.as_posix() == "S/_cache"
    assert cfg.journaux.as_posix() == "M/_log"
    assert cfg.dap is None and cfg.sauvegarde is None and cfg.references.audit is None
    assert cfg.ffmpeg == "ffmpeg"
    assert cfg.reference_lufs == -18.0 and len(cfg.categories) == 7  # défaut


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
        config.depuis_dict({"chemins": {"sortie": "S"}})


@pytest.mark.parametrize(("ancienne", "nouvelle"), [("musique", "racine"), ("donnees", "base")])
def test_anciennes_cles_signalees(ancienne, nouvelle):
    with pytest.raises(config.ErreurConfig, match=nouvelle):
        config.depuis_dict({"chemins": {ancienne: "M"}, "categories": {}})


CATEGORIES = '[categories."Mon Ajout"]\ntype = "projets"\npages = true\n'


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
    assert cfg.racine == sandbox
    assert cfg.sources == (sandbox / "_bot" / "config.toml", clone)
    assert str(cfg.dap) == "D"  # lu dans _bot
    assert cfg.fpcalc == "G"  # le clone l'emporte
    assert "Mon Ajout" in cfg.categories and "Artists" in cfg.categories
    # Origine de chaque valeur
    assert cfg.origine("chemins.racine") == config.CLONE
    assert cfg.origine("dap.destination") == config.BOT
    assert cfg.origine("outils.fpcalc") == config.CLONE
    assert cfg.origine("categories.Mon Ajout") == config.BOT
    assert cfg.origine("categories.Artists") == config.DEFAUT
    assert cfg.origine("chemins.sortie") == config.DEDUIT


def test_config_a_cote_de_l_environnement(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    bot = tmp_path / "_bot"
    bot.mkdir()
    (bot / "config.toml").write_text(CATEGORIES, encoding="utf-8")
    monkeypatch.setattr(config, "dossier_environnement", lambda: bot)
    assert config.trouver() == bot / "config.toml"


def _sans_fichier(tmp_path, monkeypatch, programme):
    """Aucun config.toml nulle part ; le programme tourne depuis `programme`."""
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "RACINE_DEPOT", tmp_path)
    monkeypatch.setattr(config, "dossier_programme", lambda: programme)


def test_aucun_fichier_trouve(tmp_path, monkeypatch):
    _sans_fichier(tmp_path, monkeypatch, None)
    assert config.trouver() is None


def test_fichier_explicite_absent(tmp_path):
    with pytest.raises(config.ErreurConfig, match="introuvable"):
        config.trouver(tmp_path / "rien.toml")


def test_sans_config_depuis_bot(tmp_path, monkeypatch):
    """Production sans config.toml : racine déduite de _bot, configuration par défaut."""
    _sans_fichier(tmp_path, monkeypatch, tmp_path / "Musique" / "_bot")
    cfg = config.charger()
    assert cfg.racine == tmp_path / "Musique" and cfg.sources == ()
    assert set(cfg.categories) == {
        "Artists",
        "Classical music",
        "Compilations",
        "Musicals",
        "Soundtrack",
        "Bulk",
        "_sort",
    }
    assert not cfg.categorie("Bulk").rg_album and cfg.categorie("_sort").type == "arrivees"
    assert cfg.origine("chemins.racine") == config.DEDUIT
    assert cfg.origine("categories.Bulk") == config.DEFAUT


def test_sans_config_hors_bot(tmp_path, monkeypatch):
    """Ni config ni programme dans _bot : la racine est introuvable."""
    _sans_fichier(tmp_path, monkeypatch, tmp_path / "clone")
    with pytest.raises(config.ErreurConfig, match="Racine introuvable"):
        config.charger()


def test_surcharge_partielle_de_categorie(tmp_path):
    """Une clé redéfinie garde les autres clés du défaut ; « ignore » retire la catégorie."""
    bot = tmp_path / "_bot"
    bot.mkdir()
    (bot / "config.toml").write_text(
        '[categories.Soundtrack]\npages = false\n[categories.Musicals]\ntype = "ignore"\n',
        encoding="utf-8",
    )
    cfg = config.charger(bot / "config.toml")
    st = cfg.categorie("Soundtrack")
    assert st.type == "projets" and not st.pages and st.rg_album
    assert cfg.origine("categories.Soundtrack") == config.BOT
    assert cfg.origine("categories.Soundtrack.type") == config.DEFAUT
    mu = cfg.categorie("Musicals")
    assert mu.type == "ignore" and not mu.pages and not mu.rg_album


def test_variable_environnement(config_exemple, monkeypatch):
    monkeypatch.setenv("DISCO_CONFIG", str(config_exemple))
    assert config.trouver() == config_exemple


def test_outils_dans_bot_tools(tmp_path):
    """Sans chemin dans [outils], un outil posé dans <bot>/tools est utilisé ; sinon le PATH."""
    tools = tmp_path / "_bot" / "tools"
    tools.mkdir(parents=True)
    nom = "fpcalc.exe" if os.name == "nt" else "fpcalc"
    (tools / nom).write_bytes(b"")
    d = {"chemins": {"racine": str(tmp_path)}, "categories": {"A": {"type": "artistes"}}}
    cfg = config.depuis_dict(d)
    assert cfg.fpcalc == str(tools / nom)
    assert cfg.ffmpeg == "ffmpeg"  # absent de tools : PATH
    d["outils"] = {"fpcalc": "autre"}
    assert config.depuis_dict(d).fpcalc == "autre"  # la config l'emporte
