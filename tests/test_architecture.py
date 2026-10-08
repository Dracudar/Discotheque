"""
test_architecture.py - Garde-fou de la règle de dépendance entre couches

Description:
    Lit les `import` de chaque fichier de `src` (y compris ceux faits dans une fonction)
    et échoue si une couche importe ce qu'elle n'a pas le droit d'importer (voir
    docs/ARCHITECTURE.md) :
      - core peut tout importer ;
      - un mod n'importe que backend, UI et lui-même, jamais un autre mod ni core ;
      - UI n'importe que backend ;
      - backend n'importe que lui-même, jamais core, UI ni mod ;
      - les modules à la racine de `src` (`__versions__.py`), lisibles par toutes les
        couches, n'importent rien du paquet (sauf `__main__.py`, point d'entrée).
    Vérifie aussi que chaque dossier de `src` est une couche connue.

Auteur :
    Dracudar

Version :
    1.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.08
"""

import ast
from pathlib import Path

import pytest

DEPOT = Path(__file__).resolve().parents[1]
SRC = DEPOT / "src"
PAQUET = "src"
COUCHES = {"core", "backend", "UI", "assets", "mod"}

# Modules de la racine de `src` qui peuvent importer le paquet (points d'entrée)
ENTREES = {"__main__"}

# Couches que chacune peut importer, en plus d'elle-même (un mod : lui seul, pas les autres)
AUTORISE = {
    "core": {"backend", "UI", "assets", "mod"},
    "mod": {"backend", "UI", "assets"},
    "UI": {"backend", "assets"},
    "backend": {"assets"},
}


def couche(module: str) -> str | None:
    """Couche d'un module du paquet : « core », « backend », « UI », « mod.<nom> »…

    Args:
        module: Nom pointé (« src.mod.copies.dap »).

    Returns:
        La couche, « mod.<nom> » pour un mod, ou None hors du paquet ou à sa racine
        (`__main__.py`, point d'entrée comme core).
    """
    parties = module.split(".")
    if parties[0] != PAQUET or len(parties) < 2 or parties[1] not in COUCHES:
        return None
    if parties[1] == "mod" and len(parties) >= 3:
        return f"mod.{parties[2]}"
    return parties[1]


def nom_module(fichier: Path, src: Path = SRC) -> str:
    """Nom pointé d'un fichier de `src` (`src/mod/copies/dap.py` → « src.mod.copies.dap »)."""
    parties = list(fichier.relative_to(src.parent).with_suffix("").parts)
    if parties[-1] == "__init__":
        parties.pop()
    return ".".join(parties)


def importes(fichier: Path, src: Path = SRC) -> set[str]:
    """Modules importés par un fichier, imports relatifs résolus.

    Pour « from a import b », donne « a.b » : `b` peut être un sous-module (« from src
    import mod »), et la couche se lit de toute façon sur le début du nom.
    """
    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    paquet = nom_module(fichier, src).split(".")
    if fichier.name != "__init__.py":
        paquet.pop()
    noms: set[str] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            noms.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            base = paquet[: len(paquet) - n.level + 1] if n.level else []
            module = ".".join([*base, *([n.module] if n.module else [])])
            noms.update(f"{module}.{a.name}" for a in n.names)
    return noms


def violations(src: Path = SRC) -> list[str]:
    """Imports interdits par la règle de dépendance, sous la forme « fichier → module »."""
    trouvees = []
    for fichier in sorted(src.rglob("*.py")):
        source = couche(nom_module(fichier, src))
        if fichier.parent == src and fichier.stem not in ENTREES:
            # module feuille de la racine : n'importe rien du paquet
            trouvees += [
                f"{fichier.relative_to(src.parent).as_posix()} → {m}"
                for m in sorted(importes(fichier, src))
                if m.split(".")[0] == PAQUET
            ]
            continue
        if source is None or source == "core":
            continue
        famille = source.split(".")[0]
        for module in sorted(importes(fichier, src)):
            cible = couche(module)
            if cible is None or cible == source:
                continue
            if cible.split(".")[0] not in AUTORISE[famille]:
                trouvees.append(f"{fichier.relative_to(src.parent).as_posix()} → {module}")
    return trouvees


def test_regle_de_dependance():
    assert violations() == []


def test_couches_connues():
    dossiers = {d.name for d in SRC.iterdir() if d.is_dir() and d.name != "__pycache__"}
    assert dossiers <= COUCHES, f"dossier hors couche : {', '.join(sorted(dossiers - COUCHES))}"


def _ecrire(racine: Path, chemin: str, texte: str = "") -> None:
    """Écrit un fichier Python fictif sous `racine/src`."""
    f = racine / "src" / chemin
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(texte, encoding="utf-8")


@pytest.mark.parametrize(
    ("chemin", "texte", "interdit"),
    [
        ("mod/a/x.py", "from src.mod.b import y\n", "src.mod.b.y"),
        ("mod/a/x.py", "from src.core import cli\n", "src.core.cli"),
        ("mod/a/x.py", "def f():\n    import src.mod.b.y\n", "src.mod.b.y"),
        ("mod/a/x.py", "from ..b import y\n", "src.mod.b.y"),
        ("mod/a/x.py", "from src import mod\n", "src.mod"),
        ("backend/x.py", "from src.mod.a import y\n", "src.mod.a.y"),
        ("backend/x.py", "from ..core import cli\n", "src.core.cli"),
        ("UI/x.py", "from src.mod.a import y\n", "src.mod.a.y"),
        ("__versions__.py", "from src.backend import config\n", "src.backend.config"),
        ("__versions__.py", "from . import core\n", "src.core"),
    ],
)
def test_violations_detectees(tmp_path, chemin, texte, interdit):
    _ecrire(tmp_path, chemin, texte)
    assert violations(tmp_path / "src") == [f"src/{chemin} → {interdit}"]


def test_imports_autorises(tmp_path):
    _ecrire(tmp_path, "core/cli.py", "from src.mod.a import x\nfrom src.backend import c\n")
    _ecrire(tmp_path, "mod/a/x.py", "from src.backend import c\nfrom . import y\nimport os\n")
    _ecrire(tmp_path, "mod/a/y.py", "from src.mod.a import x\n")
    _ecrire(tmp_path, "UI/z.py", "from src.backend.config import charger\n")
    _ecrire(tmp_path, "mod/a/v.py", "from src.__versions__ import __version__\n")
    _ecrire(tmp_path, "backend/v.py", "from src import __versions__\n")
    _ecrire(tmp_path, "__main__.py", "from src.core.cli import main\n")
    _ecrire(tmp_path, "__versions__.py", "import tomllib\n__version__ = '0'\n")
    assert violations(tmp_path / "src") == []
