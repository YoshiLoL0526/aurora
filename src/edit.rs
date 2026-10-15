//! Modelo de edición de texto, sin nada de pintura: texto, cursor, selección
//! y deshacer/rehacer. Las posiciones son índices de bytes UTF-8 siempre
//! alineados a grafemas, así que un emoji compuesto o una letra con tilde
//! combinada se borran y recorren como un solo carácter.

use std::ops::Range;

use unicode_segmentation::UnicodeSegmentation;

/// Máximo de pasos de deshacer que se guardan.
const UNDO_LIMIT: usize = 200;

#[derive(Clone, Debug, PartialEq)]
struct Snapshot {
    text: String,
    cursor: usize,
    anchor: usize,
}

#[derive(Clone, Debug, Default)]
pub struct Editor {
    text: String,
    /// Extremo móvil de la selección (donde se dibuja el cursor).
    cursor: usize,
    /// Extremo fijo de la selección; igual a `cursor` si no hay selección.
    anchor: usize,
    undo: Vec<Snapshot>,
    redo: Vec<Snapshot>,
    /// La última operación fue escribir caracteres: se agrupan en un solo paso de deshacer.
    typing: bool,
}

impl Editor {
    pub fn new(text: &str) -> Self {
        Self {
            text: text.to_owned(),
            cursor: text.len(),
            anchor: text.len(),
            ..Self::default()
        }
    }

    pub fn text(&self) -> &str {
        &self.text
    }

    pub fn cursor(&self) -> usize {
        self.cursor
    }

    pub fn selection(&self) -> Range<usize> {
        self.cursor.min(self.anchor)..self.cursor.max(self.anchor)
    }

    pub fn has_selection(&self) -> bool {
        self.cursor != self.anchor
    }

    pub fn selected_text(&self) -> &str {
        &self.text[self.selection()]
    }

    /// El texto cambió desde fuera (Python asignó otro valor): se adopta y el
    /// cursor se conserva si sigue siendo válido.
    pub fn set_external(&mut self, text: &str) {
        if text == self.text {
            return;
        }
        self.text = text.to_owned();
        self.cursor = self.snap(self.cursor.min(text.len()));
        self.anchor = self.snap(self.anchor.min(text.len()));
        self.typing = false;
    }

    /// Mayor frontera de grafema que no supera `pos`.
    pub fn snap(&self, pos: usize) -> usize {
        let pos = pos.min(self.text.len());
        if pos == self.text.len() {
            return pos;
        }
        self.text
            .grapheme_indices(true)
            .map(|(i, _)| i)
            .take_while(|&i| i <= pos)
            .last()
            .unwrap_or(0)
    }

    fn snapshot(&mut self, typing: bool) {
        if !(typing && self.typing) {
            self.undo.push(Snapshot {
                text: self.text.clone(),
                cursor: self.cursor,
                anchor: self.anchor,
            });
            if self.undo.len() > UNDO_LIMIT {
                self.undo.remove(0);
            }
        }
        self.redo.clear();
        self.typing = typing;
    }

    fn replace(&mut self, range: Range<usize>, with: &str) {
        self.text.replace_range(range.clone(), with);
        self.cursor = range.start + with.len();
        self.anchor = self.cursor;
    }

    /// Escribe `s` en el cursor, reemplazando la selección. Las letras seguidas
    /// se deshacen de una vez; un espacio o salto de línea cierra el grupo.
    pub fn insert(&mut self, s: &str) -> bool {
        if s.is_empty() && !self.has_selection() {
            return false;
        }
        let typing = !self.has_selection() && !s.chars().any(char::is_whitespace);
        self.snapshot(typing);
        self.replace(self.selection(), s);
        true
    }

    /// Borra la selección, o el grafema (o la palabra) anterior al cursor.
    pub fn backspace(&mut self, word: bool) -> bool {
        if self.has_selection() {
            return self.delete_selection();
        }
        if self.cursor == 0 {
            return false;
        }
        let start = if word {
            prev_word(&self.text, self.cursor)
        } else {
            prev_grapheme(&self.text, self.cursor)
        };
        self.snapshot(false);
        self.replace(start..self.cursor, "");
        true
    }

    /// Borra la selección, o el grafema (o la palabra) siguiente al cursor.
    pub fn delete(&mut self, word: bool) -> bool {
        if self.has_selection() {
            return self.delete_selection();
        }
        if self.cursor == self.text.len() {
            return false;
        }
        let end = if word {
            next_word(&self.text, self.cursor)
        } else {
            next_grapheme(&self.text, self.cursor)
        };
        self.snapshot(false);
        self.replace(self.cursor..end, "");
        true
    }

    pub fn delete_selection(&mut self) -> bool {
        if !self.has_selection() {
            return false;
        }
        self.snapshot(false);
        self.replace(self.selection(), "");
        true
    }

    /// Mueve el cursor; con `extend` amplía la selección en vez de quitarla.
    pub fn move_to(&mut self, pos: usize, extend: bool) {
        self.cursor = self.snap(pos);
        if !extend {
            self.anchor = self.cursor;
        }
        self.typing = false;
    }

    pub fn left(&mut self, word: bool, extend: bool) {
        if !extend && self.has_selection() {
            return self.move_to(self.selection().start, false);
        }
        let pos = if word {
            prev_word(&self.text, self.cursor)
        } else {
            prev_grapheme(&self.text, self.cursor)
        };
        self.move_to(pos, extend);
    }

    pub fn right(&mut self, word: bool, extend: bool) {
        if !extend && self.has_selection() {
            return self.move_to(self.selection().end, false);
        }
        let pos = if word {
            next_word(&self.text, self.cursor)
        } else {
            next_grapheme(&self.text, self.cursor)
        };
        self.move_to(pos, extend);
    }

