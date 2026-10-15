//! Estado de una app en ejecución, independiente de la ventana: árbol de la
//! vista, regiones de hit-testing, puntero, foco, teclado y despacho de eventos.
//!
//! Lo comparten el bucle de winit (`window.rs`) y el piloto headless
//! (`pilot.rs`), así que lo que se prueba sin pantalla es exactamente lo que
//! ocurre con una ventana abierta.

use std::collections::HashSet;
use std::sync::atomic::{AtomicBool, Ordering};

use pyo3::prelude::*;
use skia_safe::{Canvas, Point, Rect};

use crate::keys::{KeyEvent, KeyInput};
use crate::render::{Engine, HitRegion, ancestors, hit_test, topmost};
use crate::scroll::LINE;
use crate::spec::{self, Node};

/// Lo activa `wake()` desde cualquier hilo; el siguiente frame lo consume y
/// reconstruye la vista.
static WAKE_PENDING: AtomicBool = AtomicBool::new(false);

/// Margen que se deja alrededor de un nodo al desplazar para mostrarlo.
const REVEAL_MARGIN: f32 = 8.0;

/// Marca la vista como desactualizada y despierta el bucle de eventos si hay
/// uno en marcha. Seguro desde cualquier hilo; sin bucle no hace nada más.
pub fn wake() {
    WAKE_PENDING.store(true, Ordering::Release);
    crate::window::notify();
}

pub struct Runtime {
    build: Py<PyAny>,
    pub engine: Engine,
    tree: Option<Node>,
    regions: Vec<HitRegion>,
    dirty: bool,
    /// Última posición conocida del puntero (píxeles lógicos).
    pointer: Option<(f32, f32)>,
    /// Arrastre en curso del pulgar de una barra de desplazamiento.
    drag: Option<Drag>,
    /// Nodo pulsado con Espacio, que se activa al soltar la tecla.
    space_pressed: Option<String>,
    /// Nodos con `autofocus` de la vista anterior: solo toma el foco el que aparece.
    autofocus_seen: HashSet<String>,
    /// Desplazar los `scroll` para mostrar el nodo enfocado tras el próximo frame.
    reveal_focus: bool,
}

struct Drag {
    key: String,
    vertical: bool,
    /// Distancia entre el puntero y el inicio del pulgar al agarrarlo.
    grab: f32,
}

impl Runtime {
    pub fn new(build: Py<PyAny>) -> Self {
        Self {
            build,
            engine: Engine::new(),
            tree: None,
            regions: Vec::new(),
            dirty: true,
            pointer: None,
            drag: None,
            space_pressed: None,
            autofocus_seen: HashSet::new(),
            reveal_focus: false,
        }
    }

    pub fn has_tree(&self) -> bool {
        self.tree.is_some()
    }

    /// Si la vista tiene que reconstruirse (un manejador cambió estado).
    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    /// Reconstruye la vista si algo la invalidó. Si la vista falla, se
    /// conserva el árbol anterior y se devuelve el error.
    pub fn sync(&mut self) -> PyResult<()> {
        if WAKE_PENDING.swap(false, Ordering::AcqRel) {
            self.dirty = true;
        }
        if !self.dirty && self.tree.is_some() {
            return Ok(());
        }
        self.dirty = false;
        let tree = Python::attach(|py| -> PyResult<Node> {
            let obj = self.build.call0(py)?;
            spec::parse(obj.bind(py))
        })?;

        // El foco se pierde si su nodo desaparece o deja de ser enfocable.
        if let Some(focused) = &self.engine.focused
            && find(&tree, focused).is_none_or(|n| !n.is_focusable())
        {
            self.engine.focused = None;
        }
        let mut autofocus = Vec::new();
        collect_autofocus(&tree, &mut autofocus);
        let appeared = autofocus
            .iter()
            .rev()
            .find(|k| !self.autofocus_seen.contains(*k))
            .cloned();
        self.autofocus_seen = autofocus.into_iter().collect();
        self.tree = Some(tree);

        if let Some(key) = appeared {
            self.reveal_focus = true;
            self.focus(Some(key))?;
        }
        Ok(())
    }

    /// Avanza las transiciones. Devuelve `true` si alguna sigue en curso.
    pub fn tick(&mut self, dt: f32) -> bool {
        self.engine.tick(dt)
    }

    /// Pinta el árbol y recalcula el hover: tras una reconstrucción, lo que
    /// hay bajo el puntero puede haber cambiado aunque el puntero no se mueva.
    /// Devuelve `true` si hace falta otro frame.
    pub fn draw(&mut self, canvas: &Canvas, width: f32, height: f32, scale: f32) -> bool {
        if let Some(tree) = &self.tree {
            self.regions = self.engine.draw(canvas, tree, width, height, scale);
        }
        let revealed = std::mem::take(&mut self.reveal_focus) && self.reveal_focused();
        self.refresh_hover() || revealed
    }

    // ---------------------------------------------------------------- puntero

    pub fn hovered(&self) -> Option<&str> {
        self.engine.hovered.as_deref()
    }

