package dev.claudeswe.audiodiary.ui

import android.content.Intent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.Timeline
import androidx.media3.exoplayer.ExoPlayer
import dev.claudeswe.audiodiary.DiaryApp
import dev.claudeswe.audiodiary.data.Entry
import dev.claudeswe.audiodiary.data.EntryStatus
import dev.claudeswe.audiodiary.data.EntryStore
import dev.claudeswe.audiodiary.data.Format
import dev.claudeswe.audiodiary.data.TextExporter
import dev.claudeswe.audiodiary.transcribe.TranscribeWorker
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EntryScreen(store: EntryStore, id: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val version by store.version.collectAsState()
    val loaded by produceState<Pair<Entry, String>?>(null, version) {
        value = withContext(Dispatchers.IO) { store.load(id)?.let { it to store.readBody(id) } }
    }
    var editing by rememberSaveable { mutableStateOf(false) }
    var draft by rememberSaveable { mutableStateOf("") }
    var confirmDelete by remember { mutableStateOf(false) }
    var confirmRedo by remember { mutableStateOf(false) }

    val pair = loaded
    if (pair == null) {
        // Not loaded yet, or deleted elsewhere (e.g. from a second window): go back rather than show a blank page.
        LaunchedEffect(version) { if (!withContext(Dispatchers.IO) { store.exists(id) }) onBack() }
        Box(Modifier.fillMaxSize())
        return
    }
    val (entry, body) = pair

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(Format.listDate(entry.createdAt), style = MaterialTheme.typography.titleMedium) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") }
                },
                actions = {
                    if (entry.status == EntryStatus.DONE && !editing) {
                        IconButton(onClick = {
                            draft = body.trim()
                            editing = true
                        }) { Icon(Icons.Filled.Edit, "Edit transcript") }
                        IconButton(onClick = { shareText(context, store.textFile(id)) }) {
                            Icon(Icons.Filled.Share, "Share text file")
                        }
                    }
                    IconButton(onClick = { confirmDelete = true }) { Icon(Icons.Filled.Delete, "Delete") }
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
                .padding(horizontal = 20.dp, vertical = 8.dp),
        ) {
            AudioPlayer(store.segments(id), entry.durationMs)
            Spacer(Modifier.height(20.dp))

            if (entry.status != EntryStatus.DONE || entry.error != null) {
                StatusLine(entry)
                if (entry.status == EntryStatus.TRANSCRIBING || entry.status == EntryStatus.QUEUED) {
                    LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 10.dp))
                }
                if (entry.status == EntryStatus.FAILED || entry.status == EntryStatus.QUEUED) {
                    OutlinedButton(
                        onClick = { TranscribeWorker.enqueue(context, id) },
                        modifier = Modifier.padding(vertical = 8.dp),
                    ) { Text("Retry now") }
                }
                Spacer(Modifier.height(12.dp))
            }

            if (editing) {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 240.dp),
                    textStyle = MaterialTheme.typography.bodyLarge,
                )
                Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = { editing = false }) { Text("Cancel") }
                    TextButton(onClick = {
                        editing = false
                        scope.launch(Dispatchers.IO) {
                            val text = store.writeBody(entry, draft) ?: return@launch
                            val export = (context.applicationContext as DiaryApp).settings.load().exportText
                            val uri = if (export) TextExporter.export(context, id, text, entry.exportUri) else null
                            store.update(id) {
                                it.copy(edited = true, exportUri = uri ?: it.exportUri, preview = Format.preview(draft))
                            }
                        }
                    }) { Text("Save") }
                }
            } else if (entry.status == EntryStatus.DONE) {
                SelectionContainer {
                    Text(
                        body.trim().ifBlank { "(no speech detected)" },
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
                Spacer(Modifier.height(28.dp))
                Text(
                    buildString {
                        append(if (entry.exportUri != null) "Saved as ${TextExporter.displayFolder}/$id.txt" else "Not exported")
                        if (entry.edited) append(" · edited")
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TextButton(onClick = { confirmRedo = true }, modifier = Modifier.padding(top = 4.dp)) {
                    Text("Transcribe again")
                }
            }
            Spacer(Modifier.height(40.dp))
        }
    }

    if (confirmDelete) {
        var alsoText by remember { mutableStateOf(false) }
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete this entry?") },
            text = {
                Column {
                    Text("The recording and transcript are removed from the app.")
                    if (entry.exportUri != null) {
                        Row(
                            Modifier.padding(top = 12.dp).clickable { alsoText = !alsoText },
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(alsoText, onCheckedChange = { alsoText = it })
                            Text("Also delete $id.txt from ${TextExporter.displayFolder}")
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmDelete = false
                    if (alsoText) entry.exportUri?.let { TextExporter.delete(context, it) }
                    TranscribeWorker.cancel(context, id)
                    store.delete(id)
                    onBack()
                }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
    }

    if (confirmRedo) {
        AlertDialog(
            onDismissRequest = { confirmRedo = false },
            title = { Text("Transcribe again?") },
            text = {
                Text(
                    "Sends the audio to your transcription provider again with the current Settings" +
                        if (entry.edited) ". Your edits to this transcript will be replaced." else ".",
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    confirmRedo = false
                    TranscribeWorker.enqueue(context, id, restart = true)
                }) { Text("Transcribe") }
            },
            dismissButton = { TextButton(onClick = { confirmRedo = false }) { Text("Cancel") } },
        )
    }
}

@Composable
private fun AudioPlayer(segments: List<File>, knownDurationMs: Long) {
    val context = LocalContext.current
    val player = remember(segments) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItems(segments.filter { it.length() > 0 }.map { MediaItem.fromUri(android.net.Uri.fromFile(it)) })
            prepare()
        }
    }
    var playing by remember { mutableStateOf(false) }
    var position by remember { mutableLongStateOf(0L) }
    var total by remember { mutableLongStateOf(knownDurationMs) }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) {
                playing = isPlaying
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) {
                    player.pause()
                    player.seekTo(0, 0)
                }
            }
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }
    LaunchedEffect(player) {
        val window = Timeline.Window()
        while (true) {
            val tl = player.currentTimeline
            if (!tl.isEmpty) {
                var before = 0L
                var sum = 0L
                for (i in 0 until tl.windowCount) {
                    val d = tl.getWindow(i, window).durationMs.coerceAtLeast(0)
                    if (i < player.currentMediaItemIndex) before += d
                    sum += d
                }
                position = before + player.currentPosition
                if (sum > 0) total = sum
            }
            delay(200)
        }
    }

    Surface(shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surfaceContainer) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .clickable(onClickLabel = if (playing) "Pause" else "Play") {
                        if (playing) player.pause() else player.play()
                    },
                contentAlignment = Alignment.Center,
            ) {
                GlyphIcon(if (playing) Glyph.PAUSE else Glyph.PLAY, MaterialTheme.colorScheme.primary, 26.dp)
            }
            Column(Modifier.weight(1f).padding(start = 10.dp)) {
                LinearProgressIndicator(
                    progress = { if (total > 0) (position.toFloat() / total).coerceIn(0f, 1f) else 0f },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "${Format.clock(position)} / ${Format.clock(total)}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

private fun shareText(context: android.content.Context, file: File) {
    if (!file.exists()) return
    val uri = FileProvider.getUriForFile(context, context.packageName + ".files", file)
    val send = Intent(Intent.ACTION_SEND)
        .setType("text/plain")
        .putExtra(Intent.EXTRA_STREAM, uri)
        .putExtra(Intent.EXTRA_TEXT, file.readText())
        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    context.startActivity(Intent.createChooser(send, "Share transcript"))
}
