package dev.claudeswe.audiodiary

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import dev.claudeswe.audiodiary.data.EntryStatus
import dev.claudeswe.audiodiary.data.EntryStore
import dev.claudeswe.audiodiary.data.SettingsStore
import dev.claudeswe.audiodiary.recording.RecorderBus
import dev.claudeswe.audiodiary.recording.RecorderService
import dev.claudeswe.audiodiary.transcribe.TranscribeWorker
import java.io.File

class DiaryApp : Application() {
    lateinit var store: EntryStore
        private set
    lateinit var settings: SettingsStore
        private set

    override fun onCreate() {
        super.onCreate()
        store = EntryStore(File(filesDir, "entries"))
        settings = SettingsStore(this)
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_RECORDING, "Recording", NotificationManager.IMPORTANCE_LOW),
        )
        recoverInterruptedRecordings()
    }

    /**
     * A fresh process can't have a recording in progress, so any entry still marked RECORDING was cut short
     * (app killed, phone rebooted). Keep whatever audio made it to disk and transcribe it.
     */
    private fun recoverInterruptedRecordings() {
        if (RecorderBus.state.value.entryId != null) return
        for (entry in store.list().filter { it.status == EntryStatus.RECORDING }) {
            if (store.segments(entry.id).none { it.length() > 0 }) {
                store.delete(entry.id)
            } else {
                // Duration wasn't recorded; estimate it from the audio size at the fixed bit rate.
                val bytes = store.segments(entry.id).sumOf { it.length() }
                val estimateMs = bytes * 8 * 1000 / RecorderService.BIT_RATE
                store.update(entry.id) { it.copy(interrupted = true, durationMs = estimateMs) }
                TranscribeWorker.enqueue(this, entry.id)
            }
        }
    }

    companion object {
        const val CHANNEL_RECORDING = "recording"
    }
}
