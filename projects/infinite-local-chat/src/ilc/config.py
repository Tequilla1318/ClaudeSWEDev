"""Configuration: defaults in code, optional overrides from ``~/.ilc/config.toml``.

The token budgets mirror design §4.4. They are validated so that the assembled prompt plus the
reply always fits in the model's context window.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class ConfigError(ValueError):
    """Raised when the configuration file is malformed or the values are inconsistent."""


@dataclass(frozen=True)
class Budget:
    """Token budget per prompt section (design §4.4)."""

    system: int = 300
    core_memory: int = 500
    summary: int = 1000
    recent: int = 4000
    recall: int = 2000
    user_message: int = 1000

    @property
    def prompt_total(self) -> int:
        """Maximum number of prompt tokens the assembler may produce."""
        return sum(getattr(self, f.name) for f in fields(self))


@dataclass(frozen=True)
class Server:
    """Network and process settings. Everything binds to loopback only."""

    host: str = "127.0.0.1"
    app_port: int = 8765
    chat_port: int = 8080
    embed_port: int = 8081
    idle_minutes: int = 30


@dataclass(frozen=True)
class Model:
    """Model runtime settings."""

    context_window: int = 16384
    max_reply_tokens: int = 2048
    thinking_default: bool = False


@dataclass(frozen=True)
class Config:
    """Full application configuration."""

    data_dir: Path = field(default_factory=lambda: default_data_dir())
    server: Server = field(default_factory=Server)
    model: Model = field(default_factory=Model)
    budget: Budget = field(default_factory=Budget)

    @property
    def db_path(self) -> Path:
        """Path of the SQLite memory database."""
        return self.data_dir / "memory.db"

    def validate(self) -> None:
        """Raise :class:`ConfigError` if values are out of range or inconsistent."""
        s, m, b = self.server, self.model, self.budget
        if s.host not in LOOPBACK_HOSTS:
            raise ConfigError(f"server.host must be a loopback address, got {s.host!r}")
        ports = (s.app_port, s.chat_port, s.embed_port)
        if any(not 1024 <= p <= 65535 for p in ports):
            raise ConfigError(f"ports must be in 1024-65535, got {ports}")
        if len(set(ports)) != len(ports):
            raise ConfigError(f"ports must be distinct, got {ports}")
        if s.idle_minutes < 0:
            raise ConfigError("server.idle_minutes must be >= 0 (0 disables idle shutdown)")
        if any(getattr(b, f.name) <= 0 for f in fields(b)):
            raise ConfigError("every budget section must be a positive token count")
        if m.max_reply_tokens <= 0:
            raise ConfigError("model.max_reply_tokens must be positive")
        needed = b.prompt_total + m.max_reply_tokens
        if needed > m.context_window:
            raise ConfigError(
                f"budget ({b.prompt_total}) + max_reply_tokens ({m.max_reply_tokens}) = {needed} "
                f"exceeds model.context_window ({m.context_window})"
            )


def default_data_dir() -> Path:
    """Return the data directory: ``$ILC_HOME`` if set, else ``~/.ilc``."""
    env = os.environ.get("ILC_HOME")
    return Path(env).expanduser() if env else Path.home() / ".ilc"


_SECTIONS: dict[str, type] = {"server": Server, "model": Model, "budget": Budget}


def _apply_section(base: Any, name: str, values: Any) -> Any:
    if not isinstance(values, dict):
        raise ConfigError(f"[{name}] must be a table")
    known = {f.name: f for f in fields(base)}
    unknown = set(values) - set(known)
    if unknown:
        raise ConfigError(f"unknown key(s) in [{name}]: {', '.join(sorted(unknown))}")
    for key, value in values.items():
        expected = type(getattr(base, key))
        # bool is a subclass of int; keep the two strictly apart to catch typos like `port = true`.
        if isinstance(value, bool) != (expected is bool) or not isinstance(value, expected):
            raise ConfigError(f"[{name}].{key} must be {expected.__name__}, got {value!r}")
    return replace(base, **values)


def load_config(path: Path | None = None) -> Config:
    """Load configuration, applying overrides from a TOML file if it exists.

    Args:
        path: Config file to read. Defaults to ``<data_dir>/config.toml``. A missing file means
            "use defaults".

    Returns:
        A validated :class:`Config`.

    Raises:
        ConfigError: If the file is malformed, has unknown keys or wrong types, or the resulting
            values are inconsistent.
    """
    config = Config()
    path = path or config.data_dir / "config.toml"
    if path.is_file():
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{path}: {exc}") from exc
        unknown = set(raw) - set(_SECTIONS) - {"data_dir"}
        if unknown:
            raise ConfigError(f"unknown section(s) in {path}: {', '.join(sorted(unknown))}")
        updates: dict[str, Any] = {
            name: _apply_section(getattr(config, name), name, raw[name])
            for name in _SECTIONS
            if name in raw
        }
        if "data_dir" in raw:
            if not isinstance(raw["data_dir"], str):
                raise ConfigError("data_dir must be a string path")
            updates["data_dir"] = Path(raw["data_dir"]).expanduser()
        config = replace(config, **updates)
    config.validate()
    return config
