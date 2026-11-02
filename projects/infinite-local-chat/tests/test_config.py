from pathlib import Path

import pytest

from ilc.config import Budget, Config, ConfigError, Model, Server, default_data_dir, load_config


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ILC_HOME", str(tmp_path / "ilc-home"))
    return tmp_path


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_are_valid_and_match_design():
    config = load_config()
    # Design §4.4: ~8k-token prompt inside a 16k window.
    assert config.budget.prompt_total == 8800
    assert config.model.context_window == 16384
    assert config.budget.prompt_total + config.model.max_reply_tokens <= 16384
    assert config.server.host == "127.0.0.1"
    assert config.model.thinking_default is False


def test_ilc_home_controls_data_dir(isolated_home):
    assert default_data_dir() == isolated_home / "ilc-home"
    assert load_config().db_path == isolated_home / "ilc-home" / "memory.db"


def test_missing_file_means_defaults(tmp_path):
    assert load_config(tmp_path / "nope.toml") == load_config()


def test_overrides_apply(tmp_path):
    path = write(
        tmp_path / "c.toml",
        "[server]\napp_port = 9000\n[budget]\nrecent = 6000\n[model]\nthinking_default = true\n",
    )
    config = load_config(path)
    assert config.server.app_port == 9000
    assert config.budget.recent == 6000
    assert config.model.thinking_default is True
    assert config.server.chat_port == Server().chat_port  # untouched keys keep defaults


def test_data_dir_override_expands_user(tmp_path):
    config = load_config(write(tmp_path / "c.toml", 'data_dir = "~/elsewhere"\n'))
    assert config.data_dir == Path("~/elsewhere").expanduser()


def test_default_file_location_is_inside_data_dir(isolated_home):
    home = isolated_home / "ilc-home"
    home.mkdir()
    write(home / "config.toml", "[server]\nidle_minutes = 5\n")
    assert load_config().server.idle_minutes == 5


@pytest.mark.parametrize(
    "toml, message",
    [
        ("[server]\nport = 1\n", "unknown key"),
        ("[serverr]\n", "unknown section"),
        ('[server]\napp_port = "8765"\n', "must be int"),
        ("[server]\napp_port = true\n", "must be int"),
        ("[model]\nthinking_default = 1\n", "must be bool"),
        ("server = 3\n", "must be a table"),
        ("data_dir = 3\n", "string path"),
        ("[server\n", "c.toml"),
    ],
)
def test_malformed_files_are_rejected(tmp_path, toml, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path / "c.toml", toml))


@pytest.mark.parametrize(
    "config, message",
    [
        (Config(server=Server(host="0.0.0.0")), "loopback"),
        (Config(server=Server(app_port=80)), "1024-65535"),
        (Config(server=Server(chat_port=8765)), "distinct"),
        (Config(server=Server(idle_minutes=-1)), "idle_minutes"),
        (Config(budget=Budget(recall=0)), "positive"),
        (Config(model=Model(max_reply_tokens=0)), "max_reply_tokens"),
        (Config(budget=Budget(recent=20000)), "exceeds model.context_window"),
        (Config(model=Model(context_window=4096)), "exceeds model.context_window"),
    ],
)
def test_inconsistent_values_are_rejected(config, message):
    with pytest.raises(ConfigError, match=message):
        config.validate()


def test_budget_exactly_filling_window_is_allowed():
    budget = Budget()
    model = Model(context_window=budget.prompt_total + 2048, max_reply_tokens=2048)
    Config(model=model, budget=budget).validate()
