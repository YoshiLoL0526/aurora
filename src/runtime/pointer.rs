//! Puntero y gestos: hover, clics, arrastres (barras, gráficos y `on_drag`).

use super::*;

/// Dos clics más cerca que esto (en tiempo y distancia) cuentan como doble clic.
const MULTI_CLICK: Duration = Duration::from_millis(400);
const MULTI_CLICK_DISTANCE: f32 = 4.0;

pub(super) struct Drag {
    pub(super) key: String,
    pub(super) vertical: bool,
    /// Distancia entre el puntero y el inicio del pulgar al agarrarlo.
    pub(super) grab: f32,
}

/// Arrastre del eje x de un `chart`: la ventana sigue al puntero.
pub(super) struct Pan {
    key: String,
    /// Última posición del puntero.
    last: (f32, f32),
    /// Si llegó a moverse (un arrastre no completa el clic).
    moved: bool,
}

/// Arrastre de un nodo con `on_drag`: empieza al pulsar sobre él y le llegan
/// todos los movimientos hasta soltar, aunque el puntero salga de su caja.
pub(super) struct Grip {
    key: String,
    /// Dónde se pulsó.
    start: (f32, f32),
    /// Última posición entregada.
    last: (f32, f32),
    /// Si llegó a moverse (un arrastre no completa el clic).
    moved: bool,
}

/// Lo que recibe un manejador `on_drag`: posición del puntero y desplazamiento
/// desde donde se pulsó (píxeles lógicos), y la fase del gesto.
#[pyclass(frozen, get_all, module = "aurora._core", name = "DragEvent")]
#[derive(Clone, Debug)]
pub struct DragEvent {
    pub x: f32,
    pub y: f32,
    pub dx: f32,
    pub dy: f32,
    /// `"start"` al pulsar, `"move"` en cada movimiento y `"end"` al soltar.
    pub phase: String,
}

#[pymethods]
impl DragEvent {
    fn __repr__(&self) -> String {
        format!(
            "DragEvent(phase={:?}, x={}, y={}, dx={}, dy={})",
            self.phase, self.x, self.y, self.dx, self.dy
        )
    }
}

impl Runtime {
    pub fn hovered(&self) -> Option<&str> {
        self.engine.hovered.as_deref()
    }

    /// Devuelve `true` si hace falta pintar otro frame.
    pub fn pointer_move(&mut self, x: f32, y: f32) -> PyResult<bool> {
        self.pointer = Some((x, y));
        // Modo selección del inspector: sobre la app solo se resalta el nodo
        // bajo el puntero, sin hover ni Python (ver `refresh_hover`).
        if self.inspector.pick && self.pick_at(x, y).is_some() {
            return Ok(self.refresh_hover());
        }
        if let Some(key) = &self.selecting
            && let Some(state) = self.engine.inputs.get_mut(key)
        {
            if let Some(pos) = state.position_at(Point::new(x, y)) {
                state.editor.move_to(pos, true);
                state.blink = 0.0;
            }
            return Ok(true);
        }
        if let Some(drag) = &self.drag {
            if let Some(state) = self.engine.scroll.get_mut(&drag.key) {
                let pos = if drag.vertical { y } else { x };
                state.drag_thumb_to(drag.vertical, pos - drag.grab);
            }
            return Ok(true);
        }
        // Arrastre de un nodo con `on_drag`: cada movimiento llega a su manejador.
        if let Some(grip) = &mut self.grip {
            if grip.last == (x, y) {
                return Ok(false);
            }
            grip.last = (x, y);
            grip.moved = true;
            self.send_drag("move")?;
            return Ok(true);
        }
        // Arrastre de la ventana de un `chart`: el eje x sigue al puntero.
        if let Some(pan) = &mut self.pan {
            let dx = x - pan.last.0;
            pan.last = (x, y);
            pan.moved |= dx != 0.0;
            return Ok(dx != 0.0 && self.charts.pan(&pan.key, dx));
        }
        let bar_changed = self.hover_scrollbar();
        let hover_changed = self.refresh_hover();
        // Entrar o salir de un `chart` con zoom también cambia el cursor.
        let grab = self.zoom_at().is_some();
        let grab_changed = self.zoom_hover != grab;
        self.zoom_hover = grab;
        Ok(hover_changed || bar_changed || grab_changed)
    }

    /// Nodo que elegiría el modo selección en `(x, y)`: el pintado más arriba,
    /// salvo dentro del panel del inspector (`None`).
    fn pick_at(&self, x: f32, y: f32) -> Option<String> {
        let regions = &self.engine.regions;
        let idx = topmost(regions, x, y)?;
        if ancestors(regions, Some(idx)).any(|r| r.key == PANEL_KEY) {
            return None;
        }
        Some(regions[idx].key.clone())
    }

