"""
test_cli.py - Tests de la ligne de commande

Description:
    Tests de « disco config » : affichage de la configuration et de l'origine
    de chaque valeur, configuration absente, configuration par défaut seule.

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
"""

from src.backend import config
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
