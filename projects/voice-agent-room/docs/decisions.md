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
- 2026-11-01 — Human-in-the-loop, not autonomous: the primary AI clarifies, proposes a plan, waits for
  approval, reports continuously and pauses when blocked — owner requirement (ChatGPT chat) —
  rejected: agents that work on a goal unsupervised.
- 2026-11-01 — Listening is manually armed by one Terminal command and stopped by a phrase; nothing
  installed, no personal files read or modified on the Mac — owner requirement — rejected: an
  always-on login service or a native Mac app.
- 2026-11-01 — Primary AI is the owner's single point of contact; specialist agents report to it;
  an independent supervisor model monitors them — owner requirement — rejected: every agent
  speaking to the owner directly.
- 2026-11-01 — (proposed) Wake-word detection runs inside an armed Chrome app window, not a Terminal
  script — Chrome's sandbox blocks file access, which a script running as the user cannot guarantee;
  nothing to install — rejected: Python + Vosk script, Swift menu-bar app (ChatGPT's suggestion).
- 2026-11-01 — (proposed) A deterministic orchestrator enforces permissions; merges, deploys and
  scope changes always need explicit owner approval — an LLM supervisor is not a security boundary —
  rejected: letting the supervisor or primary AI authorise actions.
- 2026-11-01 — (proposed) Proof of concept becomes a text-only consultation loop (clarify → plan →
  approve → one delegated answer from a second model), superseding the "hey gang" text-room PoC —
  the owner's core value is the human-in-the-loop conversation; build conversation first, agents
  second — rejected: starting with multi-agent or voice.
- 2026-11-01 — **No separate supervisor model.** Claude is the main AI: it may work itself or
  delegate, checks on workers at regular intervals, and supervises Gemini's coding. Supersedes the
  "independent supervisor model" part of the earlier entry — owner correction — rejected: a third
  model watching the workers.
- 2026-11-01 — Models are Claude (main) + Gemini (worker); others only if free and useful — owner
  choice — rejected: GPT as a core model.
- 2026-11-01 — Cybersecurity / web-app security is the top priority; updates only when something
  important happens; teaching on request is a core feature — owner requirement.
- 2026-11-01 — Phone app with voice PR approval is deferred until the laptop version works — owner
  choice — rejected: building phone access early.
- 2026-11-01 — (proposed) Voice PR approval is executed by deterministic code after an authenticated,
  explicit owner confirmation with a read-back; the LLM can request but never grant approval —
  prevents misheard approvals and prompt-injected merges — rejected: letting Claude merge when it
  believes the owner agreed.
- 2026-11-01 — (proposed) Gemini free tier used only for non-sensitive work (Google may use free-tier
  data and human reviewers may read it); paid tier if anything sensitive is involved — security
  priority — rejected: sending everything to the free tier.
- 2026-11-01 — PR approval by spoken passphrase after Claude explains the PR — owner requirement —
  rejected: tap-to-approve only.
- 2026-11-01 — (proposed) The passphrase is verified by deterministic code against a stored hash and
  removed from the transcript before any model or log sees it; approval must name the PR number,
  is rate-limited, and only works from a logged-in session — models are injectable and must never
  hold or judge the secret — rejected: Claude checking the passphrase itself.
- 2026-11-01 — A correct passphrase does not merge on its own; Claude must then confirm the target
  branch with the owner, and the merge happens only after the owner's confirmation — owner
  requirement — rejected: merging immediately on passphrase.
- 2026-11-01 — (proposed) The passphrase creates a short-lived pending approval bound to PR number +
  target branch; the branch shown is read from GitHub by the gate, and any change of target branch
  voids the approval and needs the phrase again — stops a model from redirecting a merge.
