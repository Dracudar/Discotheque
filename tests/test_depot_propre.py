"""
test_depot_propre.py - Garde-fou du dépôt public

Description:
    Garde-fou : aucune donnée de la discothèque ne doit entrer dans le dépôt.

    Le dépôt ne contient que du code, des tests sur données fictives et de la
    documentation de mise en place. Ce test échoue si un fichier suivi par Git
    ressemble à une donnée réelle (fiche, index, paroles, audio, journal…).

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.08
"""

import re
import subprocess
from pathlib import PurePosixPath

import pytest

INTERDITS_EXT = {
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
INTERDITS_NOMS = {"recap.json", "recap.html", "registry.json", "artists.txt", "config.toml"}
AUTORISES = {"tests/fixtures/fiche_fictive.json"}


def fichiers_suivis(racine) -> list[str]:
    try:
        r = subprocess.run(["git", "ls-files"], cwd=racine, capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("git absent")
    if r.returncode != 0:
        pytest.skip("pas un dépôt Git")
    return r.stdout.splitlines()


def test_aucune_donnee_reelle(racine):
    fautifs = []
    for f in fichiers_suivis(racine):
        p = PurePosixPath(f)
        if f in AUTORISES:
            continue
        if p.suffix.lower() in INTERDITS_EXT or p.name in INTERDITS_NOMS:
            fautifs.append(f)
    assert not fautifs, "Données de la discothèque dans le dépôt : " + ", ".join(fautifs)


# Chemins absolus Windows : seul le lecteur fictif X: est permis (exemples de configuration).
LECTEUR = re.compile(r"(?<![A-Za-z0-9])([A-WYZ]):" + re.escape("\\"))
TEXTES = {
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


def test_aucun_chemin_du_poste(racine):
    fautifs = []
    for f in fichiers_suivis(racine):
        if PurePosixPath(f).suffix.lower() not in TEXTES:
            continue
        texte = (racine / f).read_text(encoding="utf-8", errors="replace")
        for n, ligne in enumerate(texte.splitlines(), 1):
            if LECTEUR.search(ligne):
                fautifs.append(f"{f}:{n}")
    assert not fautifs, "Chemins de lecteur réels (utiliser X:) : " + ", ".join(fautifs)
