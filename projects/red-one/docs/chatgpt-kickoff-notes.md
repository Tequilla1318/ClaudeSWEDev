# ChatGPT kickoff notes — "Project Red One"

Summary, in Claude's words, of the owner's ChatGPT conversation "Voice activated AI system"
(pasted by the owner on 2026-11-01). These are **inputs**, not decisions: ChatGPT's suggestions are
listed so the design doc can accept or reject them explicitly. Owner decisions live in
`decisions.md`.

## What the owner asked for (owner's own words, paraphrased)
1. A phrase spoken aloud (e.g. "Red One, boot up") opens a voice chat with the AIs.
2. The system picks the model per topic/task, can assign tasks to different models and run them
   in the background, and a separate LLM monitors them. The owner mostly talks to one AI
   (e.g. Claude or GPT).
3. **Hard condition:** nothing on the Mac is modified or installed; personal files are never read
   or changed. Work happens on GitHub.
4. **Not autonomous — human in the loop.** The owner gives a task; the AI starts, and whenever it
   hits something it asks questions, treating the owner as a client. It gives constant spoken
   updates ("this was found…"), and the owner can say "go ahead" or ask "why are you doing this?".
   Agents report to a main agent, which finally hands the owner the data on what happened, what
   they can do and how to improve.
5. The only local piece: **one terminal command arms wake-word detection**. On the phrase, it opens
   the browser with the voice-chat front end and all the agents in the group.

## ChatGPT's proposed architecture
- **Three separable systems:** activation (mic + wake word on the Mac), intelligence (router,
  primary AI, specialist agents, supervisor), execution (cloud machines + GitHub).
- **Activation flow:** run `redone` in Terminal (armed) → say "Red One, boot up" → browser opens the
  control interface → talk → "Red One, shut down" closes the session and stops the listener. Plus an
  emergency stop (key or button).
- **Mac's only jobs:** microphone, wake phrase, open a URL, talk to the remote service, exit on
  request. No Full Disk Access, Accessibility, Screen Recording or AppleScript permissions.
- **Caveat ChatGPT raised:** a Terminal script runs with the user's full permissions; choosing not to
  write file-access code does not *prevent* file access. Stronger options: a sandboxed app, or a
  separate macOS user account.
- **Roles:** primary conversational AI (the owner's single point of contact; acts as project
  manager), task router, specialist agents (research, engineering, analysis, development),
  **independent** supervisor (different model from the primary, so no model grades its own work).
- **Authority:** owner > a small *deterministic* orchestrator that enforces permissions > AI agents.
  "An AI supervisor is not a security boundary."
- **Permission levels:** 1 Investigate (no extra approval once a task is assigned) · 2 Propose (owner
  decides) · 3 Execute approved work in cloud workspaces / authorised branches · 4 Consequential
  actions (merge, deploy, publish, change scope): explicit approval every time. Plus a **blocked**
  state: on ambiguity or out-of-permission actions, pause and ask, never guess.
- **Interaction cycle:** problem → AI consults (clarifying questions) → owner clarifies → AI proposes a
  plan → owner approves → agents work and report → owner can interrupt at any time → consolidated
  report (findings, datasets, open questions, recommendations).
- **Communication:** agents don't talk to the owner directly; the primary AI relays. Priorities:
  critical (stop and ask now), important (interrupt at a natural pause), informational (next update),
  routine (log only). Share sources, calculations and assumptions, not models' hidden reasoning.
- **Shared project memory as source of truth** (not chat history): brief, requirements, decision log,
  research database, task registry, question register. Lets the AI resume across days ("yesterday
  we…") and stops one agent's assumption becoming another's "fact".
- **Supervisor duties:** spot contradictions between agents, duplicated work, unsupported claims,
  drift from the objective, and where more research would help.
- **Dashboard:** what each agent is doing, findings, blocked tasks, pending decisions, supervisor
  flags, progress, next actions; also queryable by voice ("Red One, status report").
- **Suggested stack (ChatGPT's):** Porcupine wake word, Swift menu-bar app, OpenAI Realtime API for
  voice, Claude API, Python/TypeScript orchestrator, LangGraph or custom, GitHub Codespaces for
  execution, server-side secrets. ChatGPT itself advised avoiding a big agent framework until the
  basics work.
- **Suggested phases:** 1 voice activation · 2 multiple providers + routing · 3 background agents ·
  4 supervisor · 5 cloud execution on GitHub · 6 security hardening. Also: build it as a
  **conversational system first, agent system second**.
- Note: API access is billed separately from Claude/ChatGPT subscriptions.

## Where Claude's view differs (for the design doc to settle)
- **Wake word can run inside the browser instead of a Terminal script.** The `redone` command can be
  a single line that opens a Chrome app window; that page holds the mic and listens for the phrase
  (on-device wake-word model in WebAssembly). Nothing is installed, and the page sits inside
  Chrome's sandbox, which **cannot read the owner's files**. That is a stronger guarantee than a
  Python script, which runs with full user permissions. Trade-off: the window must stay open while
  armed. (Chrome writes a temporary profile folder, deleted on exit; no personal files touched.)
- **Swift menu-bar app** contradicts "install nothing"; not needed with the browser approach.
- **Execution environment:** Claude Code cloud sessions (already in use) vs GitHub Codespaces.
- **Security order:** the permission model and auth come with the first hosted version, not phase 6.
