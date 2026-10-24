"""
lot.py - Dossiers de lot et décisions de l'opérateur

Description:
    Cadre commun des lots, sans métier : tout ce que le bot propose d'écrire sur la
    musique passe par un lot que l'opérateur valide (règle 3). Un lot est un dossier,
    dans `paths.in_review` (le bot a tranché) ou `paths.pending` (le bot pose une
    question), qui contient :

    - `_lot.md` : rapport lisible (proposition et raisons, ou question posée) ;
    - `_lot.json` : manifeste (mod, opération, date, version du programme, actions, et
      lignes déjà traitées) ;
    - `_decisions.csv` : une ligne par action, que l'opérateur remplit dans Excel ;
    - `traiter.bat` : lance « disco lot » sur le dossier d'un double-clic ;
    - les copies retravaillées éventuelles (règle 2).

    Le format de `_decisions.csv` est neutre (en-têtes et valeurs en anglais, voir
    #110 et #56) : la relecture accepte aussi les réponses en français (« oui »,
    « non », « o », « n »), et `_lot.md` explique les colonnes. Il est écrit avec des
    « ; » et en UTF-8 avec BOM, pour qu'Excel en français l'ouvre directement.

    Ce module ne sait rien des actions elles-mêmes : chaque mod prépare ses lots
    (`create`) et applique ses actions ; `src.core.lots` relie les deux.

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

import csv
import datetime as dt
import io
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.__versions__ import __version__
from src.backend import trash

MANIFEST_NAME = "_lot.json"
REPORT_NAME = "_lot.md"
DECISIONS_NAME = "_decisions.csv"
BAT_NAME = "traiter.bat"
PROGRAM_NAME = "disco.exe"

COLUMNS = ("id", "action", "before", "after", "reason", "decision", "comment")
# Colonnes écrites par le bot : l'opérateur ne doit pas les modifier
FIXED = ("action", "before", "after", "reason")

YES, NO = "yes", "no"
# Réponses acceptées dans la colonne « decision », casse et espaces ignorés
ANSWERS = {"yes": YES, "y": YES, "oui": YES, "o": YES, "no": NO, "n": NO, "non": NO}

# États d'une ligne déjà traitée, notés dans le manifeste
APPLIED, REFUSED, FAILED = "applied", "refused", "failed"
# États d'un lot : le dossier qui le contient
IN_REVIEW, PENDING = "in_review", "pending"


class LotError(Exception):
    """Lot invalide : nom, manifeste, `_decisions.csv` modifié à tort, emplacement."""


@dataclass(frozen=True)
class Action:
    """Une action proposée par le bot, c'est-à-dire une ligne de `_decisions.csv`.

    Attributes:
        id: Identifiant unique dans le lot.
        action: Nature de l'action, propre au mod (« tag », « replace »…).
        before: État actuel, tel que le mod le relira pour vérifier que rien n'a changé.
        after: État proposé.
        reason: Pourquoi le bot le propose.
    """

    id: str
    action: str
    before: str
    after: str
    reason: str

    def to_json(self) -> dict:
        """Action telle qu'écrite dans le manifeste."""
        return {"id": self.id, "action": self.action, "before": self.before, "after": self.after, "reason": self.reason}

    @classmethod
    def from_json(cls, d: dict) -> Action:
        """Action relue du manifeste.

        Raises:
            KeyError: Champ manquant.
        """
        return cls(*(str(d[k]) for k in ("id", "action", "before", "after", "reason")))


@dataclass
class Manifest:
    """Contenu de `_lot.json`.

    Attributes:
        name: Nom du lot, qui est aussi celui de son dossier.
        mod: Mod qui a préparé le lot et qui applique ses actions.
        operation: Opération du mod (« replaygain », « sort »…).
        created: Date de création du lot.
        version: Version du programme qui a préparé le lot.
        actions: Actions proposées, dans l'ordre de `_decisions.csv`.
        done: Lignes déjà traitées par une passe précédente : identifiant -> état
            (`APPLIED`, `REFUSED` ou `FAILED`).
    """

    name: str
    mod: str
    operation: str
    created: dt.datetime
    version: str
    actions: tuple[Action, ...]
    done: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict:
        """Contenu du manifeste."""
        return {
            "lot": self.name,
            "mod": self.mod,
            "operation": self.operation,
            "created": self.created.isoformat(timespec="seconds"),
            "version": self.version,
            "actions": [a.to_json() for a in self.actions],
            "done": dict(self.done),
        }

    @classmethod
    def from_json(cls, d: dict) -> Manifest:
        """Manifeste relu de `_lot.json`.

        Raises:
            KeyError, ValueError, TypeError: Contenu incomplet ou mal formé.
        """
        return cls(
            name=str(d["lot"]),
            mod=str(d["mod"]),
            operation=str(d["operation"]),
            created=dt.datetime.fromisoformat(d["created"]),
            version=str(d["version"]),
            actions=tuple(Action.from_json(a) for a in d["actions"]),
            done={str(k): str(v) for k, v in d.get("done", {}).items()},
        )


