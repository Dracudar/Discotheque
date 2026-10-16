"""
test_db.py - Tests de la connexion à la base

Description:
    Vérifie les promesses de `open_db()` (src/backend/db.py), chacune par un test :
    création du dossier et du fichier de la base, clés étrangères réellement appliquées,
    écritures perdues sans `commit()`, base rouverte avec son contenu, et échec franc
    quand `_data` manque. Chaque test travaille dans un dossier temporaire neuf
    (`tmp_path`) : jamais dans la sandbox.

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.13

Date de modification :
    2026.10.13
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from src.backend.db import DB_NAME, open_db


@pytest.fixture
def db_dir(tmp_path) -> Path:
    """Dossier `_data/_base` d'une racine fictive : `_data` existe, `_base` pas encore.

    C'est l'état que `open_db()` suppose au démarrage : le programme crée `_data`,
    `open_db()` crée `_base`.
    """
    data = tmp_path / "_data"
    data.mkdir()
    return data / "_base"


def test_creates_db_dir_and_file(db_dir):
    assert not db_dir.exists()  # point de départ : _base n'existe pas
    with closing(open_db(db_dir)):
        assert (db_dir / DB_NAME).is_file()


def test_foreign_keys_enabled(db_dir):
    with closing(open_db(db_dir)) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_foreign_key_enforced(db_dir):
    """Le pragma ne suffit pas à le prouver : une ligne orpheline doit être refusée."""
    with closing(open_db(db_dir)) as conn:
        conn.executescript(
            """
            CREATE TABLE parent (id INTEGER PRIMARY KEY);
            CREATE TABLE child (parent_id INTEGER REFERENCES parent(id));
            """
        )
        conn.execute("INSERT INTO parent (id) VALUES (1)")
        conn.execute("INSERT INTO child (parent_id) VALUES (1)")  # parent existant : accepté
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            conn.execute("INSERT INTO child (parent_id) VALUES (99)")  # aucun parent 99


def test_write_lost_without_commit(db_dir):
    """`autocommit=False` : une écriture non validée disparaît à la fermeture."""
    with closing(open_db(db_dir)) as conn:
        assert conn.autocommit is False
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.commit()  # la table est validée
        conn.execute("INSERT INTO t (x) VALUES (1)")
        # pas de commit() : la ligne n'est pas enregistrée
    with closing(open_db(db_dir)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 0


def test_reopen_keeps_content(db_dir):
    """Rouvrir une base existante ne lève pas d'erreur (`exist_ok=True`) et retrouve ses données."""
    with closing(open_db(db_dir)) as conn:
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.execute("INSERT INTO t (x) VALUES (42)")
        conn.commit()
    with closing(open_db(db_dir)) as conn:
        assert conn.execute("SELECT x FROM t").fetchone()[0] == 42


def test_missing_data_dir_raises(tmp_path):
    """Sans `_data`, `open_db()` échoue au lieu de créer une base ailleurs (fail fast)."""
    db_dir = tmp_path / "_data" / "_base"  # _data n'est pas créé
    with pytest.raises(FileNotFoundError):
        open_db(db_dir)
    assert not (tmp_path / "_data").exists()  # rien n'a été créé à moitié
