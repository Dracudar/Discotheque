"""Fixtures communes aux tests."""

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
