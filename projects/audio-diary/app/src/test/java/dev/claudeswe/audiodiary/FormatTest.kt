package dev.claudeswe.audiodiary

import dev.claudeswe.audiodiary.data.Format
import dev.claudeswe.audiodiary.recording.RecorderService
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDateTime
import java.time.ZoneId

class FormatTest {
    private val zone = ZoneId.of("America/Toronto")
    private val t = LocalDateTime.of(2026, 11, 1, 20, 45, 12).atZone(zone).toInstant().toEpochMilli()

    @Test fun entryIdIsFileSafeAndSortable() {
        assertEquals("2026-11-01_20-45-12", Format.entryId(t, zone))
    }

    @Test fun clock() {
        assertEquals("0:00", Format.clock(0))
        assertEquals("0:07", Format.clock(7_900))
        assertEquals("3:12", Format.clock(192_000))
        assertEquals("1:02:05", Format.clock(3_725_000))
        assertEquals("0:00", Format.clock(-5))
    }

    @Test fun duration() {
        assertEquals("45s", Format.duration(45_000))
        assertEquals("3m 12s", Format.duration(192_000))
        assertEquals("1h 2m", Format.duration(3_725_000))
    }

    @Test fun textFileHasHeaderBlankLineAndTrimmedBody() {
        val text = Format.textFile(t, 192_000, "  Hello there.\n", zone)
        assertEquals("Sun 1 Nov 2026, 20:45 · 3m 12s\n\nHello there.\n", text)
    }

    @Test fun previewCollapsesWhitespaceAndCutsOnWordBoundary() {
        assertEquals("a b c", Format.preview("a\n\n b   c"))
        val long = "word ".repeat(60)
        val p = Format.preview(long, max = 20)
        assertTrue(p.endsWith("…"))
        assertEquals("word word word word…", p)
    }

    @Test fun levelMeterScale() {
        assertEquals(0f, RecorderService.toLevel(0), 0f)
        assertEquals(1f, RecorderService.toLevel(32767), 1e-6f)
        // -20 dBFS (amplitude ~3277) sits at 60% of a 50 dB meter.
        assertEquals(0.6f, RecorderService.toLevel(3277), 0.01f)
        assertEquals(0f, RecorderService.toLevel(10), 0f) // below -50 dBFS clamps to 0
    }

    @Test fun segmentSizeIsAboutFourMinutes() {
        val seconds = RecorderService.SEGMENT_BYTES * 8.0 / RecorderService.BIT_RATE
        assertEquals(240.0, seconds, 1.0)
    }
}
