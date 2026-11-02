package dev.claudeswe.audiodiary

import dev.claudeswe.audiodiary.transcribe.TranscriptionClient
import dev.claudeswe.audiodiary.transcribe.TranscriptionException
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.tls.HandshakeCertificates
import okhttp3.tls.HeldCertificate
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.net.InetAddress

/**
 * Checks the request against the OpenAI audio-transcriptions contract (multipart form with `file`, `model`,
 * optional `language` / `prompt`, Bearer auth), the error handling the worker relies on, and the network
 * hardening. Runs over real TLS with a throwaway certificate so the HTTPS-only rule is exercised as in the app.
 */
class TranscriptionClientTest {
    @get:Rule val tmp = TemporaryFolder()

    private val localhost = InetAddress.getByName("localhost").canonicalHostName
    private val cert = HeldCertificate.Builder().addSubjectAlternativeName(localhost).build()
    private val serverCerts = HandshakeCertificates.Builder().heldCertificate(cert).build()
    private val clientCerts = HandshakeCertificates.Builder().addTrustedCertificate(cert.certificate).build()
    private val server = MockWebServer().apply { useHttps(serverCerts.sslSocketFactory(), false) }
    private val http: OkHttpClient = TranscriptionClient.hardened(
        OkHttpClient.Builder().sslSocketFactory(clientCerts.sslSocketFactory(), clientCerts.trustManager),
    )

    @Before fun start() = server.start()
    @After fun stop() = server.shutdown()

    private fun baseUrl() = server.url("/v1/").toString()
    private fun client(model: String = "gpt-4o-transcribe", key: String = "sk-test-123", url: String = baseUrl()) =
        TranscriptionClient(url, key, model, http)

    private fun audio() = File(tmp.root, "seg_000.m4a").apply { writeBytes(ByteArray(1234) { 7 }) }

    // ---- API contract ----

    @Test fun sendsOpenAiCompatibleMultipartRequest() {
        server.enqueue(MockResponse().setBody("""{"text":"  Hello diary.  "}"""))
        val text = client().transcribe(audio(), language = "en", prompt = "Nkechi, Kubernetes")
        assertEquals("Hello diary.", text)

        val req = server.takeRequest()
        assertEquals("POST", req.method)
        assertEquals("/v1/audio/transcriptions", req.path)
        assertEquals("Bearer sk-test-123", req.getHeader("Authorization"))
        assertTrue(req.getHeader("Content-Type")!!.startsWith("multipart/form-data"))
        val body = req.body.readUtf8()
        assertTrue(body.contains("name=\"file\"; filename=\"seg_000.m4a\""))
        assertTrue(body.contains("Content-Type: audio/mp4"))
        assertTrue(body.contains("name=\"model\"\r\nContent-Length: 17\r\n\r\ngpt-4o-transcribe"))
        assertTrue(body.contains("name=\"response_format\"\r\nContent-Length: 4\r\n\r\njson"))
        assertTrue(body.contains("name=\"language\"\r\nContent-Length: 2\r\n\r\nen"))
        assertTrue(body.contains("name=\"prompt\""))
        assertTrue(body.contains("Nkechi, Kubernetes"))
        assertTrue(req.bodySize > 1234) // audio bytes included
    }

    @Test fun omitsOptionalFieldsWhenBlank() {
        server.enqueue(MockResponse().setBody("""{"text":"x"}"""))
        client().transcribe(audio())
        val body = server.takeRequest().body.readUtf8()
        assertFalse(body.contains("name=\"language\""))
        assertFalse(body.contains("name=\"prompt\""))
    }

    @Test fun badKeyIsPermanentWithApiMessage() {
        server.enqueue(
            MockResponse().setResponseCode(401)
                .setBody("""{"error":{"message":"Incorrect API key provided.","type":"invalid_request_error"}}"""),
        )
        val e = expectFailure { client().transcribe(audio()) }
        assertEquals(401, e.httpCode)
        assertFalse(e.retryable)
        assertEquals("API key rejected: Incorrect API key provided.", e.message)
    }

    @Test fun rateLimitAndServerErrorsAreRetryable() {
        server.enqueue(MockResponse().setResponseCode(429).setBody("""{"error":{"message":"slow down"}}"""))
        assertTrue(expectFailure { client().transcribe(audio()) }.retryable)
        server.enqueue(MockResponse().setResponseCode(503).setBody("upstream down"))
        val e = expectFailure { client().transcribe(audio()) }
        assertTrue(e.retryable)
        assertEquals("HTTP 503: upstream down", e.message)
    }

    @Test fun networkFailureIsRetryable() {
        server.shutdown()
        val e = expectFailure { client().transcribe(audio()) }
        assertTrue(e.retryable)
        assertEquals(null, e.httpCode)
    }

