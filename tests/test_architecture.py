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
    2.0

Date de création :
    2026.10.08

Date de modification :
    2026.10.09
"""

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
PACKAGE = "src"
LAYERS = {"core", "backend", "UI", "assets", "mod"}

# Modules de la racine de `src` qui peuvent importer le paquet (points d'entrée)
ENTRY_POINTS = {"__main__"}

# Couches que chacune peut importer, en plus d'elle-même (un mod : lui seul, pas les autres)
ALLOWED = {
    "core": {"backend", "UI", "assets", "mod"},
    "mod": {"backend", "UI", "assets"},
    "UI": {"backend", "assets"},
    "backend": {"assets"},
}


def layer(module: str) -> str | None:
    """Couche d'un module du paquet : « core », « backend », « UI », « mod.<nom> »…

    Args:
        module: Nom pointé (« src.mod.copies.dap »).

    Returns:
        La couche, « mod.<nom> » pour un mod, ou None hors du paquet ou à sa racine
        (`__main__.py`, point d'entrée comme core).
    """
    parts = module.split(".")
    if parts[0] != PACKAGE or len(parts) < 2 or parts[1] not in LAYERS:
        return None
    if parts[1] == "mod" and len(parts) >= 3:
        return f"mod.{parts[2]}"
    return parts[1]


def module_name(file: Path, src: Path = SRC) -> str:
    """Nom pointé d'un fichier de `src` (`src/mod/copies/dap.py` → « src.mod.copies.dap »)."""
    parts = list(file.relative_to(src.parent).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imported(file: Path, src: Path = SRC) -> set[str]:
    """Modules importés par un fichier, imports relatifs résolus.

    Pour « from a import b », donne « a.b » : `b` peut être un sous-module (« from src
    import mod »), et la couche se lit de toute façon sur le début du nom.
    """
    tree = ast.parse(file.read_text(encoding="utf-8"))
    package = module_name(file, src).split(".")
    if file.name != "__init__.py":
        package.pop()
    names: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            base = package[: len(package) - n.level + 1] if n.level else []
            module = ".".join([*base, *([n.module] if n.module else [])])
            names.update(f"{module}.{a.name}" for a in n.names)
    return names


def violations(src: Path = SRC) -> list[str]:
    """Imports interdits par la règle de dépendance, sous la forme « fichier → module »."""
    found = []
    for file in sorted(src.rglob("*.py")):
        source = layer(module_name(file, src))
        if file.parent == src and file.stem not in ENTRY_POINTS:
            # module feuille de la racine : n'importe rien du paquet
            found += [f"{file.relative_to(src.parent).as_posix()} → {m}" for m in sorted(imported(file, src)) if m.split(".")[0] == PACKAGE]
            continue
        if source is None or source == "core":
            continue
        family = source.split(".")[0]
        for module in sorted(imported(file, src)):
            target = layer(module)
            if target is None or target == source:
                continue
            if target.split(".")[0] not in ALLOWED[family]:
                found.append(f"{file.relative_to(src.parent).as_posix()} → {module}")
    return found


def test_dependency_rule():
    assert violations() == []


def test_known_layers():
    folders = {d.name for d in SRC.iterdir() if d.is_dir() and d.name != "__pycache__"}
    assert folders <= LAYERS, f"dossier hors couche : {', '.join(sorted(folders - LAYERS))}"


def _write(root: Path, path: str, text: str = "") -> None:
    """Écrit un fichier Python fictif sous `root/src`."""
    f = root / "src" / path
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "text", "forbidden"),
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
def test_violations_detected(tmp_path, path, text, forbidden):
    _write(tmp_path, path, text)
    assert violations(tmp_path / "src") == [f"src/{path} → {forbidden}"]


def test_allowed_imports(tmp_path):
    _write(tmp_path, "core/cli.py", "from src.mod.a import x\nfrom src.backend import c\n")
    _write(tmp_path, "mod/a/x.py", "from src.backend import c\nfrom . import y\nimport os\n")
    _write(tmp_path, "mod/a/y.py", "from src.mod.a import x\n")
    _write(tmp_path, "UI/z.py", "from src.backend.config import load\n")
    _write(tmp_path, "mod/a/v.py", "from src.__versions__ import __version__\n")
    _write(tmp_path, "backend/v.py", "from src import __versions__\n")
    _write(tmp_path, "__main__.py", "from src.core.cli import main\n")
    _write(tmp_path, "__versions__.py", "import tomllib\n__version__ = '0'\n")
    assert violations(tmp_path / "src") == []
