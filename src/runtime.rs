//! Estado de una app en ejecución, independiente de la ventana: árbol de la
//! vista, regiones de hit-testing, puntero y despacho de eventos.
//!
//! Lo comparten el bucle de winit (`window.rs`) y el piloto headless
//! (`pilot.rs`), así que lo que se prueba sin pantalla es exactamente lo que
//! ocurre con una ventana abierta.

use std::sync::atomic::{AtomicBool, Ordering};

use pyo3::prelude::*;
use skia_safe::{Canvas, Rect};

use crate::render::{Engine, HitRegion, hit_test};
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

    /// Devuelve `true` si cambió el nodo bajo el puntero.
    pub fn pointer_move(&mut self, x: f32, y: f32) -> bool {
        self.pointer = Some((x, y));
        self.refresh_hover()
    }

    pub fn pointer_leave(&mut self) {
        self.pointer = None;
        self.engine.hovered = None;
    }

    pub fn pointer_down(&mut self) {
        self.engine.pressed = self.engine.hovered.clone();
    }

    /// Un clic se completa si se suelta sobre el mismo nodo que se pulsó.
    pub fn pointer_up(&mut self) -> PyResult<()> {
        if let Some(key) = self.engine.pressed.take()
            && self.engine.hovered.as_deref() == Some(key.as_str())
        {
            self.dispatch(&key, "click", None)?;
        }
        Ok(())
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
