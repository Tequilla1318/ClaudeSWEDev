# Decisions — audio-diary

## 2026-11-01 — Native Kotlin + Compose, sideloaded APK
Why: Android-only, needs reliable background mic recording (foreground service), which web apps can't do.
Rejected: PWA (no background recording), Flutter/React Native (extra layer, no benefit for one platform).

## 2026-11-01 — Cloud transcription via OpenAI-compatible API, user's own key
Why: owner's complaint is accuracy; gpt-4o-transcribe / Whisper large-v3 are far ahead of Android's built-in
recognizer. One client covers OpenAI, Groq and self-hosted servers.
Rejected for v1: on-device Whisper (needs NDK build + ~500 MB model for large quality; good v2 candidate).

## 2026-11-01 — 4-minute gapless segments, previous text as prompt
Why: gpt-4o-transcribe truncates after ~2k output tokens; 25 MB upload caps. Rejected: one file per entry.

## 2026-11-01 — AAC 44.1 kHz / 64 kbps mono
Why: most widely supported MediaRecorder configuration (reliability on the owner's OnePlus 12R over size).

## 2026-11-01 — Plain files, no database
Why: data stays inspectable; the .txt export is the product. Entry = folder with meta.json, segments, body.

## 2026-11-01 — Security defaults on
HTTPS-only, system CAs only, no redirects, per-provider Keystore-encrypted keys, no backups/transfers,
FLAG_SECURE on by default, .txt export on by default (owner asked for files) with a toggle. See security-review.md.

## 2026-11-01 — No R8 minification
Why: can't test on a device; avoid shrinker-related runtime surprises in v1. Cost: ~26 MB APK.
