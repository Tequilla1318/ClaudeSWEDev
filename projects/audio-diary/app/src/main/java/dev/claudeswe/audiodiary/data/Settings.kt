package dev.claudeswe.audiodiary.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.edit
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** A transcription service that speaks the OpenAI `/audio/transcriptions` API. */
enum class Provider(val label: String, val baseUrl: String, val defaultModel: String) {
    OPENAI("OpenAI", "https://api.openai.com/v1", "gpt-4o-transcribe"),
    GROQ("Groq", "https://api.groq.com/openai/v1", "whisper-large-v3"),
    CUSTOM("Custom", "", ""),
}

data class TranscriptionSettings(
    val provider: Provider = Provider.OPENAI,
    val baseUrl: String = Provider.OPENAI.baseUrl,
    val model: String = Provider.OPENAI.defaultModel,
    /** Key for [provider]. Each provider keeps its own key so switching never sends one provider's key to another. */
    val apiKey: String = "",
    val language: String = "",
    val vocabulary: String = "",
    /** Mirror transcripts to shared storage (Documents/AudioDiary). */
    val exportText: Boolean = true,
    /** FLAG_SECURE: no screenshots, blank preview in Recents. */
    val hideScreen: Boolean = true,
) {
    val isConfigured: Boolean get() = Validation.problem(this) == null
}

/** Input checks applied before any key is sent anywhere. Pure functions, unit-tested. */
object Validation {
    private val keyChars = Regex("^[\\x21-\\x7E]{8,512}$") // printable ASCII, no spaces/newlines
    private val modelChars = Regex("^[A-Za-z0-9._:/-]{1,100}$")
    private val languageChars = Regex("^([a-z]{2,3})?$")

    /** Returns a user-facing reason the settings can't be used, or null if they're fine. */
    fun problem(s: TranscriptionSettings): String? = when {
        s.apiKey.isBlank() -> "No API key set."
        !keyLooksValid(s.apiKey) -> "The API key contains spaces or unusual characters."
        baseUrlProblem(s.baseUrl) != null -> baseUrlProblem(s.baseUrl)
        !modelChars.matches(s.model) -> "Model name is empty or has unusual characters."
        !languageChars.matches(s.language) -> "Language must be a 2–3 letter code like en, or blank."
        else -> null
    }

    fun keyLooksValid(key: String): Boolean = keyChars.matches(key)

    /** Only HTTPS URLs without embedded credentials, query or fragment are allowed, so the key is never sent in clear text. */
    fun baseUrlProblem(url: String): String? {
        val parsed = url.trim().toHttpUrlOrNull() ?: return "Base URL isn't a valid URL."
        return when {
            !parsed.isHttps -> "Base URL must start with https:// (the API key would otherwise be sent unencrypted)."
            parsed.username.isNotEmpty() || parsed.password.isNotEmpty() -> "Base URL must not contain a username or password."
            parsed.query != null || parsed.fragment != null -> "Base URL must not contain ? or #."
            else -> null
        }
    }
}

/**
 * Settings live in app-private SharedPreferences. API keys are encrypted with an AES-256-GCM key held in the
 * Android Keystore (hardware-backed where the phone supports it), so a copy of the prefs file alone doesn't
 * reveal them. Backups and device transfers are disabled for app data (see data_extraction_rules.xml).
 */
class SettingsStore(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    fun load(): TranscriptionSettings {
        val provider = runCatching { Provider.valueOf(prefs.getString("provider", null)!!) }.getOrDefault(Provider.OPENAI)
        return TranscriptionSettings(
            provider = provider,
            baseUrl = if (provider == Provider.CUSTOM) prefs.getString("customBaseUrl", "")!! else provider.baseUrl,
            model = prefs.getString("model_${provider.name}", provider.defaultModel)!!,
            apiKey = keyFor(provider),
            language = prefs.getString("language", "")!!,
            vocabulary = prefs.getString("vocabulary", "")!!,
            exportText = prefs.getBoolean("exportText", true),
            hideScreen = prefs.getBoolean("hideScreen", true),
        )
    }

    /** Saved model for [provider] (used when switching providers in the UI). */
    fun modelFor(provider: Provider): String = prefs.getString("model_${provider.name}", provider.defaultModel)!!

    fun customBaseUrl(): String = prefs.getString("customBaseUrl", "")!!

    /** Saved (decrypted) key for [provider], or "" if none or it can't be decrypted. */
    fun keyFor(provider: Provider): String =
        prefs.getString("key_${provider.name}", null)?.let { KeyCipher.decrypt(it) } ?: ""

    fun save(s: TranscriptionSettings) {
        prefs.edit {
            putString("provider", s.provider.name)
            if (s.provider == Provider.CUSTOM) putString("customBaseUrl", s.baseUrl.trim())
            putString("model_${s.provider.name}", s.model.trim())
            val key = s.apiKey.trim()
            if (key.isEmpty()) remove("key_${s.provider.name}") else putString("key_${s.provider.name}", KeyCipher.encrypt(key))
            putString("language", s.language.trim().lowercase())
            putString("vocabulary", s.vocabulary.trim())
            putBoolean("exportText", s.exportText)
            putBoolean("hideScreen", s.hideScreen)
            remove("apiKey") // never written by this version; clears any plaintext key from older builds
        }
    }
}

/** AES-GCM with a non-exportable Android Keystore key. Output: base64(iv ‖ ciphertext+tag). */
private object KeyCipher {
    private const val ALIAS = "audio-diary-settings"
    private const val TRANSFORM = "AES/GCM/NoPadding"

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return gen.generateKey()
    }

    fun encrypt(plain: String): String {
        val cipher = Cipher.getInstance(TRANSFORM).apply { init(Cipher.ENCRYPT_MODE, key()) }
        val out = cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(out, Base64.NO_WRAP)
    }

    fun decrypt(encoded: String): String? = runCatching {
        val bytes = Base64.decode(encoded, Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORM)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes, 0, 12))
        String(cipher.doFinal(bytes, 12, bytes.size - 12), Charsets.UTF_8)
    }.getOrNull()
}
