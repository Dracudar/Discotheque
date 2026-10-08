"""
test_cli.py - Tests de la ligne de commande

Description:
    Tests de « disco config » : affichage de la configuration et de l'origine
    de chaque valeur, configuration absente, configuration par défaut seule.

Auteur :
    Dracudar

Version :
    1.1

Date de création :
    2026.10.06

Date de modification :
    2026.10.08
"""

from src.backend import config
from src.core.cli import main


def test_config(config_exemple, capsys):
    assert main(["--config", str(config_exemple), "config"]) == 0
    sortie = capsys.readouterr().out
    assert "Classical music" in sortie
    assert "vraie x8" in sortie
    # Origine de chaque valeur
    assert r"Racine    : X:\Musique  [clone]" in sortie
    assert "[défaut]" in sortie and "[déduit]" in sortie


def test_config_absente(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "rien.toml"), "config"]) == 2


def test_config_sans_fichier(tmp_path, monkeypatch, capsys):
    """Programme lancé depuis <racine>/_bot sans aucun config.toml : configuration par défaut."""
    monkeypatch.delenv("DISCO_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config, "RACINE_DEPOT", tmp_path)
    monkeypatch.setattr(config, "dossier_programme", lambda: tmp_path / "_bot")
    assert main(["config"]) == 0
    assert "aucun (configuration par défaut)" in capsys.readouterr().out