@dataclass(frozen=True)
class Decision:
    """Décision de l'opérateur sur une action.

    Attributes:
        action: L'action concernée.
        decision: `YES`, `NO`, ou « » si la ligne n'est pas encore décidée.
        comment: Texte libre ; dans `_pending`, la réponse à la question du bot.
    """

    action: Action
    decision: str
    comment: str


def check_name(name: str) -> None:
    """Refuse un nom de lot qui ne serait pas un simple nom de dossier.

    Raises:
        LotError: Nom vide, avec séparateur, « . », « .. » ou commençant par « _ ».
    """
    if not name or name in {".", ".."} or "/" in name or "\\" in name or name.startswith("_"):
        raise LotError(f"Nom de lot invalide : {name!r}")


def program_path(bot: Path) -> Path:
    """Chemin du programme compilé dans l'installation de production (`paths.bot`)."""
    return Path(bot) / PROGRAM_NAME


def write_manifest(folder: Path, manifest: Manifest) -> None:
    """Écrit (ou réécrit) `_lot.json` dans le dossier du lot."""
    (Path(folder) / MANIFEST_NAME).write_text(json.dumps(manifest.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")


def read_manifest(folder: Path) -> Manifest:
    """Relit `_lot.json`.

    Raises:
        LotError: Manifeste absent ou illisible.
    """
    path = Path(folder) / MANIFEST_NAME
    if not path.is_file():
        raise LotError(f"{folder} n'est pas un lot : {MANIFEST_NAME} absent")
    try:
        return Manifest.from_json(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        raise LotError(f"{path} illisible : {e}") from e


def write_decisions(folder: Path, actions: tuple[Action, ...] | list[Action]) -> None:
    """Écrit `_decisions.csv`, colonnes `decision` et `comment` vides.

    Le BOM (`utf-8-sig`) indique à Excel que le fichier est en UTF-8 (sinon les accents
    sont mal lus), et le « ; » est le séparateur qu'Excel attend en français.
    """
    with open(Path(folder) / DECISIONS_NAME, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\r\n")
        writer.writerow(COLUMNS)
        for a in actions:
            writer.writerow([a.id, a.action, a.before, a.after, a.reason, "", ""])


def _decode(data: bytes) -> tuple[str, str]:
    """Texte de `_decisions.csv`, en UTF-8 (avec ou sans BOM), sinon en cp1252.

    Excel réenregistre parfois le fichier en « CSV (séparateur : point-virgule) »,
    c'est-à-dire dans l'encodage Windows (cp1252), sans BOM : le relire en UTF-8
    échouerait sur le premier accent. Un texte valide en UTF-8 l'est presque
    toujours vraiment, d'où cet ordre.

    Returns:
        Le texte et l'encodage reconnu.
    """
    try:
        return data.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), "cp1252"


def _as_saved(value: str, encoding: str) -> str:
    """Valeur telle qu'elle revient d'un fichier réenregistré dans `encoding`.

    En cp1252, Excel remplace par « ? » les caractères absents (« − », « → »…) : on
    compare donc la valeur du manifeste après la même perte, pour ne pas prendre ce
    remplacement pour une modification de l'opérateur.
    """
    if encoding == "utf-8":
        return value
    return value.encode(encoding, errors="replace").decode(encoding)


def read_decisions(folder: Path, manifest: Manifest) -> list[Decision]:
    """Relit et valide `_decisions.csv`, modifié par l'opérateur.

    Les lignes entièrement vides (ajoutées par Excel en fin de fichier) sont ignorées.

    Args:
        folder: Dossier du lot.
        manifest: Manifeste du lot, qui fait foi pour les colonnes écrites par le bot.

    Returns:
        Une décision par action, dans l'ordre du manifeste.

    Raises:
        LotError: Fichier absent, en-tête modifié, identifiant inconnu, en double ou
            manquant, colonne du bot modifiée, ou valeur inconnue dans `decision` ; le
            message donne la ligne en cause.
    """
    path = Path(folder) / DECISIONS_NAME
    if not path.is_file():
        raise LotError(f"{DECISIONS_NAME} absent de {folder}")
    text, encoding = _decode(path.read_bytes())
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";")
    known = {a.id: a for a in manifest.actions}
    found: dict[str, Decision] = {}
    header = None
    for row in reader:
        line = reader.line_num
        if not any(cell.strip() for cell in row):
            continue
        if header is None:
            header = tuple(cell.strip().lower() for cell in row)
            if header != COLUMNS:
                raise LotError(f"{DECISIONS_NAME}, ligne {line} : en-tête modifié ; attendu {';'.join(COLUMNS)}")
            continue
        if len(row) > len(COLUMNS):
            raise LotError(f"{DECISIONS_NAME}, ligne {line} : {len(row)} colonnes au lieu de {len(COLUMNS)}")
        # Excel peut omettre les « ; » des dernières cellules vides
        values = dict(zip(COLUMNS, [*row, *[""] * (len(COLUMNS) - len(row))], strict=True))
        ident = values["id"].strip()
        action = known.get(ident)
        if action is None:
            raise LotError(f"{DECISIONS_NAME}, ligne {line} : identifiant inconnu {ident!r}")
        if ident in found:
            raise LotError(f"{DECISIONS_NAME}, ligne {line} : identifiant {ident!r} en double")
        for column in FIXED:
            if values[column].strip() != _as_saved(getattr(action, column), encoding).strip():
                raise LotError(f"{DECISIONS_NAME}, ligne {line} : colonne {column} modifiée (id {ident}) ; seules decision et comment se remplissent")
        answer = values["decision"].strip().lower()
        if answer and answer not in ANSWERS:
            raise LotError(
                f"{DECISIONS_NAME}, ligne {line} : decision {values['decision']!r} inconnue (id {ident}) ; "
                "écrire yes, no (ou oui, non), ou laisser vide"
            )
        found[ident] = Decision(action, ANSWERS.get(answer, ""), values["comment"].strip())
    if header is None:
        raise LotError(f"{DECISIONS_NAME} est vide")
    missing = [a.id for a in manifest.actions if a.id not in found]
    if missing:
        raise LotError(f"{DECISIONS_NAME} : ligne(s) supprimée(s), identifiant(s) {', '.join(missing)}")
    return [found[a.id] for a in manifest.actions]


def write_bat(folder: Path, exe: Path) -> None:
    """Écrit `traiter.bat`, qui lance « disco lot » sur le dossier du lot.

    Le fichier ne contient aucune logique : seulement le chemin du programme, connu à
    la création du lot, et un message clair si le programme a été déplacé depuis.

    `%~dp0` est le dossier du `.bat`, terminé par « \\ ». Entre guillemets, ce « \\ »
    final échapperait le guillemet fermant (`"X:\\lot\\"` serait lu `X:\\lot"`) : on
    ajoute donc « . », qui désigne le même dossier.

    Le fichier est en UTF-8 sans BOM (un BOM casserait la première commande), lu
    correctement grâce à `chcp 65001`, et avec des fins de ligne Windows.
    """
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f'if not exist "{exe}" (',
        f"  echo Programme introuvable : {exe}",
        "  echo Le dossier _bot a sans doute été déplacé depuis la création du lot.",
        '  echo Lancer à la main : disco lot "%~dp0."',
        "  pause",
        "  exit /b 1",
        ")",
        f'"{exe}" lot "%~dp0."',
        "pause",
    ]
    (Path(folder) / BAT_NAME).write_text("\r\n".join(lines) + "\r\n", encoding="utf-8", newline="")


def create(
    parent: Path,
    name: str,
    mod: str,
    operation: str,
    actions: list[Action],
    report: str,
    exe: Path,
    now: dt.datetime | None = None,
) -> Path:
    """Crée un dossier de lot : manifeste, rapport, `_decisions.csv` et `traiter.bat`.

    Les copies retravaillées éventuelles sont ajoutées ensuite par le mod dans le
    dossier renvoyé.

    Args:
        parent: `paths.in_review` (proposition) ou `paths.pending` (question).
        name: Nom du lot, nouveau.
        mod: Mod qui appliquera les actions (clé de `src.core.lots.MODS`).
        operation: Opération du mod.
        actions: Actions proposées, identifiants uniques.
        report: Contenu de `_lot.md` (Markdown).
        exe: Programme lancé par `traiter.bat` (`program_path(cfg.bot)`).
        now: Date de création ; l'heure courante par défaut (utile aux tests).

    Returns:
        Le dossier du lot.

    Raises:
        LotError: Nom invalide, lot déjà présent, aucune action ou identifiants en
            double.
    """
    check_name(name)
    folder = Path(parent) / name
    if folder.exists():
        raise LotError(f"Le lot {folder} existe déjà")
    ids = [a.id for a in actions]
    if not ids:
        raise LotError(f"Lot {name} sans action")
    if len(set(ids)) != len(ids):
        raise LotError(f"Lot {name} : identifiants d'action en double")
    manifest = Manifest(name, mod, operation, (now or dt.datetime.now()).replace(microsecond=0), __version__, tuple(actions))
    folder.mkdir(parents=True)
    write_manifest(folder, manifest)
    (folder / REPORT_NAME).write_text(report, encoding="utf-8")
    write_decisions(folder, manifest.actions)
    write_bat(folder, exe)
    return folder


def state_of(folder: Path, in_review: Path, pending: Path) -> str:
    """État d'un lot d'après le dossier qui le contient.

    Returns:
        `IN_REVIEW` ou `PENDING`.

    Raises:
        LotError: Le lot n'est ni dans `in_review` ni dans `pending`.
    """
    parent = Path(folder).resolve().parent
    if parent == Path(in_review).resolve():
        return IN_REVIEW
    if parent == Path(pending).resolve():
        return PENDING
    raise LotError(f"{folder} n'est ni dans {in_review} ni dans {pending}")


def find_lots(in_review: Path, pending: Path) -> list[tuple[str, Path]]:
    """Lots présents, ceux à valider d'abord, chacun avec son état.

    Un dossier sans manifeste est ignoré : ce n'est pas un lot.
    """
    found = []
    for state, parent in ((IN_REVIEW, Path(in_review)), (PENDING, Path(pending))):
        if parent.is_dir():
            found += [(state, p) for p in sorted(parent.iterdir()) if (p / MANIFEST_NAME).is_file()]
    return found


def move(folder: Path, parent: Path) -> Path:
    """Déplace un lot dans un autre état (de `pending` vers `in_review`).

    Raises:
        LotError: Un lot du même nom existe déjà à l'arrivée.
    """
    target = Path(parent) / Path(folder).name
    if target.exists():
        raise LotError(f"Le lot {target} existe déjà")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(folder, target)
    return target


def archive(folder: Path, trash_dir: Path, logs: Path, log: Callable[[str], None], now: dt.datetime | None = None) -> trash.Lot:
    """Met un lot entièrement traité dans la corbeille, en entier.

    Le lot de corbeille s'appelle `<lot>_done`, distinct de ceux qui reçoivent les
    fichiers remplacés. Les chemins y sont relatifs au dossier parent du lot, pour que
    le `_lot.json` du lot ne se confonde pas avec le manifeste de la corbeille. Les
    dossiers vides qui restent ensuite sont retirés.
    """
    folder = Path(folder)
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    result = trash.put(files, folder.parent, trash_dir, logs, f"{folder.name}_done", "lot", log, now)
    for d in sorted((p for p in folder.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        d.rmdir()
    folder.rmdir()
    return result


def confirm(text: str, ask: Callable[[str], str] = input, question: str = "Appliquer ?") -> bool:
    """Affiche un résumé et demande confirmation, non par défaut.

    Args:
        text: Résumé de ce qui va être fait.
        ask: Fonction de saisie (`input` ; les tests en passent une autre).
        question: Question posée après le résumé.

    Returns:
        Vrai seulement si l'opérateur répond oui (« o », « oui », « y », « yes »).
        Une entrée fermée (pas de console) vaut non.
    """
    try:
        answer = ask(f"{text}\n{question} (o/N) ")
    except EOFError:
        return False
    return ANSWERS.get(answer.strip().lower()) == YES
