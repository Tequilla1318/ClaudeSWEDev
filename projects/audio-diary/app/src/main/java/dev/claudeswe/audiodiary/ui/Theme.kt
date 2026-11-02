package dev.claudeswe.audiodiary.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/** Record-button red, shared by both themes. */
val RecordRed = Color(0xFFE0674F)

private val Light = lightColorScheme(
    primary = Color(0xFF2E4A55),
    onPrimary = Color.White,
    secondary = RecordRed,
    background = Color(0xFFF7F3EC),
    onBackground = Color(0xFF1E2427),
    surface = Color(0xFFF7F3EC),
    onSurface = Color(0xFF1E2427),
    surfaceVariant = Color(0xFFECE6DC),
    onSurfaceVariant = Color(0xFF59615F),
    surfaceContainer = Color(0xFFFFFCF7),
    error = Color(0xFFB3261E),
)

private val Dark = darkColorScheme(
    primary = Color(0xFFA9C7D2),
    onPrimary = Color(0xFF12262D),
    secondary = RecordRed,
    background = Color(0xFF15191B),
    onBackground = Color(0xFFE8E4DC),
    surface = Color(0xFF15191B),
    onSurface = Color(0xFFE8E4DC),
    surfaceVariant = Color(0xFF242A2D),
    onSurfaceVariant = Color(0xFFA6ADAA),
    surfaceContainer = Color(0xFF1D2224),
    error = Color(0xFFF2B8B5),
)

@Composable
fun DiaryTheme(content: @Composable () -> Unit) {
    val base = Typography()
    val typography = base.copy(
        displayMedium = base.displayMedium.copy(fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Light),
        titleLarge = TextStyle(fontFamily = FontFamily.Serif, fontWeight = FontWeight.Medium, fontSize = 24.sp),
        bodyLarge = base.bodyLarge.copy(fontFamily = FontFamily.Serif, fontSize = 17.sp, lineHeight = 27.sp),
    )
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) Dark else Light,
        typography = typography,
        content = content,
    )
}
