//! Teclado: manejadores `on_key`, Tab/Enter/Espacio y desplazamiento con las flechas.

use super::*;

impl Runtime {
    /// Atajos del inspector: F12 abre y cierra el panel, Ctrl+Mayús+C entra
    /// y sale del modo selección y Escape sale de él. Devuelve si la atendió.
    fn inspector_key(&mut self, input: &KeyInput) -> bool {
        let m = input.mods;
        let plain = !(m.ctrl || m.shift || m.alt || m.meta);
        let pick_combo =
            (m.ctrl || m.meta) && m.shift && !m.alt && input.key.eq_ignore_ascii_case("c");
        if input.is("F12") && plain {
            let open = !self.inspector.open;
            self.inspector.set_open(open);
        } else if pick_combo {
            let pick = !self.inspector.pick;
            self.inspector.set_pick(pick);
        } else if input.is("Escape") && plain && self.inspector.pick {
            self.inspector.set_pick(false);
        } else {
            return false;
        }
        self.dirty = true;
        true
    }
}

impl Runtime {
    /// Pulsación o liberación de una tecla. Devuelve `true` si hace falta otro frame.
    ///
    /// Primero la reciben los manejadores `on_key`, del nodo enfocado hacia la
    /// raíz (o solo la raíz si no hay foco); uno que devuelva un valor verdadero
    /// la da por atendida. Si nadie la atiende, se aplica el comportamiento por
    /// defecto: Tab mueve el foco, Enter y Espacio activan, y las flechas,
    /// RePág/AvPág, Inicio/Fin y Espacio desplazan.
    pub fn key_event(&mut self, input: &KeyInput, pressed: bool) -> PyResult<bool> {
        if !pressed {
            return self.key_up(input);
        }
        self.engine.tip.suppressed = true;
        if self.inspector.enabled && !input.repeat && self.inspector_key(input) {
            return Ok(true);
        }
        if self.dispatch_key(input)? {
            return Ok(true);
        }
        if self.edit_key(input)? {
            return Ok(true);
        }
        let shortcut = input.mods.ctrl || input.mods.alt || input.mods.meta;
        let focused = self.engine.focused.clone();
        let clickable = focused
            .as_ref()
            .and_then(|f| self.tree.as_ref().and_then(|t| t.find(f)))
            .is_some_and(Node::is_interactive);
        match input.key.as_str() {
            "Tab" if !shortcut => {
                self.focus_next(input.mods.shift)?;
                Ok(true)
            }
            "Enter" if clickable && !shortcut => {
                if let Some(key) = focused {
                    self.dispatch(&key, "click", None)?;
                }
                Ok(true)
            }
            "Space" if clickable && !shortcut => {
                if !input.repeat {
                    self.engine.pressed = focused.clone();
                    self.space_pressed = focused;
                }
                Ok(true)
            }
            _ => Ok(self.keyboard_scroll(input)),
        }
    }

    fn key_up(&mut self, input: &KeyInput) -> PyResult<bool> {
        if input.is("Space")
            && let Some(key) = self.space_pressed.take()
        {
            self.engine.pressed = None;
            if self.engine.focused.as_deref() == Some(key.as_str()) {
                self.dispatch(&key, "click", None)?;
            }
            return Ok(true);
        }
        Ok(false)
    }

    /// Entrega la tecla a los `on_key` del nodo enfocado y sus ancestros.
    fn dispatch_key(&mut self, input: &KeyInput) -> PyResult<bool> {
        let start = self
            .engine
            .focused
            .as_ref()
            .and_then(|f| self.engine.regions.iter().rposition(|r| &r.key == f))
            .or(if self.engine.regions.is_empty() {
                None
            } else {
                Some(0)
            });
        self.dispatch_key_chain(start, input)
    }

    /// Entrega la tecla a los `on_key` de `key` y sus ancestros, como si ese
    /// nodo tuviera el foco (lo usan las acciones de ajuste de los lectores).
    pub(super) fn dispatch_key_from(&mut self, key: &str, input: &KeyInput) -> PyResult<bool> {
        let start = self.engine.regions.iter().rposition(|r| r.key == key);
        self.dispatch_key_chain(start, input)
    }

    /// Entrega la tecla a los `on_key` de la región `start` y sus ancestros,
    /// de dentro hacia fuera.
    fn dispatch_key_chain(&mut self, start: Option<usize>, input: &KeyInput) -> PyResult<bool> {
        let chain: Vec<String> = ancestors(&self.engine.regions, start)
            .map(|r| r.key.clone())
            .collect();
        if chain.is_empty() {
            return Ok(false);
        }
        let event: Py<PyAny> =
            Python::attach(|py| Py::new(py, KeyEvent::from(input)).map(|e| e.into_any()))?;
        for key in chain {
            let arg = Python::attach(|py| event.clone_ref(py));
            if let Some(ret) = self.call(&key, "key", Some(arg))?
                && Python::attach(|py| ret.bind(py).is_truthy())?
            {
                return Ok(true);
            }
        }
        Ok(false)
    }

    /// Desplazamiento con el teclado del `scroll` que contiene al foco o, sin
    /// foco, del que está bajo el puntero.
    fn keyboard_scroll(&mut self, input: &KeyInput) -> bool {
        const FAR: f32 = 1.0e9;
        let page = |v: Rect| (v.height() - 2.0 * LINE).max(LINE);
        let delta = |v: Rect| -> Option<Point> {
            Some(match input.key.as_str() {
                "ArrowDown" => Point::new(0.0, LINE),
                "ArrowUp" => Point::new(0.0, -LINE),
                "ArrowRight" => Point::new(LINE, 0.0),
                "ArrowLeft" => Point::new(-LINE, 0.0),
                "PageDown" => Point::new(0.0, page(v)),
                "PageUp" => Point::new(0.0, -page(v)),
                "Space" if input.mods.shift => Point::new(0.0, -page(v)),
                "Space" => Point::new(0.0, page(v)),
                "Home" => Point::new(0.0, -FAR),
                "End" => Point::new(0.0, FAR),
                _ => return None,
            })
        };
        let start = match &self.engine.focused {
            Some(f) => self.engine.regions.iter().rposition(|r| &r.key == f),
            None => self
                .pointer
                .and_then(|(x, y)| topmost(&self.engine.regions, x, y)),
        };
        let keys: Vec<String> = ancestors(&self.engine.regions, start)
            .filter(|r| r.scroll.is_some())
            .map(|r| r.key.clone())
            .collect();
        keys.iter().any(|key| {
            self.engine.scroll.get_mut(key).is_some_and(|state| {
                delta(state.viewport).is_some_and(|d| state.scroll_by(d, true))
            })
        })
    }
}
