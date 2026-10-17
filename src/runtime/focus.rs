//! Foco: cambio con `on_focus`/`on_blur`, recorrido con Tab y revelado del nodo.

use super::*;

/// Margen que se deja alrededor de un nodo al desplazar para mostrarlo.
const REVEAL_MARGIN: f32 = 8.0;

impl Runtime {
    pub fn focused(&self) -> Option<&str> {
        self.engine.focused.as_deref()
    }

    /// Cambia el foco y avisa con `on_blur` al nodo que lo pierde y con
    /// `on_focus` al que lo gana.
    pub fn focus(&mut self, key: Option<String>) -> PyResult<()> {
        if self.engine.focused == key {
            return Ok(());
        }
        let old = std::mem::replace(&mut self.engine.focused, key.clone());
        let blur = match old {
            Some(old) => self.dispatch(&old, "blur", None).map(drop),
            None => Ok(()),
        };
        let focus = match key {
            Some(new) => self.dispatch(&new, "focus", None).map(drop),
            None => Ok(()),
        };
        blur.and(focus)
    }

    /// Enfoca con el teclado un nodo concreto (anillo visible).
    pub fn focus_key(&mut self, key: &str) -> PyResult<bool> {
        if !self
            .engine
            .regions
            .iter()
            .any(|r| r.key == key && r.focusable)
        {
            return Ok(false);
        }
        self.engine.focus_visible = true;
        self.reveal_focus = true;
        self.focus(Some(key.to_owned()))?;
        Ok(true)
    }

    /// Tab / Shift+Tab: siguiente nodo enfocable en orden de pintura. Si hay
    /// una barrera (`capture`, p. ej. un modal), el foco no sale de ella.
    pub(super) fn focus_next(&mut self, back: bool) -> PyResult<()> {
        let scope = self
            .engine
            .regions
            .iter()
            .rposition(|r| r.capture)
            .map(|i| self.engine.regions[i].key.clone());
        let order: Vec<String> = (0..self.engine.regions.len())
            .filter(|&i| self.engine.regions[i].focusable)
            .filter(|&i| {
                scope
                    .as_ref()
                    .is_none_or(|s| ancestors(&self.engine.regions, Some(i)).any(|r| &r.key == s))
            })
            .map(|i| self.engine.regions[i].key.clone())
            .collect();
        if order.is_empty() {
            return Ok(());
        }
        let n = order.len();
        let current = self
            .engine
            .focused
            .as_ref()
            .and_then(|f| order.iter().position(|k| k == f));
        let next = match (current, back) {
            (None, false) => 0,
            (None, true) => n - 1,
            (Some(i), false) => (i + 1) % n,
            (Some(i), true) => (i + n - 1) % n,
        };
        self.engine.focus_visible = true;
        self.reveal_focus = true;
        self.focus(Some(order[next].clone()))
    }

    /// Desplaza los `scroll` que contienen al nodo enfocado hasta que se vea.
    pub(super) fn reveal_focused(&mut self) -> bool {
        let Some(key) = self.engine.focused.clone() else {
            return false;
        };
        self.reveal_key(&key)
    }

    /// Desplaza los `scroll` que contienen a `key` hasta que se vea.
    pub(super) fn reveal_key(&mut self, key: &str) -> bool {
        let Some(idx) = self.engine.regions.iter().rposition(|r| r.key == key) else {
            return false;
        };
        // En un campo de texto lo que tiene que verse es el cursor; en la primera
        // o la última línea, también el borde del campo.
        let field = self.engine.regions[idx].rect;
        let mut rect = match self
            .engine
            .inputs
            .get(&self.engine.regions[idx].key)
            .and_then(InputState::caret)
        {
            Some(caret) => {
                let edge = 2.0 * caret.height();
                Rect::new(
                    caret.left,
                    if caret.top - field.top < edge {
                        field.top
                    } else {
                        caret.top
                    },
                    caret.right,
                    if field.bottom - caret.bottom < edge {
                        field.bottom
                    } else {
                        caret.bottom
                    },
                )
            }
            None => field,
        };
        let scrolls: Vec<String> = ancestors(&self.engine.regions, self.engine.regions[idx].parent)
            .filter(|r| r.scroll.is_some())
            .map(|r| r.key.clone())
            .collect();
        let mut moved = false;
        for key in scrolls {
            if let Some(state) = self.engine.scroll.get_mut(&key) {
                let d = state.reveal(rect, REVEAL_MARGIN);
                if d != Point::default() {
                    moved = true;
                    // Lo que mueve el `scroll` interior acerca el nodo al exterior.
                    rect = rect.with_offset(-d);
                }
            }
        }
        moved
    }
}
