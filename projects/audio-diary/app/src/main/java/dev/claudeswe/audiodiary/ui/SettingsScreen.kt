package dev.claudeswe.audiodiary.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import dev.claudeswe.audiodiary.data.Provider
import dev.claudeswe.audiodiary.data.SettingsStore
import dev.claudeswe.audiodiary.data.TextExporter
import dev.claudeswe.audiodiary.data.Validation
import androidx.compose.material3.Switch
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import dev.claudeswe.audiodiary.transcribe.TranscriptionClient
import dev.claudeswe.audiodiary.transcribe.TranscriptionException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(store: SettingsStore, onBack: () -> Unit) {
    var s by remember { mutableStateOf(store.load()) }
    var check by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun saveAndBack() {
        store.save(s)
        onBack()
    }
    androidx.activity.compose.BackHandler(onBack = ::saveAndBack)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = ::saveAndBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Save and go back") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .imePadding()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Transcription service", style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Provider.entries.forEach { p ->
                    FilterChip(
                        selected = s.provider == p,
                        onClick = {
                            // Each provider has its own saved key; a key typed for one is never sent to another.
                            if (p != s.provider) {
                                store.save(s) // keep what was typed for the provider we're leaving
                                s = s.copy(
                                    provider = p,
                                    baseUrl = if (p == Provider.CUSTOM) store.customBaseUrl() else p.baseUrl,
                                    model = store.modelFor(p),
                                    apiKey = store.keyFor(p),
                                )
                            }
                            check = null
                        },
                        label = { Text(p.label) },
                    )
                }
            }
            Text(
                when (s.provider) {
                    Provider.OPENAI -> "Best accuracy with gpt-4o-transcribe; whisper-1 is the older, cheaper model. " +
                        "Key from platform.openai.com."
                    Provider.GROQ -> "Whisper large-v3, very fast and cheap; has a free tier. Key from console.groq.com."
                    Provider.CUSTOM -> "Any HTTPS server with an OpenAI-compatible /audio/transcriptions endpoint."
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedTextField(
                value = s.apiKey,
                onValueChange = { s = s.copy(apiKey = it); check = null },
                label = { Text("API key") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = s.model,
                onValueChange = { s = s.copy(model = it); check = null },
                label = { Text("Model") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            if (s.provider == Provider.CUSTOM) {
                OutlinedTextField(
                    value = s.baseUrl,
                    onValueChange = { s = s.copy(baseUrl = it); check = null },
                    label = { Text("Base URL (https only)") },
                    placeholder = { Text("https://example.com/v1") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            val problem = Validation.problem(s)
            if (problem != null && s.apiKey.isNotEmpty()) {
                Text(problem, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            OutlinedButton(
                enabled = s.isConfigured,
                onClick = {
                    check = "Checking…"
                    scope.launch {
                        check = withContext(Dispatchers.IO) {
                            try {
                                TranscriptionClient(s.baseUrl.trim(), s.apiKey.trim(), s.model.trim()).checkKey()
                            } catch (e: TranscriptionException) {
                                e.message
                            } catch (e: Exception) {
                                "Check failed (${e.javaClass.simpleName})."
                            }
                        }
                    }
                },
            ) { Text("Test key") }
            check?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }

            Spacer(Modifier.height(8.dp))
            Text("Accuracy", style = MaterialTheme.typography.titleSmall)
            OutlinedTextField(
                value = s.language,
                onValueChange = { s = s.copy(language = it.take(5)) },
                label = { Text("Language code (blank = auto-detect)") },
                placeholder = { Text("en") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = s.vocabulary,
                onValueChange = { s = s.copy(vocabulary = it) },
                label = { Text("Words to spell right") },
                placeholder = { Text("Names, places, jargon — e.g. Nkechi, Kubernetes, Mississauga") },
                modifier = Modifier.fillMaxWidth().heightIn(min = 100.dp),
            )
            Text(
                "Sent with every recording as a spelling hint. Setting the language also helps.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(8.dp))
            Text("Files & privacy", style = MaterialTheme.typography.titleSmall)
            ToggleRow(
                title = "Save transcripts as .txt files",
                detail = "Written to ${TextExporter.displayFolder}, visible in the Files app and to apps you give " +
                    "all-files access. Audio always stays inside the app.",
                checked = s.exportText,
                onChange = { s = s.copy(exportText = it) },
            )
            ToggleRow(
                title = "Hide from screenshots & Recents",
                detail = "Blocks screenshots and screen recording of the app, and blanks its preview in the app switcher.",
                checked = s.hideScreen,
                onChange = { s = s.copy(hideScreen = it) },
            )
            Text(
                "Audio is sent only to the transcription service above, over HTTPS, using your key. " +
                    "Nothing else leaves the phone.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(8.dp))
            Text("Background", style = MaterialTheme.typography.titleSmall)
            val unrestricted = rememberBatteryUnrestricted()
            val context = LocalContext.current
            if (unrestricted) {
                Text("Background activity allowed ✓", style = MaterialTheme.typography.bodyMedium)
            } else {
                OutlinedButton(onClick = { Battery.requestUnrestricted(context) }) { Text("Allow background activity") }
                Text(
                    "OxygenOS may otherwise pause transcription, or stop very long recordings, to save battery.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(8.dp))
            Button(onClick = ::saveAndBack, modifier = Modifier.fillMaxWidth()) { Text("Save") }
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun ToggleRow(title: String, detail: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f).padding(end = 12.dp)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}
