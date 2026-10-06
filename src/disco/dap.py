"""Synchronisation de la discothèque avec le baladeur (DAP), par robocopy.

Deux sens :
- **envoi** : la discothèque est recopiée en miroir sur le DAP (`/MIR`), sauf le dossier
  d'arrivées (transporté par le DAP, jamais écrasé) et la sortie générée `_discotheque` ;
- **récupération** : le dossier d'arrivées du DAP est copié vers celui de la discothèque,
  sans rien supprimer.

Les chemins viennent de la configuration (`[chemins]`, `[dap]`). robocopy n'existe que
sous Windows : ailleurs, seule la simulation (affichage de la commande) est possible.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path, PureWindowsPath

from disco.config import Config, ErreurConfig

# Options communes : copie robuste, reprise, nouvelles tentatives limitées, pas de pourcentage
OPTIONS_COMMUNES = ["/FFT", "/Z", "/R:3", "/W:5", "/NP"]


def _w(p: Path | str) -> PureWindowsPath:
    return PureWindowsPath(str(p))


def _destination(cfg: Config) -> PureWindowsPath:
    if cfg.dap.destination is None:
        raise ErreurConfig("Section [dap] : clé « destination » absente de config.toml.")
    return _w(cfg.dap.destination)


def _journal(cfg: Config, sens: str, maintenant: dt.datetime) -> PureWindowsPath:
    return _w(cfg.journaux) / "dap" / f"{maintenant:%Y-%m-%d_%H%M}_{sens}.log"


def exclusions_envoi(cfg: Config) -> list[str]:
    """Dossiers jamais recopiés ni purgés lors de l'envoi."""
    src, dst = _w(cfg.musique), _destination(cfg)
    exclus = [src / cfg.dap.arrivees, dst / cfg.dap.arrivees]
    sortie = _w(cfg.sortie)
    if sortie.is_relative_to(src):
        exclus += [sortie, dst / sortie.relative_to(src)]
    return [str(p) for p in exclus]


def commande_envoi(cfg: Config, simulation: bool = False, maintenant=None) -> list[str]:
    maintenant = maintenant or dt.datetime.now()
    args = ["robocopy", str(_w(cfg.musique)), str(_destination(cfg)), "/MIR", "/MT:32"]
    args += OPTIONS_COMMUNES
    args += ["/XD", *exclusions_envoi(cfg), "/XF", "desktop.ini"]
    args += [f"/LOG:{_journal(cfg, 'PC_vers_DAP', maintenant)}", "/TEE"]
    return args + (["/L"] if simulation else [])


def commande_recuperation(cfg: Config, simulation: bool = False, maintenant=None) -> list[str]:
    maintenant = maintenant or dt.datetime.now()
    src = _destination(cfg) / cfg.dap.arrivees
    dst = _w(cfg.musique) / cfg.dap.arrivees
    args = ["robocopy", str(src), str(dst), "/E", "/COPY:DAT", *OPTIONS_COMMUNES]
    args += [f"/LOG:{_journal(cfg, 'DAP_vers_PC', maintenant)}", "/TEE"]
    return args + (["/L"] if simulation else [])


def executer(args: list[str], journaux: Path) -> int:
    """Lance robocopy ; renvoie 0 si tout va bien (robocopy : code < 8), 1 sinon."""
    (Path(journaux) / "dap").mkdir(parents=True, exist_ok=True)
    code = subprocess.run(args).returncode
    return 0 if code < 8 else 1
