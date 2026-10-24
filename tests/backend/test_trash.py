"""
test_trash.py - Tests de la corbeille et de sa purge

Description:
    Tests de la corbeille des opérations sur une corbeille temporaire : entrée d'un
    lot (déplacement, journal, manifeste), purge après la rétention comptée depuis la
    date du journal, lot purgé en entier, annonce des purges proches, rétention à 0,
    et lots jamais purgés (absents du journal, manifeste manquant ou différent,
    fichier ajouté, déjà purgé).

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.24

Date de modification :
    2026.10.24
"""

import datetime as dt
import json
import os

import pytest

from src.backend import trash

T0 = dt.datetime(2026, 10, 1, 12, 0, 0)


@pytest.fixture
def env(tmp_path):
    """Racine fictive avec deux fichiers, corbeille et journaux temporaires."""
    root = tmp_path / "Musique"
    album = root / "Artists" / "Les Exemples" / "Album"
    album.mkdir(parents=True)
    (album / "01 - Titre.alac.m4a").write_bytes(b"a" * 10)
    (album / "cover.jpg").write_bytes(b"b" * 3)
    return {
        "root": root,
        "files": [album / "01 - Titre.alac.m4a", album / "cover.jpg"],
        "trash": root / "_workspace" / "_bin",
        "logs": root / "_bot" / "_log",
    }


def _put(env, lot="lot1", now=T0, files=None):
    """Met les fichiers de la fixture (ou `files`) dans un lot, journal ignoré."""
    return trash.put(files or env["files"], env["root"], env["trash"], env["logs"], lot, "conversion", lambda m: None, now)


def _purge(env, days=30, now=None, lines=None):
    """Lance la purge ; les lignes du journal d'opération vont dans `lines`."""
    log = lines.append if lines is not None else (lambda m: None)
    return trash.purge(env["trash"], env["logs"], days, log, now)


