# Decisions — voice-agent-room

Append-only. Format: date — decision — why — alternatives rejected.
Entries marked "(proposed)" are Claude's suggestions awaiting the owner's approval.

- 2026-11-01 — Side project on long-lived branch `project/voice-agent-room`, never merged to `main`;
  all PRs target that branch — owner asked for a separate project on a different base — rejected:
  merging the project into `main`.
- 2026-11-01 — Build our own chat room — owner preference; it's "just a chat room" and gives full
  control — rejected: adopting OpenBot (openbot.run) as the room.
- 2026-11-01 — Chrome for the room window — owner finds Safari unreliable — rejected: Safari.
- 2026-11-01 — Only the wake script lives on the owner's Mac; the room runs elsewhere and nothing
  else is stored on the Mac — owner does not want data on their computer — rejected: a `localhost`
  server on the Mac (Claude's earlier suggestion).
- 2026-11-01 — Start with the smallest proof of concept and expand incrementally — owner wants to
  avoid feature creep — rejected: building wake word, voice, phone and multi-agent at once.
- 2026-11-01 — (proposed) Other LLMs through official API free tiers — stable, within terms —
  rejected: browser automation of consumer chat sites (brittle, likely against terms, account risk).
- 2026-11-01 — (proposed) Agents share one thread in the room with Claude as moderator; Discord
  deferred to an optional bridge — fewer moving parts — rejected for v1: Discord as the primary
  channel.
- 2026-11-01 — (proposed) First proof of concept is text-only: "hey gang" gating plus Claude and
  Gemini replying in one thread — smallest slice that tests the core loop in the cloud — rejected:
  starting with the wake word (needs a mic, untestable in the cloud).