    /// Devuelve `true` si hace falta pintar otro frame.
    pub fn pointer_move(&mut self, x: f32, y: f32) -> bool {
        self.pointer = Some((x, y));
        if let Some(drag) = &self.drag {
            if let Some(state) = self.engine.scroll.get_mut(&drag.key) {
                let pos = if drag.vertical { y } else { x };
                state.drag_thumb_to(drag.vertical, pos - drag.grab);
            }
            return true;
        }
        let bar_changed = self.hover_scrollbar();
        self.refresh_hover() || bar_changed
    }

    pub fn pointer_leave(&mut self) {
        self.pointer = None;
        self.engine.hovered = None;
        self.hover_scrollbar();
    }

    /// Pulsar enfoca el nodo enfocable más cercano bajo el puntero (sin anillo,
    /// como `:focus-visible`), o quita el foco si no hay ninguno.
    pub fn pointer_down(&mut self) -> PyResult<()> {
        if self.start_drag() {
            self.engine.pressed = None;
            return Ok(());
        }
        self.engine.pressed = self.engine.hovered.clone();
        self.engine.focus_visible = false;
        let target = self.pointer.and_then(|(x, y)| {
            ancestors(&self.regions, topmost(&self.regions, x, y))
                .find(|r| r.focusable)
                .map(|r| r.key.clone())
        });
        self.focus(target)
    }

    /// Un clic se completa si se suelta sobre el mismo nodo que se pulsó.
    pub fn pointer_up(&mut self) -> PyResult<()> {
        if let Some(drag) = self.drag.take() {
            if let Some(state) = self.engine.scroll.get_mut(&drag.key) {
                state.dragging = false;
                state.poke();
            }
            return Ok(());
        }
        if let Some(key) = self.engine.pressed.take()
            && self.engine.hovered.as_deref() == Some(key.as_str())
        {
            self.dispatch(&key, "click", None)?;
        }
        Ok(())
    }

