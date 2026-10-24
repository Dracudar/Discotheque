"""
lots.py - Traitement des lots validés par l'opérateur

Description:
    Relie les lots (`src.backend.lot`) aux mods qui les préparent et les appliquent :
    « disco lot », « disco review » et « disco reject ».

    Le manifeste d'un lot nomme son mod ; `MODS` donne le module qui le traite. Ce
    registre est vide tant qu'aucun traitement ne produit de lot : chaque traitement
    qui écrit sur la musique (tags ReplayGain #21, conventions #82, rangement de
    `_sort` #78) y ajoutera une ligne. Le module d'un mod fournit quatre fonctions :

    - `current(action, cfg) -> str` : état réel, relu au moment d'appliquer ; s'il
      diffère de `action.before`, le fichier a changé depuis la préparation et la
      ligne est refusée ;
    - `to_trash(action, cfg) -> list[Path]` : fichiers que l'action retire de la
      discothèque (original remplacé par sa copie retravaillée, fichier brut de
      `_sort`), tous sous `paths.root` ; le cadre les met dans la corbeille juste
      avant `apply` ;
    - `apply(actions, folder, cfg, log) -> dict[str, str]` : applique les actions
      acceptées avec les garanties de la règle 3 (sauvegarde des tags, empreinte
      audio avant et après, `journal.csv`, script d'annulation) et renvoie les échecs
      (identifiant -> message) ;
    - `rework(folder, answers, cfg, log) -> list[Action] | None` : relance la passe
      d'un lot de `_pending` avec les réponses de l'opérateur (identifiant ->
      texte) ; renvoie les actions proposées (le lot passe à valider) ou None (il
      reste en attente). Le mod peut réécrire `_lot.md` et les copies du dossier.

Auteur :
    Claude (Anthropic)

Version :
    1.0

Date de création :
    2026.10.24

Date de modification :
    2026.10.24
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

from src.backend import lot, oplog, trash
from src.backend.config import Config
from src.backend.lot import LotError

# Nom du mod (champ « mod » du manifeste) -> module qui traite ses lots
MODS: dict[str, ModuleType] = {}


def locate(target: str, cfg: Config) -> Path:
    """Dossier d'un lot, donné par son chemin ou par son seul nom.

    Raises:
        LotError: Aucun lot à ce chemin, ni de ce nom dans `in_review` ou `pending`.
    """
    candidates = [Path(target), Path(cfg.in_review) / target, Path(cfg.pending) / target]
    for folder in candidates:
        if (folder / lot.MANIFEST_NAME).is_file():
            return folder.resolve()
    raise LotError(f"Lot introuvable : {target}")


def _mod(manifest: lot.Manifest) -> ModuleType:
    """Module du mod qui traite le lot.

    Raises:
        LotError: Mod absent du registre.
    """
    module = MODS.get(manifest.mod)
    if module is None:
        raise LotError(f"Lot {manifest.name} : mod inconnu {manifest.mod!r}")
    return module


def _current(module: ModuleType, action: lot.Action, cfg: Config) -> str | None:
    """État réel relu par le mod, ou None si le fichier ne peut plus être lu.

    Un fichier disparu ou illisible (`OSError`) compte comme un fichier changé : la
    ligne sera refusée, sans arrêter le reste du lot.
    """
    try:
        return module.current(action, cfg)
    except OSError:
        return None


def _describe(action: lot.Action, comment: str) -> str:
    """Ligne de journal d'une action, avec l'avis de l'opérateur s'il y en a un."""
    text = f"{action.id} {action.action} {action.before} -> {action.after}"
    return f"{text} (avis : {comment})" if comment else text


def _report(cfg: Config, log: oplog.OpLog, title: str, folder: Path, manifest: lot.Manifest, figures, errors, notes) -> Path:
    """Rapport d'une opération sur un lot, avec le lot, son mod et son opération."""
    context = [("Lot", str(folder)), ("Mod", manifest.mod), ("Opération", manifest.operation)]
    return oplog.write_report(cfg.reports, log, title, context, figures, errors, notes)


def run(target: str, cfg: Config, ask: Callable[[str], str] = input) -> int:
    """« disco lot » : traite un lot selon son état.

    Dans `in_review`, applique les lignes acceptées ; dans `pending`, relance la passe
    du mod avec les réponses. Rien n'est écrit sans confirmation.

    Args:
        target: Dossier du lot, ou son nom.
        cfg: Configuration chargée.
        ask: Fonction de saisie de la confirmation (`input` par défaut).

    Returns:
        0 si tout s'est bien passé (ou rien à faire), 1 si le lot est invalide ou si
        des lignes ont été refusées d'office ou ont échoué.
    """
    try:
        folder = locate(target, cfg)
        state = lot.state_of(folder, cfg.in_review, cfg.pending)
        manifest = lot.read_manifest(folder)
        module = _mod(manifest)
        decisions = lot.read_decisions(folder, manifest)
    except LotError as e:
        print(e, file=sys.stderr)
        return 1
    if state == lot.PENDING:
        return _rework(folder, manifest, module, decisions, cfg, ask)
    return _apply(folder, manifest, module, decisions, cfg, ask)


