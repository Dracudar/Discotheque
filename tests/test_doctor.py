"""
test_doctor.py - Tests du diagnostic

Description:
    Tests de « disco doctor » : Python et modules, fonctions SQLite, outils
    externes, fpcalc sur l'entrée standard, chemins de la configuration,
    diagnostic sans configuration ou avec une configuration cassée.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.08
"""

import os

import pytest

from disco import config, doctor


def test_python_et_modules():
    assert doctor.verifier_python().statut == doctor.OK
    assert all(r.statut == doctor.OK for r in doctor.verifier_modules())


def test_fonctions_sqlite():
    dispo = doctor.fonctions_sqlite()
    assert set(dispo) == {"FTS5", "JSON", "UPSERT", "RETURNING", "STRICT"}
    assert dispo["JSON"] and dispo["UPSERT"]


def test_outil_absent():
    r = doctor.verifier_outil("bidon", "outil-qui-n-existe-pas-12345")
    assert r.statut == doctor.ERREUR


def _outils() -> tuple[str, str]:
    """ffmpeg et fpcalc tels que la configuration les trouve (`_bot/tools`, `[outils]`),
    sinon par leur nom dans le PATH (cas de la CI, sans config)."""
    try:
        cfg = config.charger()
    except config.ErreurConfig:
        return "ffmpeg", "fpcalc"
    return cfg.ffmpeg, cfg.fpcalc


FFMPEG, FPCALC = _outils()


# En CI (variable CI définie par GitHub Actions), les outils doivent être présents :
# le test ne peut pas être sauté, sinon la vérification sous Windows serait silencieuse.
@pytest.mark.skipif(
    not os.environ.get("CI") and not (doctor.localiser(FFMPEG) and doctor.localiser(FPCALC)),
    reason="ffmpeg ou fpcalc absent",
)
def test_fpcalc_entree_standard():
    r = doctor.verifier_fpcalc_entree_standard(FFMPEG, FPCALC)
    assert r.statut == doctor.OK, r.detail


def test_config_dossiers(tmp_path):
    (tmp_path / "Artists").mkdir()
    (tmp_path / "Divers").mkdir()
    cfg = config.depuis_dict(
        {
            "chemins": {"racine": str(tmp_path), "sortie": str(tmp_path / "_data")},
            "categories": {"Artists": {"type": "artistes"}},
        },
        sources=(tmp_path / "config.toml",),
    )
    res = {r.nom: r for r in doctor.verifier_config(cfg)}
    assert res["Racine"].statut == doctor.ATTENTION
    assert "Divers" in res["Racine"].detail
    assert "sera créé" in res["Dossier de sortie"].detail


def test_diagnostic_sans_config(capsys):
    res = doctor.diagnostic(None, config.RacineIntrouvable("Racine introuvable"))
    code = doctor.afficher(res)
    assert code in (0, 1)
    assert "Configuration" in capsys.readouterr().out
    # Racine introuvable (clone neuf, CI) : attention, pas erreur bloquante
    assert res[-1].statut == doctor.ATTENTION


def test_diagnostic_config_cassee():
    res = doctor.diagnostic(None, config.ErreurConfig("TOML invalide"))
    assert res[-1].statut == doctor.ERREUR


def test_config_fichiers_lus(tmp_path):
    """La ligne « Configuration » liste tous les fichiers lus, ou le défaut seul."""
    d = {"chemins": {"racine": str(tmp_path)}}
    a, b = tmp_path / "_bot" / "config.toml", tmp_path / "clone" / "config.toml"
    res = doctor.verifier_config(config.depuis_dict(d, sources=(a, b)))
    assert res[0].statut == doctor.OK and str(a) in res[0].detail and str(b) in res[0].detail
    res = doctor.verifier_config(config.depuis_dict(d))
    assert res[0].statut == doctor.OK and "par défaut" in res[0].detail
