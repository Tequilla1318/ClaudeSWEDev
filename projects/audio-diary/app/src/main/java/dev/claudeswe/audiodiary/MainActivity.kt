package dev.claudeswe.audiodiary

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import dev.claudeswe.audiodiary.recording.RecorderService
import dev.claudeswe.audiodiary.ui.DiaryTheme
import dev.claudeswe.audiodiary.ui.EntryScreen
import dev.claudeswe.audiodiary.ui.HomeScreen
import dev.claudeswe.audiodiary.ui.SettingsScreen

class MainActivity : ComponentActivity() {

    private val permissions = ActivityResultContracts.RequestMultiplePermissions()
    private val askPermissions = registerForActivityResult(permissions) {
        // Check the real state: the result map only lists what was asked this time.
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            RecorderService.send(this, RecorderService.ACTION_START)
        } else {
            Toast.makeText(this, "Microphone permission is needed to record.", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val app = application as DiaryApp
        setContent {
            DiaryTheme {
                // "" = home, "settings", or an entry id.
                var screen by rememberSaveable { mutableStateOf("") }
                BackHandler(enabled = screen.isNotEmpty()) { screen = "" }
                LaunchedEffect(screen) { applyScreenPrivacy() } // re-applied after leaving Settings
                when (screen) {
                    "" -> HomeScreen(
                        store = app.store,
                        settings = app.settings,
                        onRecord = ::startRecording,
                        onOpen = { screen = it },
                        onSettings = { screen = "settings" },
                    )
                    "settings" -> SettingsScreen(app.settings, onBack = { screen = "" })
                    else -> EntryScreen(app.store, screen, onBack = { screen = "" })
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        applyScreenPrivacy()
    }

    /** FLAG_SECURE blocks screenshots/screen recording and blanks the app in Recents. On by default. */
    private fun applyScreenPrivacy() {
        if ((application as DiaryApp).settings.load().hideScreen) {
            window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    private fun startRecording() {
        val needed = buildList {
            add(Manifest.permission.RECORD_AUDIO)
            if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
        }.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (needed.isEmpty()) {
            RecorderService.send(this, RecorderService.ACTION_START)
        } else {
            askPermissions.launch(needed.toTypedArray())
        }
    }
}
