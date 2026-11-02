package dev.claudeswe.audiodiary.recording

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/** What the recorder is doing right now; published by [RecorderService], observed by the UI. */
data class RecorderState(
    val entryId: String? = null,
    val paused: Boolean = false,
    val elapsedMs: Long = 0,
    /** Input level 0..1 for the meter. */
    val level: Float = 0f,
    val error: String? = null,
) {
    val active: Boolean get() = entryId != null
}

object RecorderBus {
    internal val mutable = MutableStateFlow(RecorderState())
    val state: StateFlow<RecorderState> = mutable
}
