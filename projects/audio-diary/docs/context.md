# Context — audio-diary

Feedback last read: 2026-11-01

Side project on branch `project/audio-diary` (never merged to main). Owner asked for a one-shot build without
the design-doc/PR process; iterate from real use.

## State (2026-11-01)
- v0.1.1 built: record → segment → transcribe (OpenAI/Groq/custom) → .txt in Documents/AudioDiary.
- Security review done and fixes applied: docs/security-review.md. 38 JVM unit tests, lint clean.
- Never run on a device: the cloud VM has no KVM, so no emulator. First real test is the owner's OnePlus 12R.

## Known gaps / next
- Signing key lives only in the session that built v0.1.1; the owner must decide where it's kept (GitHub
  Actions secret was blocked from the session). Without it, updates need uninstall → in-app audio lost.
- No CI for the Android build yet (repo CI only discovers Python projects).
- Ideas: on-device Whisper (offline/private), biometric lock, search, export-all, R8 shrink (APK is ~26 MB).

## Gotchas
- `MediaRecorder(Context)` is API 31+; Android 10/11 need the deprecated constructor (lint catches it).
- Android SDK isn't preinstalled: install cmdline-tools from dl.google.com into ~/android-sdk.
- Real API errors: `{"error":{"message":...}}` for both OpenAI and Groq (verified 2026-11-01).