def test_put_moves_files_and_writes_traces(env):
    lines = []
    lot = trash.put(env["files"], env["root"], env["trash"], env["logs"], "lot1", "conversion", lines.append, T0)
    folder = env["trash"] / "lot1"
    assert not env["files"][0].exists()
    assert (folder / "Artists/Les Exemples/Album/01 - Titre.alac.m4a").read_bytes() == b"a" * 10
    # Journal de la corbeille et manifeste : la même liste
    journal = [json.loads(x) for x in trash.journal_path(env["logs"]).read_text(encoding="utf-8").splitlines()]
    assert journal[0]["event"] == trash.ENTRY and journal[0]["lot"] == "lot1"
    manifest = json.loads((folder / trash.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest == lot.to_json() == {k: v for k, v in journal[0].items() if k != "event"}
    assert manifest["files"][0] == {
        "path": "Artists/Les Exemples/Album/01 - Titre.alac.m4a",
        "original": str(env["files"][0]),
        "size": 10,
    }
    assert manifest["entered"] == "2026-10-01T12:00:00"
    # Le journal de l'opération note chaque fichier
    assert len(lines) == 3 and "lot1" in lines[0] and str(env["files"][1]) in lines[2]


@pytest.mark.parametrize("name", ["", "..", "a/b", "a\\b", "_lot"])
def test_put_rejects_bad_name(env, name):
    with pytest.raises(trash.TrashError, match="invalide"):
        _put(env, lot=name)


def test_put_rejects_known_lot_and_outside_file(env, tmp_path):
    _put(env, files=env["files"][:1])
    with pytest.raises(trash.TrashError, match="existe déjà"):
        _put(env, files=env["files"][1:])
    other = tmp_path / "ailleurs.flac"
    other.write_bytes(b"x")
    with pytest.raises(trash.TrashError, match="n'est pas sous"):
        _put(env, lot="lot2", files=[other])
    assert other.exists()


def test_purge_after_retention(env):
    _put(env)
    # 29 jours : gardé, et annoncé (purge dans les 7 jours)
    outcome = _purge(env, now=T0 + dt.timedelta(days=29))
    assert outcome.kept == 1 and not outcome.purged
    assert [(lot.name, date) for lot, date in outcome.upcoming] == [("lot1", T0 + dt.timedelta(days=30))]
    # 30 jours : purgé en entier, manifeste compris
    lines = []
    outcome = _purge(env, now=T0 + dt.timedelta(days=30), lines=lines)
    assert [lot.name for lot in outcome.purged] == ["lot1"]
    assert not (env["trash"] / "lot1").exists()
    journal = [json.loads(x) for x in trash.journal_path(env["logs"]).read_text(encoding="utf-8").splitlines()]
    assert journal[-1]["event"] == trash.PURGE and journal[-1]["files"] == [str(f) for f in env["files"]]
    assert any(str(env["files"][0]) in line for line in lines)
    # L'entrée du journal reste après la purge
    lots, purged = trash.read_journal(env["logs"])
    assert "lot1" in lots and purged == {"lot1"}


def test_age_from_journal_not_file_dates(env):
    """Des fichiers très anciens (date de modification d'origine) ne sont pas purgés."""
    old = (T0 - dt.timedelta(days=400)).timestamp()
    for f in env["files"]:
        os.utime(f, (old, old))
    _put(env)
    assert _purge(env, now=T0 + dt.timedelta(days=1)).kept == 1
    assert (env["trash"] / "lot1").is_dir()


def test_no_notice_far_from_purge(env):
    _put(env)
    assert _purge(env, now=T0 + dt.timedelta(days=5)).upcoming == []


def test_retention_zero_never_purges(env):
    _put(env)
    outcome = _purge(env, days=0, now=T0 + dt.timedelta(days=3650))
    assert outcome.kept == 1 and not outcome.purged and not outcome.upcoming


def test_missing_trash_folder(env):
    assert _purge(env) == trash.PurgeOutcome()


def _flagged(env) -> dict[str, str]:
    """Lots signalés par une purge lancée bien après la rétention."""
    outcome = _purge(env, now=T0 + dt.timedelta(days=365))
    return dict(outcome.flagged)


def test_lot_absent_from_journal_flagged(env):
    stray = env["trash"] / "inconnu"
    stray.mkdir(parents=True)
    (stray / "a.flac").write_bytes(b"x")
    assert "absent du journal" in _flagged(env)["inconnu"]
    assert stray.is_dir()


def test_missing_manifest_flagged(env):
    _put(env)
    (env["trash"] / "lot1" / trash.MANIFEST_NAME).unlink()
    assert _flagged(env)["lot1"] == "manifeste absent"
    assert (env["trash"] / "lot1").is_dir()


def test_manifest_differs_from_journal_flagged(env):
    _put(env)
    manifest = env["trash"] / "lot1" / trash.MANIFEST_NAME
    content = json.loads(manifest.read_text(encoding="utf-8"))
    content["entered"] = "2020-01-01T00:00:00"  # rajeunir n'est pas possible, vieillir non plus
    manifest.write_text(json.dumps(content), encoding="utf-8")
    assert "ne correspond pas" in _flagged(env)["lot1"]


def test_unlisted_file_flagged(env):
    """Un fichier ajouté au lot à la main ne disparaît pas avec lui."""
    _put(env)
    (env["trash"] / "lot1" / "ajout.flac").write_bytes(b"x")
    assert "hors du manifeste" in _flagged(env)["lot1"]
    assert (env["trash"] / "lot1" / "ajout.flac").exists()


def test_purged_lot_restored_flagged(env):
    """Un dossier revenu sous le nom d'un lot déjà purgé n'est pas supprimé."""
    _put(env)
    _purge(env, now=T0 + dt.timedelta(days=31))
    (env["trash"] / "lot1").mkdir()
    assert _flagged(env)["lot1"] == "déjà purgé selon le journal"


def test_unreadable_journal_line_ignored(env):
    _put(env)
    with open(trash.journal_path(env["logs"]), "a", encoding="utf-8") as f:
        f.write("{pas du json\n")
    lots, _ = trash.read_journal(env["logs"])
    assert list(lots) == ["lot1"]