    /// Lo que el inspector resalta sobre la interfaz: el nodo elegido y el que
    /// está bajo el puntero en modo selección.
    pub(super) fn marks(&self) -> Vec<Mark> {
        let insp = &self.inspector;
        if !insp.open {
            return Vec::new();
        }
        let Some(tree) = &self.tree else {
            return Vec::new();
        };
        let mark = |key: &String, hovered: bool| {
            let rect = self.rect(key)?;
            let node = tree.find(key)?;
            // Como en el árbol del panel: `row`, `column` y `scroll` en vez de `box`.
            let kind = match node.kind {
                spec::Kind::Box if node.style.scroll.is_some() => "scroll",
                spec::Kind::Box if node.style.row => "row",
                spec::Kind::Box => "column",
                kind => kind.name(),
            };
            Some(Mark {
                rect,
                padding: node.style.padding,
                label: format!(
                    "{} {}  {} × {}",
                    kind,
                    key,
                    rect.width().round(),
                    rect.height().round()
                ),
                hovered,
            })
        };
        let selected = insp.selected.as_ref().and_then(|k| mark(k, false));
        let hovered = insp
            .hovered
            .as_ref()
            .filter(|k| insp.pick && insp.selected.as_ref() != Some(*k))
            .and_then(|k| mark(k, true));
        selected.into_iter().chain(hovered).collect()
    }
}

impl Runtime {
    /// Entrega la posición actual del arrastre a su `on_drag`.
    fn send_drag(&mut self, phase: &str) -> PyResult<()> {
        let Some(grip) = &self.grip else {
            return Ok(());
        };
        let (x, y) = grip.last;
        let key = grip.key.clone();
        let event = DragEvent {
            x,
            y,
            dx: x - grip.start.0,
            dy: y - grip.start.1,
            phase: phase.to_owned(),
        };
        let arg = Python::attach(|py| Py::new(py, event).map(|e| e.into_any()))?;
        self.dispatch(&key, "drag", Some(arg)).map(drop)
    }

    pub fn pointer_leave(&mut self) {
        self.pointer = None;
        self.zoom_hover = false;
        self.engine.hovered = None;
        self.engine.tip.set_key(None);
        self.hover_scrollbar();
    }
}

impl Runtime {
    /// Pulsar enfoca el nodo enfocable más cercano bajo el puntero (sin anillo,
    /// como `:focus-visible`), o quita el foco si no hay ninguno.
    pub fn pointer_down(&mut self) -> PyResult<()> {
        // En modo selección, un clic sobre la app elige el nodo y no le llega.
        if self.inspector.pick
            && let Some((x, y)) = self.pointer
            && let Some(key) = self.pick_at(x, y)
        {
            self.inspector.selected = Some(key);
            self.inspector.set_pick(false);
            self.engine.pressed = None;
            self.dirty = true;
            return Ok(());
        }
        if self.start_drag() {
            self.engine.pressed = None;
            return Ok(());
        }
        self.engine.pressed = self.engine.hovered.clone();
        self.engine.tip.suppressed = true;
        self.engine.focus_visible = false;
        // Un nodo con `on_drag` bajo el puntero se lleva el gesto (sin tocar el foco).
        if let (Some(key), Some(at)) = (self.engine.hovered.clone(), self.pointer)
            && self
                .tree
                .as_ref()
                .and_then(|t| t.find(&key))
                .is_some_and(Node::is_draggable)
        {
            self.grip = Some(Grip {
                key,
                start: at,
                last: at,
                moved: false,
            });
            return self.send_drag("start");
        }
        // Un `chart` con zoom bajo el puntero: el arrastre mueve su ventana y el
        // doble clic vuelve a la vista completa.
        if let (Some((key, _)), Some((x, y))) = (self.zoom_at(), self.pointer) {
            if self.click_count(Point::new(x, y)) == 2 {
                self.charts.reset(&key);
            }
            self.pan = Some(Pan {
                key,
                last: (x, y),
                moved: false,
            });
        }
        let target = self.pointer.and_then(|(x, y)| {
            ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
                .find(|r| r.focusable)
                .map(|r| (r.key.clone(), r.editable))
        });
        let editable = target.as_ref().filter(|(_, e)| *e).map(|(k, _)| k.clone());
        let result = self.focus(target.map(|(k, _)| k));
        if let (Some(key), Some((x, y))) = (editable, self.pointer) {
            self.place_cursor(key, Point::new(x, y));
        }
        result
    }

