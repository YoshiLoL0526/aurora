//! Campos de texto: edición, portapapeles, deshacer, IME y geometría del cursor.

use super::*;

impl Runtime {
    /// Edición en el campo enfocado. Devuelve `true` si la tecla era suya.
    pub(super) fn edit_key(&mut self, input: &KeyInput) -> PyResult<bool> {
        let Some(key) = self.engine.focused.clone() else {
            return Ok(false);
        };
        let Some(state) = self.engine.inputs.get_mut(&key) else {
            return Ok(false);
        };
        let m = input.mods;
        let mac = cfg!(target_os = "macos");
        // Atajos: Cmd en macOS, Ctrl en el resto. Saltar palabras: Alt en macOS, Ctrl en el resto.
        let cmd = if mac { m.meta } else { m.ctrl };
        let word = if mac { m.alt } else { m.ctrl };
        // Inicio/Fin de documento en un campo multilínea: Cmd en macOS (donde `alt`
        // ya salta por palabras), Ctrl en el resto; mismo modificador que `word`.
        let doc_edge = if mac { m.meta } else { m.ctrl };
        let (shift, multiline) = (m.shift, state.multiline);
        let before = state.editor.text().to_owned();
        let len = before.len();
        let mut submit = false;
        let letter = input.key.to_lowercase();
        match input.key.as_str() {
            "Backspace" => {
                state.editor.backspace(word);
            }
            "Delete" => {
                state.editor.delete(word);
            }
            "ArrowLeft" if mac && m.meta => line_edge(state, false, shift),
            "ArrowRight" if mac && m.meta => line_edge(state, true, shift),
            "ArrowLeft" => state.editor.left(word, shift),
            "ArrowRight" => state.editor.right(word, shift),
            "ArrowUp" | "ArrowDown" if multiline => {
                vertical(state, input.key == "ArrowDown", shift);
            }
            "ArrowUp" => state.editor.move_to(0, shift),
            "ArrowDown" => state.editor.move_to(len, shift),
            // Inicio/Fin de línea en multilínea; con el modificador de documento (Ctrl en
            // Windows/Linux, Cmd en macOS), al principio o al final del texto.
            "End" | "Home" if multiline && doc_edge => {
                state
                    .editor
                    .move_to(if input.key == "End" { len } else { 0 }, shift);
            }
            "End" | "Home" if multiline => {
                line_edge(state, input.key == "End", shift);
            }
            "Home" => state.editor.move_to(0, shift),
            "End" => state.editor.move_to(len, shift),
            "Enter" if multiline && !cmd => {
                state.editor.insert("\n");
            }
            "Enter" => submit = true,
            _ if cmd && letter == "a" => state.editor.select_all(),
            _ if cmd && (letter == "c" || letter == "x") => {
                if state.editor.has_selection() {
                    self.clipboard.set(state.editor.selected_text().to_owned());
                    if letter == "x" {
                        state.editor.delete_selection();
                    }
                }
            }
            _ if cmd && letter == "v" => {
                if let Some(text) = self.clipboard.get() {
                    state.editor.insert(&clean(&text, multiline));
                }
            }
            _ if cmd && letter == "z" && !shift => {
                state.editor.undo();
            }
            _ if cmd && (letter == "z" || letter == "y") => {
                state.editor.redo();
            }
            _ => {
                // AltGr llega como Ctrl+Alt y sí escribe texto.
                let shortcut = (m.ctrl && !m.alt) || m.meta;
                match &input.text {
                    Some(text) if !shortcut && state.preedit.is_none() => {
                        state.editor.insert(&clean(text, multiline));
                        self.last_typed = Some((text.clone(), Instant::now()));
                    }
                    _ => return Ok(false),
                }
            }
        }
        self.after_edit(&key, &before, submit)?;
        Ok(true)
    }

