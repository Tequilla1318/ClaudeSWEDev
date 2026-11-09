# Design amendment — talk to Red One by voice ("Voice milestone")

Status: **proposed** (awaiting owner approval). Amends the Claude-Code-native direction in
[`proposal-claude-code-native.md`](proposal-claude-code-native.md). Not implemented.

## 1. Goal
**On the owner's phone** (owner, 2026-11-08), and also in Chrome on the Mac: tap the Red One icon,
say **"Daddy's home"**, then talk to Claude out loud and hear it answer in a natural voice, at
**$0** on the owner's Pro plan, with **nothing installed on the Mac or the phone** beyond a
home-screen shortcut to a web page. Inspired by the
owner's reference write-up of "Ember" (a local voice assistant with voice ID), cut down to what
Red One needs. Voice-clone attacks are explicitly **out of scope** (owner, 2026-11-08).

## 2. Why this is possible without an API key
The 2026-11-02 decision assumed a custom app can't run on Pro. Re-reading Anthropic's current docs:

- `claude -p` (headless Claude Code) with the user's own subscription login is documented, and it
  **draws from normal subscription limits**. A June 2026 plan to bill it from a separate Agent SDK
  credit was paused (support article "Use the Claude Agent SDK with your Claude plan").
- The restriction is on **third-party developers offering claude.ai login to *their* users**, or
  routing requests through plan credentials *on behalf of* users. It explicitly does **not** prevent
  an end user signing in to the **unmodified Claude Code binary** with their own subscription
  (Claude Code docs, "Legal and compliance → Authentication and credential use").
- Pro limits "assume ordinary, individual usage of Claude Code and the Agent SDK" (same page).

So: a page that the owner alone uses, sending their own spoken words to the **unmodified** `claude`
CLI logged in with **their own** Pro account, is ordinary individual use. When open-sourced, each
user signs in with their own subscription, which the docs allow. **Not allowed, and not designed:**
sharing the page with anyone else, storing or forwarding the login token anywhere but the
codespace, or patching the binary. This is my reading of the terms, not legal advice; Anthropic
reserves the right to enforce, so the risk is the owner's call (open question 1).

Trade-off kept from #36: **Pro limits are shared** with chat and with build sessions. Every spoken
turn costs the same as a typed Claude Code turn.

## 3. Scope
**In:** wake phrase, push-to-talk and hands-free turns, speech-to-text, spoken replies with a
natural voice, echo handling on laptop speakers, a light "is it you?" check, a text box fallback.

**Out (for now):** Ember v2 (detectors, synthetic crowd, AS-Norm, prosody), anti-spoofing, company
mode and guest conversations, multiple voices per team member (M4 later), a native/app-store phone
app, listening with the phone locked or the page in the background, voice approval of
PRs (approvals stay **typed**; M7's passphrase is separate), Gemini as a voice fallback brain.

## 4. Architecture
```
Phone browser (home-screen web app) or Chrome on the Mac
                       ── Codespaces private forwarded port (HTTPS + GitHub sign-in) ──┐
  getUserMedia(echoCancellation, noiseSuppression, autoGainControl)                    │
  Silero VAD in the browser (onnxruntime-web) → speech segments only, 16 kHz PCM  ─────►│
  ◄──── reply audio (per sentence) + live captions                                     │
                                                                                       ▼
Codespace (2 cores, free allowance)   red_one server on 127.0.0.1:8765 (the #35 scaffold)
  ├─ wake gate     faster-whisper on each segment; fuzzy match "Daddy's home" → conversation open;
  │                "shut down" or 2 min of silence → closed. Not armed → segments dropped, no Claude.
  ├─ speaker check WeSpeaker ResNet34 via sherpa-onnx: you / not-you / unsure (Ember v1 rules)
  ├─ STT           faster-whisper small.en, int8, CPU
  ├─ brain         ONE long-lived `claude -p --input-format stream-json --output-format stream-json`
  │                process, run in the Red One workspace checkout, owner's Pro login; voice style via
  │                --append-system-prompt ("speak in 1–3 short sentences, no markdown, no code");
  │                read-only tools by default; Red One's hooks still gate edits/pushes on typed /approve
  ├─ TTS           Kokoro-82M (kokoro-onnx), first sentence synthesised while Claude keeps streaming
  └─ echo guards   own-words check; barge-in only after 700 ms of speech that checks as "you"
```

**Why each choice**
- **Browser echo cancellation instead of Ember's NLMS filter.** Chrome's built-in AEC does the
  same job for audio it plays itself, for free. Ember's other lessons are kept: stricter barge-in
  on speakers, dropping transcripts that are ≥70% Ember's (Claude's) own recent words.
