package dev.claudeswe.audiodiary.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Media glyphs drawn directly, so the app doesn't need the large extended-icons library. */
enum class Glyph { PLAY, PAUSE, STOP }

@Composable
fun GlyphIcon(glyph: Glyph, color: Color, size: Dp = 22.dp) {
    Canvas(Modifier.size(size)) {
        val w = this.size.width
        val h = this.size.height
        when (glyph) {
            Glyph.PLAY -> drawPath(
                Path().apply {
                    moveTo(w * 0.22f, h * 0.12f)
                    lineTo(w * 0.88f, h * 0.5f)
                    lineTo(w * 0.22f, h * 0.88f)
                    close()
                },
                color,
            )
            Glyph.PAUSE -> {
                val bar = Size(w * 0.24f, h * 0.76f)
                val r = CornerRadius(w * 0.05f)
                drawRoundRect(color, Offset(w * 0.18f, h * 0.12f), bar, r)
                drawRoundRect(color, Offset(w * 0.58f, h * 0.12f), bar, r)
            }
            Glyph.STOP -> drawRoundRect(
                color, Offset(w * 0.16f, h * 0.16f), Size(w * 0.68f, h * 0.68f), CornerRadius(w * 0.1f),
            )
        }
    }
}
