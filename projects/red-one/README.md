# Red One

A voice-activated, human-in-the-loop AI team. You talk to Claude; Claude clarifies, plans, waits for
your approval, and keeps you posted. Everything runs in the cloud; nothing is installed on your Mac.

**Status:** M1 in progress (story 1 of 6: scaffold). The page currently only shows that the server
is running and whether it's in stub or live mode. Plan: [`docs/roadmap.md`](docs/roadmap.md);
M1 design: [`docs/design.md`](docs/design.md).

## Run it (GitHub Codespaces, in your browser)
1. On GitHub, open the repo, switch to the **`project/red-one`** branch.
2. **Code → Codespaces → ⋯ → New with options.** Choose branch `project/red-one` and dev container
   configuration **Red One**. Create.
3. When the codespace is ready, in its terminal run:
   ```
   make run
   ```
4. Open the **PORTS** tab. Port **8765** ("Red One") must show **Visibility: Private**. Click the
   globe icon to open it in a new browser tab. Open it as a tab, not in the editor's preview pane;
   the page refuses to be framed.
5. Stop with `Ctrl+C`. Stop the codespace from github.com/codespaces when done, so it doesn't use
   your free hours.

**Stub mode vs live mode.** Without an `ANTHROPIC_API_KEY`, Red One runs in **stub mode**: scripted
replies, zero cost. To enable real Claude replies later, add the key at
**GitHub → Settings → Codespaces → Secrets** with access to this repository, then rebuild the
codespace. Never paste the key into code or chat.

## Develop
```
make install   # editable install with dev tools
make test      # pytest (no API key needed; live tests are skipped)
make lint      # ruff check + format check
```

## Security notes
- Binds to `127.0.0.1` only; reachable through Codespaces **private** port forwarding, which needs
  your GitHub sign-in.
- Strict Content-Security-Policy and other security headers on every response; API docs pages off.
- CI: ruff (including bandit-style `S` rules), pytest, gitleaks secret scan, pip-audit.
