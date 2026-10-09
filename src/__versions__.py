"""
__versions__.py - Versions du programme et de ce qu'il utilise

Description:
    Lecteur de `assets/versions.toml`, seule source des versions de la livraison. Pour
    l'instant, le numéro de version du programme (`__version__`, au format
    majeur.mineur.correctif, distinct de la version de chaque fichier) :
    `pyproject.toml` le lit à l'installation et « disco --version » l'affiche. Le
    fichier recevra les versions figées des outils externes, des dépendances Python
    (extraites vers requirements.txt) et des modèles d'IA (issues #52 et #55).

    Placé à la racine du paquet et n'important que la bibliothèque standard : toutes
    les couches peuvent le lire, et un script (CI, compilation) peut l'exécuter sans
    installer le programme.

Auteur :
    Dracudar

Version :
    2.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.09
"""

import tomllib
from pathlib import Path

FILE = Path(__file__).resolve().parent / "assets" / "versions.toml"


def read(path: Path = FILE) -> dict:
    """Contenu du fichier des versions.

    Args:
        path: Fichier TOML à lire ; celui du paquet par défaut.

    Returns:
        Les tables du fichier (`program`, puis `tools`, `dependencies`…).
    """
    with open(path, "rb") as f:
        return tomllib.load(f)


VERSIONS = read()
__version__: str = VERSIONS["program"]["version"]
