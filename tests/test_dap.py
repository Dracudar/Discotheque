import datetime as dt

import pytest

from disco import config, dap
from disco.cli import main

MAINTENANT = dt.datetime(2026, 1, 2, 3, 4)


def cfg_exemple(**dap_section):
    return config.depuis_dict(
        {
            "chemins": {"musique": r"X:\Musique", "sortie": r"X:\Musique\_discotheque"},
            "dap": {"destination": r"X:\Baladeur\Music", **dap_section},
            "categories": {"Artists": {"type": "artistes"}},
        }
    )


def test_envoi_exclut_arrivees_et_sortie():
    args = dap.commande_envoi(cfg_exemple(), maintenant=MAINTENANT)
    assert args[:5] == ["robocopy", r"X:\Musique", r"X:\Baladeur\Music", "/MIR", "/MT:32"]
    xd = args[args.index("/XD") + 1 : args.index("/XF")]
    assert xd == [
        r"X:\Musique\_sort",
        r"X:\Baladeur\Music\_sort",
        r"X:\Musique\_discotheque",
        r"X:\Baladeur\Music\_discotheque",
    ]
    assert (
        r"/LOG:X:\Musique\_discotheque\_data\journaux\dap\2026-01-02_0304_PC_vers_DAP.log" in args
    )
    assert "/L" not in args


def test_sortie_hors_discotheque_non_exclue():
    cfg = config.depuis_dict(
        {
            "chemins": {"musique": r"X:\Musique", "sortie": r"X:\Pages"},
            "dap": {"destination": r"X:\Baladeur"},
            "categories": {"Artists": {"type": "artistes"}},
        }
    )
    assert dap.exclusions_envoi(cfg) == [r"X:\Musique\_sort", r"X:\Baladeur\_sort"]


def test_recuperation_sans_suppression():
    args = dap.commande_recuperation(cfg_exemple(arrivees="_arrivees"), simulation=True)
    assert args[1:3] == [r"X:\Baladeur\Music\_arrivees", r"X:\Musique\_arrivees"]
    assert "/E" in args and "/MIR" not in args and args[-1] == "/L"


def test_destination_absente():
    cfg = config.depuis_dict(
        {
            "chemins": {"musique": "M", "sortie": "S"},
            "categories": {"Artists": {"type": "artistes"}},
        }
    )
    with pytest.raises(config.ErreurConfig, match="destination"):
        dap.commande_envoi(cfg)


def test_cli_simulation(config_exemple, capsys, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    assert main(["--config", str(config_exemple), "dap", "envoyer", "--simulation"]) == 0
    sortie = capsys.readouterr().out
    assert "robocopy" in sortie and "/MIR" in sortie and "/L" in sortie
