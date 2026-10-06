import os
import shutil

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


# En CI (variable CI définie par GitHub Actions), les outils doivent être présents :
# le test ne peut pas être sauté, sinon la vérification sous Windows serait silencieuse.
@pytest.mark.skipif(
    not os.environ.get("CI") and not (shutil.which("ffmpeg") and shutil.which("fpcalc")),
    reason="ffmpeg ou fpcalc absent",
)
def test_fpcalc_entree_standard():
    r = doctor.verifier_fpcalc_entree_standard("ffmpeg", "fpcalc")
    assert r.statut == doctor.OK, r.detail


def test_config_dossiers(tmp_path):
    (tmp_path / "Artists").mkdir()
    (tmp_path / "Divers").mkdir()
    cfg = config.depuis_dict(
        {
            "chemins": {"racine": str(tmp_path), "sortie": str(tmp_path / "_data")},
            "categories": {"Artists": {"type": "artistes"}},
        },
        source=tmp_path / "config.toml",
    )
    res = {r.nom: r for r in doctor.verifier_config(cfg)}
    assert res["Racine"].statut == doctor.ATTENTION
    assert "Divers" in res["Racine"].detail
    assert "sera créé" in res["Dossier de sortie"].detail


def test_diagnostic_sans_config(capsys):
    res = doctor.diagnostic(None, "absente")
    code = doctor.afficher(res)
    assert code in (0, 1)
    assert "Configuration" in capsys.readouterr().out
