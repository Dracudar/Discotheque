from disco.cli import main


def test_config(config_exemple, capsys):
    assert main(["--config", str(config_exemple), "config"]) == 0
    sortie = capsys.readouterr().out
    assert "Original Game Soundtrack" in sortie
    assert "crête vraie x8" in sortie


def test_config_absente(tmp_path, capsys):
    assert main(["--config", str(tmp_path / "rien.toml"), "config"]) == 2
