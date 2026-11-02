# Context — voice-agent-room ("Project Red One")

Feedback last read: 2026-11-01 (no comments on PR #24 yet)

## Branch model
**Side project: lives on `project/voice-agent-room`; never merged to `main`** (owner, 2026-11-01).
Cut story branches from `project/voice-agent-room` and open PRs against it. To pick up repo-wide
changes (CI, CLAUDE.md), merge `origin/main` into the project branch via a `chore/` PR.

## Current state
- **Discussion only. No design doc, no code.** Two sources of requirements:
  the kickoff chat with Claude (summarised below) and the owner's ChatGPT conversation, summarised
  in [`chatgpt-kickoff-notes.md`](chatgpt-kickoff-notes.md). Read both before writing `design.md`.
- Owner's instruction: **start with the smallest possible thing and expand later; avoid feature creep.**

## The idea in one paragraph
A voice-activated, **human-in-the-loop** AI team. The owner runs one command in Terminal to arm it,
then says "Red One, boot up". A Chrome window opens on a hosted chat room. The owner talks to one
primary AI, which acts like a project manager: it asks clarifying questions as if the owner were a
client, proposes a plan, waits for approval, then hands work to specialist agents on other models
(Claude, GPT, Gemini, free tiers), chosen per task. Agents report to the primary AI; an independent
supervisor LLM watches for contradictions and drift. The owner gets constant updates, can ask
"why?" or redirect at any time, and ends with a report of findings and recommendations. All real
work happens in the cloud and on GitHub. Reachable from the phone too.

## Requirements stated by the owner
1. **Manually armed wake phrase.** One Terminal command arms listening (not an always-on service);
   the owner can start and stop it on demand. Phrases so far: "Red One, boot up" / "Red One, shut
   down" (latest), earlier "Claude boot up". In the first chat, utterances also had to start with
   "hey gang" to reach the agents; whether that prefix stays is open.
2. **Nothing modified or installed on the Mac; personal files never read.** Only the arming command
   and mic access are acceptable. The chat room runs elsewhere.
3. **Human in the loop, not autonomous.** Clarify first, plan, get approval, report continuously,
   pause and ask when blocked, owner can interrupt and question any step.
4. **Primary AI as single point of contact**; specialist agents report to it; the owner can inspect
   any agent's evidence on request.
5. **Model routing by task**, background tasks on different models, **independent supervisor LLM**.
6. **LLMs as the brain** (speech-to-text is still needed as the "ears"; interpretation to confirm).
7. **Chrome, not Safari.**
8. **Build our own room** (OpenBot rejected).
9. **Phone access:** use the room and/or trigger the laptop to open it.
10. **Free LLMs** set up on the AI-only Google account should be able to join.
11. **Work happens on GitHub**; final output is data on what happened and how to improve.

## Proposed smallest proof of concept (to confirm in the design doc)
**Text-only consultation loop.** A web chat room where the owner types a request; the primary AI
(Claude) asks clarifying questions, proposes a plan and waits for "approve"; then one second model
(e.g. Gemini) answers a delegated sub-question and the primary AI relays it. No voice, no wake word,
no supervisor, no GitHub execution yet. Testable entirely in a cloud session with pytest and stubbed
model calls. This matches both Claude's and ChatGPT's advice: conversational system first, agents
second.

Rough order after that: wake word + voice → hosting with login + phone → routing across models →
background agents with a task registry → supervisor → GitHub execution in cloud sessions.

## Key design positions (proposed; see decisions.md)
- **Wake word in the browser, not a script:** `redone` = one line that opens a Chrome app window
  with a temporary profile; the page listens on-device for the phrase. Chrome's sandbox means the
  page cannot read the owner's files, a stronger guarantee than a Python script (which runs with full
  user permissions). Trade-off: the window must stay open while armed.
- Other LLMs via **official APIs**, not by automating consumer chat sites.
- A **deterministic orchestrator** enforces permissions; LLMs (including the supervisor) are never
  the security boundary. Merges, deploys and scope changes always need the owner.
- **Project state store** (brief, decisions, tasks, open questions) is the source of truth, not
  chat history.

## Open questions for the owner
1. **Hosting:** which host for the room, and is a small monthly cost OK? (Claude Code cloud VMs are
   for development, not always-on hosting.)
2. **Wake word in browser vs Terminal script:** OK with an armed Chrome window instead of a script?
3. **"hey gang" prefix:** keep it, or is "Red One, boot up" enough?
4. **Voice privacy:** may speech-to-text go to a cloud provider (Google, OpenAI) or must it be
   on-device?
5. **Phone:** use the room on the phone, remotely open it on the laptop, or both?
6. **Models:** Claude primary? Which others (GPT needs a paid OpenAI API key; Gemini has a free tier)?
7. **Name:** rename project and branch to `red-one`? Cheap now, before anything merges.

## Known issues / gotchas
- Cloud VMs have **no microphone or speaker**; voice is tested with recorded/synthesised audio.
  Live-mic behaviour can only be checked by the owner on their Mac.
- Claude never touches the owner's Mac; the owner runs the arming command themselves.
- A hosted room holding API keys needs **authentication** from day one, or anyone with the URL can
  spend the keys.
- API usage is billed separately from Claude/ChatGPT subscriptions.
- `gh pr create` fails (GraphQL blocked); use the REST API via `gh api` (see CLAUDE.md).
- This repo was shallow-cloned single-branch; add fetch refspecs for project branches or `git status`
  can't see their remotes.

## Related, outside this project
- **Linking the owner's main GitHub:** add `Tequilla1318` as a collaborator on chosen repos of the
  main account (or an org it owns), so the main account is never connected to Claude.

## Next
1. Owner answers the open questions (PR #24 comments are fine) and merges PR #24.
2. Claude opens the design-doc PR (`docs/design.md`) against `project/voice-agent-room`, detailed for
   the proof of concept, with later milestones listed but not detailed.
3. No implementation until the design doc is approved.
