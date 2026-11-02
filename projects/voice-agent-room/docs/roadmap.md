# Roadmap — voice-agent-room ("Project Red One")

Status: **proposed**, for the owner's review in PR #24. The design doc (`design.md`) will detail
M1 into user stories; later milestones are detailed when they are next.

## Rules every milestone follows
- **Usable on its own.** Each milestone ends with something the owner can actually use, even if
  nothing after it is ever built.
- **Tagged release.** When a milestone is done, the project branch is tagged
  (`voice-agent-room-v0.1.0`, `-v0.2.0`, …) with release notes, so the owner can go back to any
  working level with one command or one click on GitHub.
- **"How to test it" for the owner** (manual, in the browser, nothing on the Mac) **plus automated
  tests in CI** (pytest, models stubbed so CI never spends API credits or needs keys).
- **Security gate per milestone:** no secrets in the repo, secret scanning and dependency audit in
  CI, and the threat model (`docs/security.md`, started in M1) updated with whatever the milestone
  adds. A milestone isn't done until its security checklist passes.
- **Ask "why" anytime.** During any status update or conversation the owner can ask "why?" and
  Claude drills down into what is actually going on (the reasoning, the evidence, the code) as deep
  as asked. Explanations are on demand, not attached to everything.
- **Open-source ready from day one:** self-contained package, "bring your own API keys", nothing
  specific to the owner hard-coded, so it can later be published or run as a server.

## Where it runs before hosting is decided
Until M3, the owner uses it through **GitHub Codespaces**: a cloud machine opened from the GitHub
website, with the room's page forwarded to the owner's browser. Nothing is installed or stored on
the Mac, API keys live in Codespaces secrets, and personal GitHub accounts get a free monthly
allowance. (Proposed; alternative is to decide hosting now and skip this.)

---

## M1 — Talk to Claude, the careful way (text)
**What you get:** a web chat with Claude that behaves like a contractor: it asks clarifying
questions, proposes a plan, waits for "approve", then answers. Ask "teach me X" at any time.
Conversation and decisions saved per project.
**Useful because:** a thinking partner that doesn't run off and guess.
**How you test it:** open a Codespace → run one command → open the forwarded link → give it a vague
request ("research better battery chemistries") and check it asks questions before answering, refuses
to proceed without "approve", and explains a term when asked.
**Automated:** state machine tests (clarify → plan → approved), stubbed-model conversation tests.
**Security:** keys server-side only, page protected by a password, threat model started.

## M2 — Claude + Gemini research team
**What you get:** Claude delegates sub-questions to Gemini, reviews what comes back, and tells you
what it found and who found it. You can ask to see Gemini's raw answer.
**Useful because:** a two-model research assistant for any random idea.
**How you test it:** ask a research question; check the transcript shows the delegation, Claude's
review, and the relayed summary; ask "what did Gemini actually say?".
**Automated:** routing/delegation tests with stubs; one optional live smoke test, run only when keys
are present.
**Security:** content from Gemini and the web treated as untrusted data (prompt-injection tests);
free-tier vs paid Gemini setting.
**Built for a bigger team later:** each AI is a "team member" defined by config (provider, model,
role, voice, spending cap). Adding GPT, Grok or anything else later = a new config entry plus a
small provider adapter, not a rewrite.

## M3 — Hosted, with a login
**What you get:** the room at a private web address, no Codespace step. Works in any browser,
including your phone's.
**Useful because:** open it anywhere in seconds.
**How you test it:** visit the URL, log in, check wrong passwords are rejected and locked out, check
it works on the phone browser.
**Automated:** auth tests, rate limiting, security headers.
**Security:** HTTPS, proper login (not a shared password), session timeouts, a review against the
OWASP Top 10.

