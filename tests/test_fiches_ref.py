"""Fiches d'achat : format et ancien gabarit.

- En CI : une fiche **fictive** (`fixtures/fiche_fictive.json`), aucune donnée réelle.
- Sur le PC : les fiches réelles, lues **hors du dépôt**, dans le dossier indiqué par la
  variable d'environnement DISCO_FICHES_REF ou, à défaut, par `[references] fiches_achat`
  de config.toml. Elles serviront de jeu de validation au jalon 4.1. Sans l'un ou l'autre,
  ces tests sont sautés.
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

CLES = {"artiste", "dossier_discotheque", "name", "h1", "sub", "recap", "l1note", "l1", "l3"}
CLES |= {"points"}


@pytest.fixture(scope="module")
def gen(request):
    racine = request.config.rootpath
    spec = importlib.util.spec_from_file_location("gen", racine / "legacy" / "fiches" / "gen.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def fiche_fictive(racine) -> dict:
    return json.loads((racine / "tests" / "fixtures" / "fiche_fictive.json").read_text("utf-8"))


def pastilles(d: dict) -> list:
    """Toutes les valeurs de pastilles d'une fiche (colonnes Discothèque et Qualité dispo)."""
    vals = [v for r in d["l1"] for v in (r[4], r[5])]
    vals += [v for r in d.get("l1b", []) for v in (r[3], r[4])]
    vals += [r[3] for r in d.get("l2", [])] + [r[4] for r in d["l3"]]
    return [v for v in vals if v is not None]


def verifier_fiche(d: dict, codes_permis: set, nom: str) -> None:
    assert CLES <= set(d), f"{nom} : clés manquantes {CLES - set(d)}"
    for p in pastilles(d):
        codes = p if isinstance(p, list) else str(p).split("+")
        assert set(codes) <= codes_permis, f"{nom} : pastille inconnue {p}"


def test_fiche_fictive(fiche_fictive, gen):
    verifier_fiche(fiche_fictive, set(gen.P), "fiche fictive")
    html = gen.build(fiche_fictive)
    assert "<title>Discothèque : Les Exemples</title>" in html
    for section in ("Liste d'achat", "Bandes originales", "Sorties écartées", "Points à vérifier"):
        assert section in html
    # Pastilles cumulées : CD + Lossy + Partiel sur la même ligne
    assert 'class="pill cd"' in html and 'class="pill pa"' in html


def _dossier_reel() -> str | None:
    if os.environ.get("DISCO_FICHES_REF"):
        return os.environ["DISCO_FICHES_REF"]
    try:
        from disco.config import charger

        dossier = charger().references.fiches_achat
    except Exception:
        return None
    return str(dossier) if dossier and dossier.is_dir() else None


DOSSIER_REEL = _dossier_reel()


@pytest.mark.skipif(not DOSSIER_REEL, reason="fiches réelles non configurées (tests locaux)")
def test_fiches_reelles(gen):
    dossier = Path(DOSSIER_REEL)
    fiches = sorted(dossier.glob("*/recap.json"))
    assert fiches, f"aucune fiche recap.json dans {dossier}"
    for f in fiches:
        d = json.loads(f.read_text(encoding="utf-8"))
        verifier_fiche(d, set(gen.P), f.parent.name)
        assert "<title>Discothèque :" in gen.build(d)
