"""
__versions__.py - Versions du programme et de ce qu'il utilise

Description:
    Seule source des versions de la livraison. Pour l'instant, le numéro de version du
    programme (`__version__`, au format majeur.mineur.correctif, distinct de la version
    de chaque fichier) : `pyproject.toml` le lit à l'installation et « disco --version »
    l'affiche. Recevra les versions figées des outils externes, des dépendances Python
    (extraites vers requirements.txt) et des modèles d'IA (issues #52 et #55).

    Placé à la racine du paquet, sans aucune importation : toutes les couches peuvent
    le lire, et un script (CI, compilation) peut l'exécuter sans installer le programme.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.08
"""

__version__ = "0.1.0.dev0"