def _apply(folder: Path, manifest: lot.Manifest, module: ModuleType, decisions: list[lot.Decision], cfg: Config, ask) -> int:
    """Applique les lignes acceptées d'un lot de `in_review` (voir `run`).

    L'application est partielle : les lignes vides restent en attente, et le lot ne
    part dans la corbeille que lorsqu'il n'en a plus. Les lignes déjà traitées par une
    passe précédente (notées dans le manifeste) sont ignorées.
    """
    todo = [d for d in decisions if d.action.id not in manifest.done]
    accepted = [d for d in todo if d.decision == lot.YES]
    refused = [d for d in todo if d.decision == lot.NO]
    waiting = [d for d in todo if not d.decision]
    # Une ligne dont l'état réel ne correspond plus à la préparation est refusée
    changed = [d for d in accepted if _current(module, d.action, cfg) != d.action.before]
    accepted = [d for d in accepted if d not in changed]
    to_trash = [Path(p) for d in accepted for p in module.to_trash(d.action, cfg)]

    text = (
        f"Lot {manifest.name} ({manifest.mod}, {manifest.operation}) : "
        f"{len(accepted)} ligne(s) à appliquer, {len(refused)} refusée(s), {len(waiting)} en attente ; "
        f"{len(to_trash)} fichier(s) partiront dans la corbeille."
    )
    if changed:
        ids = ", ".join(d.action.id for d in changed)
        text += f"\n{len(changed)} ligne(s) refusée(s) d'office, fichier changé depuis la préparation du lot : {ids}"
    if not (accepted or refused or changed):
        print(text)
        print("Rien à faire : aucune nouvelle ligne décidée.")
        return 0
    if not lot.confirm(text, ask):
        print("Annulé : rien n'a été modifié.")
        return 0

    errors: list[str] = []
    with oplog.OpLog(cfg.logs, "lot") as log:
        log(f"Lot {folder} ({manifest.mod}, {manifest.operation})")
        for d in refused:
            manifest.done[d.action.id] = lot.REFUSED
            log(f"  refusée : {_describe(d.action, d.comment)}")
        for d in changed:
            manifest.done[d.action.id] = lot.REFUSED
            message = f"Ligne {d.action.id} refusée : {d.action.before} a changé depuis la préparation du lot"
            log(f"  {message}")
            errors.append(message)
        if accepted:
            errors += _apply_accepted(folder, manifest, module, accepted, to_trash, cfg, log)
        lot.write_manifest(folder, manifest)
        notes = []
        if not waiting:
            archived = lot.archive(folder, cfg.trash, cfg.logs, log)
            notes.append(f"Lot entièrement traité, rangé dans la corbeille ({archived.name})")
        else:
            notes.append(f"{len(waiting)} ligne(s) encore en attente : le lot reste à valider")
        report = _report(
            cfg,
            log,
            f"Lot {manifest.name}",
            folder,
            manifest,
            [
                ("Lignes appliquées", str(sum(1 for d in accepted if manifest.done.get(d.action.id) == lot.APPLIED))),
                ("Lignes refusées", str(len(refused))),
                ("Lignes refusées d'office (fichier changé)", str(len(changed))),
                ("Lignes en échec", str(sum(1 for d in accepted if manifest.done.get(d.action.id) == lot.FAILED))),
                ("Lignes en attente", str(len(waiting))),
                ("Fichiers mis à la corbeille", str(len(to_trash))),
            ],
            errors,
            notes,
        )
        log(f"Rapport : {report}")
    return 1 if errors else 0


def _apply_accepted(folder, manifest, module, accepted, to_trash, cfg: Config, log: oplog.OpLog) -> list[str]:
    """Met les fichiers retirés à la corbeille, puis fait appliquer les lignes par le mod.

    Note chaque ligne dans le manifeste (`APPLIED` ou `FAILED`) et renvoie les erreurs.
    """
    if to_trash:
        try:
            trash.put(to_trash, cfg.root, cfg.trash, cfg.logs, f"{manifest.name}_{oplog.timestamp(log.start)}", manifest.operation, log)
        except trash.TrashError as e:
            # Rien n'a été déplacé : les lignes restent à appliquer
            log(f"Corbeille impossible, aucune ligne appliquée : {e}")
            return [f"Corbeille impossible, aucune ligne appliquée : {e}"]
    try:
        failures = module.apply([d.action for d in accepted], folder, cfg, log)
    except Exception as e:
        # Erreur imprévue dans le mod : on ne sait pas quelles lignes ont été écrites.
        # Elles sont notées en échec pour ne jamais être appliquées deux fois ;
        # le journal et le script d'annulation du mod permettent de vérifier.
        log(f"Erreur du mod {manifest.mod} : {e!r}")
        failures = {d.action.id: f"erreur du mod : {e!r}" for d in accepted}
    errors = []
    for d in accepted:
        if d.action.id in failures:
            manifest.done[d.action.id] = lot.FAILED
            errors.append(f"Ligne {d.action.id} en échec : {failures[d.action.id]}")
            log(f"  échec : {d.action.id} : {failures[d.action.id]}")
        else:
            manifest.done[d.action.id] = lot.APPLIED
            log(f"  appliquée : {_describe(d.action, d.comment)}")
    return errors


