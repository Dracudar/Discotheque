"""
conftest.py - Fixtures communes

Description:
    Fixtures communes aux tests : racine du dépôt et exemples de configuration
    (production, livré avec le programme ; développement, à la racine du dépôt).

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    """Racine du dépôt."""
    return REPO_ROOT


@pytest.fixture
def dev_example(repo_root) -> Path:
    """Exemple de configuration de développement (modèle du config.toml du clone)."""
    return repo_root / "config.dev_example.toml"


@pytest.fixture
def prod_example(repo_root) -> Path:
    """Exemple de configuration de production, livré avec le programme (tout commenté)."""
    return repo_root / "src" / "assets" / "config.example.toml"
