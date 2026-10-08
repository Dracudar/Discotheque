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
    1.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.08
"""

import tomllib
from pathlib import Path

FICHIER = Path(__file__).resolve().parent / "assets" / "versions.toml"


def lire(chemin: Path = FICHIER) -> dict:
    """Contenu du fichier des versions.

    Args:
        chemin: Fichier TOML à lire ; celui du paquet par défaut.

    Returns:
        Les tables du fichier (`programme`, puis `outils`, `dependances`…).
    """
    with open(chemin, "rb") as f:
        return tomllib.load(f)


VERSIONS = lire()
__version__: str = VERSIONS["programme"]["version"]
