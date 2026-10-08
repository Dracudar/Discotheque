"""
test_entetes.py - Garde-fou des en-têtes et docstrings

Description:
    Garde-fou : chaque fichier Python de `src/disco` et de `tests` porte son en-tête, et
    chaque module de `src/disco` documente ses fonctions et ses classes.

    L'en-tête suit le modèle commun aux projets de Dracudar : nom du fichier et titre,
    puis les rubriques Description, Auteur, Version, Date de création et Date de
    modification (dates au format aaaa.mm.jj). La version est propre au fichier, au format
    majeur.mineur, distincte de celle du programme (majeur.mineur.correctif).

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.07

Date de modification :
    2026.10.08
"""

import ast
import re
from pathlib import Path

import pytest

DEPOT = Path(__file__).resolve().parents[1]
MODULES = sorted((DEPOT / "src" / "disco").glob("*.py"))
TESTS = sorted((DEPOT / "tests").glob("*.py"))
RUBRIQUES = (
    "Description:",
    "Auteur :",
    "Version :",
    "Date de création :",
    "Date de modification :",
)
DATE = re.compile(r"^\s+\d{4}\.\d{2}\.\d{2}$", re.MULTILINE)
VERSION = re.compile(r"\nVersion :\n\s+\d+\.\d+\n")


@pytest.mark.parametrize("module", MODULES + TESTS, ids=lambda p: p.relative_to(DEPOT).as_posix())
def test_entete(module):
    doc = ast.get_docstring(ast.parse(module.read_text(encoding="utf-8")), clean=False)
    assert doc, f"{module.name} : en-tête absent"
    assert doc.lstrip("\n").startswith(f"{module.name} - "), "première ligne : « nom - titre »"
    for rubrique in RUBRIQUES:
        assert f"\n{rubrique}\n" in doc, f"{module.name} : rubrique « {rubrique} » absente"
    assert len(DATE.findall(doc)) == 2, f"{module.name} : dates au format aaaa.mm.jj"
    assert VERSION.search(doc), f"{module.name} : version du fichier au format majeur.mineur"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_docstrings(module):
    arbre = ast.parse(module.read_text(encoding="utf-8"))
    sans = [
        n.name
        for n in ast.walk(arbre)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and not ast.get_docstring(n)
    ]
    assert not sans, f"{module.name} : sans docstring : {', '.join(sans)}"
