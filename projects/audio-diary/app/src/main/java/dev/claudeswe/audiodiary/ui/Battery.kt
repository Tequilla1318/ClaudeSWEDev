package dev.claudeswe.audiodiary.ui

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import androidx.core.net.toUri
import android.os.PowerManager
import android.provider.Settings
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.currentStateAsState

/**
 * OxygenOS (and other OEM skins) stop background work aggressively unless the app is exempt from battery
 * optimisation. The microphone foreground service is normally protected, but transcription work and very long
 * recordings are safer with the exemption.
 */
object Battery {
    fun isUnrestricted(context: Context): Boolean =
        context.getSystemService(PowerManager::class.java)?.isIgnoringBatteryOptimizations(context.packageName) ?: true

    /** Shows the system "Let app always run in background?" dialog, falling back to the settings list. */
    @SuppressLint("BatteryLife") // sideloaded personal app; the exemption is the point
    fun requestUnrestricted(context: Context) {
        val direct = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, "package:${context.packageName}".toUri())
        try {
            context.startActivity(direct)
        } catch (_: ActivityNotFoundException) {
            runCatching { context.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        } catch (_: SecurityException) {
            runCatching { context.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS)) }
        }
    }
}

/** Re-checked every time the screen resumes, so the banner disappears after the user grants it. */
@Composable
fun rememberBatteryUnrestricted(): Boolean {
    val context = LocalContext.current
    val state by LocalLifecycleOwner.current.lifecycle.currentStateAsState()
    return remember(state) { Battery.isUnrestricted(context) }
}
