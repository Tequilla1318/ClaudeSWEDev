package dev.claudeswe.audiodiary.data

import android.content.ContentValues
import android.content.Context
import androidx.core.net.toUri
import android.os.Environment
import android.provider.MediaStore
import android.util.Log

/**
 * Mirrors each transcript as a plain .txt in the phone's shared storage, `Documents/AudioDiary/`,
 * so it's visible in the Files app and to sync tools. Uses MediaStore, so no storage permission is needed.
 */
object TextExporter {
    const val FOLDER = "AudioDiary"
    private const val TAG = "TextExporter"

    /** Human-readable location shown in the UI. */
    val displayFolder: String = "${Environment.DIRECTORY_DOCUMENTS}/$FOLDER"

    /**
     * Writes [text] as `<id>.txt`. Overwrites the previous export when [previous] still belongs to us;
     * otherwise creates a new file. Returns the content URI, or null if shared storage refused.
     */
    fun export(context: Context, id: String, text: String, previous: String?): String? {
        val resolver = context.contentResolver
        previous?.takeIf { it.startsWith("content://media/") }?.let { prev ->
            val ok = runCatching {
                resolver.openOutputStream(prev.toUri(), "wt")?.use { it.write(text.toByteArray()) } != null
            }.getOrDefault(false)
            if (ok) return prev
        }
        val attempts = listOf(
            MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL) to Environment.DIRECTORY_DOCUMENTS,
            MediaStore.Downloads.EXTERNAL_CONTENT_URI to Environment.DIRECTORY_DOWNLOADS,
        )
        for ((collection, base) in attempts) {
            try {
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, "$id.txt")
                    put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
                    put(MediaStore.MediaColumns.RELATIVE_PATH, "$base/$FOLDER")
                }
                val uri = resolver.insert(collection, values) ?: continue
                resolver.openOutputStream(uri, "wt")?.use { it.write(text.toByteArray()) }
                return uri.toString()
            } catch (e: Exception) {
                Log.w(TAG, "Export to $base failed", e)
            }
        }
        return null
    }

    fun delete(context: Context, uri: String) {
        runCatching { context.contentResolver.delete(uri.toUri(), null, null) }
    }
}