    pub fn select_all(&mut self) {
        self.anchor = 0;
        self.cursor = self.text.len();
        self.typing = false;
    }

    /// Selecciona la palabra (o el bloque de espacios/símbolos) que contiene `pos`.
    pub fn select_word_at(&mut self, pos: usize) {
        let pos = pos.min(self.text.len());
        let range = self
            .text
            .split_word_bound_indices()
            .map(|(i, w)| i..i + w.len())
            .find(|r| r.contains(&pos) || (pos == self.text.len() && r.end == pos))
            .unwrap_or(pos..pos);
        self.anchor = range.start;
        self.cursor = range.end;
        self.typing = false;
    }

    pub fn undo(&mut self) -> bool {
        let Some(prev) = self.undo.pop() else {
            return false;
        };
        self.redo.push(self.current());
        self.restore(prev);
        true
    }

    pub fn redo(&mut self) -> bool {
        let Some(next) = self.redo.pop() else {
            return false;
        };
        self.undo.push(self.current());
        self.restore(next);
        true
    }

    fn current(&self) -> Snapshot {
        Snapshot {
            text: self.text.clone(),
            cursor: self.cursor,
            anchor: self.anchor,
        }
    }

    fn restore(&mut self, s: Snapshot) {
        self.text = s.text;
        self.cursor = s.cursor;
        self.anchor = s.anchor;
        self.typing = false;
    }
}

pub fn prev_grapheme(text: &str, pos: usize) -> usize {
    text[..pos]
        .grapheme_indices(true)
        .next_back()
        .map(|(i, _)| i)
        .unwrap_or(0)
}

pub fn next_grapheme(text: &str, pos: usize) -> usize {
    text[pos..]
        .graphemes(true)
        .next()
        .map(|g| pos + g.len())
        .unwrap_or(text.len())
}

fn is_word(w: &str) -> bool {
    w.chars().any(char::is_alphanumeric)
}

/// Inicio de la palabra anterior (saltando espacios y signos), como Ctrl+←.
pub fn prev_word(text: &str, pos: usize) -> usize {
    text.split_word_bound_indices()
        .take_while(|(i, _)| *i < pos)
        .filter(|(_, w)| is_word(w))
        .map(|(i, _)| i)
        .last()
        .unwrap_or(0)
}

/// Fin de la palabra siguiente (saltando espacios y signos), como Ctrl+→.
pub fn next_word(text: &str, pos: usize) -> usize {
    text.split_word_bound_indices()
        .map(|(i, w)| (i + w.len(), w))
        .find(|(end, w)| *end > pos && is_word(w))
        .map(|(end, _)| end)
        .unwrap_or(text.len())
}

/// Índice UTF-16 equivalente a un índice de bytes UTF-8 (Skia mide en UTF-16).
pub fn utf8_to_utf16(text: &str, byte: usize) -> usize {
    text[..byte.min(text.len())].encode_utf16().count()
}

/// Índice de bytes UTF-8 equivalente a un índice UTF-16 (redondeando hacia abajo).
pub fn utf16_to_utf8(text: &str, unit: usize) -> usize {
    let mut units = 0;
    for (i, c) in text.char_indices() {
        if units >= unit {
            return i;
        }
        units += c.len_utf16();
        if units > unit {
            return i;
        }
    }
    text.len()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn typing_and_backspace_respect_graphemes() {
        let mut e = Editor::new("");
        e.insert("e\u{301}"); // é con tilde combinada
        e.insert("👍🏽");
        assert_eq!(e.text(), "e\u{301}👍🏽");
        e.backspace(false);
        assert_eq!(e.text(), "e\u{301}");
        e.backspace(false);
        assert_eq!(e.text(), "");
    }

    #[test]
    fn selection_is_replaced_by_insert() {
        let mut e = Editor::new("hola mundo");
        e.move_to(0, false);
        e.right(true, true);
        assert_eq!(e.selected_text(), "hola");
        e.insert("adiós");
        assert_eq!(e.text(), "adiós mundo");
    }

    #[test]
    fn word_motion_skips_spaces_and_punctuation() {
        let text = "uno, dos  tres";
        assert_eq!(next_word(text, 0), 3);
        assert_eq!(next_word(text, 3), 8);
        assert_eq!(prev_word(text, text.len()), 10);
        assert_eq!(prev_word(text, 10), 5);
        let mut e = Editor::new(text);
        e.backspace(true);
        assert_eq!(e.text(), "uno, dos  ");
    }

    #[test]
    fn typing_is_undone_in_word_groups() {
        let mut e = Editor::new("");
        for c in ["h", "o", "l", "a", " ", "m", "u", "n", "d", "o"] {
            e.insert(c);
        }
        assert!(e.undo());
        assert_eq!(e.text(), "hola ");
        assert!(e.undo());
        assert_eq!(e.text(), "hola");
        assert!(e.undo());
        assert_eq!(e.text(), "");
        assert!(e.redo());
        assert_eq!(e.text(), "hola");
    }

    #[test]
    fn external_text_keeps_cursor_in_bounds() {
        let mut e = Editor::new("abcdef");
        e.set_external("ab");
        assert_eq!(e.cursor(), 2);
        assert!(!e.has_selection());
    }

    #[test]
    fn select_word_at_position() {
        let mut e = Editor::new("hola mundo");
        e.select_word_at(7);
        assert_eq!(e.selected_text(), "mundo");
    }

    #[test]
    fn utf16_round_trip() {
        let text = "a😀b";
        assert_eq!(utf8_to_utf16(text, 5), 3);
        assert_eq!(utf16_to_utf8(text, 3), 5);
        assert_eq!(utf16_to_utf8(text, 2), 1); // mitad de un par subrogado: hacia abajo
    }
}
