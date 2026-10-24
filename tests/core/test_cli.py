"""
test_cli.py - Tests de la ligne de commande

Description:
    Tests de « disco config » : affichage de la configuration et de l'origine
    de chaque valeur, configuration absente, configuration par défaut seule ; et de
    « disco purge » (journal, rapport, lots signalés).

Auteur :
    Claude (Anthropic)

Version :
    2.1

Date de création :
    2026.10.06

Date de modification :
    2026.10.24
"""

import datetime as dt

from src.backend import config, trash
from src.core.cli import main


def test_config(dev_example, capsys):
    assert main(["--config", str(dev_example), "config"]) == 0
    out = capsys.readouterr().out
    assert "Classical music" in out
    assert "vraie x8" in out
    # Origine de chaque valeur
    assert r"Racine    : X:\Musique  [clone]" in out
    assert "[défaut]" in out and "[déduit]" in out


def test_config_missing(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "rien.toml"), "config"]) == 2


def test_config_without_file(tmp_path, monkeypatch, capsys):
    """Programme lancé depuis <racine>/_bot sans aucun config.toml : configuration par défaut."""
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(config, "program_dir", lambda: tmp_path / "_bot")
    assert main(["config"]) == 0
    assert "aucun (configuration par défaut)" in capsys.readouterr().out


def test_purge(tmp_path, capsys):
    """« disco purge » : lot ancien purgé, lot inconnu signalé, journal et rapport écrits."""
    root = tmp_path / "Musique"
    f = root / "Bulk" / "piste.flac"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f"[paths]\nroot = '{root}'\n[trash]\nretention_days = 30\n", encoding="utf-8")
    cfg = config.load(cfg_file)
    trash.put([f], root, cfg.trash, cfg.logs, "ancien", "essai", lambda m: None, dt.datetime(2020, 1, 1))
    assert main(["--config", str(cfg_file), "purge"]) == 0
    assert not (cfg.trash / "ancien").exists()
    (cfg.trash / "inconnu").mkdir()
    assert main(["--config", str(cfg_file), "purge"]) == 1
    reports = sorted(cfg.reports.glob("*_purge.md"))
    assert reports and "inconnu" in reports[-1].read_text(encoding="utf-8")
    assert list(cfg.logs.glob("*_purge.log"))
    capsys.readouterr()
