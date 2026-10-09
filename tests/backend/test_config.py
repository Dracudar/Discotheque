"""
test_config.py - Tests de la configuration

Description:
    Tests du chargement de la configuration : exemples de production et de
    développement, catégories, chemins déduits de la racine, superposition des couches
    (défaut, _bot, clone), ordre de recherche, anciens noms et valeurs refusés, outils
    externes.

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
"""

import os
import shutil

import pytest

from src.backend import config


def test_dev_example_is_valid(dev_example):
    cfg = config.load(dev_example)
    assert cfg.sources == (dev_example,)
    # Les apostrophes TOML gardent les « \ » de Windows tels quels
    assert str(cfg.root) == r"X:\Musique"
    assert cfg.true_peak_oversampling == 8
    assert cfg.references.purchase_sheets is not None and cfg.references.audit is not None
    # Dossiers système déduits de la racine
    assert cfg.output.name == "_data" and cfg.logs.name == "_log"
    assert cfg.db.name == "_base" and cfg.db.parent == cfg.output
    assert cfg.reports.name == "_reports" and cfg.trash.name == "_to_delete"
    assert cfg.bot.name == "_bot" and cfg.incoming.name == "_sort"
    assert cfg.reference_lufs == -18.0
    # L'exemple n'ajoute aucune catégorie : celles par défaut seulement
    assert len(cfg.categories) == 7


def test_prod_example_changes_nothing(prod_example, tmp_path):
    """L'exemple de production, entièrement commenté, donne exactement le défaut."""
    bot = tmp_path / "Musique" / "_bot"
    bot.mkdir(parents=True)
    shutil.copy(prod_example, bot / "config.toml")
    cfg = config.load(bot / "config.toml")
    expected = config.from_dict({"paths": {"root": str(tmp_path / "Musique")}})
    assert cfg.root == tmp_path / "Musique"
    assert cfg.categories == expected.categories
    assert (cfg.reference_lufs, cfg.true_peak_oversampling, cfg.workers) == (
        expected.reference_lufs,
        expected.true_peak_oversampling,
        expected.workers,
    )
    assert cfg.origins == {"paths.root": config.ORIGIN_DERIVED}  # aucune clé écrite


def test_default_categories():
    cfg = config.from_dict({"paths": {"root": "M"}})
    assert cfg.category("Artists").pages and cfg.category("Artists").rg_album
    # Bulk : pas de pages, ReplayGain piste seulement
    c = cfg.category("Bulk")
    assert c.type == "bulk" and not c.pages and not c.rg_album
    assert cfg.category("_data").type == "ignore"  # dossier système implicite
    assert cfg.category("Inconnu") is None


def test_db_and_cache_default_paths():
    cfg = config.from_dict({"paths": {"root": "M", "output": "S"}})
    assert cfg.db.as_posix() == "S/_base" and cfg.cache.as_posix() == "S/_cache"
    assert cfg.logs.as_posix() == "M/_log"
    assert cfg.references.audit is None
    assert cfg.ffmpeg == "ffmpeg"
    assert cfg.reference_lufs == -18.0 and len(cfg.categories) == 7  # défaut


def test_unknown_type_rejected():
    with pytest.raises(config.ConfigError, match="Type inconnu"):
        config.from_dict(
            {"paths": {"root": "M"}, "categories": {"X": {"type": "nimporte"}}},
        )


def test_missing_root():
    with pytest.raises(config.RootNotFound, match="root"):
        config.from_dict({"paths": {"output": "S"}})


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        # Ancienne section : le message donne la nouvelle et les clés renommées
        ({"chemins": {"racine": "M"}}, r"\[chemins\] s'appelle désormais \[paths\].*racine → root"),
        ({"outils": {"ffmpeg": "f"}}, r"\[outils\] s'appelle désormais \[tools\]"),
        ({"analyse": {"processus": 2}}, r"\[analysis\].*processus → workers"),
        # Ancienne clé dans une section au nouveau nom
        ({"paths": {"root": "M", "base": "B"}}, r"\[paths\] base s'appelle désormais db"),
        ({"references": {"fiches_achat": "F"}}, "purchase_sheets"),
        # Ancien type de catégorie
        ({"categories": {"X": {"type": "vrac"}}}, "'vrac' s'appelle désormais 'bulk'"),
        # Sections retirées
        ({"dap": {"destination": "D"}}, r"\[dap\] n'est plus lue"),
        ({"sauvegarde": {"destination": "S"}}, r"\[sauvegarde\] n'est plus lue"),
    ],
)
def test_old_names_rejected(written, expected):
    with pytest.raises(config.ConfigError, match=expected):
        config.from_dict({"paths": {"root": "M"}} | written)


