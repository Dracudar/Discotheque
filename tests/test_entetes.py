"""Garde-fou : chaque module de `src/disco` porte son en-tête et documente ses fonctions.

L'en-tête suit le modèle commun aux projets de Dracudar : nom du fichier et titre,
puis les rubriques Description, Auteur, Version, Date de création et Date de
modification (dates au format aaaa.mm.jj).
"""

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "disco"
MODULES = sorted(SRC.glob("*.py"))
RUBRIQUES = (
    "Description:",
    "Auteur :",
    "Version :",
    "Date de création :",
    "Date de modification :",
)
DATE = re.compile(r"^\s+\d{4}\.\d{2}\.\d{2}$", re.MULTILINE)


@pytest.mark.parametrize("module", MODULES, ids=lambda p: p.name)
def test_entete(module):
    doc = ast.get_docstring(ast.parse(module.read_text(encoding="utf-8")), clean=False)
    assert doc, f"{module.name} : en-tête absent"
    assert doc.lstrip("\n").startswith(f"{module.name} - "), "première ligne : « nom - titre »"
    for rubrique in RUBRIQUES:
        assert f"\n{rubrique}\n" in doc, f"{module.name} : rubrique « {rubrique} » absente"
    assert len(DATE.findall(doc)) == 2, f"{module.name} : dates au format aaaa.mm.jj"


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