    /// Cuántos clics seguidos lleva el puntero (1, 2 o 3), para el doble y el
    /// triple clic.
    fn click_count(&mut self, at: Point) -> u8 {
        let now = Instant::now();
        let count = match self.last_click {
            Some((t, p, n))
                if now.duration_since(t) < MULTI_CLICK
                    && (p - at).length() < MULTI_CLICK_DISTANCE =>
            {
                n % 3 + 1
            }
            _ => 1,
        };
        self.last_click = Some((now, at, count));
        count
    }

    /// Clic en un campo: coloca el cursor (Mayús amplía la selección); doble
    /// clic selecciona la palabra y triple clic todo el texto.
    fn place_cursor(&mut self, key: String, at: Point) {
        let count = self.click_count(at);
        let Some(state) = self.engine.inputs.get_mut(&key) else {
            return;
        };
        let Some(pos) = state.position_at(at) else {
            return;
        };
        match count {
            1 => state.editor.move_to(pos, self.mods.shift),
            2 => state.editor.select_word_at(pos),
            _ => state.editor.select_all(),
        }
        state.blink = 0.0;
        self.selecting = (count == 1).then_some(key);
    }

    /// Cursor del ratón para lo que hay bajo el puntero.
    pub fn cursor(&self) -> CursorKind {
        if self.inspector.pick && self.inspector.hovered.is_some() {
            return CursorKind::Crosshair;
        }
        if self.selecting.is_some() {
            return CursorKind::Text;
        }
        // Mientras dura un arrastre manda el cursor del nodo arrastrado.
        if let Some(grip) = &self.grip {
            let own = self.engine.regions.iter().find(|r| r.key == grip.key);
            return own.and_then(|r| r.cursor).unwrap_or(CursorKind::Grabbing);
        }
        if self.pan.as_ref().is_some_and(|p| p.moved) {
            return CursorKind::Grabbing;
        }
        if self.zoom_at().is_some() {
            return CursorKind::Grab;
        }
        // La propiedad `cursor` del nodo bajo el puntero (o de un ancestro).
        if let Some((x, y)) = self.pointer
            && let Some(cursor) =
                ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
                    .find_map(|r| r.cursor)
        {
            return cursor;
        }
        match self.engine.hovered.as_ref() {
            Some(key)
                if self
                    .engine
                    .regions
                    .iter()
                    .any(|r| &r.key == key && r.editable) =>
            {
                CursorKind::Text
            }
            Some(_) => CursorKind::Pointer,
            None => CursorKind::Default,
        }
    }

    /// Un clic se completa si se suelta sobre el mismo nodo que se pulsó.
    pub fn pointer_up(&mut self) -> PyResult<()> {
        self.selecting = None;
        if let Some(drag) = self.drag.take() {
            if let Some(state) = self.engine.scroll.get_mut(&drag.key) {
                state.dragging = false;
                state.poke();
            }
            return Ok(());
        }
        // Un arrastre movió la ventana del gráfico: el gesto no completa el clic.
        if self.pan.take().is_some_and(|pan| pan.moved) {
            self.engine.pressed = None;
        }
        // Igual con un `on_drag` que llegó a moverse; si no se movió, es un clic.
        if let Some(grip) = &self.grip {
            if grip.moved {
                self.engine.pressed = None;
            }
            let result = self.send_drag("end");
            self.grip = None;
            result?;
        }
        if let Some(key) = self.engine.pressed.take()
            && self.engine.hovered.as_deref() == Some(key.as_str())
        {
            self.dispatch(&key, "click", None)?;
        }
        Ok(())
    }
}

impl Runtime {
    pub(super) fn refresh_hover(&mut self) -> bool {
        // En modo selección, sobre la app no hay hover: solo el nodo resaltado.
        let mut picked_changed = false;
        if self.inspector.pick {
            let picked = self.pointer.and_then(|(x, y)| self.pick_at(x, y));
            picked_changed = picked != self.inspector.hovered;
            if picked.is_some() {
                let changed = picked_changed || self.engine.hovered.is_some();
                self.inspector.hovered = picked;
                self.engine.hovered = None;
                return self.engine.tip.set_key(None) || changed;
            }
            self.inspector.hovered = None;
        }
        let hovered = self
            .pointer
            .and_then(|(x, y)| hit_test(&self.engine.regions, x, y));
        let changed = hovered != self.engine.hovered;
        self.engine.hovered = hovered;
        let tip = self.pointer.and_then(|(x, y)| {
            ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
                .find(|r| r.tooltip)
                .map(|r| r.key.clone())
        });
        self.engine.tip.set_key(tip) || changed || picked_changed
    }
}