    // ------------------------------------------------------------------- foco

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
        if !self.regions.iter().any(|r| r.key == key && r.focusable) {
            return Ok(false);
        }
        self.engine.focus_visible = true;
        self.reveal_focus = true;
        self.focus(Some(key.to_owned()))?;
        Ok(true)
    }

    /// Tab / Shift+Tab: siguiente nodo enfocable en orden de pintura. Si hay
    /// una barrera (`capture`, p. ej. un modal), el foco no sale de ella.
    fn focus_next(&mut self, back: bool) -> PyResult<()> {
        let scope = self
            .regions
            .iter()
            .rposition(|r| r.capture)
            .map(|i| self.regions[i].key.clone());
        let order: Vec<String> = (0..self.regions.len())
            .filter(|&i| self.regions[i].focusable)
            .filter(|&i| {
                scope
                    .as_ref()
                    .is_none_or(|s| ancestors(&self.regions, Some(i)).any(|r| &r.key == s))
            })
            .map(|i| self.regions[i].key.clone())
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
    fn reveal_focused(&mut self) -> bool {
        let Some(idx) = self
            .engine
            .focused
            .as_ref()
            .and_then(|f| self.regions.iter().rposition(|r| &r.key == f))
        else {
            return false;
        };
        let mut rect = self.regions[idx].rect;
        let scrolls: Vec<String> = ancestors(&self.regions, self.regions[idx].parent)
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

    // ---------------------------------------------------------------- teclado

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
        if self.dispatch_key(input)? {
            return Ok(true);
        }
        let shortcut = input.mods.ctrl || input.mods.alt || input.mods.meta;
        let focused = self.engine.focused.clone();
        let clickable = focused
            .as_ref()
            .and_then(|f| self.tree.as_ref().and_then(|t| find(t, f)))
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
            .and_then(|f| self.regions.iter().rposition(|r| &r.key == f))
            .or(if self.regions.is_empty() {
                None
            } else {
                Some(0)
            });
        let chain: Vec<String> = ancestors(&self.regions, start)
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
            Some(f) => self.regions.iter().rposition(|r| &r.key == f),
            None => self.pointer.and_then(|(x, y)| topmost(&self.regions, x, y)),
        };
        let keys: Vec<String> = ancestors(&self.regions, start)
            .filter(|r| r.scroll.is_some())
            .map(|r| r.key.clone())
            .collect();
        keys.iter().any(|key| {
            self.engine.scroll.get_mut(key).is_some_and(|state| {
                delta(state.viewport).is_some_and(|d| state.scroll_by(d, true))
            })
        })
    }

    // ----------------------------------------------------------------- scroll

    /// Rueda o trackpad sobre el puntero: desplaza el `scroll` más interno que
    /// aún pueda moverse en esa dirección (al llegar al límite, pasa al de fuera).
    /// `delta` en píxeles, positivo hacia el final del contenido. `smooth` anima
    /// el recorrido (rueda por pasos); sin él se aplica tal cual (trackpad).
    pub fn wheel(&mut self, delta: Point, smooth: bool) -> bool {
        let Some((x, y)) = self.pointer else {
            return false;
        };
        let idx = topmost(&self.regions, x, y);
        let keys: Vec<String> = ancestors(&self.regions, idx)
            .filter(|r| r.scroll.is_some())
            .map(|r| r.key.clone())
            .collect();
        keys.iter().any(|key| {
            self.engine
                .scroll
                .get_mut(key)
                .is_some_and(|state| state.scroll_by(delta, smooth))
        })
    }

    /// Desplazamiento actual del `scroll` con esa key.
    pub fn scroll_offset(&self, key: &str) -> Option<Point> {
        self.engine.scroll.get(key).map(|s| s.offset)
    }

    /// Barra (key del `scroll`, si es vertical) cuya franja está bajo el puntero.
    fn scrollbar_at(&self) -> Option<(String, bool)> {
        let (x, y) = self.pointer?;
        let inside = |r: Rect| x >= r.left && x < r.right && y >= r.top && y < r.bottom;
        ancestors(&self.regions, topmost(&self.regions, x, y))
            .filter(|r| r.scroll.is_some())
            .find_map(|r| {
                let state = self.engine.scroll.get(&r.key)?;
                [true, false]
                    .into_iter()
                    .find(|&v| state.track(v).is_some_and(inside))
                    .map(|v| (r.key.clone(), v))
            })
    }

    /// Muestra la barra bajo el puntero. Devuelve `true` si cambió algo visible.
    fn hover_scrollbar(&mut self) -> bool {
        let target = self.scrollbar_at().map(|(key, _)| key);
        let mut changed = false;
        for (key, state) in self.engine.scroll.iter_mut() {
            let hovered = target.as_deref() == Some(key.as_str());
            if hovered != state.hovered || (hovered && state.bar < 1.0) {
                changed = true;
            }
            state.hovered = hovered;
            if hovered {
                state.poke();
            }
        }
        changed
    }

    /// Empieza a arrastrar una barra si se pulsa sobre su franja. Pulsar fuera
    /// del pulgar lo centra bajo el puntero.
    fn start_drag(&mut self) -> bool {
        let (Some((key, vertical)), Some((x, y))) = (self.scrollbar_at(), self.pointer) else {
            return false;
        };
        let Some(state) = self.engine.scroll.get_mut(&key) else {
            return false;
        };
        let Some(thumb) = state.thumb(vertical) else {
            return false;
        };
        let (pos, start, len) = if vertical {
            (y, thumb.top, thumb.height())
        } else {
            (x, thumb.left, thumb.width())
        };
        let grab = if (start..start + len).contains(&pos) {
            pos - start
        } else {
            len / 2.0
        };
        state.dragging = true;
        state.drag_thumb_to(vertical, pos - grab);
        self.drag = Some(Drag {
            key,
            vertical,
            grab,
        });
        true
    }

    fn refresh_hover(&mut self) -> bool {
        let hovered = self
            .pointer
            .and_then(|(x, y)| hit_test(&self.regions, x, y));
        let changed = hovered != self.engine.hovered;
        self.engine.hovered = hovered;
        changed
    }

    // ---------------------------------------------------------------- eventos

    /// Llama al manejador `event` del nodo `key`, con `arg` como único
    /// argumento si se indica. Devuelve `false` si el nodo no lo tiene.
    pub fn dispatch(&mut self, key: &str, event: &str, arg: Option<Py<PyAny>>) -> PyResult<bool> {
        self.call(key, event, arg).map(|ret| ret.is_some())
    }

    /// Como `dispatch`, pero devuelve lo que devolvió el manejador (`None` si no hay).
    ///
    /// Tras ejecutar un manejador la vista se marca para reconstruirse, aunque
    /// lance una excepción: el estado puede haber cambiado a medias.
    fn call(
        &mut self,
        key: &str,
        event: &str,
        arg: Option<Py<PyAny>>,
    ) -> PyResult<Option<Py<PyAny>>> {
        let Some(cb) = self
            .tree
            .as_ref()
            .and_then(|tree| find(tree, key))
            .and_then(|node| node.handler(event))
        else {
            return Ok(None);
        };
        let result = Python::attach(|py| match arg {
            Some(arg) => cb.call1(py, (arg,)),
            None => cb.call0(py),
        });
        self.dirty = true;
        result.map(Some)
    }

    /// Rectángulo absoluto (píxeles lógicos) con el que se pintó `key` en el último frame.
    pub fn rect(&self, key: &str) -> Option<Rect> {
        self.regions
            .iter()
            .rev()
            .find(|r| r.key == key)
            .map(|r| r.rect)
    }
}

fn find<'a>(node: &'a Node, key: &str) -> Option<&'a Node> {
    if node.key == key {
        return Some(node);
    }
    node.children.iter().find_map(|c| find(c, key))
}

fn collect_autofocus(node: &Node, out: &mut Vec<String>) {
    if node.style.autofocus && node.is_focusable() {
        out.push(node.key.clone());
    }
    for child in &node.children {
        collect_autofocus(child, out);
    }
}