- **VAD in the browser.** Only speech leaves the Mac, never a constant audio stream. Silence and
  background hum never reach the codespace.
- **Wake phrase by transcription, not a trained wake-word model.** Works on day one, no training.
  Cost: each speech segment is transcribed while unarmed (CPU only, nothing sent to Claude). A
  trained openWakeWord model can replace it later if CPU or false wakes become a problem.
- **Local STT (faster-whisper) over Chrome's built-in recognition.** Private and testable in CI with
  recorded clips. Chrome's recogniser is faster but sends audio to Google (open question 2).
- **Kokoro** is free, Apache-2.0, runs on CPU and was already the open-weight candidate in M4.
- **Speaker check = Ember v1, one model.** Enough to stop a TV or a friend's speech from reaching
  Claude. Enrolment by reading a passage aloud once (cut into 2 s pieces, outliers > 0.15 below the
  median dropped, personal cutoff = lowest 5% − 0.1, clamped to [0.5, 0.85]). Only the voiceprint
  (numbers) is stored, in the codespace, never committed.
- **One long-lived CLI process** keeps the conversation's context and avoids the CLI start-up cost
  on every turn. If it dies, it restarts with `--resume <session id>`.

**Running it from the phone.** All the heavy work stays in the codespace, so the phone only needs
a browser. The page works in the phone browser over the codespace's HTTPS address, which mobile
browsers require for the microphone.
- **Start:** open github.com/codespaces on the phone, tap the Red One codespace to start it
  (about a minute), then tap the home-screen shortcut. The forwarded address stays the same for
  the same codespace, so the shortcut keeps working. The codespace idle timeout is raised to its
  maximum so it doesn't stop mid-conversation; it still stops itself when idle, which saves hours.
- **Phone-first page:** one big talk button (tap to talk, tap to stop) as the main control; the
  wake phrase works while the page is open and the screen is on. Mobile browsers pause the mic when
  the screen locks or the page goes to the background, so **hands-free listening with the phone in
  a pocket is not possible from a web page**. A "keep screen on" toggle (Wake Lock API) covers
  hands-free use with the phone on a desk.
- **Audio:** the phone's loudspeaker is "speakers mode" (echo guards on); earbuds or a headset are
  "headset mode". The browser requires one tap before playing audio, so the page asks for a tap
  when it opens.
- **Installable:** a web app manifest so "Add to Home Screen" gives a full-screen icon (the old M8
  idea, reached early). No app store.
- **Data:** only speech segments go up (16 kHz, roughly 32 KB per second of speech) and short reply
  audio comes back, so mobile data use is small.

**Login.** The owner runs `claude auth login` once in the codespace's browser terminal (Anthropic's
own sign-in flow; nothing local). Easiest from the Mac's browser, but the codespace editor also
opens in a phone browser. The token lives in the codespace's home directory, never in the
repo or logs. Deleting the codespace logs out.

**Latency estimate (to be measured in V3, not promised):** end-of-speech 0.5 s + STT ≈1 s + Claude
first sentence 2–4 s + TTS first sentence ≈0.5 s → **about 4–6 s** to first audio. If too slow:
`base.en` STT, shorter replies, or Chrome recognition.

## 5. Security
- Port stays **private** (GitHub sign-in); server binds to 127.0.0.1; existing CSP and headers.
- Spoken input is **untrusted text** to Claude like any other message. Voice turns run with
  read-only tools; file edits, pushes and delegation still need the **typed** `/approve` from the
  #36 hooks. Voice can never approve or merge.
- The codespace has a GitHub token; Claude's tools in voice mode can't push (hook-gated), and the
  owner still merges every PR.
