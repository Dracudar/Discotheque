"""
test_doctor.py - Tests du diagnostic

Description:
    Tests de « disco doctor » : Python et modules, fonctions SQLite, outils
    externes, fpcalc sur l'entrée standard, chemins de la configuration,
    diagnostic sans configuration ou avec une configuration cassée.

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

import pytest

from src.backend import config
from src.core import doctor


def test_python_and_modules():
    assert doctor.check_python().status == doctor.OK
    assert all(r.status == doctor.OK for r in doctor.check_modules())


def test_sqlite_features():
    available = doctor.sqlite_features()
    assert set(available) == {"FTS5", "JSON", "UPSERT", "RETURNING", "STRICT"}
    assert available["JSON"] and available["UPSERT"]


def test_missing_tool():
    r = doctor.check_tool("bidon", "outil-qui-n-existe-pas-12345")
    assert r.status == doctor.ERROR


def _tools() -> tuple[str, str]:
    """ffmpeg et fpcalc tels que la configuration les trouve (`_bot/tools`, `[tools]`),
    sinon par leur nom dans le PATH (cas de la CI, sans config)."""
    try:
        cfg = config.load()
    except config.ConfigError:
        return "ffmpeg", "fpcalc"
    return cfg.ffmpeg, cfg.fpcalc


FFMPEG, FPCALC = _tools()


# En CI (variable CI définie par GitHub Actions), les outils doivent être présents :
# le test ne peut pas être sauté, sinon la vérification sous Windows serait silencieuse.
@pytest.mark.skipif(
    not os.environ.get("CI") and not (doctor.locate(FFMPEG) and doctor.locate(FPCALC)),
    reason="ffmpeg ou fpcalc absent",
)
def test_fpcalc_stdin():
    r = doctor.check_fpcalc_stdin(FFMPEG, FPCALC)
    assert r.status == doctor.OK, r.detail


def test_config_folders(tmp_path):
    (tmp_path / "Artists").mkdir()
    (tmp_path / "Divers").mkdir()
    cfg = config.from_dict(
        {
            "paths": {"root": str(tmp_path), "output": str(tmp_path / "_data")},
            "categories": {"Artists": {"type": "artists"}},
        },
        sources=(tmp_path / "config.toml",),
    )
    res = {r.name: r for r in doctor.check_config(cfg)}
    assert res["Racine"].status == doctor.WARNING
    assert "Divers" in res["Racine"].detail
    assert "sera créé" in res["Dossier de sortie"].detail


def test_diagnose_without_config(capsys):
    res = doctor.diagnose(None, config.RootNotFound("Racine introuvable"))
    code = doctor.show(res)
    assert code in (0, 1)
    assert "Configuration" in capsys.readouterr().out
    # Racine introuvable (clone neuf, CI) : attention, pas erreur bloquante
    assert res[-1].status == doctor.WARNING


def test_diagnose_broken_config():
    res = doctor.diagnose(None, config.ConfigError("TOML invalide"))
    assert res[-1].status == doctor.ERROR


def test_config_files_read(tmp_path):
    """La ligne « Configuration » liste tous les fichiers lus, ou le défaut seul."""
    d = {"paths": {"root": str(tmp_path)}}
    a, b = tmp_path / "_bot" / "config.toml", tmp_path / "clone" / "config.toml"
    res = doctor.check_config(config.from_dict(d, sources=(a, b)))
    assert res[0].status == doctor.OK and str(a) in res[0].detail and str(b) in res[0].detail
    res = doctor.check_config(config.from_dict(d))
    assert res[0].status == doctor.OK and "par défaut" in res[0].detail
