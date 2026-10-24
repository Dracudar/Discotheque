"""
test_lot.py - Tests du format des lots

Description:
    Tests du cadre des lots sur des lots fictifs : création du dossier (manifeste,
    rapport, `_decisions.csv`, `traiter.bat`), relecture de `_decisions.csv` tel
    qu'Excel le réenregistre (BOM, « ; », accents, cp1252), décisions mixtes et
    réponses en français, erreurs signalées avec leur ligne (valeur inconnue, colonne
    modifiée, identifiant inconnu, en double ou supprimé), confirmation, états,
    archivage dans la corbeille.

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

import pytest

from src.backend import lot, trash
from src.backend.lot import Action, LotError

T0 = dt.datetime(2026, 10, 1, 12, 0, 0)
ACTIONS = [
    Action("1", "tag", "-6.20 dB", "-7.50 dB", "gain recalculé (référence −18 LUFS)"),
    Action("2", "tag", "-3.10 dB", "-4.00 dB", "crête vraie ×8"),
    Action("3", "replace", "piste.m4a", "piste.flac", "conversion ALAC → FLAC"),
]


@pytest.fixture
def folder(tmp_path):
    """Lot fictif de trois actions dans un dossier `_in_review` temporaire."""
    return lot.create(
        tmp_path / "_in_review", "2026-10-01_120000_replaygain", "fake", "replaygain", ACTIONS, "# Lot\n", tmp_path / "_bot" / "disco.exe", T0
    )


def _write_csv(folder, rows, encoding="utf-8-sig"):
    """Réécrit `_decisions.csv` comme le ferait Excel (lignes déjà jointes par « ; »).

    En cp1252, les caractères absents deviennent « ? », comme avec Excel.
    """
    (folder / lot.DECISIONS_NAME).write_bytes(("\r\n".join(rows) + "\r\n").encode(encoding, errors="replace"))


def _rows(decisions):
    """Lignes de `_decisions.csv` pour les actions de test, avec ces décisions et avis."""
    rows = [";".join(lot.COLUMNS)]
    for a, (decision, comment) in zip(ACTIONS, decisions, strict=True):
        rows.append(";".join([a.id, a.action, a.before, a.after, a.reason, decision, comment]))
    return rows


def test_create_writes_folder(folder, tmp_path):
    assert sorted(p.name for p in folder.iterdir()) == sorted([lot.MANIFEST_NAME, lot.REPORT_NAME, lot.DECISIONS_NAME, lot.BAT_NAME])
    manifest = json.loads((folder / lot.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["mod"] == "fake" and manifest["created"] == "2026-10-01T12:00:00" and manifest["done"] == {}
    assert lot.read_manifest(folder).actions == tuple(ACTIONS)
    # CSV lisible par Excel en français : BOM, « ; », accents en UTF-8
    data = (folder / lot.DECISIONS_NAME).read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8-sig").splitlines()[0] == "id;action;before;after;reason;decision;comment"
    assert "ALAC → FLAC" in data.decode("utf-8-sig")


def test_create_refuses_bad_lots(tmp_path):
    exe = tmp_path / "disco.exe"
    with pytest.raises(LotError):
        lot.create(tmp_path, "_secret", "fake", "op", ACTIONS, "", exe)
    with pytest.raises(LotError):
        lot.create(tmp_path, "vide", "fake", "op", [], "", exe)
    with pytest.raises(LotError):
        lot.create(tmp_path, "double", "fake", "op", [ACTIONS[0], ACTIONS[0]], "", exe)
    lot.create(tmp_path, "lot", "fake", "op", ACTIONS, "", exe)
    with pytest.raises(LotError):
        lot.create(tmp_path, "lot", "fake", "op", ACTIONS, "", exe)


def test_bat(folder, tmp_path):
    data = (folder / lot.BAT_NAME).read_bytes()
    assert b"\r\n" in data and not data.startswith(b"\xef\xbb\xbf")
    text = data.decode("utf-8")
    exe = tmp_path / "_bot" / "disco.exe"
    assert f'"{exe}" lot "%~dp0."' in text
    assert f'if not exist "{exe}"' in text and "pause" in text


def test_fresh_csv_is_all_waiting(folder):
    decisions = lot.read_decisions(folder, lot.read_manifest(folder))
    assert [d.decision for d in decisions] == ["", "", ""]


def test_mixed_decisions_and_french_answers(folder):
    _write_csv(folder, _rows([(" Oui ", "d'accord"), ("non", "trop fort"), ("", "")]))
    decisions = lot.read_decisions(folder, lot.read_manifest(folder))
    assert [(d.decision, d.comment) for d in decisions] == [(lot.YES, "d'accord"), (lot.NO, "trop fort"), ("", "")]


def test_cp1252_and_trailing_empty_lines(folder):
    """Fichier réenregistré par Excel en « CSV point-virgule » : cp1252, sans BOM.

    « − » et « → » (raisons des actions 1 et 3) n'existent pas en cp1252 : leur
    remplacement par « ? » n'est pas pris pour une modification.
    """
    rows = _rows([("yes", "très bien"), ("n", ""), ("", "")]) + [";;;;;;", ""]
    _write_csv(folder, rows, encoding="cp1252")
    decisions = lot.read_decisions(folder, lot.read_manifest(folder))
    assert decisions[0].comment == "très bien" and decisions[1].decision == lot.NO


def test_missing_trailing_cells(folder):
    """Excel peut omettre les « ; » des dernières cellules vides."""
    rows = _rows([("yes", ""), ("", ""), ("", "")])
    rows[3] = ";".join([ACTIONS[2].id, ACTIONS[2].action, ACTIONS[2].before, ACTIONS[2].after, ACTIONS[2].reason])
    _write_csv(folder, rows)
    assert lot.read_decisions(folder, lot.read_manifest(folder))[2].decision == ""


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda rows: rows.__setitem__(2, rows[2].replace(";;", ";peut-être;")), "ligne 3 : decision 'peut-être' inconnue"),
        (lambda rows: rows.__setitem__(1, rows[1].replace("-7.50 dB", "-9 dB")), "ligne 2 : colonne after modifiée"),
        (lambda rows: rows.__setitem__(3, "9" + rows[3][1:]), "ligne 4 : identifiant inconnu '9'"),
        (lambda rows: rows.__setitem__(3, "1" + rows[3][1:]), "identifiant '1' en double"),
        (lambda rows: rows.pop(3), "identifiant(s) 3"),
        (lambda rows: rows.__setitem__(0, rows[0].replace("decision", "décision")), "ligne 1 : en-tête modifié"),
    ],
)
def test_invalid_csv(folder, change, message):
    rows = _rows([("", ""), ("", ""), ("", "")])
    change(rows)
    _write_csv(folder, rows)
    with pytest.raises(LotError, match=message.replace("(", r"\(").replace(")", r"\)")):
        lot.read_decisions(folder, lot.read_manifest(folder))


def test_confirm():
    assert lot.confirm("résumé", lambda prompt: "o")
    assert lot.confirm("résumé", lambda prompt: " Oui ")
    assert not lot.confirm("résumé", lambda prompt: "")
    assert not lot.confirm("résumé", lambda prompt: "n")

    def closed(prompt):
        raise EOFError

    assert not lot.confirm("résumé", closed)
    prompts = []
    lot.confirm("18 lignes à appliquer", lambda p: prompts.append(p) or "")
    assert prompts == ["18 lignes à appliquer\nAppliquer ? (o/N) "]


def test_states_and_move(folder, tmp_path):
    in_review, pending = tmp_path / "_in_review", tmp_path / "_pending"
    assert lot.state_of(folder, in_review, pending) == lot.IN_REVIEW
    moved = lot.move(folder, pending)
    assert lot.state_of(moved, in_review, pending) == lot.PENDING
    assert lot.find_lots(in_review, pending) == [(lot.PENDING, moved)]
    with pytest.raises(LotError):
        lot.state_of(moved, tmp_path / "ailleurs", tmp_path / "autre")


def test_archive(folder, tmp_path):
    (folder / "copies").mkdir()
    (folder / "copies" / "piste.flac").write_bytes(b"x")
    archived = lot.archive(folder, tmp_path / "_bin", tmp_path / "_log", lambda m: None)
    assert not folder.exists()
    assert archived.name == f"{folder.name}_done"
    target = tmp_path / "_bin" / archived.name / folder.name
    assert (target / lot.MANIFEST_NAME).is_file() and (target / "copies" / "piste.flac").is_file()
    # Le manifeste de la corbeille reste distinct de celui du lot
    assert json.loads((tmp_path / "_bin" / archived.name / trash.MANIFEST_NAME).read_text(encoding="utf-8"))["lot"] == archived.name
