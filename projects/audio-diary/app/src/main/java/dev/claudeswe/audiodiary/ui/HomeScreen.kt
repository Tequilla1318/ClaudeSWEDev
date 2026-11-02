package dev.claudeswe.audiodiary.ui

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.claudeswe.audiodiary.data.Entry
import dev.claudeswe.audiodiary.data.EntryStatus
import dev.claudeswe.audiodiary.data.EntryStore
import dev.claudeswe.audiodiary.data.Format
import dev.claudeswe.audiodiary.data.SettingsStore
import dev.claudeswe.audiodiary.data.Validation
import dev.claudeswe.audiodiary.recording.RecorderBus
import dev.claudeswe.audiodiary.recording.RecorderService
import dev.claudeswe.audiodiary.recording.RecorderState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    store: EntryStore,
    settings: SettingsStore,
    onRecord: () -> Unit,
    onOpen: (String) -> Unit,
    onSettings: () -> Unit,
) {
    val version by store.version.collectAsState()
    val entries by produceState(emptyList<Entry>(), version) {
        value = withContext(Dispatchers.IO) { store.list() }
    }
    val rec by RecorderBus.state.collectAsState()
    val current = settings.load()
    val problem = Validation.problem(current)
    val context = LocalContext.current
    val batteryRestricted = !rememberBatteryUnrestricted()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Audio Diary", style = MaterialTheme.typography.titleLarge) },
                actions = {
                    IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, "Settings") }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        LazyColumn(
            Modifier.fillMaxSize().padding(padding),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item { RecordPanel(rec, onRecord) }
            if (problem != null) {
                item {
                    Banner("$problem Set it up in Settings. Recordings are kept and will transcribe once it's fixed.", onSettings)
                }
            }
            if (batteryRestricted) {
                item {
                    Banner(
                        "Tap to let Audio Diary run in the background, so long recordings and transcription aren't " +
                            "stopped by battery saving.",
                        onClick = { Battery.requestUnrestricted(context) },
                    )
                }
            }
            if (entries.isEmpty() && !rec.active) {
                item {
                    Text(
                        "No entries yet. Tap the red button and talk.",
                        Modifier.fillMaxWidth().padding(top = 32.dp),
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                    )
                }
            }
            items(entries.filter { it.id != rec.entryId }, key = { it.id }) { entry ->
                EntryRow(entry, onClick = { onOpen(entry.id) })
            }
        }
    }
}

@Composable
private fun RecordPanel(rec: RecorderState, onRecord: () -> Unit) {
    val context = LocalContext.current
    Surface(
        shape = RoundedCornerShape(24.dp),
        color = MaterialTheme.colorScheme.surfaceContainer,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            Modifier.padding(vertical = 28.dp, horizontal = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                Format.clock(rec.elapsedMs),
                style = MaterialTheme.typography.displayMedium,
                color = if (rec.active) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(14.dp))
            LevelMeter(if (rec.active && !rec.paused) rec.level else 0f)
            Spacer(Modifier.height(22.dp))
            if (!rec.active) {
                RecordButton(onClick = onRecord)
                Spacer(Modifier.height(10.dp))
                Text("Tap to record", color = MaterialTheme.colorScheme.onSurfaceVariant)
                rec.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp)) }
            } else {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                    TextButton(onClick = { RecorderService.send(context, RecorderService.ACTION_DISCARD) }) {
                        Text("Discard", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    CircleControl(
                        onClick = {
                            RecorderService.send(
                                context,
                                if (rec.paused) RecorderService.ACTION_RESUME else RecorderService.ACTION_PAUSE,
                            )
                        },
                        filled = false,
                        description = if (rec.paused) "Resume" else "Pause",
                    ) {
                        GlyphIcon(if (rec.paused) Glyph.PLAY else Glyph.PAUSE, MaterialTheme.colorScheme.onSurface)
                    }
                    CircleControl(
                        onClick = { RecorderService.send(context, RecorderService.ACTION_STOP) },
                        filled = true,
                        description = "Stop and save",
                    ) { GlyphIcon(Glyph.STOP, Color.White) }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    if (rec.paused) "Paused" else "Recording — keeps going with the screen off",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun RecordButton(onClick: () -> Unit) {
    Box(
        Modifier
            .size(88.dp)
            .clip(CircleShape)
            .border(4.dp, RecordRed.copy(alpha = 0.35f), CircleShape)
            .clickable(onClickLabel = "Start recording", onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Box(Modifier.size(64.dp).clip(CircleShape).background(RecordRed))
    }
}

@Composable
private fun CircleControl(
    onClick: () -> Unit,
    filled: Boolean,
    description: String,
    content: @Composable () -> Unit,
) {
    val outline = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f)
    Box(
        Modifier
            .size(68.dp)
            .clip(CircleShape)
            .then(if (filled) Modifier.background(RecordRed) else Modifier.border(2.dp, outline, CircleShape))
            .clickable(onClickLabel = description, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { content() }
}

@Composable
private fun LevelMeter(level: Float) {
    val animated by animateFloatAsState(level, label = "level")
    Box(
        Modifier
            .width(200.dp)
            .height(6.dp)
            .clip(RoundedCornerShape(3.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Box(
            Modifier
                .fillMaxWidth(animated)
                .height(6.dp)
                .background(RecordRed),
        )
    }
}

@Composable
private fun Banner(text: String, onClick: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.14f),
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
    ) {
        Text(text, Modifier.padding(14.dp), style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun EntryRow(entry: Entry, onClick: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainer,
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    Format.listDate(entry.createdAt),
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    Format.duration(entry.durationMs),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(6.dp))
            when (entry.status) {
                EntryStatus.DONE -> Text(
                    entry.preview,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
                else -> StatusLine(entry)
            }
        }
    }
}

@Composable
fun StatusLine(entry: Entry) {
    val (text, color) = when (entry.status) {
        EntryStatus.RECORDING -> "Recording…" to RecordRed
        EntryStatus.QUEUED -> (entry.error ?: "Waiting to transcribe (needs a connection)") to
            MaterialTheme.colorScheme.onSurfaceVariant
        EntryStatus.TRANSCRIBING -> "Transcribing…" to MaterialTheme.colorScheme.primary
        EntryStatus.FAILED -> ("Transcription failed: " + (entry.error ?: "unknown error")) to
            MaterialTheme.colorScheme.error
        EntryStatus.DONE -> (entry.error ?: "") to MaterialTheme.colorScheme.error
    }
    if (text.isNotBlank()) Text(text, color = color, style = MaterialTheme.typography.bodyMedium)
}
