# Context — voice-agent-room

Feedback last read: 2026-11-01 (no PRs or issues for this project yet)

## Branch model
**Side project: lives on `project/voice-agent-room`; never merged to `main`** (owner, 2026-11-01).
Cut story branches from `project/voice-agent-room` and open PRs against it. To pick up repo-wide
changes (CI, CLAUDE.md), merge `origin/main` into the project branch via a `chore/` PR.

## Current state
- **Discussion only. No design doc, no code.** This file records everything agreed so far in the
  kickoff chat (2026-11-01) so the next session can write `design.md` without re-asking.
- Owner's instruction: **start with the smallest possible thing and expand later; avoid feature creep.**
- Origin: a ChatGPT conversation titled "Voice activated AI system" (shared link). Only the title
  could be read (the share page renders client-side), so its contents are **not** captured here.
  If it matters, ask the owner to paste the key parts.

## The idea in one paragraph
A voice-activated chat room where the owner talks to several LLMs at once. A small script on the
owner's Mac listens for a wake phrase ("Claude boot up"). On hearing it, a temporary Chrome window
opens on the chat room. Inside the room, only speech that starts with "hey gang" is sent to the
agents; everything else is ignored. Claude plus other (free-tier) LLMs reply in one shared thread
and can talk to each other, producing a multi-agent output. The room should also be reachable from
the owner's phone.

## Requirements stated by the owner
1. **Two-stage trigger.** "Claude boot up" wakes the system; while awake, only utterances beginning
   with "hey gang" go to the agents. (A sleep phrase such as "Claude shut down" was suggested by
   Claude; not yet confirmed.)
2. **LLMs as the brain.** Owner said "I'd rather it only use LLMs". Interpretation not yet
   confirmed: most likely "an LLM decides everything, no hand-written command rules", with a
   speech-to-text model (e.g. Whisper) still needed as the "ears". See open questions.
3. **Chrome, not Safari.** The temporary window is a Chrome window (Safari described as "weird").
4. **Build our own chat room.** Owner chose to build it rather than adopt OpenBot.
5. **Minimal footprint on the Mac.** Owner does not want data stored on their computer. The wake
   script is the one thing allowed to live on the Mac, and the owner wants to **start and stop it
   on demand**. The chat room itself should run **not locally**. (This replaces Claude's earlier
   suggestion of a `localhost` server on the Mac.)
6. **Phone access.** From the phone, the owner wants to (a) use the chat room and/or (b) trigger the
   laptop to open the chat room window. Exact behaviour not yet specified.
7. **Multiple LLMs in one conversation**, including free ones (e.g. Gemini) set up on the AI-only
   Google account. They need a way to talk to each other and produce a combined result. Owner
   floated a Discord group as one channel, and is open to "an optimized way" chosen by Claude.

## What Claude proposed (not yet approved)
- **Wake word on the Mac:** Vosk (small, offline) restricted to the wake phrase(s), so idle audio
  never leaves the Mac. Alternatives: openWakeWord, Porcupine, rolling Whisper + string match.
- **Temporary window:** Chrome app-mode window with a throwaway profile, e.g.
  `open -na "Google Chrome" --args --app=<room URL> --user-data-dir=<temp dir>`, deleted on close,
  so nothing persists on the Mac.
- **Speech in the room:** browser speech recognition (zero install, but Chrome sends audio to
  Google) vs Whisper (private, more setup). Undecided.
- **Other LLMs via official free API tiers** (e.g. a Gemini key from Google AI Studio; Groq and
  OpenRouter also have free tiers), **not** by automating the consumer chat websites. Automating
  chatgpt.com / gemini.google.com breaks on UI changes and likely violates their terms, risking the
  account. Free tiers are rate-limited; check each provider's data-use terms.
- **Agent-to-agent talk:** one shared thread in the room with Claude as moderator (reads the
  "hey gang" message, picks which agents answer, writes the final synthesis). Discord deferred to a
  later optional "second window" onto the same thread.
- **API keys stay server-side**, never in the browser.

## Smallest proof of concept (proposed, to confirm in the design doc)
A text-only chat room: the owner types "hey gang, ..." and Claude plus one other model (Gemini)
reply in one shared thread; lines without "hey gang" are ignored. No voice, no wake script, no
phone yet. Fully testable in a cloud session with pytest. Later steps, in order: voice in the room,
the Mac wake script, phone access, Discord bridge.

## Open questions for the owner
1. **Where does the room run?** "Not locally" means a hosted service (e.g. a small cloud host).
   Which host, and is a small monthly cost OK? Claude Code cloud VMs are for development, not
   always-on hosting.
2. **Privacy of voice:** is browser speech recognition (audio to Google) acceptable, or must
   transcription be private (Whisper)?
3. **"Only LLMs":** confirm the interpretation in requirement 2.
4. **Phone behaviour:** use the room directly on the phone, remotely open it on the laptop, or both?
5. **Which models besides Claude?** Gemini is the default free choice.
6. **Sleep phrase:** add "Claude shut down" (or another phrase)?
7. **Project name:** `voice-agent-room` was chosen by Claude; rename if preferred.

## Known issues / gotchas
- Cloud VMs have **no microphone or speaker**. Voice parts are tested with recorded/synthesised
  audio files; live-mic behaviour can only be checked on the owner's Mac, by the owner.
- Claude must never touch the owner's Mac. The owner installs and runs the wake script themselves.
- A hosted room that holds API keys needs **authentication**, or anyone with the URL can spend the
  keys. Must be in the design.
- `gh pr create` fails (GraphQL blocked); use the REST API via `gh api` (see CLAUDE.md).

## Related, outside this project
- **Linking the owner's main GitHub account:** suggested approach is to add `Tequilla1318` as a
  collaborator on chosen repos of the main account (or an org owned by the main account), so the
  main account is never connected to Claude. Not part of this project; owner hasn't acted on it.
- **OpenBot** (openbot.run, desktop multi-agent app, PolyForm Noncommercial licence) was considered
  and rejected in favour of building our own.

## Next
1. Owner reviews this PR and answers the open questions (PR comments are fine).
2. Claude opens the design-doc PR (`docs/design.md`) against `project/voice-agent-room`,
   scoped to the smallest proof of concept, with later milestones listed but not detailed.
3. No implementation until the design doc is approved.
