"""
test_purchase_sheets.py - Tests des fiches d'achat

Description:
    Fiches d'achat : format et ancien gabarit.

    - En CI : une fiche **fictive** (`fixtures/fiche_fictive.json`), aucune donnée réelle.
    - Sur le PC : les fiches réelles, lues **hors du dépôt**, dans le dossier indiqué par la
      variable d'environnement DISCO_PURCHASE_SHEETS ou, à défaut, par
      `[references] purchase_sheets`
      de config.toml. Elles serviront de jeu de validation au jalon 4.1. Sans l'un ou l'autre,
      ces tests sont sautés.

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

KEYS = {"artiste", "dossier_discotheque", "name", "h1", "sub", "recap", "l1note", "l1", "l3"}
KEYS |= {"points"}


@pytest.fixture(scope="module")
def gen(request):
    """Ancien générateur des fiches (`legacy/fiches/gen.py`), chargé comme module."""
    repo_root = request.config.rootpath
    spec = importlib.util.spec_from_file_location("gen", repo_root / "legacy" / "fiches" / "gen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def fake_sheet(repo_root) -> dict:
    """Fiche fictive des tests (`tests/fixtures/fiche_fictive.json`)."""
    return json.loads((repo_root / "tests" / "fixtures" / "fiche_fictive.json").read_text("utf-8"))


def pills(d: dict) -> list:
    """Toutes les valeurs de pastilles d'une fiche (colonnes Discothèque et Qualité dispo)."""
    vals = [v for r in d["l1"] for v in (r[4], r[5])]
    vals += [v for r in d.get("l1b", []) for v in (r[3], r[4])]
    vals += [r[3] for r in d.get("l2", [])] + [r[4] for r in d["l3"]]
    return [v for v in vals if v is not None]


def check_sheet(d: dict, allowed_codes: set, name: str) -> None:
    """Vérifie les clés d'une fiche et les codes de ses pastilles."""
    assert KEYS <= set(d), f"{name} : clés manquantes {KEYS - set(d)}"
    for p in pills(d):
        codes = p if isinstance(p, list) else str(p).split("+")
        assert set(codes) <= allowed_codes, f"{name} : pastille inconnue {p}"


def test_fake_sheet(fake_sheet, gen):
    check_sheet(fake_sheet, set(gen.P), "fiche fictive")
    html = gen.build(fake_sheet)
    assert "<title>Discothèque : Les Exemples</title>" in html
    for section in ("Liste d'achat", "Bandes originales", "Sorties écartées", "Points à vérifier"):
        assert section in html
    # Pastilles cumulées : CD + Lossy + Partiel sur la même ligne
    assert 'class="pill cd"' in html and 'class="pill pa"' in html


def _real_folder() -> str | None:
    """Dossier des fiches réelles (hors dépôt), ou None s'il n'est pas configuré."""
    if os.environ.get("DISCO_PURCHASE_SHEETS"):
        return os.environ["DISCO_PURCHASE_SHEETS"]
    try:
        from src.backend.config import load

        folder = load().references.purchase_sheets
    except Exception:
        return None
    return str(folder) if folder and folder.is_dir() else None


REAL_FOLDER = _real_folder()


@pytest.mark.skipif(not REAL_FOLDER, reason="fiches réelles non configurées (tests locaux)")
def test_real_sheets(gen):
    folder = Path(REAL_FOLDER)
    sheets = sorted(folder.glob("*/recap.json"))
    assert sheets, f"aucune fiche recap.json dans {folder}"
    for f in sheets:
        d = json.loads(f.read_text(encoding="utf-8"))
        check_sheet(d, set(gen.P), f.parent.name)
        assert "<title>Discothèque :" in gen.build(d)
