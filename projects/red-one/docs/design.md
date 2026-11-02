# Design — red-one, Milestone 1: "Careful Claude" (text)

Status: **approved** (PR #26, 2026-11-02); owner answers folded in (§8).
Scope: M1 only. Later milestones are outlined in [`roadmap.md`](roadmap.md) and get their own
design section when they're next.

## 1. Goal
A private web chat with Claude that **behaves like a contractor with a client**: it asks clarifying
questions before doing anything, proposes a plan with a reason for each step, waits for the owner's
explicit approval, does the work while reporting anything important, and answers "why?" by drilling
down on demand. Runs free in GitHub Codespaces; nothing on the Mac.

Usable on its own: a thinking partner for any random idea that doesn't run off and guess.

## 2. Scope
**In:** text chat in the browser; the consult → plan → approve → work → report loop; "why" and
"teach me" on demand; a status report; saved projects you can resume; one model (Claude);
spending cap; Codespaces setup; CI with lint, tests and security scans; a threat model.

**Out (later milestones):** Gemini and delegation (M2), app-level login (M3), voice (M4), wake
phrase (M5), GitHub code execution (M6), passphrase approval (M7), phone (M8). Also out: web
search, code execution or any other external tool for Claude in M1 (structured replies use tool-call
format, but nothing outside the app runs). "Work" in M1 means Claude reasoning and writing in the
conversation (analysis, explanations, designs, pseudo-code), not running code or browsing.

## 3. What using it looks like
1. Owner opens the codespace from GitHub (one click from a saved link), runs `make run`, and opens
   the forwarded link in Chrome.
2. Owner: "What if we used flywheels instead of batteries for home energy storage?"
3. Claude **asks** 2–4 focused questions (scale? budget? depth: quick take or deep dive?).
4. Owner answers. Claude **proposes a plan**: numbered steps, each with *what* and *why*.
5. Owner clicks **Approve plan** (or types `/approve`), or asks for changes, which produces a revised
   plan.
6. Claude **works** through the steps one at a time. After each step: a short result. Anything
   surprising or decision-worthy is flagged ⚠ and Claude **pauses to ask** instead of guessing.
7. Owner can type at any time: "why did you rule out lithium?" → Claude drills down, then resumes.
   "/status" → where we are, what's done, what's next, open questions.
8. Claude delivers a **report**: what was found, the reasoning, open questions, suggested next steps.
9. Next day the owner reopens the project and Claude picks up from the saved state.

## 4. Architecture

```
Browser (Chrome, private forwarded port)
   │  JSON over HTTPS (GitHub-authenticated port forwarding)
   ▼
FastAPI app (localhost:8765 in the codespace)
   ├── web/        HTTP routes + static page (plain HTML/JS, no build step)
   ├── engine/     conversation state machine  ← deterministic; owns all transitions
   ├── team/       team-member config + provider adapters (Claude; Stub for tests)
   ├── budget/     token counting + spending cap
   └── store/      SQLite (projects, messages, plan, decisions, open questions)
```

Package layout: `projects/red-one/src/red_one/{web,engine,team,budget,store}`, tests in
`projects/red-one/tests/`. Python 3.11, FastAPI + Uvicorn, the official `anthropic` SDK,
Pydantic, stdlib `sqlite3`. Deliberately small dependency list (supply-chain risk).

### 4.1 The conversation engine (the core)
A state machine in plain Python. **Code, not Claude, decides which state we're in.**

| State | Claude may | Leaves when |
|---|---|---|
| `CLARIFYING` | `ask_questions`, `answer` | Claude calls `propose_plan` |
| `PLAN_PROPOSED` | `answer`, `propose_plan` (revision) | **owner** approves → `WORKING` |
| `WORKING` | `step_result`, `ask_questions` (→ `BLOCKED`), `answer`, `report` | `report` → `REPORTED` |
| `BLOCKED` | `answer` | owner replies → `WORKING` |
| `REPORTED` | `answer`, `ask_questions` (new round) | new request → `CLARIFYING` |

- Claude replies through **structured tool calls** (Anthropic tool use), e.g.
  `propose_plan(steps=[{what, why}])`, `step_result(step, summary, important: bool)`,
  `ask_questions(questions=[...])`, `report(findings, reasoning, open_questions, next_steps)`,
  `answer(text)` for "why"/teach/chat. The engine rejects a tool that isn't allowed in the current
  state and asks Claude again (max 2 retries, then shows an error).
- **Approval is an owner action only:** the Approve button or `/approve`. If Claude writes
  "approved" or "let's start", nothing happens. This is the M1 version of the rule that will later
  protect PR merges.
- **Interrupts:** the owner can send a message during `WORKING`; it's handled before the next step.
  `/pause` stops after the current step.
- **"Why" anytime:** any question is answered via `answer` with the project's saved plan, decisions
  and step results in context, so Claude explains from the record, not from a vague memory. Asking
  "deeper" continues the drill-down.
- **Important-only updates:** each `step_result` is shown briefly; `important=true` adds ⚠ and, if
  it changes the plan, Claude must use `ask_questions` (→ `BLOCKED`) rather than change course alone.

### 4.2 Team config and providers
`team.toml` (in the repo, no secrets):

```toml
[members.claude]
provider = "anthropic"
model = "claude-haiku-5-5"            # default for every turn
escalate_to = ["claude-sonnet-5-5", "claude-opus-5-5"]
escalate_without_asking = ["claude-sonnet-5-5"]
role = "lead"
monthly_cap_usd = 5.00
```

- **Start on Haiku, step up when the task needs it** (owner, PR #26). Claude can call an
  `escalate(model, reason)` tool for the current step. Code checks the model is in `escalate_to`
  and that the budget allows it. Sonnet is allowed automatically and shown to the owner
  ("⬆ using Sonnet for this step: <reason>"). Opus needs the owner's OK in the chat. Escalation lasts
  one step, then drops back to Haiku.

- One `Provider` interface (`send(messages, tools) -> ToolCall`) with `AnthropicProvider` and a
  `StubProvider` that replays scripted tool calls for tests. M2 adds `GeminiProvider` and a router;
  nothing in the engine changes.
- The API key comes only from the `ANTHROPIC_API_KEY` environment variable (a Codespaces secret).
  Missing key → the app starts in **stub mode** with a visible banner, so it's still usable for
  trying the flow at zero cost.
- Each message carries a `sensitivity` field (default `sensitive`) from day one, so M2's router can
  enforce "sensitive stays with Claude" without a data migration.

### 4.3 Budget
Token usage from each API response × a per-model price table in config → running monthly spend per member,
stored in SQLite. Before each call: if `spend + worst-case cost of this call > cap`, refuse and tell
the owner. Also a per-message `max_tokens`. Indicative cost at Haiku 5.5 prices ($0.10 / $0.50 per
million input/output tokens): a typical turn (~3k tokens in, ~0.5k out) is about $0.0006, so a
$5 cap is several thousand turns.

### 4.4 Store
SQLite file at `~/.red-one/red-one.db` inside the codespace (outside the repo, never committed).
Tables: `projects`, `messages`, `plans` (versioned), `steps`, `decisions`, `open_questions`,
`spend`. `/export` writes a project to Markdown for download. **Limitation:** deleting the codespace
deletes the data (export first). Nothing is stored on the Mac.

### 4.5 Front end
One static page: message list, input box, Approve button, state badge (Clarifying / Plan / Working /
Blocked / Done), project switcher, budget indicator. Plain HTML/CSS/JS served by FastAPI; no
third-party scripts or CDNs. Deliberately plain: the polished voice-first UI is M4.

## 5. Security (threat model v1 → `docs/security.md` in story 6)
| Asset / threat | Mitigation in M1 |
|---|---|
| API key leaks | Codespaces secret → env var only; never sent to the browser, never logged; secret scanning (gitleaks) in CI; `.env` ignored |
| Someone else reaches the room | Server binds `127.0.0.1`; reached only via Codespaces **private** port forwarding, which requires the owner's GitHub sign-in. Owner test step checks the port is private |
| Malicious content rendered as code (XSS) | All messages inserted as text (`textContent`, never `innerHTML`); strict Content-Security-Policy (no inline scripts, `self` only); tested |
| Cross-site requests (CSRF) | JSON-only API requiring a custom header + same-origin check |
| Cost abuse / runaway loops | Monthly cap, per-call `max_tokens`, retry limit |
| Supply chain | Few dependencies, pinned versions, `pip-audit` in CI |
| Data at rest | Only in the codespace; logs hold metadata (ids, states, token counts), not message text |
| Prompt injection | M1 has no external content; noted as the main new risk for M2 (Gemini output, web pages) |

## 6. Testing and validation
- **Unit/integration (CI, no API key, no cost):** every state transition; illegal tool per state is
  rejected; Claude text saying "approved" does **not** approve; owner `/approve` does; interrupts and
  `/pause`; budget refusal at the cap; store round-trip and resume; API routes via FastAPI
  `TestClient`; CSP header present; HTML escaping of a `<script>` message.
- **Live smoke test** (`pytest -m live`): one real Claude round-trip, skipped unless the key is set.
  Never runs in CI.
- **CI additions:** a project security job on the project branch (gitleaks + pip-audit) next to the
  existing ruff/pytest job.
- No numerical code in M1, so the reference-validation rule doesn't apply.
- **Owner acceptance test (M1 done when all pass):** open the codespace → `make run` → confirm the
  port shows *Private* → give a vague request → Claude asks before answering → refuse to approve and
  check nothing proceeds → approve → ask "why?" mid-work → `/status` → get a report → close, reopen,
  resume the project → `/export`.

## 7. Stories (one PR each, target `project/red-one`)
1. **Scaffold + Codespaces + CI.** `pyproject.toml`, package skeleton, `.devcontainer/red-one/`
   (Python 3.11, port 8765 private, `make run`), security CI job, README run steps.
   *Done when:* codespace starts from GitHub, `make run` serves a "hello" page on a private port, CI green.
2. **Team config, providers, budget.** `team.toml`, `AnthropicProvider`, `StubProvider`, stub mode,
   per-model prices, spending cap, `escalate` rules. *Done when:* tests cover cap refusal, stub replay
   and escalation rules; live smoke test passes once a key exists (skipped until then).
3. **Conversation engine.** State machine + tool schemas + owner-only approval.
   *Done when:* the transition table above is fully tested, including the "Claude says approved" case.
4. **Store.** SQLite schema, resume, export. *Done when:* a project survives an app restart.
5. **Web API + page.** Routes, page, Approve button, state badge, CSP, escaping.
   *Done when:* the full loop works in the browser (stub mode) and security tests pass.
6. **Why/status/report polish + threat model + release.** `/status`, drill-down context,
   `docs/security.md`, owner test guide, tag `red-one-v0.1.0`.
   *Done when:* owner acceptance test (§6) passes.

## 8. Owner answers (PR #26)
1. **Paying for Red One's Claude.** The owner asked to use the Pro plan ("use yourself"). Not
   possible: the Agent SDK docs state that apps built on Claude must use API-key authentication, not
   a claude.ai sign-in, and the Agent SDK falls under Anthropic's Commercial Terms, while Pro is a
   consumer plan. Using Pro would put the account that runs this whole dev workflow at risk. So
   **M1 is built and tested in stub mode**; real Claude replies switch on the moment an
   `ANTHROPIC_API_KEY` Codespaces secret exists ($5 prepaid, auto-reload off, recommended; or a Max
   plan's included monthly API credits). Nothing in M1 development is blocked.
2. **Model:** Haiku 5.5 by default, escalating to heavier models by task complexity (§4.2).
3. **Approval:** Approve button + `/approve` for M1. Yes.
4. **Data:** lives in the codespace with `/export` as the backup. Yes.

## 9. Decisions proposed in this doc
FastAPI + plain JS; deterministic state machine with tool-call replies; owner-only approval;
stub mode when no key; `sensitivity` field from day one; SQLite in the codespace; Haiku default with
code-checked escalation (Sonnet automatic, Opus with owner OK) under a $5 monthly cap; private port
forwarding as M1's access control. Recorded in `decisions.md`.

## 10. References
- Anthropic tool use (structured replies): https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview
- Claude API pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Monthly API credits for Max/Ultra/Team: https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-ultra-and-team-plans
- Agent SDK overview (authentication note): https://code.claude.com/docs/en/agent-sdk/overview
- Claude Code legal and compliance (authentication and credential use): https://code.claude.com/docs/en/legal-and-compliance
- Codespaces billing and included usage: https://docs.github.com/billing/managing-billing-for-github-codespaces/about-billing-for-github-codespaces
- Codespaces port forwarding: https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace
- OWASP Top 10: https://owasp.org/Top10/