def test_old_section_reported_before_missing_root(tmp_path):
    """Une racine écrite sous l'ancienne section est signalée comme telle, pas comme absente."""
    f = tmp_path / "config.toml"
    f.write_text("[chemins]\nracine = 'M'\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match=r"\[chemins\] s'appelle désormais \[paths\]"):
        config.load(f)


CATEGORIES = '[categories."Mon Ajout"]\ntype = "projects"\npages = true\n'


def test_root_derived_from_bot(tmp_path):
    """Production : <racine>/_bot/config.toml, sans clé root."""
    bot = tmp_path / "Musique" / "_bot"
    bot.mkdir(parents=True)
    (bot / "config.toml").write_text(CATEGORIES, encoding="utf-8")
    cfg = config.load(bot / "config.toml")
    assert cfg.root == tmp_path / "Musique" and cfg.bot == bot
    assert cfg.output == tmp_path / "Musique" / "_data"


def test_clone_config_overrides_bot_config(tmp_path):
    """Développement : le clone ne donne que la racine, le reste vient de _bot."""
    sandbox = tmp_path / "Sandbox"
    (sandbox / "_bot").mkdir(parents=True)
    (sandbox / "_bot" / "config.toml").write_text(CATEGORIES + '[tools]\nffmpeg = "E"\nfpcalc = "F"\n', encoding="utf-8")
    clone = tmp_path / "clone" / "config.toml"
    clone.parent.mkdir()
    clone.write_text(f"[paths]\nroot = '{sandbox}'\n[tools]\nfpcalc = 'G'\n", encoding="utf-8")
    cfg = config.load(clone)
    assert cfg.root == sandbox
    assert cfg.sources == (sandbox / "_bot" / "config.toml", clone)
    assert cfg.ffmpeg == "E"  # lu dans _bot
    assert cfg.fpcalc == "G"  # le clone l'emporte
    assert "Mon Ajout" in cfg.categories and "Artists" in cfg.categories
    # Origine de chaque valeur
    assert cfg.origin("paths.root") == config.ORIGIN_CLONE
    assert cfg.origin("tools.ffmpeg") == config.ORIGIN_BOT
    assert cfg.origin("tools.fpcalc") == config.ORIGIN_CLONE
    assert cfg.origin("categories.Mon Ajout") == config.ORIGIN_BOT
    assert cfg.origin("categories.Artists") == config.ORIGIN_DEFAULT
    assert cfg.origin("paths.output") == config.ORIGIN_DERIVED


def test_old_names_in_bot_config_rejected(tmp_path):
    """Un ancien nom dans le _bot/config.toml lu en dessous du clone est aussi signalé."""
    sandbox = tmp_path / "Sandbox"
    (sandbox / "_bot").mkdir(parents=True)
    (sandbox / "_bot" / "config.toml").write_text('[dap]\ndestination = "D"\n', encoding="utf-8")
    clone = tmp_path / "config.toml"
    clone.write_text(f"[paths]\nroot = '{sandbox}'\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match=r"\[dap\] n'est plus lue"):
        config.load(clone)


def test_config_next_to_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    bot = tmp_path / "_bot"
    bot.mkdir()
    (bot / "config.toml").write_text(CATEGORIES, encoding="utf-8")
    monkeypatch.setattr(config, "environment_dir", lambda: bot)
    assert config.find() == bot / "config.toml"


def _no_file(tmp_path, monkeypatch, program):
    """Aucun config.toml nulle part ; le programme tourne depuis `program`."""
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(config, "program_dir", lambda: program)


def test_no_file_found(tmp_path, monkeypatch):
    _no_file(tmp_path, monkeypatch, None)
    assert config.find() is None


def test_explicit_file_missing(tmp_path):
    with pytest.raises(config.ConfigError, match="introuvable"):
        config.find(tmp_path / "rien.toml")


def test_no_config_from_bot(tmp_path, monkeypatch):
    """Production sans config.toml : racine déduite de _bot, configuration par défaut."""
    _no_file(tmp_path, monkeypatch, tmp_path / "Musique" / "_bot")
    cfg = config.load()
    assert cfg.root == tmp_path / "Musique" and cfg.sources == ()
    assert set(cfg.categories) == {
        "Artists",
        "Classical music",
        "Compilations",
        "Musicals",
        "Soundtrack",
        "Bulk",
        "_sort",
    }
    assert not cfg.category("Bulk").rg_album and cfg.category("_sort").type == "incoming"
    assert cfg.origin("paths.root") == config.ORIGIN_DERIVED
    assert cfg.origin("categories.Bulk") == config.ORIGIN_DEFAULT


def test_no_config_outside_bot(tmp_path, monkeypatch):
    """Ni config ni programme dans _bot : la racine est introuvable."""
    _no_file(tmp_path, monkeypatch, tmp_path / "clone")
    with pytest.raises(config.RootNotFound, match="Racine introuvable"):
        config.load()


def test_partial_category_override(tmp_path):
    """Une clé redéfinie garde les autres clés du défaut ; « ignore » retire la catégorie."""
    bot = tmp_path / "_bot"
    bot.mkdir()
    (bot / "config.toml").write_text(
        '[categories.Soundtrack]\npages = false\n[categories.Musicals]\ntype = "ignore"\n',
        encoding="utf-8",
    )
    cfg = config.load(bot / "config.toml")
    st = cfg.category("Soundtrack")
    assert st.type == "projects" and not st.pages and st.rg_album
    assert cfg.origin("categories.Soundtrack") == config.ORIGIN_BOT
    assert cfg.origin("categories.Soundtrack.type") == config.ORIGIN_DEFAULT
    mu = cfg.category("Musicals")
    assert mu.type == "ignore" and not mu.pages and not mu.rg_album


def test_environment_variable(dev_example, monkeypatch):
    monkeypatch.setenv("DISCO_CONFIG", str(dev_example))
    assert config.find() == dev_example


def test_tools_in_bot_tools(tmp_path):
    """Sans chemin dans [tools], un outil posé dans <bot>/tools est utilisé ; sinon le PATH."""
    tools = tmp_path / "_bot" / "tools"
    tools.mkdir(parents=True)
    name = "fpcalc.exe" if os.name == "nt" else "fpcalc"
    (tools / name).write_bytes(b"")
    d = {"paths": {"root": str(tmp_path)}, "categories": {"A": {"type": "artists"}}}
    cfg = config.from_dict(d)
    assert cfg.fpcalc == str(tools / name)
    assert cfg.ffmpeg == "ffmpeg"  # absent de tools : PATH
    d["tools"] = {"fpcalc": "autre"}
    assert config.from_dict(d).fpcalc == "autre"  # la config l'emporte
