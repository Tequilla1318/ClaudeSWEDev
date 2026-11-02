# Proposal — run Red One *inside* Claude Code, on the owner's Pro plan

Status: **chosen by the owner** (2026-11-02, chat). Open questions below still need answers. If approved, it replaces the M1 architecture in
`design.md` (custom FastAPI app calling the Claude API). Not implemented.

## Why the current design can't use Pro
Pro pays for Anthropic's own apps: claude.ai, the Claude app, and Claude Code (including the cloud
sessions this project is built in). The current design is **our own app calling Claude**. That needs
API access, and Anthropic's Agent SDK docs say apps built on Claude must use API-key authentication,
not a claude.ai sign-in. Doing it anyway would risk the account this whole workflow runs on.

## The flip
Instead of our app calling Claude, **Claude Code calls our pieces**. Claude Code is designed to be
extended with repo-committed skills, slash commands, hooks, subagents and MCP servers, and all of
them load in cloud sessions. That is ordinary use of Claude Code, so it runs on Pro at no extra
cost. Each future user signs in with their own subscription, so open-sourcing it stays compliant.

```
Owner (Chrome on the Mac, or the Claude app on the phone)
   │ "Daddy's home" → armed page opens claude.ai/code
   ▼
Claude Code cloud session (Anthropic VM, Pro plan)          ← the lead: Claude
   ├── .claude/skills/careful-consult   clarify → plan → wait for /approve → work → report
   ├── .claude/commands/                /approve, /status, /why, /report
   ├── .claude/settings.json hooks      gate: no file edits, pushes or delegation before /approve
   ├── .claude/agents/                  subagents on Haiku / Sonnet / Opus = escalation
   └── .mcp.json → red-one-team (our Python MCP server, runs in the session VM)
          └── delegate_to_gemini(task, sensitivity) → Gemini API (free tier)
                 key = cloud-environment *network secret*: added by Anthropic's proxy outside the
                 VM, never visible to Claude; server refuses anything marked sensitive
   ▼
GitHub (PRs; the owner merges)
```

## How each requirement maps
| Requirement | Current design | Claude-Code-native |
|---|---|---|
| Use Pro, spend nothing | API key needed (~$5) | **Pro only**, shared with Pro's usage limits |
| Nothing on the Mac | Codespaces | Cloud sessions (Anthropic VMs); nothing on the Mac |
| Clarify → plan → approve | State machine in our code | Skill + `/approve` command + hooks |
| Owner-only approval | Hard (our code) | **Medium.** A `UserPromptSubmit` hook records `/approve` only from *your* typed message; a `PreToolUse` hook blocks edits, pushes and delegation until then, and blocks edits to `.claude/`. It runs in the same VM Claude controls, so it is a strong guardrail, not a security wall. The walls stay: isolated VM, no Mac access, secrets outside the VM, and **you** merge PRs |
| Haiku first, escalate | Our escalation code | Subagents with `model: haiku/sonnet/opus`; Sonnet automatic, Opus asks you (skill rule) |
| Claude + Gemini, sensitive stays with Claude | Our router | Our MCP server enforces it in code |
| Ask "why" anytime, status | Our engine | `/why`, `/status` + project notes in the repo |
| Phone | M8 (later) | **Already works**: Claude app → Code tab |
| Wake phrase "Daddy's home" | M5 | Same armed Chrome page; on the phrase it opens claude.ai/code |
| Voice in | M4 (ours) | Phone: built-in keyboard dictation. Mac browser: our wake page can't type into claude.ai, so typing (or macOS dictation) for now |
| Human-sounding voice out, per-member voices, own UI | M4 (ours) | **Lost** for now. claude.ai is Anthropic's UI; we don't automate or restyle it |
| Projects saved, resumable | SQLite in codespace | claude.ai keeps sessions; project notes committed to the repo |
| Background work, check-ins | M6 | Cloud sessions keep running; subagents; Claude Code "Projects" coordinate parallel sessions; scheduled tasks |

## What we'd build (new M1, much smaller)
1. **Consult workflow:** skill, `/approve` `/status` `/why` `/report` commands, approval hooks + tests
   (hook scripts are plain Python, unit-tested in CI).
2. **Gemini MCP server:** `delegate_to_gemini` with the sensitivity gate, rate-limit handling,
   tests with a fake Gemini; owner adds the Gemini key as a network secret.
3. **Escalation subagents:** researcher (Haiku), analyst (Sonnet), deep-thinker (Opus, asks first).
4. **Wake page:** static page; "Daddy's home" → opens claude.ai/code. Folds old M5 in.
5. Threat model + owner test guide + release tag.

## Trade-offs to accept
- **Pro usage limits are shared** with chat and with the Claude Code sessions that build Red One.
  Heavy Red One days mean less building that day. Haiku subagents stretch it further.
- **The approval gate is softer** than our own code would be (see table). Real protection stays
  with GitHub (you merge) and the VM isolation.
- **No custom voice UI or spoken replies** in this version. If you want that later, it comes back
  with an API key, as the current design has it.
- **Conversations live on claude.ai** (Anthropic's servers) rather than in your codespace.

## What happens to existing work
- PR #35 (FastAPI scaffold): put on hold. If this proposal is approved, close it; the security CI
  workflow and ruff/pytest setup get reused for the MCP server and hooks.
- Issues #27–#33: closed and replaced by new stories for the list above.
- Roadmap M2–M9 get re-cut around this; the multi-model team idea still works via MCP servers.

## Open questions for the owner
1. **Approve this direction?** Pro-only and $0, in exchange for losing the custom voice UI and
   having a softer approval gate.
2. **Where Red One sessions live.** Claude Code loads `.claude/` from the repo a session opens. If
   Red One's hooks sit in ClaudeSWEDev, they'd also gate *these* build sessions. Options:
   (a) **a small separate repo you create**, e.g. `red-one-workspace`, holding only Red One's
       runtime config and the work it produces; this repo keeps the source and tests, and a script
       copies releases over (recommended);
   (b) a dedicated branch of ClaudeSWEDev that only Red One sessions open.
3. **Gemini key** as a network secret on your cloud environment (one-time, I'd give exact steps).

## Sources
- Agent SDK overview (authentication note): https://code.claude.com/docs/en/agent-sdk/overview
- Claude Code legal and compliance: https://code.claude.com/docs/en/legal-and-compliance
- Cloud sessions (Pro, phone, limits): https://code.claude.com/docs/en/claude-code-on-the-web
- Cloud environments (what loads from the repo, network secrets): https://code.claude.com/docs/en/cloud-environments
- Hooks: https://code.claude.com/docs/en/hooks
- Mobile: https://code.claude.com/docs/en/mobile
- Voice dictation (CLI only, local mic): https://code.claude.com/docs/en/voice-dictation
