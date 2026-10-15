//! Estado de una app en ejecución, independiente de la ventana: árbol de la
//! vista, regiones de hit-testing, puntero y despacho de eventos.
//!
//! Lo comparten el bucle de winit (`window.rs`) y el piloto headless
//! (`pilot.rs`), así que lo que se prueba sin pantalla es exactamente lo que
//! ocurre con una ventana abierta.

use std::sync::atomic::{AtomicBool, Ordering};

use pyo3::prelude::*;
use skia_safe::{Canvas, Point, Rect};

use crate::render::{Engine, HitRegion, ancestors, hit_test, topmost};
use crate::spec::{self, Node};

/// Lo activa `wake()` desde cualquier hilo; el siguiente frame lo consume y
/// reconstruye la vista.
static WAKE_PENDING: AtomicBool = AtomicBool::new(false);

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
        }
    }

    pub fn has_tree(&self) -> bool {
        self.tree.is_some()
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
        self.tree = Some(tree);
        Ok(())
    }

    /// Avanza las transiciones. Devuelve `true` si alguna sigue en curso.
    pub fn tick(&mut self, dt: f32) -> bool {
        self.engine.tick(dt)
    }

    /// Pinta el árbol y recalcula el hover: tras una reconstrucción, lo que
    /// hay bajo el puntero puede haber cambiado aunque el puntero no se mueva.
    /// Devuelve `true` si el hover cambió (hace falta otro frame).
    pub fn draw(&mut self, canvas: &Canvas, width: f32, height: f32, scale: f32) -> bool {
        if let Some(tree) = &self.tree {
            self.regions = self.engine.draw(canvas, tree, width, height, scale);
        }
        self.refresh_hover()
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

    pub fn pointer_down(&mut self) {
        if self.start_drag() {
            self.engine.pressed = None;
            return;
        }
        self.engine.pressed = self.engine.hovered.clone();
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
    ///
    /// Tras ejecutar un manejador la vista se marca para reconstruirse, aunque
    /// lance una excepción: el estado puede haber cambiado a medias.
    pub fn dispatch(&mut self, key: &str, event: &str, arg: Option<Py<PyAny>>) -> PyResult<bool> {
        let Some(cb) = self
            .tree
            .as_ref()
            .and_then(|tree| find(tree, key))
            .and_then(|node| node.handler(event))
        else {
            return Ok(false);
        };
        let result = Python::attach(|py| match arg {
            Some(arg) => cb.call1(py, (arg,)),
            None => cb.call0(py),
        });
        self.dirty = true;
        result.map(|_| true)
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