## M4 — Voice in the room, with a human-sounding voice and a "living" UI
**What you get:** a push-to-talk mic button; Claude replies in a **natural, human-sounding voice**
(generic: not robotic, and not anyone the owner knows or any recognisable person). Human-sounding is
preferred because it makes talking to it easier, but it's a nice-to-have, not a blocker.
**Each team member gets its own distinct voice**, so the owner can tell who's talking. The page gets a proper voice-first look: an animated
presence that reacts while you talk and while Claude speaks, live captions, and a clear indicator of
who is speaking (Claude or Gemini, possibly with different voices).
**Useful because:** a conversation that feels like talking to a colleague.
**How you test it:** hold the button, ask something, check the transcript is right and the reply
sounds natural; compare 3–4 candidate voices in a blind listening test and pick one.
**Automated:** speech-to-text tests on recorded audio clips (the cloud has no mic); TTS output checks
(audio returned, duration sane, captions match text).
**Voice options to compare:** hosted natural-TTS services (e.g. ElevenLabs, OpenAI, Google/Gemini
voices; best quality, paid or limited free tier, Claude's replies are sent to that provider) vs an
open-weight model running in the browser or on the server (e.g. Kokoro; free and private, somewhat
less expressive). Pick by listening, cost and privacy.
**Ethics/security:** no cloning of a real person's voice without their consent; the owner's own
voice only if the owner chooses to, via the provider's consent flow. Provider choice recorded in the
threat model (what text leaves the system).

## M5 — "Red One, boot up"
**What you get:** the `redone` command opens an armed Chrome window; saying the wake phrase starts
the conversation, "shut down" ends it and closes the window.
**Useful because:** hands-free start.
**How you test it:** run the one command, say the phrase, check it wakes; check it ignores other
speech; say the shutdown phrase.
**Automated:** wake-phrase detection on recorded clips, including near-miss phrases.
**Security:** the window can't read local files (Chrome sandbox); temporary profile deleted on exit.

## M6 — The team writes code on GitHub
**What you get:** after you approve a plan, Claude and Gemini write code in a dedicated repo/branch,
run tests in the cloud and open a PR; Claude reviews Gemini's code; you get a report and updates
when something important happens; Claude checks in at intervals.
**Useful because:** ideas turn into tested code you can look at.
**How you test it:** ask for a small simulation; check a PR appears with passing tests and a clear
report.
**Security:** the GitHub token is limited to the agents' repos; agents can open PRs but not merge;
code runs in an isolated cloud sandbox.

## M7 — Approve by passphrase
**What you get:** Claude explains the PR; you say "approve PR 31" + your passphrase; Claude confirms
the target branch; you say yes; it merges.
**Useful because:** review and ship by voice.
**How you test it:** wrong phrase → rejected; right phrase → asks for branch confirmation; changing
the branch → asks for the phrase again; confirm → merged.
**Automated:** gate tests (hashing, stripping the phrase from logs and model input, replay with a
different PR number, lockout, expiry).
**Security:** independent review of the gate before it touches a real repo.

## M8 — Phone app
**What you get:** an installable phone web app (no app store needed) for talking while walking,
with background work and approvals.
**How you test it:** add it to your home screen, start a task while away from the laptop.

## M9 — Open-source release
**What you get:** the project split into its own repo with a licence, install guide, `SECURITY.md`,
self-hosting instructions, and the threat model; or deployed as a server for others.
**How you test it:** someone else follows the README from scratch with their own keys.

---

## Long-term vision (not scheduled)
**A full engineering team room:** many models (Claude, Gemini, GPT, Grok, …), each with its own
role and voice, working in the background, speaking up when they have something to say, then going
back to work. Claude stays the moderator: it decides who gets the floor so the room doesn't turn
into everyone talking at once, and the owner can address any member directly. Enabled by the
team-member abstraction from M2. Cost note: this needs **API keys (pay-per-use, with spending
caps)**, not consumer subscriptions like ChatGPT Plus, which generally don't include API access.

## Not in any milestone yet
Discord bridge, a progress dashboard beyond the chat, and starting a
session on the laptop from the phone.
