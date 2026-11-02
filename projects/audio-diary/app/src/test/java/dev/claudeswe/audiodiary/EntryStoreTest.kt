package dev.claudeswe.audiodiary

import dev.claudeswe.audiodiary.data.Entry
import dev.claudeswe.audiodiary.data.EntryStatus
import dev.claudeswe.audiodiary.data.EntryStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class EntryStoreTest {
    @get:Rule val tmp = TemporaryFolder()

    private fun store() = EntryStore(File(tmp.root, "entries"))
    private fun id(n: Int) = "2026-11-01_20-45-%02d".format(n)

    @Test fun entryJsonRoundTrip() {
        val e = Entry(id(1), 123, 4567, EntryStatus.FAILED, "boom", true, "content://x/1", "hi", interrupted = true)
        assertEquals(e, Entry.fromJson(e.toJson()))
        val minimal = Entry(id(2), 5)
        assertEquals(minimal, Entry.fromJson(minimal.toJson()))
    }

    @Test fun unknownStatusLoadsAsFailedInsteadOfCrashing() {
        val json = Entry(id(1), 1).toJson().replace("RECORDING", "SOMETHING_NEW")
        assertEquals(EntryStatus.FAILED, Entry.fromJson(json).status)
    }

    @Test fun createGivesUniqueIdsForSameSecond() {
        val store = store()
        assertEquals(id(12), store.create(1000, baseId = id(12)).id)
        assertEquals(id(12) + "-2", store.create(1000, baseId = id(12)).id)
    }

    @Test fun listIsNewestFirstAndSkipsJunk() {
        val store = store()
        store.create(1000, id(1))
        store.create(3000, id(3))
        store.create(2000, id(2))
        File(store.root, id(4)).mkdirs() // no meta.json
        File(store.root, "stray.txt").writeText("x")
        File(store.root, "not-an-id").mkdirs()
        assertEquals(listOf(id(3), id(2), id(1)), store.list().map { it.id })
    }

    @Test fun segmentsAreOrderedAndTextFilesIgnored() {
        val store = store()
        val e = store.create(1, id(1))
        listOf(10, 2, 0, 1).forEach { store.segmentAudio(e.id, it).writeText("a") }
        store.segmentText(store.segmentAudio(e.id, 0)).writeText("t")
        assertEquals(
            listOf("seg_000.m4a", "seg_001.m4a", "seg_002.m4a", "seg_010.m4a"),
            store.segments(e.id).map { it.name },
        )
    }

    @Test fun writeBodyPutsShareableFileOutsideEntryFolder() {
        val store = store()
        val e = store.create(0, id(1)).copy(durationMs = 5_000)
        store.writeBody(e, "  hello world  ")
        assertEquals("hello world\n", store.readBody(e.id))
        val file = store.textFile(e.id)
        assertEquals("${id(1)}.txt", file.name)
        assertEquals(store.sharedDir, file.parentFile)
        assertTrue(file.readText().endsWith("\n\nhello world\n"))
    }

    @Test fun clearSegmentTranscriptsKeepsAudio() {
        val store = store()
        val e = store.create(0, id(1))
        val audio = store.segmentAudio(e.id, 0).apply { writeText("a") }
        store.segmentText(audio).writeText("t")
        store.clearSegmentTranscripts(e.id)
        assertTrue(audio.exists())
        assertFalse(store.segmentText(audio).exists())
    }

    @Test fun updateAndDeleteRemoveEverything() {
        val store = store()
        val e = store.create(0, id(1))
        store.writeBody(e, "text")
        val v0 = store.version.value
        store.update(e.id) { it.copy(status = EntryStatus.DONE) }
        assertEquals(EntryStatus.DONE, store.load(e.id)!!.status)
        assertTrue(store.version.value > v0)
        store.delete(e.id)
        assertNull(store.load(e.id))
        assertFalse(store.textFile(e.id).exists())
        assertNull(store.update(e.id) { it })
    }

    @Test fun writesAfterDeleteNeverResurrectAnEntry() {
        // The worker may still be running when the user deletes; its late writes must be no-ops.
        val store = store()
        val e = store.create(0, id(1))
        store.delete(e.id)
        store.save(e.copy(status = EntryStatus.DONE))
        assertNull(store.writeBody(e, "late transcript"))
        assertFalse(store.dir(e.id).exists())
        assertFalse(store.textFile(e.id).exists())
        assertTrue(store.list().isEmpty())
    }

    @Test fun pathTraversalIdsAreRejected() {
        val store = store()
        val secret = File(tmp.root, "secret.txt").apply { writeText("do not touch") }
        for (bad in listOf("..", "../secret", "../../etc", "/etc/passwd", "a/b", "", ".", id(1) + "/..")) {
            try {
                store.dir(bad)
                fail("accepted id '$bad'")
            } catch (_: IllegalArgumentException) {
            }
            assertFalse(store.exists(bad))
        }
        // delete() goes through dir(), so it can't be pointed outside the store either.
        try {
            store.delete("..")
        } catch (_: IllegalArgumentException) {
        }
        assertTrue(secret.exists())
        assertTrue(store.root.exists())
    }

    @Test fun tamperedMetaWithMismatchedIdIsIgnored() {
        val store = store()
        store.create(0, id(1))
        File(store.dir(id(1)), "meta.json").writeText(Entry("../../evil", 0).toJson())
        assertNull(store.load(id(1)))
    }

    @Test fun assembleJoinsNonEmptyPartsWithSpaces() {
        assertEquals("one two three", EntryStore.assemble(listOf(" one ", "", "two\n", "   ", "three")))
        assertEquals("", EntryStore.assemble(emptyList()))
    }
}
