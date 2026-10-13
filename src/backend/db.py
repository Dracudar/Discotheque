"""
db.py - Configuration de la DB SQLite

Description:
    Mise en place de la base de données SQLite pour l'application et la gestion des connexions.
    Prévision : inclure la création des tables

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.09
"""

import sqlite3
from pathlib import Path

DB_NAME = "discotheque.sqlite"


def open_db(db_dir: Path) -> sqlite3.Connection:
    """
    Établit une connexion à la base de données SQLite spécifiée et la crée si elle n'existe pas.

    Args:
        db_dir (Path): Dossier de la base (`Config.db`, soit `_data/_base`).
            Il est créé s'il manque, mais son parent (`_data`) doit déjà exister.

    Returns:
        La connexion, en mode `autocommit=False` : chaque écriture doit être validée par `conn.commit()`.
        L'appelant la ferme, par exemple avec `contextlib.closing()`.

    Raises:
        FileNotFoundError: Si le dossier `_data` n'existe pas.
    """

    db_dir.mkdir(parents=False, exist_ok=True)
    db_path = db_dir / DB_NAME

    # `PRAGMA foreign_keys` est ignoré pendant une transaction :
    # on l'active en `autocommit=True` (aucune transaction ouverte),
    # puis on passe en `autocommit=False`, qui en ouvre une aussitôt.
    conn = sqlite3.connect(db_path, autocommit=True)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.autocommit = False

    return conn