    @Test fun malformedSuccessIsReported() {
        server.enqueue(MockResponse().setBody("<html>proxy page</html>"))
        val e = expectFailure { client().transcribe(audio()) }
        assertFalse(e.retryable)
        assertTrue(e.message!!.startsWith("Unexpected response"))
    }

    @Test fun checkKeyReportsMissingModel() {
        server.enqueue(MockResponse().setBody("""{"data":[{"id":"whisper-1"},{"id":"gpt-4o-transcribe"}]}"""))
        assertEquals("Key works.", client().checkKey())
        assertEquals("/v1/models", server.takeRequest().path)
        server.enqueue(MockResponse().setBody("""{"data":[{"id":"whisper-1"}]}"""))
        assertTrue(client("whisper-large-v3").checkKey().contains("isn't in this provider's model list"))
    }

    // ---- Attacks / hardening ----

    @Test fun refusesToSendKeyOverPlainHttp() {
        val plain = MockWebServer().apply { start() }
        try {
            val e = expectFailure { client(url = plain.url("/v1/").toString()).transcribe(audio()) }
            assertFalse(e.retryable)
            assertTrue(e.message!!.contains("https://"))
            assertEquals(0, plain.requestCount) // nothing (and so no key) was sent
        } finally {
            plain.shutdown()
        }
    }

    @Test fun refusesUrlsWithCredentialsOrJunk() {
        for (url in listOf("https://user:pw@api.example.com/v1", "https://api.example.com/v1?x=1", "not a url", "")) {
            expectFailure { client(url = url).transcribe(audio()) }
        }
        assertEquals(0, server.requestCount)
    }

    @Test fun headerInjectionThroughKeyIsBlocked() {
        for (key in listOf("sk-abc\r\nX-Evil: 1", "sk-abc def", "sk-ab\u0000cdef", "short", "sk-ünïcode-key")) {
            val e = expectFailure { client(key = key).transcribe(audio()) }
            assertFalse(e.retryable)
        }
        assertEquals(0, server.requestCount)
    }

    @Test fun doesNotFollowRedirectsToAnotherHost() {
        val attacker = MockWebServer().apply {
            useHttps(serverCerts.sslSocketFactory(), false)
            start()
        }
        try {
            server.enqueue(
                MockResponse().setResponseCode(307).setHeader("Location", attacker.url("/steal").toString()),
            )
            val e = expectFailure { client().transcribe(audio()) }
            assertEquals(307, e.httpCode)
            assertEquals(0, attacker.requestCount) // neither the key nor the audio reached the other host
        } finally {
            attacker.shutdown()
        }
    }

    @Test fun hugeResponseIsRejectedNotBuffered() {
        val big = Buffer().writeUtf8("{\"text\":\"").apply {
            val chunk = "a".repeat(64 * 1024)
            repeat(40) { writeUtf8(chunk) } // ~2.5 MB
            writeUtf8("\"}")
        }
        server.enqueue(MockResponse().setBody(big))
        val e = expectFailure { client().transcribe(audio()) }
        assertEquals("Server response was too large.", e.message)
    }

    @Test fun hostileErrorBodyIsTruncated() {
        server.enqueue(MockResponse().setResponseCode(400).setBody("x".repeat(100_000)))
        val e = expectFailure { client().transcribe(audio()) }
        assertTrue(e.message!!.length < 300)
    }

    @Test fun transcriptIsTreatedAsPlainData() {
        val nasty = "<script>alert(1)</script> ‮gnp.exe ../../etc/passwd"
        server.enqueue(MockResponse().setBody(org.json.JSONObject().put("text", nasty).toString()))
        assertEquals(nasty, client().transcribe(audio())) // returned verbatim; only ever shown as plain text
    }

    // ---- Prompt building ----

    @Test fun promptKeepsVocabularyAndTailOfPreviousSegment() {
        assertEquals("", TranscriptionClient.buildPrompt("", ""))
        assertEquals("Nkechi", TranscriptionClient.buildPrompt("  Nkechi \n", ""))
        assertEquals("Nkechi\nand then we", TranscriptionClient.buildPrompt("Nkechi", "and then we"))

        val previous = (1..400).joinToString(" ") { "w$it" }
        val p = TranscriptionClient.buildPrompt("Vocab", previous)
        assertTrue(p.length <= TranscriptionClient.PROMPT_CHARS)
        assertTrue(p.startsWith("Vocab\n"))
        assertTrue(p.endsWith("w400"))
        assertTrue(p.substringAfter("\n").startsWith("w"))

        val hugeVocab = "x".repeat(5000)
        assertEquals(TranscriptionClient.PROMPT_CHARS / 2, TranscriptionClient.buildPrompt(hugeVocab, "").length)
    }

    private fun expectFailure(block: () -> Unit): TranscriptionException {
        try {
            block()
        } catch (e: TranscriptionException) {
            return e
        }
        fail("expected TranscriptionException")
        throw AssertionError()
    }
}