    /// Tras editar: reinicia el parpadeo, muestra el cursor y avisa a Python
    /// con `on_change(texto)` si cambió y `on_submit(texto)` al enviar.
    pub(super) fn after_edit(&mut self, key: &str, before: &str, submit: bool) -> PyResult<()> {
        let Some(state) = self.engine.inputs.get_mut(key) else {
            return Ok(());
        };
        state.blink = 0.0;
        self.reveal_focus = true;
        let text = state.editor.text().to_owned();
        let arg = |t: &str| Python::attach(|py| PyString::new(py, t).into_any().unbind());
        if text != before {
            // Se reconstruye aunque no haya `on_change`: si Python no acepta el
            // cambio, el campo vuelve a mostrar su valor (campo controlado).
            self.dirty = true;
        }
        let changed = if text != before {
            self.dispatch(key, "change", Some(arg(&text))).map(drop)
        } else {
            Ok(())
        };
        let submitted = if submit {
            self.dispatch(key, "submit", Some(arg(&text))).map(drop)
        } else {
            Ok(())
        };
        changed.and(submitted)
    }

    /// Texto en composición del IME (vacío = se canceló la composición).
    pub fn ime_preedit(&mut self, text: &str) -> bool {
        let Some(state) = self.focused_input() else {
            return false;
        };
        state.preedit = (!text.is_empty()).then(|| text.to_owned());
        state.blink = 0.0;
        true
    }

    /// El IME confirma texto. Si es justo lo que acaba de llegar como tecla,
    /// se ignora: algunas plataformas entregan ambos.
    pub fn ime_commit(&mut self, text: &str) -> PyResult<bool> {
        let recent = self
            .last_typed
            .take()
            .is_some_and(|(t, at)| t == text && at.elapsed() < Duration::from_millis(50));
        let Some(key) = self.engine.focused.clone() else {
            return Ok(false);
        };
        let Some(state) = self.engine.inputs.get_mut(&key) else {
            return Ok(false);
        };
        state.preedit = None;
        if recent {
            return Ok(true);
        }
        let before = state.editor.text().to_owned();
        let multiline = state.multiline;
        state.editor.insert(&clean(text, multiline));
        self.after_edit(&key, &before, false)?;
        Ok(true)
    }

    pub(super) fn focused_input(&mut self) -> Option<&mut InputState> {
        let key = self.engine.focused.as_ref()?;
        self.engine.inputs.get_mut(key)
    }

    /// Cursor del campo enfocado (para colocar la ventana del IME).
    pub fn ime_area(&self) -> Option<Rect> {
        let key = self.engine.focused.as_ref()?;
        self.engine.inputs.get(key)?.caret()
    }
}

impl Runtime {
    /// Selección del campo `key` en caracteres (no bytes): `(inicio, fin)`.
    pub fn selection(&self, key: &str) -> Option<(usize, usize)> {
        let editor = &self.engine.inputs.get(key)?.editor;
        let chars = |b: usize| editor.text()[..b].chars().count();
        let r = editor.selection();
        Some((chars(r.start), chars(r.end)))
    }
}

/// Normaliza texto pegado o escrito: sin `\r` y, en un campo de una línea, sin saltos.
fn clean(text: &str, multiline: bool) -> String {
    let text = text.replace("\r\n", "\n").replace('\r', "\n");
    if multiline {
        text
    } else {
        text.replace('\n', " ")
    }
}

/// Inicio o fin de la línea visual del cursor (Inicio/Fin en un campo multilínea).
fn line_edge(state: &mut InputState, end: bool, extend: bool) {
    let Some(caret) = state.caret() else {
        return;
    };
    let x = if end { 1.0e6 } else { -1.0e6 };
    if let Some(pos) = state.position_at(Point::new(x, caret.center_y())) {
        state.editor.move_to(pos, extend);
    }
}

/// Flecha arriba/abajo en un campo multilínea: misma columna en la línea
/// vecina; desde la primera (o última) línea, al principio (o al final).
fn vertical(state: &mut InputState, down: bool, extend: bool) {
    let (Some(caret), Some(frame)) = (state.caret(), state.frame.as_ref()) else {
        return;
    };
    let top = frame.origin.y;
    let bottom = top + frame.paragraph.height();
    let y = if down {
        caret.bottom + 1.0
    } else {
        caret.top - 1.0
    };
    let pos = if y < top {
        Some(0)
    } else if y >= bottom {
        Some(state.editor.text().len())
    } else {
        state.position_at(Point::new(caret.left, y))
    };
    if let Some(pos) = pos {
        state.editor.move_to(pos, extend);
    }
}
