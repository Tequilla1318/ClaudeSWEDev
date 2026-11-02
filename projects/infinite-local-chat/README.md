# infinite-local-chat

A local chat assistant for an Apple Silicon Mac: Qwen3.5-9B via llama.cpp, a browser chat UI
started with one command, and a memory layer so long conversations never lose information
while each turn uses a small, fixed number of tokens.

Status: **M1 in progress** — scaffold done (S1); the chat itself arrives in S2–S4.
See [docs/design.md](docs/design.md).

## Commands (so far)

| Command | What it does | Status |
|---|---|---|
| `ilc` / `ilc start` | start the model and open the chat in your browser | S2–S4 |
| `ilc stop`, `ilc status` | stop / show the model servers | S2 |
| `ilc doctor` | check this machine (macOS, Apple Silicon, RAM, disk, llama.cpp) | works |
| `ilc config` | print the effective configuration | works |

Settings go in `~/.ilc/config.toml` (set `ILC_HOME` to use another folder), for example:

```toml
[server]
idle_minutes = 60   # stop the model after an hour idle (0 = never)

[budget]
recent = 6000       # more recent messages verbatim in each prompt
```

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check . && pytest
```

- Context for resuming work: [docs/context.md](docs/context.md)
- Decision log: [docs/decisions.md](docs/decisions.md)
