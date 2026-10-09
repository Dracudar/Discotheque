"""
test_clean_repo.py - Garde-fou du dépôt public

Description:
    Garde-fou : aucune donnée de la discothèque ne doit entrer dans le dépôt.

    Le dépôt ne contient que du code, des tests sur données fictives et de la
    documentation de mise en place. Ce test échoue si un fichier suivi par Git
    ressemble à une donnée réelle (fiche, index, paroles, audio, journal…).

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.09
"""

import re
import subprocess
from pathlib import PurePosixPath

import pytest

FORBIDDEN_EXT = {
    ".flac",
    ".mp3",
    ".m4a",
    ".opus",
    ".ogg",
    ".wav",
    ".aif",
    ".aiff",  # audio
    ".lrc",  # paroles
    ".sqlite",
    ".db",
    ".jsonl",
    ".csv",
    ".xlsx",
    ".log",  # index, scans, journaux
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",  # pochettes, spectrogrammes
}
FORBIDDEN_NAMES = {"recap.json", "recap.html", "registry.json", "artists.txt", "config.toml"}
ALLOWED = {"tests/fixtures/fiche_fictive.json"}


def tracked_files(repo_root) -> list[str]:
    """Fichiers suivis par Git (le test est sauté hors d'un dépôt Git)."""
    try:
        r = subprocess.run(["git", "ls-files"], cwd=repo_root, capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("git absent")
    if r.returncode != 0:
        pytest.skip("pas un dépôt Git")
    return r.stdout.splitlines()


def test_no_real_data(repo_root):
    culprits = []
    for f in tracked_files(repo_root):
        p = PurePosixPath(f)
        if f in ALLOWED:
            continue
        if p.suffix.lower() in FORBIDDEN_EXT or p.name in FORBIDDEN_NAMES:
            culprits.append(f)
    assert not culprits, "Données de la discothèque dans le dépôt : " + ", ".join(culprits)


# Chemins absolus Windows : seul le lecteur fictif X: est permis (exemples de configuration).
DRIVE = re.compile(r"(?<![A-Za-z0-9])([A-WYZ]):" + re.escape("\\"))
TEXT_EXT = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".txt",
    ".ps1",
    ".sh",
    ".html",
    ".json",
    ".cfg",
    ".cmd",
}


def test_no_local_path(repo_root):
    culprits = []
    for f in tracked_files(repo_root):
        if PurePosixPath(f).suffix.lower() not in TEXT_EXT:
            continue
        text = (repo_root / f).read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if DRIVE.search(line):
                culprits.append(f"{f}:{n}")
    assert not culprits, "Chemins de lecteur réels (utiliser X:) : " + ", ".join(culprits)
