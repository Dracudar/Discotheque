"""
test_versions.py - Tests du fichier des versions

Description:
    Vérifie que `src/assets/versions.toml` est bien la seule source de la version du
    programme : format majeur.mineur.correctif, lue par `src.__versions__`, reprise
    par l'installation (métadonnées du paquet) et par « disco --version ».

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.09
"""

import re
from importlib import metadata

from src import __versions__
from src.core.cli import main

# majeur.mineur.correctif, avec un suffixe éventuel (« .dev0 », « rc1 »…)
FORMAT = re.compile(r"^\d+\.\d+\.\d+(\S*)$")


def test_version_format():
    assert FORMAT.match(__versions__.__version__)


def test_read_from_toml(tmp_path):
    f = tmp_path / "versions.toml"
    f.write_text('[program]\nversion = "9.8.7"\n', encoding="utf-8")
    assert __versions__.read(f)["program"]["version"] == "9.8.7"
    assert __versions__.read()["program"]["version"] == __versions__.__version__


def test_same_version_when_installed():
    assert metadata.version("discotheque") == __versions__.__version__


def test_disco_version(capsys):
    try:
        main(["--version"])
    except SystemExit:
        pass
    assert capsys.readouterr().out.strip() == f"disco {__versions__.__version__}"
