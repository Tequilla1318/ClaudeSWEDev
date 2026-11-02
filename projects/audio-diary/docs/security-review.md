# Security review — Audio Diary v0.1.1

Date: 2026-11-01 · Scope: the Android app in this folder, release build `app-release.apk` (versionCode 1).
Method: OWASP Mobile Top 10 (2024) and MASVS v2 categories, Android lint (security + correctness checks),
inspection of the built APK's merged manifest, dependency scan against the OSV database, and attack tests
written as JVM unit tests (`app/src/test`). **Not done:** dynamic testing on a device or emulator (the build VM
has no hardware virtualisation), so runtime behaviour on the phone is verified by reasoning and tests, not by
running it.

## Threat model

| Asset | Threat |
|---|---|
| Diary audio and transcripts (highly personal) | Other apps on the phone, someone holding the unlocked phone, backups/transfers, network eavesdroppers |
| Transcription API key (costs money) | Leak to the wrong server, to cleartext networks, to backups, to logs |
| App integrity | Malicious server responses, hijacked tasks/intents, malformed input |

## Findings and fixes

Severity is for this app's context. All "Fixed" items have a test or an APK/lint check behind them.

| # | Category (OWASP / MASVS) | Finding | Severity | Status |
|---|---|---|---|---|
| 1 | M5 Insecure communication / NETWORK | A custom base URL could be `http://`, sending the key and audio in clear text | High | **Fixed** — HTTPS-only validation before any request; `cleartextTrafficPermitted=false`; test `refusesToSendKeyOverPlainHttp` |
| 2 | M5 / NETWORK | User-installed CAs would allow interception | Medium | **Fixed** — network security config trusts system CAs only |
| 3 | M5 / NETWORK | OkHttp follows redirects; a redirect could send audio to another host | Medium | **Fixed** — redirects disabled; test `doesNotFollowRedirectsToAnotherHost` |
| 4 | M1 Credential usage / STORAGE | One API key field shared by all providers: switching provider sent your OpenAI key to Groq | High | **Fixed** — one key per provider; switching loads that provider's own key |
| 5 | M9 Insecure data storage | API key stored in plaintext SharedPreferences | Medium | **Fixed** — AES-256-GCM with a non-exportable Android Keystore key |
| 6 | M9 / STORAGE | `allowBackup=false` is ignored for Android 12+ device-to-device transfer | Medium | **Fixed** — `dataExtractionRules` + `fullBackupContent` exclude all app data |
| 7 | M4 Insufficient input validation | API key with `\r\n` / control chars → header injection or crash; malformed URL → crash | Medium | **Fixed** — strict key/URL/model/language validation; tests `headerInjectionThroughKeyIsBlocked`, `ValidationTest` |
| 8 | M4 / CODE | Path traversal: entry ids are used as folder names | Low (ids are internal) | **Fixed** — ids must match the timestamp pattern; tampered metadata ignored; tests `pathTraversalIdsAreRejected`, `tamperedMetaWithMismatchedIdIsIgnored` |
| 9 | PLATFORM | FileProvider exposed the whole entries folder (audio + metadata) to any share grant | Medium | **Fixed** — only `files/shared/` (finished .txt files) is shareable |
| 10 | PLATFORM | Task hijacking (StrandHogg-style) | Low | **Fixed** — `taskAffinity=""`, `singleTask` |
| 11 | M8 Security misconfiguration / PRIVACY | Transcripts visible in screenshots, screen recordings and the Recents thumbnail | Low–Medium | **Fixed** — `FLAG_SECURE` on by default (toggle in Settings) |
| 12 | M4 / RESILIENCE | A hostile or broken server could return a huge body → out-of-memory | Low | **Fixed** — 2 MB response cap, error text truncated; tests `hugeResponseIsRejectedNotBuffered`, `hostileErrorBodyIsTruncated` |
| 13 | CODE | Worker could recreate a deleted entry (late write after delete) | Low (privacy: deleted diary reappearing) | **Fixed** — writes never resurrect; delete cancels transcription; test `writesAfterDeleteNeverResurrectAnEntry` |
| 14 | CODE | Unexpected exception left an entry stuck "Transcribing" forever | Low | **Fixed** — catch-all marks it Failed with Retry |
| 15 | M2 Supply chain | Guava 33.3.1 (via Media3) has GHSA-xxph-c9ww-hj94 (deserialization DoS) | Low (not reachable: no Java deserialization) | **Fixed** — pinned 33.7.2 |
| 16 | CODE (lint) | `MediaRecorder(Context)` needs API 31 → crash on Android 10–11 | High (crash) | **Fixed** — version-gated |
| 17 | M9 / PRIVACY | Exported .txt in Documents/AudioDiary is readable by apps you grant "All files access" and by a PC over USB | Inherent to the feature you asked for | **Accepted, disclosed** — toggle "Save transcripts as .txt files" in Settings |

## Verified clean

- **Exported components** (from the built APK): only the launcher activity, plus WorkManager/ProfileInstaller
  components guarded by system-only permissions (`BIND_JOB_SERVICE`, `DUMP`). The recorder service and
  FileProvider are not exported, so other apps cannot start/stop recording or read files.
- **PendingIntents** are explicit and `FLAG_IMMUTABLE`.
- **Not debuggable** in the release APK; signed with APK Signature Scheme v2; 16 KB page-aligned.
- **No secrets in the APK or repo.** The signing key is not committed (`*.jks` is git-ignored).
- **Logging**: no transcript text, audio paths beyond file names, or keys are logged.
- **No WebView, no deep links, no dynamic code loading, no JavaScript.** Transcript text from the server is
  rendered as plain text only (test `transcriptIsTreatedAsPlainData`).
- **Real API error format** confirmed against api.openai.com and api.groq.com with an invalid key (401 with
  `error.message`; OpenAI masks the key in the message).
- **Dependencies**: 114 runtime packages checked against OSV; only the Guava advisory above.

## Residual risks (not fixed, by design or out of reach)

- Anyone who can unlock your phone can open the app. An in-app biometric lock is a possible next step.
- Audio is sent to the transcription provider you choose (OpenAI or Groq), under their data policies.
- No certificate pinning (it breaks when providers rotate certificates); system CA trust only.
- The keyboard may learn words you type when editing a transcript (Compose exposes no "incognito" IME flag).
- Root access, a compromised OS, or malware with accessibility permissions defeat app-level protections.
