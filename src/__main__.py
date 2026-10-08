"""
__main__.py - Lancement par « python -m src »

Description:
    Permet « python -m src » : équivalent de la commande « disco » installée
    par pip. Le code de retour de `src.core.cli.main` devient celui du processus.

Auteur :
    Dracudar

Version :
    1.1

Date de création :
    2026.10.06

Date de modification :
    2026.10.08
"""

from src.core.cli import main

raise SystemExit(main())
