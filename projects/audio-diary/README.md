# Audio Diary (Android)

Record your thoughts, get an accurate transcript, keep it as a plain `.txt` file.

- **Record** with one tap. Keeps recording with the screen off; pause/resume/stop from the notification.
- **Transcribe** with a high-accuracy model through your own API key: OpenAI `gpt-4o-transcribe` (default),
  Groq `whisper-large-v3`, or any HTTPS server with an OpenAI-compatible `/audio/transcriptions` endpoint.
  Add names and jargon under "Words to spell right" to fix the usual mis-hearings.
- **Text files**: each transcript is saved as `Documents/AudioDiary/<date_time>.txt` (header line with date and
  length, blank line, transcript). You can also share, edit or re-transcribe any entry.
- Works offline: recordings queue and transcribe when you're back online.

Target device: OnePlus 12R (Android 14–16). Min Android 10, target SDK 35.

## How it works

```
RecorderService (foreground, mic)  --4-min AAC segments-->  files/entries/<id>/seg_NNN.m4a
        | stop
        v
TranscribeWorker (WorkManager, needs network, expedited, retries)
        |  POST {baseUrl}/audio/transcriptions per segment, prompt = vocabulary + tail of previous segment
        v
files/entries/<id>/body.txt  -> files/shared/<id>.txt -> MediaStore Documents/AudioDiary/<id>.txt
```

Why 4-minute segments: `gpt-4o-transcribe` silently truncates output beyond ~2k tokens (≈8–9 min of speech),
and all providers cap uploads at 25 MB. Segments are gapless (`MediaRecorder.setNextOutputFile`); the previous
segment's last words are sent as the prompt so sentences continue across the cut.

## Build

```
cd projects/audio-diary
./gradlew testReleaseUnitTest lintRelease assembleRelease
```

Release signing reads `AUDIO_DIARY_KEYSTORE` and `AUDIO_DIARY_KEYSTORE_PASSWORD` from the environment and falls
back to the debug key if they're unset. The keystore is never committed. Install updates signed with the same
key, or Android will refuse the update (and uninstalling deletes in-app audio).

## Security

See [docs/security-review.md](docs/security-review.md).