- No audio is stored. Transcripts go to Claude (Anthropic) only. Kokoro, whisper and the speaker
  model run inside the codespace.
- Threat model (`docs/security.md`) gets a voice section in V7.

## 6. Validation (against references)
- **STT:** word error rate on a small public clip set (e.g. 100 LibriSpeech test-clean utterances)
  compared with faster-whisper's published WER for the same model; plus Red One phrases spoken by
  Kokoro voices.
- **Speaker check:** equal-error rate on a small public trial list compared with WeSpeaker's
  published ResNet34 result; embeddings cross-checked against the reference WeSpeaker Python
  package on the same clips (cosine ≥ 0.99).
- **Wake gate:** detection and false-wake rates on synthetic clips of the phrase and near misses
  ("daddy's phone", "that's home", TV-style speech).
- Models download from GitHub releases / Hugging Face. CI is GitHub Actions (internet, cached);
  the Claude build sessions may not reach Hugging Face, so model-backed tests are marked and
  skipped there, and the PR says which ran where.

## 7. Stories (one branch and one PR each; every step usable on its own)
| # | Story | Usable result | Owner test |
|---|---|---|---|
| V1 | **Brain bridge (text), phone-first page:** `red_one.brain` wraps the CLI's stream-json; mobile layout with a text box; clear messages for "not logged in" and "usage limit reached" | Type to Claude from your phone on Pro | Log in once, open the page on the phone, type two related questions, check the second uses the first's context |
| V2 | **Spoken replies:** Kokoro TTS, sentence streaming, captions; pick a voice in a blind test of 4 Kokoro voices | Claude answers out loud | Ask something, hear the reply start before it's fully written |
| V3 | **Tap to talk:** browser capture + VAD + faster-whisper; latency measured | Tap, speak, hear the answer on the phone | Speak 5 questions on the phone; transcripts right; note the latency shown |
| V4 | **"Daddy's home" / "shut down" + keep-screen-on:** hands-free while the page is open | Hands-free with the phone on a desk | Say the phrase; check TV speech and near misses don't wake it |
| V5 | **Speakers mode:** echo guards, barge-in rule (phone loudspeaker and laptop) | Works without earbuds | Interrupt Claude mid-sentence on the loudspeaker; check it doesn't answer itself |
| V6 | **Is it you:** enrolment + you / not-you / unsure; not-you speech ignored | Others in the room don't trigger it | Enrol; have someone else (or a video) speak; check it's ignored |
| V7 | **Home-screen app + release:** web app manifest and icon, threat-model voice section, phone test guide, tag `red-one-v0.2.0` | A Red One icon on your phone; a release you can roll back to | Add to Home Screen, start the codespace from the phone, follow the guide end to end |

Out of order is fine except V1 first (everything depends on it).

## 8. Open questions for the owner
1. **OK to drive Claude with your Pro login through `claude -p` for this personal page?** (§2.)
   This reverses the 2026-11-02 "API key only" decision. Alternatives: an API key (~$5 prepaid,
   hard cap), or Gemini's free tier as the voice brain (breaks "sensitive stays with Claude").
2. **Speech-to-text:** local faster-whisper (private, slightly slower) **(recommended)**, or
   Chrome's built-in recognition (faster, free, audio goes to Google)?
3. **Android or iPhone, and which browser?** I'll build and test for that one first. Both work in
   principle; iPhone Safari is stricter about audio and background tabs.
4. **Which repo the codespace opens.** #36 answered "separate workspace repo". Have you created it
   (name?), or should V1 run in a codespace on `project/red-one` until you do?

## 9. References
- Owner's write-up of Ember's Voice ID v1/v2, headset vs speaker mode (shared in chat, 2026-11-08).
- Claude Code docs: Legal and compliance; Headless mode (`claude -p`); Agent SDK overview.
- Support: "Use the Claude Agent SDK with your Claude plan" (June and October 2026 updates).
- faster-whisper (SYSTRAN, MIT); Silero VAD; Kokoro-82M (Apache-2.0); sherpa-onnx; WeSpeaker
  ResNet34 (VoxCeleb). Model licences re-checked before the open-source release (M9).
