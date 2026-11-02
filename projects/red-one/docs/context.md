# Context — red-one ("Project Red One")

Feedback last read: 2026-11-02T01:27Z (#34 merged: escalation rules approved; owner asked to find a way to use the Pro plan → proposal PR)

## Branch model
**Side project: lives on `project/red-one`; never merged to `main`** (owner, 2026-11-01).
Cut story branches from `project/red-one` and open PRs against it. To pick up repo-wide changes
(CI, CLAUDE.md), merge `origin/main` into the project branch via a `chore/` PR.
The project was first named `voice-agent-room` (PR #24). The owner is deleting the old branches
`project/voice-agent-room` and `docs/voice-agent-room-context`. Don't use them.

## Current state
- **M1 design approved** ([`design.md`](design.md)). Building M1 in stub mode; story issues
  created (see Next). No code merged yet. Requirements come from the kickoff chat with Claude (below) and the
  owner's ChatGPT conversation ([`chatgpt-kickoff-notes.md`](chatgpt-kickoff-notes.md)).
  Milestones: [`roadmap.md`](roadmap.md). Next: the M1 design doc (`design.md`).
- Owner's instruction: **start with the smallest possible thing and expand later; avoid feature creep.**

## The idea in one paragraph
A voice-activated, **human-in-the-loop** AI team for whatever the owner is curious about:
software engineering, research ideas, simulations (mostly things that can be coded and checked).
The owner runs one command to arm it, then says **"Daddy's home"**. A Chrome window opens on the
chat room. The owner talks to **Claude**, the main AI and only point of contact. Claude clarifies
like a contractor with a client, proposes a plan, waits for approval, then does work itself and/or
hands non-sensitive pieces to **Gemini**. Claude supervises Gemini's work, updates the owner when
something important happens, and checks on progress at regular intervals. The owner can interrupt
or ask "why?" at any time and Claude drills down. All work happens in the cloud and on GitHub; the
owner gets a report of what was found. **Security is the top priority. No spending money.**

## Requirements stated by the owner
1. **Manually armed wake phrase "Daddy's home"** (owner, PR #24). One command arms listening; the
   owner starts/stops it on demand. Arming opens a Chrome window that listens (approved). Shutdown
   phrase and whether a prefix is needed after waking: not yet stated.
2. **Cybersecurity and web-app security are the highest concern.** No data leaks; nothing modified
   or installed on the Mac; personal files never read.
3. **No spending money.** "Local host, I don't want to spend money" (PR #24). Run in GitHub
   Codespaces for now (approved), reached through a forwarded localhost port.
4. **Human in the loop, not autonomous.** Clarify first, plan, get approval, pause and ask when
   blocked; the owner can interrupt and question any step.
5. **Claude is the main AI and single point of contact.** It may do work itself or delegate.
   No separate supervisor model; Claude supervises Gemini.
6. **Models: Claude + Gemini (free tier).** Others only if free and useful.
7. **Sensitive data never leaves Claude.** "Claude shouldn't assign sensitive data to anyone except
   itself" (PR #24). Gemini's free tier only gets non-sensitive work.
8. **Speech-to-text may use a cloud provider if it's free** (PR #24).
9. **Updates when something important happens**, not a constant stream.
10. **Ask "why" anytime**, especially during status updates; Claude drills down on demand. Teaches
    a concept when asked. Explanations are not attached to everything.
11. **Chrome, not Safari. Build our own room** (OpenBot rejected).
12. **Natural, human-sounding voice** (not anyone the owner knows); later, a distinct voice per team
    member.
13. **PR approval by spoken passphrase**, then Claude confirms the target branch, then the merge.
14. **Every milestone usable on its own, with owner test steps; versions kept on GitHub** for
    rollback. Long term: open-source the package or run it as a server.
15. **Phone app later**, not now.

## Key design positions (see decisions.md)
- **Wake word in an armed Chrome window**, not a script (approved): the Chrome sandbox blocks file
  access; nothing installed.
- **Sensitive-data routing:** Claude classifies each delegation; anything sensitive stays with
  Claude. Default is "sensitive" when unsure, and the owner can mark a project or message private.
  Enforced in code (a delegation tagged sensitive is refused by the router), not only by prompt.
- **Passphrase approval is checked by code, never by an LLM**: hashed, stripped before any model or
  log sees it, bound to PR number + target branch read from GitHub, rate-limited. Free cloud
  speech-to-text would see the spoken phrase; M7 must address this (e.g. type the phrase, or
  on-device recognition for that step).
- **AIs are config-defined "team members"** (provider, model, role, voice, spending cap) from M2.
- Other LLMs via **official APIs**, not by automating consumer chat sites.
- **Project state store** (brief, decisions, open questions) is the source of truth, not chat history.

## Money: what's free and what isn't
- **Codespaces:** free monthly allowance on a personal account; without a payment method on file,
  usage is blocked when the allowance runs out, so it can't charge.
- **Gemini API:** free tier (rate-limited; Google may use the data and human reviewers may read it).
- **Claude API: no free tier.** It's prepaid credits; when credits run out, calls stop (no surprise
  bill if auto-reload is off). The owner is on **Pro**: no included API credits (only Max, Ultra,
  Team), and subscription sign-in can't power a custom app (Anthropic's terms: apps, including Agent
  SDK ones, use API keys). Pro still covers the Claude Code sessions that build Red One.
  Decided: build in stub mode; real replies start when the owner adds an `ANTHROPIC_API_KEY`
  Codespaces secret (design.md §8.1). The owner asked to use Pro; explained why that's not allowed.

## Long-term vision
A large multi-model "engineering team" room, each member with its own voice and role, speaking up
when needed then returning to work, with Claude moderating (see roadmap.md). Today: Claude + Gemini.

## Known issues / gotchas
- Cloud VMs have **no microphone or speaker**; voice is tested with recorded/synthesised audio.
- Claude never touches the owner's Mac; the owner runs the arming command themselves.
- `gh pr create` fails (GraphQL blocked); use the REST API via `gh api` (see CLAUDE.md).
- The session's GitHub proxy blocks branch renames and deletes; create the new branch with
  `git push` and ask the owner to delete old ones.
- This repo is shallow-cloned single-branch; add fetch refspecs for project branches or `git status`
  can't see their remotes.

## Related, outside this project
- **Linking the owner's main GitHub:** add `Tequilla1318` as a collaborator on chosen repos of the
  main account (or an org it owns), so the main account is never connected to Claude.

## Next
1. Owner chose the Claude-Code-native direction (2026-11-02). Still open: where Red One sessions live
   (separate repo vs branch) and the Gemini network secret.
2. If yes: close #35 and #27–#33, re-cut roadmap and stories around the proposal.
   If no: continue M1 as designed in stub mode, starting with #35.
