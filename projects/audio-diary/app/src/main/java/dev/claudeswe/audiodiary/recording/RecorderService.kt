package dev.claudeswe.audiodiary.recording

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import dev.claudeswe.audiodiary.DiaryApp
import dev.claudeswe.audiodiary.MainActivity
import dev.claudeswe.audiodiary.R
import dev.claudeswe.audiodiary.data.EntryStatus
import dev.claudeswe.audiodiary.transcribe.TranscribeWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlin.math.ln

/**
 * Foreground service that owns the [MediaRecorder], so recording keeps going with the screen off or the app
 * in the background.
 *
 * Audio is AAC-LC, mono, 44.1 kHz, 64 kbit/s (~480 KB/min): the most widely supported encoder configuration
 * across Android devices, and plenty for speech.
 * The recorder rolls over to a new file every ~4 minutes using [MediaRecorder.setNextOutputFile], which is
 * gapless. Short segments keep every upload far below provider limits (25 MB, and gpt-4o-transcribe's
 * ~2k-token output cap that silently truncates long files).
 */
class RecorderService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var recorder: MediaRecorder? = null
    private var ticker: Job? = null
    private var entryId: String? = null
    private var segmentIndex = 0
    private var accumulatedMs = 0L
    private var resumedAt = 0L
    private var paused = false

    private val app get() = application as DiaryApp

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> start()
            ACTION_PAUSE -> pause()
            ACTION_RESUME -> resume()
            ACTION_STOP -> finish(keep = true)
            ACTION_DISCARD -> finish(keep = false)
        }
        return START_NOT_STICKY
    }

    private fun start() {
        if (recorder != null) return
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                startForeground(NOTIFICATION_ID, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            } else {
                // Android 10 has no microphone service type; a plain foreground service may use the mic.
                startForeground(NOTIFICATION_ID, notification())
            }
        } catch (e: Exception) {
            // e.g. mic permission revoked, or the system refused a background start.
            Log.e(TAG, "startForeground refused", e)
            RecorderBus.mutable.value = RecorderState(error = "Android didn't allow recording to start. Open the app and try again.")
            stopSelf()
            return
        }
        val entry = app.store.create(System.currentTimeMillis())
        entryId = entry.id
        segmentIndex = 0
        accumulatedMs = 0
        paused = false
        try {
            recorder = newRecorder().also { it.start() }
        } catch (e: Exception) {
            Log.e(TAG, "Could not start recording", e)
            app.store.delete(entry.id)
            entryId = null
            recorder?.release()
            recorder = null
            RecorderBus.mutable.value = RecorderState(error = "Couldn't start the microphone: ${e.message}")
            stopSelf()
            return
        }
        resumedAt = SystemClock.elapsedRealtime()
        publish()
        ticker = scope.launch {
            while (isActive) {
                publish()
                delay(100)
            }
        }
    }

    private fun newRecorder(): MediaRecorder {
        val id = entryId!!
        val recorder = if (Build.VERSION.SDK_INT >= 31) MediaRecorder(this) else @Suppress("DEPRECATION") MediaRecorder()
        return recorder.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioChannels(1)
            setAudioSamplingRate(SAMPLE_RATE)
            setAudioEncodingBitRate(BIT_RATE)
            setMaxFileSize(SEGMENT_BYTES)
            setOutputFile(app.store.segmentAudio(id, segmentIndex))
            setOnInfoListener { mr, what, _ ->
                when (what) {
                    MediaRecorder.MEDIA_RECORDER_INFO_MAX_FILESIZE_APPROACHING -> runCatching {
                        mr.setNextOutputFile(app.store.segmentAudio(id, segmentIndex + 1))
                    }.onFailure { Log.e(TAG, "Could not queue next segment", it) }
                    MediaRecorder.MEDIA_RECORDER_INFO_NEXT_OUTPUT_FILE_STARTED -> segmentIndex++
                    MediaRecorder.MEDIA_RECORDER_INFO_MAX_FILESIZE_REACHED -> {
                        // Rollover failed; stop cleanly rather than lose the audio already captured.
                        scope.launch { finish(keep = true) }
                    }
                }
            }
            setOnErrorListener { _, what, extra ->
                Log.e(TAG, "MediaRecorder error $what/$extra")
                scope.launch { finish(keep = true) }
            }
            prepare()
        }
    }

    private fun pause() {
        val r = recorder ?: return
        if (paused) return
        runCatching { r.pause() }.onSuccess {
            paused = true
            accumulatedMs += SystemClock.elapsedRealtime() - resumedAt
            publish()
            updateNotification()
        }
    }

    private fun resume() {
        val r = recorder ?: return
        if (!paused) return
        runCatching { r.resume() }.onSuccess {
            paused = false
            resumedAt = SystemClock.elapsedRealtime()
            publish()
            updateNotification()
        }
    }

    private fun elapsed(): Long =
        accumulatedMs + if (paused || recorder == null) 0 else SystemClock.elapsedRealtime() - resumedAt

    private fun publish() {
        val level = if (paused) 0f else runCatching { recorder?.maxAmplitude ?: 0 }.getOrDefault(0).let(::toLevel)
        RecorderBus.mutable.value = RecorderState(entryId = entryId, paused = paused, elapsedMs = elapsed(), level = level)
    }

    private fun finish(keep: Boolean) {
        val id = entryId ?: run { stopSelf(); return }
        val duration = elapsed()
        ticker?.cancel()
        recorder?.let { r ->
            // stop() throws if no audio was captured; the file is then empty and gets cleaned up below.
            runCatching { r.stop() }.onFailure { Log.w(TAG, "stop() failed", it) }
            r.release()
        }
        recorder = null
        entryId = null
        RecorderBus.mutable.value = RecorderState()

        val hasAudio = app.store.segments(id).any { it.length() > 0 }
        if (!keep || !hasAudio || duration < 500) {
            app.store.delete(id)
        } else {
            app.store.update(id) { it.copy(durationMs = duration, status = EntryStatus.QUEUED) }
            TranscribeWorker.enqueue(this, id)
        }
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        if (recorder != null) finish(keep = true)
        scope.cancel()
        super.onDestroy()
    }

    private fun notification(): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, DiaryApp.CHANNEL_RECORDING)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(if (paused) "Recording paused" else "Recording")
            .setContentText("Audio Diary")
            .setOngoing(true)
            .setContentIntent(open)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)
            .addAction(0, if (paused) "Resume" else "Pause", action(if (paused) ACTION_RESUME else ACTION_PAUSE, 1))
            .addAction(0, "Stop & save", action(ACTION_STOP, 2))
            .build()
    }

    private fun updateNotification() {
        getSystemService(android.app.NotificationManager::class.java).notify(NOTIFICATION_ID, notification())
    }

    private fun action(name: String, code: Int) = PendingIntent.getService(
        this, code, Intent(this, RecorderService::class.java).setAction(name), PendingIntent.FLAG_IMMUTABLE,
    )

    companion object {
        private const val TAG = "RecorderService"
        private const val NOTIFICATION_ID = 1
        const val SAMPLE_RATE = 44_100
        const val BIT_RATE = 64_000

        /** ~4 minutes at 64 kbit/s. */
        const val SEGMENT_BYTES = 1_920_000L

        const val ACTION_START = "start"
        const val ACTION_PAUSE = "pause"
        const val ACTION_RESUME = "resume"
        const val ACTION_STOP = "stop"
        const val ACTION_DISCARD = "discard"

        fun send(context: Context, action: String) {
            val intent = Intent(context, RecorderService::class.java).setAction(action)
            try {
                if (action == ACTION_START) context.startForegroundService(intent) else context.startService(intent)
            } catch (e: Exception) {
                Log.e(TAG, "Could not deliver $action", e)
                if (action == ACTION_START) {
                    RecorderBus.mutable.value = RecorderState(error = "Couldn't start recording. Please try again.")
                }
            }
        }

        /** Maps MediaRecorder's 0..32767 peak amplitude onto a perceptual 0..1 meter (log scale). */
        fun toLevel(amplitude: Int): Float {
            if (amplitude <= 0) return 0f
            val db = 20 * ln(amplitude / 32767.0) / ln(10.0) // 0 dBFS at full scale
            return ((db + 50) / 50).toFloat().coerceIn(0f, 1f)
        }
    }
}
