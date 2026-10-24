"""
test_lots.py - Tests de « disco lot », « disco review » et « disco reject »

Description:
    Tests du traitement des lots avec un faux mod, sur une racine temporaire : chaque
    « piste » est un petit fichier texte dont le contenu tient lieu d'état (tags).
    Décisions mixtes et application partielle, remplacement avec l'original à la
    corbeille, fichier changé depuis la préparation, confirmation refusée, valeur
    invalide, échec du mod, passage de `_pending` à `_in_review`, refus d'un lot
    entier, liste des lots, et sous-commandes de la ligne de commande.

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.24

Date de modification :
    2026.10.24
"""

from types import ModuleType

import pytest

from src.backend import config, lot, trash
from src.backend.lot import Action
from src.core import lots
from src.core.cli import main

YES = lambda prompt: "o"  # noqa: E731
NO = lambda prompt: ""  # noqa: E731


def _fake_mod(root):
    """Faux mod : l'état d'une piste est le contenu de `<racine>/Album/<id>.flac`.

    `replace` remplace le fichier (l'original part à la corbeille), `tag` le réécrit
    en place. `fail` donne les identifiants qui échouent, `proposal` la réponse de
    `rework`.
    """
    mod = ModuleType("fake")
    mod.applied, mod.fail, mod.proposal, mod.answers = [], set(), None, None

    def path(action):
        return root / "Album" / f"{action.id}.flac"

    def current(action, cfg):
        return path(action).read_text(encoding="utf-8")

    def to_trash(action, cfg):
        return [path(action)] if action.action == "replace" else []

    def apply(actions, folder, cfg, log):
        failures = {}
        for a in actions:
            mod.applied.append(a.id)
            if a.id in mod.fail:
                failures[a.id] = "écriture impossible"
            else:
                path(a).write_text(a.after, encoding="utf-8")
        return failures

    def rework(folder, answers, cfg, log):
        mod.answers = answers
        return mod.proposal

    mod.current, mod.to_trash, mod.apply, mod.rework = current, to_trash, apply, rework
    return mod


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Racine fictive, configuration, trois pistes et le faux mod inscrit dans `MODS`."""
    root = tmp_path / "Musique"
    (root / "Album").mkdir(parents=True)
    for i in "123":
        (root / "Album" / f"{i}.flac").write_text(f"gain {i}", encoding="utf-8")
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(f"[paths]\nroot = '{root}'\n", encoding="utf-8")
    cfg = config.load(cfg_file)
    mod = _fake_mod(root)
    monkeypatch.setattr(lots, "MODS", {"fake": mod})
    return {"root": root, "cfg": cfg, "cfg_file": cfg_file, "mod": mod}


ACTIONS = [
    Action("1", "tag", "gain 1", "gain 1 corrigé", "gain recalculé"),
    Action("2", "tag", "gain 2", "gain 2 corrigé", "gain recalculé"),
    Action("3", "replace", "gain 3", "copie FLAC", "conversion"),
]


def _lot(env, parent=None, name="2026-10-01_120000_replaygain", mod="fake"):
    """Crée un lot des trois actions, à valider par défaut."""
    cfg = env["cfg"]
    return lot.create(parent or cfg.in_review, name, mod, "replaygain", ACTIONS, "# Lot\n", lot.program_path(cfg.bot))


def _decide(folder, decisions):
    """Remplit `_decisions.csv` : identifiant -> (décision, avis)."""
    manifest = lot.read_manifest(folder)
    rows = [";".join(lot.COLUMNS)]
    for a in manifest.actions:
        decision, comment = decisions.get(a.id, ("", ""))
        rows.append(";".join([a.id, a.action, a.before, a.after, a.reason, decision, comment]))
    (folder / lot.DECISIONS_NAME).write_bytes(("\r\n".join(rows) + "\r\n").encode("utf-8-sig"))


def _track(env, i):
    """Contenu actuel de la piste fictive `i`."""
    return (env["root"] / "Album" / f"{i}.flac").read_text(encoding="utf-8")


def test_partial_then_complete(env, capsys):
    cfg, mod = env["cfg"], env["mod"]
    folder = _lot(env)
    _decide(folder, {"1": ("oui", "parfait"), "2": ("non", "trop fort")})
    prompts = []
    assert lots.run(str(folder), cfg, lambda p: prompts.append(p) or "o") == 0
    assert "1 ligne(s) à appliquer, 1 refusée(s), 1 en attente ; 0 fichier(s) partiront dans la corbeille" in prompts[0]
    assert _track(env, 1) == "gain 1 corrigé" and _track(env, 2) == "gain 2"
    # Application partielle : le lot reste à valider, les lignes traitées sont notées
    assert lot.read_manifest(folder).done == {"1": lot.APPLIED, "2": lot.REFUSED}
    assert lot.state_of(folder, cfg.in_review, cfg.pending) == lot.IN_REVIEW
    log = next(cfg.logs.glob("*_lot.log")).read_text(encoding="utf-8")
    assert "avis : trop fort" in log
    assert len(list(cfg.reports.glob("*_lot.md"))) == 1

    # Seconde passe : la ligne 3 (remplacement), les lignes déjà traitées sont ignorées
    _decide(folder, {"1": ("oui", "parfait"), "2": ("non", "trop fort"), "3": ("yes", "")})
    assert lots.run(folder.name, cfg, YES) == 0
    assert mod.applied == ["1", "3"]
    assert _track(env, 3) == "copie FLAC"
    # L'original remplacé est dans la corbeille, le lot terminé aussi (lot séparé)
    known, _ = trash.read_journal(cfg.logs)
    bins = sorted(known)
    assert bins[0].startswith(folder.name + "_2") and known[bins[0]].files[0]["path"] == "Album/3.flac"
    assert bins[1] == f"{folder.name}_done"
    assert not folder.exists()
    assert (cfg.trash / bins[0] / "Album" / "3.flac").read_text(encoding="utf-8") == "gain 3"


def test_changed_file_is_refused(env):
    folder = _lot(env)
    _decide(folder, {"1": ("oui", "")})
    (env["root"] / "Album" / "1.flac").write_text("modifié à la main", encoding="utf-8")
    prompts = []
    assert lots.run(str(folder), env["cfg"], lambda p: prompts.append(p) or "o") == 1
    assert "refusée(s) d'office" in prompts[0]
    assert env["mod"].applied == []
    assert _track(env, 1) == "modifié à la main"
    assert lot.read_manifest(folder).done == {"1": lot.REFUSED}


def test_confirmation_declined_writes_nothing(env, capsys):
    cfg = env["cfg"]
    folder = _lot(env)
    _decide(folder, {"1": ("oui", ""), "3": ("oui", "")})
    assert lots.run(str(folder), cfg, NO) == 0
    assert env["mod"].applied == [] and _track(env, 3) == "gain 3"
    assert lot.read_manifest(folder).done == {}
    assert not cfg.logs.exists() and not cfg.trash.exists()
    assert "rien n'a été modifié" in capsys.readouterr().out


def test_invalid_value_stops(env, capsys):
    folder = _lot(env)
    _decide(folder, {"2": ("peut-être", "")})
    assert lots.run(str(folder), env["cfg"], YES) == 1
    assert "ligne 3" in capsys.readouterr().err
    assert env["mod"].applied == []


def test_nothing_decided(env, capsys):
    folder = _lot(env)
    assert lots.run(str(folder), env["cfg"], YES) == 0
    assert "Rien à faire" in capsys.readouterr().out


def test_unknown_mod_and_missing_lot(env, capsys):
    folder = _lot(env, mod="inconnu")
    assert lots.run(str(folder), env["cfg"], YES) == 1
    assert lots.run("absent", env["cfg"], YES) == 1
    err = capsys.readouterr().err
    assert "mod inconnu" in err and "Lot introuvable" in err


def test_mod_failure_is_never_reapplied(env):
    folder = _lot(env)
    env["mod"].fail = {"1"}
    _decide(folder, {"1": ("oui", ""), "2": ("oui", "")})
    assert lots.run(str(folder), env["cfg"], YES) == 1
    assert lot.read_manifest(folder).done == {"1": lot.FAILED, "2": lot.APPLIED}
    _decide(folder, {"1": ("oui", ""), "2": ("oui", ""), "3": ("non", "")})
    lots.run(str(folder), env["cfg"], YES)
    assert env["mod"].applied == ["1", "2"]


def test_pending_to_review(env):
    cfg, mod = env["cfg"], env["mod"]
    folder = _lot(env, parent=cfg.pending)
    _decide(folder, {"1": ("", "c'est une compilation")})
    # Le mod ne sait toujours pas trancher : le lot reste en attente
    assert lots.run(str(folder), cfg, YES) == 0
    assert mod.answers == {"1": "c'est une compilation"} and folder.exists()
    # Le mod propose : le lot passe à valider, avec un CSV neuf
    mod.proposal = [Action("a", "tag", "gain 1", "gain album", "compilation")]
    assert lots.run(str(folder), cfg, YES) == 0
    moved = cfg.in_review / folder.name
    assert not folder.exists() and moved.is_dir()
    manifest = lot.read_manifest(moved)
    assert [a.id for a in manifest.actions] == ["a"] and manifest.done == {}
    assert [d.decision for d in lot.read_decisions(moved, manifest)] == [""]


def test_reject(env):
    cfg = env["cfg"]
    folder = _lot(env)
    _decide(folder, {"1": ("oui", ""), "2": ("", "à revoir")})
    assert lots.reject(folder.name, cfg, NO) == 0 and folder.exists()
    assert lots.reject(folder.name, cfg, YES) == 0
    assert not folder.exists() and env["mod"].applied == []
    archived = cfg.trash / f"{folder.name}_done" / folder.name
    assert set(lot.read_manifest(archived).done.values()) == {lot.REFUSED}
    assert "avis : à revoir" in next(cfg.logs.glob("*_lot_reject.log")).read_text(encoding="utf-8")


def test_review(env, capsys):
    cfg = env["cfg"]
    assert lots.review(cfg) == 0
    assert "Aucun lot" in capsys.readouterr().out
    folder = _lot(env)
    _decide(folder, {"1": ("oui", "")})
    _lot(env, parent=cfg.pending, name="question")
    assert lots.review(cfg) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("à valider") and "1 décidée(s), 2 restante(s)" in out[0]
    assert out[1].startswith("en attente") and "question" in out[1]
    _decide(folder, {"1": ("bof", "")})
    assert lots.review(cfg) == 1
    assert "invalide" in capsys.readouterr().out


def test_cli(env, capsys):
    folder = _lot(env)
    assert main(["--config", str(env["cfg_file"]), "review"]) == 0
    assert folder.name in capsys.readouterr().out
    assert main(["--config", str(env["cfg_file"]), "lot", "absent"]) == 1
    assert main(["--config", str(env["cfg_file"].parent / "rien.toml"), "reject", "x"]) == 2
