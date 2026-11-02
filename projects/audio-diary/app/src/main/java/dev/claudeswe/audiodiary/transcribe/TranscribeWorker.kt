package dev.claudeswe.audiodiary.transcribe

import android.content.Context
import android.content.pm.ServiceInfo
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import androidx.work.workDataOf
import dev.claudeswe.audiodiary.DiaryApp
import dev.claudeswe.audiodiary.R
import dev.claudeswe.audiodiary.data.EntryStatus
import dev.claudeswe.audiodiary.data.EntryStore
import dev.claudeswe.audiodiary.data.Format
import dev.claudeswe.audiodiary.data.TextExporter
import dev.claudeswe.audiodiary.data.Validation
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

/**
 * Transcribes an entry's audio segments one by one (skipping ones already done, so a retry resumes where it
 * stopped), then assembles the transcript and exports the .txt. Runs only with a network connection, as
 * expedited work so battery managers (e.g. OxygenOS) don't defer it for hours, and retries with backoff on
 * network/server errors. Any unexpected failure leaves the entry FAILED with a Retry button, never stuck.
 */
class TranscribeWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val app = applicationContext as DiaryApp
        val store = app.store
        val id = inputData.getString(KEY_ID)?.takeIf { EntryStore.ID_PATTERN.matches(it) }
            ?: return@withContext Result.failure()
        try {
            transcribe(app, store, id)
        } catch (e: CancellationException) {
            store.update(id) { it.copy(status = EntryStatus.QUEUED) }
            throw e
        } catch (e: Exception) {
            Log.e(TAG, "Unexpected failure", e)
            store.update(id) { it.copy(status = EntryStatus.FAILED, error = "Unexpected error (${e.javaClass.simpleName}).") }
            Result.failure()
        }
    }

    private fun transcribe(app: DiaryApp, store: EntryStore, id: String): Result {
        store.load(id) ?: return Result.failure()
        val settings = app.settings.load()

        Validation.problem(settings)?.let { problem ->
            store.update(id) { it.copy(status = EntryStatus.FAILED, error = "$problem Fix it in Settings, then tap Retry.") }
            return Result.failure()
        }

        val entry = store.update(id) { it.copy(status = EntryStatus.TRANSCRIBING, error = null) }
            ?: return Result.failure()
        val client = TranscriptionClient(settings.baseUrl, settings.apiKey, settings.model)
        val parts = mutableListOf<String>()
        val segments = store.segments(id)

        for ((index, audio) in segments.withIndex()) {
            if (!store.exists(id)) return Result.failure() // deleted while we were working
            val done = store.segmentText(audio)
            if (done.exists()) {
                parts += done.readText()
                continue
            }
            if (audio.length() < MIN_SEGMENT_BYTES) {
                done.writeText("") // a sliver of audio after the last rollover; nothing worth sending
                continue
            }
            try {
                val prompt = TranscriptionClient.buildPrompt(settings.vocabulary, parts.lastOrNull() ?: "")
                val text = client.transcribe(audio, settings.language, prompt)
                done.writeText(text)
                parts += text
            } catch (e: TranscriptionException) {
                // If the app was killed mid-recording, the final segment's file is unfinished and unreadable.
                // Skip just that one instead of failing the whole entry.
                if (entry.interrupted && index == segments.lastIndex && e.httpCode == 400) {
                    Log.w(TAG, "Skipping unfinished last segment of an interrupted recording")
                    done.writeText("")
                    continue
                }
                Log.w(TAG, "Segment ${audio.name} failed: HTTP ${e.httpCode}")
                val retry = e.retryable && runAttemptCount < MAX_ATTEMPTS
                store.update(id) {
                    it.copy(
                        status = if (retry) EntryStatus.QUEUED else EntryStatus.FAILED,
                        error = e.message + if (retry) " (will retry)" else "",
                    )
                }
                return if (retry) Result.retry() else Result.failure()
            }
        }

        val body = EntryStore.assemble(parts)
        val current = store.load(id) ?: return Result.failure() // deleted meanwhile
        val text = store.writeBody(current, body) ?: return Result.failure()
        val uri = if (settings.exportText) TextExporter.export(applicationContext, id, text, current.exportUri) else null
        store.update(id) {
            it.copy(
                status = EntryStatus.DONE,
                error = if (settings.exportText && uri == null) {
                    "Transcribed, but couldn't write to ${TextExporter.displayFolder}."
                } else {
                    null
                },
                edited = false,
                exportUri = uri ?: it.exportUri,
                preview = Format.preview(body).ifBlank { "(no speech detected)" },
            )
        }
        return Result.success()
    }

    /** Only used on Android 11 and older, where expedited work runs as a short foreground service. */
    override suspend fun getForegroundInfo(): ForegroundInfo {
        val notification = NotificationCompat.Builder(applicationContext, DiaryApp.CHANNEL_RECORDING)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Transcribing")
            .setOngoing(true)
            .build()
        return ForegroundInfo(2, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
    }

    companion object {
        private const val TAG = "TranscribeWorker"
        private const val KEY_ID = "entryId"
        private const val MAX_ATTEMPTS = 6

        /** ~0.25 s of audio at 64 kbit/s; anything smaller is container overhead after a rollover. */
        private const val MIN_SEGMENT_BYTES = 2_000L

        private fun workName(id: String) = "transcribe-$id"

        /** Queues transcription of [id]. [restart] wipes previous segment transcripts first. */
        fun enqueue(context: Context, id: String, restart: Boolean = false) {
            val app = context.applicationContext as DiaryApp
            if (!app.store.exists(id)) return
            if (restart) app.store.clearSegmentTranscripts(id)
            app.store.update(id) { it.copy(status = EntryStatus.QUEUED, error = null) }
            val request = OneTimeWorkRequestBuilder<TranscribeWorker>()
                .setInputData(workDataOf(KEY_ID to id))
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_REQUEST)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(workName(id), ExistingWorkPolicy.REPLACE, request)
        }

        /** Stops any transcription of [id] (used before deleting it). */
        fun cancel(context: Context, id: String) {
            WorkManager.getInstance(context).cancelUniqueWork(workName(id))
        }
    }
}
