package dev.claudeswe.audiodiary.transcribe

import dev.claudeswe.audiodiary.data.Validation
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * @property retryable true for failures worth retrying later (rate limits, server errors, network);
 *   false for ones that need the user to fix something (bad key, bad model name).
 */
class TranscriptionException(message: String, val httpCode: Int?, val retryable: Boolean) : Exception(message)

/**
 * Client for any OpenAI-compatible `POST {baseUrl}/audio/transcriptions` endpoint
 * (OpenAI, Groq, a self-hosted faster-whisper server, ...).
 */
class TranscriptionClient(
    private val baseUrl: String,
    private val apiKey: String,
    private val model: String,
    private val http: OkHttpClient = defaultHttp,
) {
    /**
     * Transcribes one audio file.
     *
     * @param language ISO-639-1 code, or blank to let the model detect it.
     * @param prompt spelling hints / preceding text; improves names, jargon and continuity across segments.
     */
    fun transcribe(audio: File, language: String = "", prompt: String = ""): String {
        checkConfig()
        val body = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("file", audio.name, audio.asRequestBody("audio/mp4".toMediaType()))
            .addFormDataPart("model", model)
            .addFormDataPart("response_format", "json")
            .apply {
                if (language.isNotBlank()) addFormDataPart("language", language.trim())
                if (prompt.isNotBlank()) addFormDataPart("prompt", prompt)
            }
            .build()
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/audio/transcriptions")
            .header("Authorization", "Bearer $apiKey")
            .post(body)
            .build()

        val (code, text) = execute(request)
        if (code !in 200..299) throw httpError(code, text)
        return try {
            JSONObject(text).getString("text").trim()
        } catch (e: Exception) {
            throw TranscriptionException("Unexpected response from server: ${text.take(200)}", code, false)
        }
    }

    /** Cheap credential check: `GET {baseUrl}/models` (supported by OpenAI and Groq). */
    fun checkKey(): String {
        checkConfig()
        val request = Request.Builder()
            .url(baseUrl.trimEnd('/') + "/models")
            .header("Authorization", "Bearer $apiKey")
            .get()
            .build()
        val (code, text) = execute(request)
        if (code !in 200..299) throw httpError(code, text)
        val models = runCatching {
            val data = JSONObject(text).getJSONArray("data")
            (0 until data.length()).map { data.getJSONObject(it).getString("id") }
        }.getOrDefault(emptyList())
        return if (models.isEmpty() || model in models) {
            "Key works."
        } else {
            "Key works, but model \"$model\" isn't in this provider's model list."
        }
    }

    /** Refuses to send the key to a non-HTTPS or malformed URL, or to put a malformed key in a header. */
    private fun checkConfig() {
        Validation.baseUrlProblem(baseUrl)?.let { throw TranscriptionException(it, null, false) }
        if (!Validation.keyLooksValid(apiKey)) {
            throw TranscriptionException("The API key contains spaces or unusual characters.", null, false)
        }
    }

    private fun execute(request: Request): Pair<Int, String> = try {
        http.newCall(request).execute().use { response ->
            val body = response.body ?: return@use response.code to ""
            // Cap what we read so a hostile or broken server can't exhaust memory.
            val source = body.source()
            source.request(MAX_RESPONSE_BYTES + 1)
            if (source.buffer.size > MAX_RESPONSE_BYTES) {
                throw TranscriptionException("Server response was too large.", response.code, false)
            }
            response.code to source.buffer.readUtf8()
        }
    } catch (e: TranscriptionException) {
        throw e
    } catch (e: IOException) {
        throw TranscriptionException("Network error: ${e.message ?: e.javaClass.simpleName}", null, true)
    } catch (e: RuntimeException) {
        throw TranscriptionException("Request failed: ${e.javaClass.simpleName}", null, false)
    }

    companion object {
        /** 2 MB is ~300k words of transcript JSON; far beyond any real response for a 4-minute segment. */
        const val MAX_RESPONSE_BYTES = 2L * 1024 * 1024

        private val defaultHttp: OkHttpClient by lazy { hardened(OkHttpClient.Builder()) }

        /** Applies the app's network hardening to [builder]; tests use it to get identical behaviour over test TLS. */
        fun hardened(builder: OkHttpClient.Builder): OkHttpClient = builder
            // Never follow redirects: a redirect could carry the request (and the audio) somewhere unexpected.
            .followRedirects(false)
            .followSslRedirects(false)
            .retryOnConnectionFailure(false) // don't silently re-upload; the worker decides about retries
            .connectTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .readTimeout(180, TimeUnit.SECONDS)
            .build()

        /** Turns an error response into a readable message, preferring the API's own `error.message`. */
        fun httpError(code: Int, body: String): TranscriptionException {
            val apiMessage = (
                runCatching { JSONObject(body).getJSONObject("error").getString("message") }.getOrNull()
                    ?: body.ifBlank { "no details" }
                ).take(200)
            val retryable = code == 408 || code == 429 || code >= 500
            val hint = when (code) {
                401 -> "API key rejected"
                403 -> "Access denied"
                404 -> "Endpoint or model not found"
                413 -> "Audio segment too large"
                429 -> "Rate limited or out of credit"
                else -> "HTTP $code"
            }
            return TranscriptionException("$hint: $apiMessage", code, retryable)
        }

        /** Max characters of hint text sent as `prompt` (Whisper reads at most ~224 tokens of it). */
        const val PROMPT_CHARS = 800

        /**
         * Builds the `prompt` for a segment: the user's vocabulary list first, then the tail of the previous
         * segment's transcript so a sentence cut at a segment boundary carries on naturally.
         */
        fun buildPrompt(vocabulary: String, previousText: String): String {
            val vocab = vocabulary.replace(Regex("\\s+"), " ").trim().take(PROMPT_CHARS / 2)
            val budget = PROMPT_CHARS - vocab.length
            val prev = previousText.trim().let { p ->
                if (p.length <= budget) p else p.takeLast(budget).substringAfter(' ', p.takeLast(budget))
            }
            return listOf(vocab, prev).filter { it.isNotBlank() }.joinToString("\n")
        }
    }
}
