# Context — voice-agent-room ("Project Red One")

Feedback last read: 2026-11-01 (no comments on PR #24 yet; owner corrections given in chat 2026-11-01)

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
A voice-activated, **human-in-the-loop** AI team for whatever the owner is curious about:
software engineering, research ideas, simulations (mostly things that can be coded and checked).
The owner runs one command in Terminal to arm it, then says the wake phrase. A Chrome window opens
on a hosted chat room. The owner talks to **Claude**, the main AI and only point of contact. Claude
clarifies like a contractor with a client, proposes a plan, waits for approval, then does work
itself and/or hands pieces to **Gemini** (research, data, code). Claude and Gemini discuss, then
code, with **Claude supervising Gemini's work**. Claude updates the owner when something important
happens and checks on progress at regular intervals. The owner can interrupt, ask "why?", or ask
Claude to **teach** them a concept at any time. All work happens in the cloud and on GitHub; the
owner gets a report of what was found. **Security is the top priority.**

## Requirements stated by the owner
1. **Manually armed wake phrase.** One Terminal command arms listening (not an always-on service);
   the owner can start and stop it on demand. **Phrase not decided** (candidates: "Red One, boot
   up", "hey Claude"; earlier "Claude boot up" + "hey gang" prefix).
2. **Cybersecurity and web-app security are the highest concern.** No data leaks; nothing modified
   or installed on the Mac; personal files never read. Only the arming command and mic access.
3. **Human in the loop, not autonomous.** Clarify first, plan, get approval, pause and ask when
   blocked; the owner can interrupt and question any step.
4. **Claude is the main AI and single point of contact.** It may do work itself or delegate.
5. **No separate supervisor model.** Claude checks on workers at regular intervals and supervises
   Gemini's coding. (Corrects ChatGPT's "independent supervisor LLM".)
6. **Models: Claude + Gemini** (a free Gemini Flash-class model). Others (e.g. Grok) only if free and
   useful; expected to stay Claude + Gemini.
7. **Updates when something important happens**, not a constant stream.
8. **Teaching mode:** the owner can ask Claude to explain anything; learning is a goal.
9. **Work types:** random research ideas, software engineering, simulations; mostly codeable and
   checkable. Work happens on GitHub; the end product is a report of what was found.
10. **Chrome, not Safari. Build our own room** (OpenBot rejected).
11. **Phone app (later, not now):** talk to Claude while walking; Claude assigns tasks to Gemini and
    works on GitHub. All work lands as PRs.
12. **PR approval by spoken passphrase.** Claude explains the PR; the owner says a secret phrase;
    if it matches, the PR is approved/merged. Applies on laptop and phone.

## Proposed smallest proof of concept (to confirm in the design doc)
**Text-only consultation loop.** A web chat room where the owner types a request; Claude asks
clarifying questions, proposes a plan and waits for "approve"; then Gemini answers one delegated
sub-question and Claude reviews and relays it. No voice, no wake word, no GitHub execution yet.
Testable entirely in a cloud session with pytest and stubbed model calls. Conversation first,
agents second.

Rough order after that: wake word + voice → hosting with login → Claude + Gemini coding on GitHub
with Claude reviewing → periodic check-ins → phone app with voice PR approval.

## Key design positions (proposed; see decisions.md)
- **Wake word in the browser, not a script:** `redone` = one line that opens a Chrome app window
  with a temporary profile; the page listens on-device for the phrase. Chrome's sandbox means the
  page cannot read the owner's files, a stronger guarantee than a Python script (which runs with full
  user permissions). Trade-off: the window must stay open while armed.
- **Gemini free tier is not private.** Google's terms say free-tier prompts and outputs are used to
  improve its products, human reviewers may read them, and users should not send sensitive,
  confidential or personal information; paid-tier prompts are not used for training. Given the
  security priority: free tier only for non-sensitive research, or pay for Gemini.
- **Passphrase approval is checked by code, never by the LLM.** The speech transcript goes to a
  deterministic gate first. The gate looks for "approve PR <number>" + passphrase, compares against a
  stored hash (argon2/bcrypt, never the plain phrase), and **strips the passphrase before any text
  reaches Claude or Gemini or the logs**. So no model ever sees it, and a prompt-injected model can't
  leak it or fake a match. Also: approval names the PR number (a recording can't approve a different
  PR), the gate reads back the PR title before merging, attempts are rate-limited with lockout, and it
  only works from a logged-in session (second factor). Weaknesses to accept or mitigate: a phrase
  spoken aloud can be overheard or recorded, and cloud speech-to-text sees it (on-device STT for the
  approval step avoids that); a rotating or one-time phrase would be stronger.
- **GitHub detail:** the account that opens a PR can't approve its own PR, so "approve" will mean
  "merge" by the bot account, or a second GitHub account does the review. Settle in the design doc.
- Other LLMs via **official APIs**, not by automating consumer chat sites.
- **Project state store** (brief, decisions, tasks, open questions) is the source of truth, not
  chat history.

## Open questions for the owner
1. **Wake phrase:** pick one (e.g. "Red One, boot up" or "hey Claude"). Is any prefix needed after
   waking, or does everything said go to Claude until shutdown?
2. **Hosting:** which host for the room, and is a small monthly cost OK? (Claude Code cloud VMs are
   for development, not always-on hosting.)
3. **Wake word in browser vs Terminal script:** OK with an armed Chrome window instead of a script?
4. **Voice privacy:** may speech-to-text go to a cloud provider, or must it stay on-device?
5. **Gemini free tier vs paid**, given free-tier data may be read by Google reviewers.
6. **Name:** rename project and branch to `red-one`? Cheap now, before anything merges.

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
