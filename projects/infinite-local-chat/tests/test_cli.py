import subprocess
import sys

import pytest

from ilc import __version__, cli
from ilc.doctor import Check, Status


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ILC_HOME", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize("argv", [[], ["start"], ["stop"], ["status"]])
def test_unimplemented_commands_say_which_story(argv, capsys):
    assert cli.main(argv) == 1
    assert "not implemented yet" in capsys.readouterr().err


def test_doctor_exit_code_follows_failures(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_checks", lambda _info: [Check("a", Status.WARN, "w")])
    assert cli.main(["doctor"]) == 0
    monkeypatch.setattr(cli, "run_checks", lambda _info: [Check("a", Status.FAIL, "f")])
    assert cli.main(["doctor"]) == 1
    assert "[fail] a" in capsys.readouterr().out


def test_config_prints_effective_values(isolated_home, capsys):
    (isolated_home / "config.toml").write_text("[server]\napp_port = 9001\n")
    assert cli.main(["config"]) == 0
    out = capsys.readouterr().out
    assert "'app_port': 9001" in out
    assert "budget.prompt_total = 8800" in out


def test_bad_config_exits_2(isolated_home, capsys):
    (isolated_home / "config.toml").write_text("[server]\nhost = '0.0.0.0'\n")
    assert cli.main(["doctor"]) == 2
    assert "loopback" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_installed_entry_point_runs(isolated_home):
    # Proves the package is importable as installed and the console script target resolves.
    result = subprocess.run(
        [sys.executable, "-c", "import sys; from ilc.cli import main; sys.exit(main(['config']))"],
        capture_output=True,
        text=True,
        env={"ILC_HOME": str(isolated_home), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
