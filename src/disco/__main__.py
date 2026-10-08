"""
__main__.py - Lancement par « python -m disco »

Description:
    Permet « python -m disco » : équivalent de la commande « disco » installée
    par pip. Le code de retour de `disco.cli.main` devient celui du processus.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.06

Date de modification :
    2026.10.07
"""

from disco.cli import main

raise SystemExit(main())
