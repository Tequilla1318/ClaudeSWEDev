package dev.claudeswe.audiodiary

import dev.claudeswe.audiodiary.data.Provider
import dev.claudeswe.audiodiary.data.TranscriptionSettings
import dev.claudeswe.audiodiary.data.Validation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class ValidationTest {
    private val ok = TranscriptionSettings(apiKey = "sk-proj-abcdEFGH1234_-")

    @Test fun presetsAreValidWithAKey() {
        for (p in listOf(Provider.OPENAI, Provider.GROQ)) {
            assertNull(Validation.problem(ok.copy(provider = p, baseUrl = p.baseUrl, model = p.defaultModel)))
        }
    }

    @Test fun missingOrMalformedKey() {
        assertEquals("No API key set.", Validation.problem(ok.copy(apiKey = "")))
        listOf("has space key", "line\nbreak123", "tab\tkey123", "short", "ключ-ключ-ключ").forEach {
            assertNotNull(it, Validation.problem(ok.copy(apiKey = it)))
        }
    }

    @Test fun baseUrlMustBeCleanHttps() {
        assertNull(Validation.baseUrlProblem("https://my.server.example/v1"))
        assertNull(Validation.baseUrlProblem("https://10.0.0.5:8443/v1"))
        listOf(
            "http://api.openai.com/v1",
            "ftp://x/v1",
            "javascript:alert(1)",
            "file:///data/data/x",
            "https://user:pw@host/v1",
            "https://host/v1?redirect=evil",
            "https://host/v1#frag",
            "",
            "   ",
        ).forEach { assertNotNull(it, Validation.baseUrlProblem(it)) }
    }

    @Test fun modelAndLanguage() {
        assertNotNull(Validation.problem(ok.copy(model = "")))
        assertNotNull(Validation.problem(ok.copy(model = "gpt 4o")))
        assertNotNull(Validation.problem(ok.copy(model = "m\r\nx")))
        assertNull(Validation.problem(ok.copy(model = "Systran/faster-whisper-large-v3")))
        assertNull(Validation.problem(ok.copy(language = "en")))
        assertNull(Validation.problem(ok.copy(language = "")))
        assertNotNull(Validation.problem(ok.copy(language = "english")))
        assertNotNull(Validation.problem(ok.copy(language = "e n")))
    }
}
