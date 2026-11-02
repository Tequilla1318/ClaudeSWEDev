package dev.claudeswe.audiodiary.data

import org.json.JSONObject

/** Lifecycle of one diary entry. */
enum class EntryStatus { RECORDING, QUEUED, TRANSCRIBING, DONE, FAILED }

/**
 * One recording session. Audio is stored as consecutive segments (seg_000.m4a, seg_001.m4a, ...)
 * so each upload stays short enough for every transcription model; see [EntryStore].
 */
data class Entry(
    val id: String,
    val createdAt: Long,
    val durationMs: Long = 0,
    val status: EntryStatus = EntryStatus.RECORDING,
    val error: String? = null,
    val edited: Boolean = false,
    val exportUri: String? = null,
    val preview: String = "",
    /** The app was killed while recording; the last audio segment may be unfinished. */
    val interrupted: Boolean = false,
) {
    fun toJson(): String = JSONObject()
        .put("id", id)
        .put("createdAt", createdAt)
        .put("durationMs", durationMs)
        .put("status", status.name)
        .put("error", error ?: JSONObject.NULL)
        .put("edited", edited)
        .put("exportUri", exportUri ?: JSONObject.NULL)
        .put("preview", preview)
        .put("interrupted", interrupted)
        .toString(2)

    companion object {
        fun fromJson(json: String): Entry {
            val o = JSONObject(json)
            return Entry(
                id = o.getString("id"),
                createdAt = o.getLong("createdAt"),
                durationMs = o.optLong("durationMs", 0),
                status = runCatching { EntryStatus.valueOf(o.getString("status")) }
                    .getOrDefault(EntryStatus.FAILED),
                error = o.optStringOrNull("error"),
                edited = o.optBoolean("edited", false),
                exportUri = o.optStringOrNull("exportUri"),
                preview = o.optString("preview", ""),
                interrupted = o.optBoolean("interrupted", false),
            )
        }

        private fun JSONObject.optStringOrNull(key: String): String? =
            if (!has(key) || isNull(key)) null else getString(key)
    }
}
