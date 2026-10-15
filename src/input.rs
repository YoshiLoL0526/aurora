//! Campos de texto: estado por key (editor, composición del IME, parpadeo y
//! desplazamiento) y geometría del cursor y la selección sobre un `Paragraph`.
//!
//! Skia mide las posiciones en UTF-16 y el editor en bytes UTF-8: todas las
//! conversiones pasan por aquí.

use std::ops::Range;

use skia_safe::textlayout::{Paragraph, RectHeightStyle, RectWidthStyle};
use skia_safe::{Point, Rect};

use crate::edit::{Editor, prev_grapheme, utf8_to_utf16, utf16_to_utf8};

pub const CARET_WIDTH: f32 = 1.5;
/// Medio periodo del parpadeo del cursor (segundos).
const BLINK: f32 = 0.53;

pub struct InputState {
    pub editor: Editor,
    /// Texto en composición del IME (aún no confirmado), que se pinta en el cursor.
    pub preedit: Option<String>,
    /// Segundos desde la última actividad: el cursor se ve fijo justo después de escribir.
    pub blink: f32,
    pub multiline: bool,
    /// Desplazamiento horizontal de un campo de una línea con más texto del que cabe.
    pub scroll_x: f32,
    /// Geometría del último frame, para resolver clics y teclas verticales.
    pub frame: Option<InputFrame>,
}

pub struct InputFrame {
    pub paragraph: Paragraph,
    /// Texto pintado (valor con composición, o el placeholder).
    pub display: String,
    pub placeholder: bool,
    /// Posición absoluta del origen del párrafo.
    pub origin: Point,
    /// Cursor en coordenadas absolutas.
    pub caret: Rect,
}

impl InputState {
    pub fn new(text: &str, multiline: bool) -> Self {
        Self {
            editor: Editor::new(text),
            preedit: None,
            blink: 0.0,
            multiline,
            scroll_x: 0.0,
            frame: None,
        }
    }

    pub fn caret_visible(&self) -> bool {
        self.blink % (2.0 * BLINK) < BLINK
    }

    /// Segundos hasta el próximo cambio del parpadeo.
    pub fn until_blink(&self) -> f32 {
        BLINK - self.blink % BLINK
    }

    /// Texto a pintar: el valor con la composición del IME insertada en el cursor.
    pub fn display(&self) -> String {
        let mut text = self.editor.text().to_owned();
        if let Some(pre) = &self.preedit {
            text.insert_str(self.editor.cursor(), pre);
        }
        text
    }

    /// Posición del valor (bytes) bajo un punto absoluto del último frame.
    pub fn position_at(&self, p: Point) -> Option<usize> {
        let frame = self.frame.as_ref()?;
        if frame.placeholder {
            return Some(0);
        }
        if self.preedit.is_some() {
            return Some(self.editor.cursor());
        }
        let pos = frame
            .paragraph
            .get_glyph_position_at_coordinate(p - frame.origin)
            .position
            .max(0) as usize;
        Some(self.editor.snap(utf16_to_utf8(&frame.display, pos)))
    }

    pub fn caret(&self) -> Option<Rect> {
        self.frame.as_ref().map(|f| f.caret)
    }
}

/// Cursor (relativo al párrafo) delante del byte `pos` de `text`.
pub fn caret_rect(p: &Paragraph, text: &str, pos: usize) -> Rect {
    let pos = pos.min(text.len());
    let line = if pos >= text.len() {
        p.line_number().saturating_sub(1)
    } else {
        p.get_line_number_at(pos).unwrap_or(0)
    };
    let (top, bottom, left) = p
        .get_line_metrics_at(line)
        .map(|m| {
            (
                (m.baseline - m.ascent) as f32,
                (m.baseline + m.descent) as f32,
                m.left as f32,
            )
        })
        .unwrap_or((0.0, p.height(), 0.0));
    let line_start = pos == 0 || text[..pos].ends_with('\n');
    let prev = prev_grapheme(text, pos);
    // Al principio de una línea (también tras un salto automático) el cursor
    // va al margen, no al final de la línea anterior.
    let x = if line_start || p.get_line_number_at(prev) != Some(line) {
        left
    } else {
        p.get_rects_for_range(
            utf8_to_utf16(text, prev)..utf8_to_utf16(text, pos),
            RectHeightStyle::Max,
            RectWidthStyle::Tight,
        )
        .last()
        .map(|b| b.rect.right)
        .unwrap_or(left)
    };
    Rect::new(x, top, x + CARET_WIDTH, bottom)
}

/// Rectángulos (relativos al párrafo) que cubren el rango de bytes `range`.
pub fn range_rects(p: &Paragraph, text: &str, range: Range<usize>) -> Vec<Rect> {
    if range.is_empty() {
        return Vec::new();
    }
    p.get_rects_for_range(
        utf8_to_utf16(text, range.start)..utf8_to_utf16(text, range.end),
        RectHeightStyle::Max,
        RectWidthStyle::Tight,
    )
    .into_iter()
    .map(|b| b.rect)
    .collect()
}
