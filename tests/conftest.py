"""
conftest.py - Fixtures communes

Description:
    Fixtures communes aux tests.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.08
"""

from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture
def racine() -> Path:
    return RACINE


@pytest.fixture
def config_exemple(racine) -> Path:
    return racine / "config.example.toml"


@pytest.fixture
def fiches_ref(racine) -> Path:
    return racine / "tests" / "fixtures" / "fiches_ref"