def _rework(folder: Path, manifest: lot.Manifest, module: ModuleType, decisions: list[lot.Decision], cfg: Config, ask) -> int:
    """Relance la passe d'un lot de `pending` avec les réponses de l'opérateur (voir `run`)."""
    answers = {d.action.id: d.comment for d in decisions if d.comment}
    if not answers:
        print(f"Lot {manifest.name} en attente : aucune réponse dans la colonne comment, rien à faire.")
        return 0
    text = (
        f"Lot {manifest.name} ({manifest.mod}, {manifest.operation}) en attente : "
        f"{len(answers)} réponse(s) ; la passe de traitement va reprendre avec elles."
    )
    if not lot.confirm(text, ask, "Relancer ?"):
        print("Annulé : rien n'a été modifié.")
        return 0
    with oplog.OpLog(cfg.logs, "lot") as log:
        log(f"Lot {folder} ({manifest.mod}, {manifest.operation}) : nouvelle passe")
        for ident, answer in answers.items():
            log(f"  réponse {ident} : {answer}")
        proposal = module.rework(folder, answers, cfg, log)
        if proposal is None:
            note = "Le mod ne sait toujours pas trancher : le lot reste en attente"
        else:
            if not proposal or len({a.id for a in proposal}) != len(proposal):
                log(f"Lot {manifest.name} : proposition du mod vide ou avec des identifiants en double ; le lot reste en attente")
                return 1
            manifest.actions = tuple(proposal)
            manifest.done = {}
            lot.write_manifest(folder, manifest)
            lot.write_decisions(folder, manifest.actions)
            folder = lot.move(folder, cfg.in_review)
            note = f"{len(proposal)} action(s) proposée(s) : le lot passe à valider ({folder})"
        log(note)
        report = _report(cfg, log, f"Lot {manifest.name} : nouvelle passe", folder, manifest, [("Réponses", str(len(answers)))], [], [note])
        log(f"Rapport : {report}")
    return 0


def reject(target: str, cfg: Config, ask: Callable[[str], str] = input) -> int:
    """« disco reject » : refuse d'un coup toutes les lignes restantes d'un lot.

    Le lot est ensuite rangé dans la corbeille. Les avis de `_decisions.csv` sont
    gardés dans le journal si le fichier est encore lisible.

    Returns:
        0 si le lot a été refusé (ou la confirmation déclinée), 1 si le lot est
        introuvable ou invalide.
    """
    try:
        folder = locate(target, cfg)
        lot.state_of(folder, cfg.in_review, cfg.pending)
        manifest = lot.read_manifest(folder)
    except LotError as e:
        print(e, file=sys.stderr)
        return 1
    try:
        comments = {d.action.id: d.comment for d in lot.read_decisions(folder, manifest)}
    except LotError:
        comments = {}
    remaining = [a for a in manifest.actions if a.id not in manifest.done]
    text = f"Lot {manifest.name} ({manifest.mod}, {manifest.operation}) : {len(remaining)} ligne(s) refusée(s) ; le lot partira dans la corbeille."
    if not lot.confirm(text, ask, "Refuser le lot ?"):
        print("Annulé : rien n'a été modifié.")
        return 0
    with oplog.OpLog(cfg.logs, "lot_reject") as log:
        log(f"Lot {folder} refusé en entier")
        for a in remaining:
            manifest.done[a.id] = lot.REFUSED
            log(f"  refusée : {_describe(a, comments.get(a.id, ''))}")
        lot.write_manifest(folder, manifest)
        archived = lot.archive(folder, cfg.trash, cfg.logs, log)
        report = _report(
            cfg,
            log,
            f"Lot {manifest.name} refusé",
            folder,
            manifest,
            [("Lignes refusées", str(len(remaining)))],
            [],
            [f"Lot rangé dans la corbeille ({archived.name})"],
        )
        log(f"Rapport : {report}")
    return 0


def review(cfg: Config) -> int:
    """« disco review » : liste les lots à valider et en attente, avec leurs décisions.

    Returns:
        0, ou 1 si un lot a un `_decisions.csv` invalide (signalé dans la liste).
    """
    lots = lot.find_lots(cfg.in_review, cfg.pending)
    if not lots:
        print("Aucun lot à valider ni en attente.")
        return 0
    code = 0
    for state, folder in lots:
        label = "à valider " if state == lot.IN_REVIEW else "en attente"
        try:
            manifest = lot.read_manifest(folder)
            todo = [d for d in lot.read_decisions(folder, manifest) if d.action.id not in manifest.done]
        except LotError as e:
            print(f"{label}  {folder.name}  invalide : {e}")
            code = 1
            continue
        decided = sum(1 for d in todo if d.decision)
        print(
            f"{label}  {folder.name}  ({manifest.mod}, {manifest.operation})  "
            f"{decided} décidée(s), {len(todo) - decided} restante(s), {len(manifest.done)} déjà traitée(s)"
        )
    return code
