"""
test_headers.py - Garde-fou des en-têtes et docstrings

Description:
    Garde-fou : chaque fichier Python de `src` et de `tests` (sous-dossiers compris) porte
    son en-tête, et chaque module de `src` documente ses fonctions et ses classes.

    L'en-tête suit le modèle commun aux projets de Dracudar : nom du fichier et titre,
    puis les rubriques Description, Auteur, Version, Date de création et Date de
    modification (dates au format aaaa.mm.jj). La version est propre au fichier, au format
    majeur.mineur, distincte de celle du programme (majeur.mineur.correctif).

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.07

Date de modification :
    2026.10.09
"""

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES = sorted((REPO_ROOT / "src").rglob("*.py"))
TESTS = sorted((REPO_ROOT / "tests").rglob("*.py"))
SECTIONS = (
    "Description:",
    "Auteur :",
    "Version :",
    "Date de création :",
    "Date de modification :",
)
DATE = re.compile(r"^\s+\d{4}\.\d{2}\.\d{2}$", re.MULTILINE)
VERSION = re.compile(r"\nVersion :\n\s+\d+\.\d+\n")


@pytest.mark.parametrize(
    "module", MODULES + TESTS, ids=lambda p: p.relative_to(REPO_ROOT).as_posix()
)
def test_header(module):
    doc = ast.get_docstring(ast.parse(module.read_text(encoding="utf-8")), clean=False)
    assert doc, f"{module.name} : en-tête absent"
    assert doc.lstrip("\n").startswith(f"{module.name} - "), "première ligne : « nom - titre »"
    for section in SECTIONS:
        assert f"\n{section}\n" in doc, f"{module.name} : rubrique « {section} » absente"
    assert len(DATE.findall(doc)) == 2, f"{module.name} : dates au format aaaa.mm.jj"
    assert VERSION.search(doc), f"{module.name} : version du fichier au format majeur.mineur"


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_docstrings(module):
    tree = ast.parse(module.read_text(encoding="utf-8"))
    missing = [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and not ast.get_docstring(n)
    ]
    assert not missing, f"{module.name} : sans docstring : {', '.join(missing)}"
