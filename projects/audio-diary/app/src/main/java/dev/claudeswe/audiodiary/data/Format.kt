package dev.claudeswe.audiodiary.data

import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Small, pure formatting helpers (unit-tested on the JVM). */
object Format {
    private val idFormat = DateTimeFormatter.ofPattern("yyyy-MM-dd_HH-mm-ss", Locale.ROOT)
    private val headerFormat = DateTimeFormatter.ofPattern("EEE d MMM yyyy, HH:mm", Locale.ENGLISH)
    private val listFormat = DateTimeFormatter.ofPattern("EEE d MMM · HH:mm", Locale.ENGLISH)

    /** File-safe id such as `2026-11-01_20-45-12`; also the base name of the exported .txt. */
    fun entryId(epochMs: Long, zone: ZoneId = ZoneId.systemDefault()): String =
        idFormat.format(Instant.ofEpochMilli(epochMs).atZone(zone))

    fun listDate(epochMs: Long, zone: ZoneId = ZoneId.systemDefault()): String =
        listFormat.format(Instant.ofEpochMilli(epochMs).atZone(zone))

    /** `0:07`, `3:12`, `1:02:05`. */
    fun clock(ms: Long): String {
        val total = (ms.coerceAtLeast(0) / 1000)
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
    }

    /** `45s`, `3m 12s`, `1h 2m`. */
    fun duration(ms: Long): String {
        val total = (ms.coerceAtLeast(0) / 1000)
        val h = total / 3600
        val m = (total % 3600) / 60
        val s = total % 60
        return when {
            h > 0 -> "${h}h ${m}m"
            m > 0 -> "${m}m ${s}s"
            else -> "${s}s"
        }
    }

    /** Contents of the exported text file: one header line, a blank line, then the transcript. */
    fun textFile(createdAt: Long, durationMs: Long, body: String, zone: ZoneId = ZoneId.systemDefault()): String {
        val header = "${headerFormat.format(Instant.ofEpochMilli(createdAt).atZone(zone))} · ${duration(durationMs)}"
        return header + "\n\n" + body.trim() + "\n"
    }

    /** First ~[max] characters of the transcript on one line, for the list. */
    fun preview(body: String, max: Int = 140): String {
        val flat = body.replace(Regex("\\s+"), " ").trim()
        return if (flat.length <= max) flat else flat.take(max).substringBeforeLast(' ') + "…"
    }
}
