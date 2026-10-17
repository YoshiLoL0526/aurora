//! Estado de una app en ejecución, independiente de la ventana: árbol de la
//! vista, regiones de hit-testing, puntero, foco, teclado y despacho de eventos.
//!
//! Lo comparten el bucle de winit (`window.rs`) y el piloto headless
//! (`pilot.rs`), así que lo que se prueba sin pantalla es exactamente lo que
//! ocurre con una ventana abierta. El código se reparte por dominio de
//! entrada: `pointer`, `keyboard`, `editing`, `focus`, `wheel` y `clipboard`.

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use pyo3::types::{PyDict, PyString};

use pyo3::prelude::*;
use skia_safe::{Canvas, Point, Rect};

use crate::canvas::Canvases;
use crate::chart::Charts;
use crate::input::InputState;
use crate::inspect::{self, Inspector, PANEL_KEY};
use crate::keys::{KeyEvent, KeyInput, Mods};
use crate::render::{Engine, Mark, TIP_DELAY, ancestors, hit_test, topmost};
use crate::scroll::{LINE, ScrollEvent};
use crate::spec::{self, Node};

pub use crate::spec::Cursor as CursorKind;

mod clipboard;
mod editing;
mod focus;
mod keyboard;
mod pointer;
mod wheel;

pub use self::clipboard::Clipboard;
pub use self::pointer::DragEvent;

use self::pointer::{Drag, Grip, Pan};

/// Lo activa `wake()` desde cualquier hilo; el siguiente frame lo consume y
/// reconstruye la vista.
static WAKE_PENDING: AtomicBool = AtomicBool::new(false);

/// Marca la vista como desactualizada y despierta el bucle de eventos si hay
/// uno en marcha. Seguro desde cualquier hilo; sin bucle no hace nada más.
pub fn wake() {
    WAKE_PENDING.store(true, Ordering::Release);
    crate::window::notify();
}

/// Cuánto costó cada fase del último frame. Base de la suite de benchmarks
/// (`benchmarks/`): `build`, `parse` y `style` valen cero si el frame no
/// reconstruyó la vista.
#[derive(Clone, Copy, Debug, Default)]
pub struct FrameStats {
    /// Llamada a Python: `view()` + serialización (`Element.to_spec`).
    pub build: Duration,
    /// Dicts de Python → `Node` (`spec::parse`).
    pub parse: Duration,
    /// Fase de estilo: comparar el árbol nuevo con el anterior (`Engine::restyle`).
    pub style: Duration,
    /// Layout y geometría (regiones, capas y tinta).
    pub layout: Duration,
    /// El layout se reutilizó del frame anterior (no cambió nada que lo afecte).
    pub layout_cached: bool,
    /// Llamadas a las funciones `draw` de los `canvas` y grabación de sus comandos.
    pub draw: Duration,
    /// Composición y pintura (el resto del frame, sin el layout ni la reconstrucción).
    pub paint: Duration,
    /// Zona repintada (píxeles lógicos), o `None` si no se pintó nada.
    pub damage: Option<Rect>,
    /// Nodos del árbol actual.
    pub nodes: usize,
    pub rebuilt: bool,
}

impl FrameStats {
    /// Tiempo de CPU del frame en Aurora: la suma de todas las fases.
    pub fn total(&self) -> Duration {
        self.build + self.parse + self.style + self.layout + self.draw + self.paint
    }

    /// Las fases en milisegundos, como las ve Python (`Pilot.stats`, inspector).
    pub fn to_dict<'py>(self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let ms = |d: Duration| d.as_secs_f64() * 1000.0;
        let out = PyDict::new(py);
        out.set_item("total", ms(self.total()))?;
        out.set_item("build", ms(self.build))?;
        out.set_item("parse", ms(self.parse))?;
        out.set_item("style", ms(self.style))?;
        out.set_item("layout", ms(self.layout))?;
        out.set_item("draw", ms(self.draw))?;
        out.set_item("paint", ms(self.paint))?;
        out.set_item("nodes", self.nodes)?;
        out.set_item("rebuilt", self.rebuilt)?;
        out.set_item("layout_cached", self.layout_cached)?;
        out.set_item(
            "damage",
            self.damage.map(|r| (r.left, r.top, r.width(), r.height())),
        )?;
        Ok(out)
    }
}

/// Frames de los que se recuerda la zona pintada: un lienzo que contiene un
/// frame más antiguo se repinta entero.
const DAMAGE_HISTORY: usize = 4;

pub struct Runtime {
    build: Py<PyAny>,
    pub engine: Engine,
    tree: Option<Node>,
    dirty: bool,
    /// Última posición conocida del puntero (píxeles lógicos).
    pointer: Option<(f32, f32)>,
    /// Arrastre en curso del pulgar de una barra de desplazamiento.
    drag: Option<Drag>,
    /// Arrastre en curso de la ventana de un `chart` (zoom y pan).
    pan: Option<Pan>,
    /// Arrastre en curso de un nodo con `on_drag`.
    grip: Option<Grip>,
    /// Nodo pulsado con Espacio, que se activa al soltar la tecla.
    space_pressed: Option<String>,
    /// Nodos con `autofocus` de la vista anterior: solo toma el foco el que aparece.
    autofocus_seen: HashSet<String>,
    /// Desplazar los `scroll` para mostrar el nodo enfocado tras el próximo frame.
    reveal_focus: bool,
    /// Modificadores pulsados (para Mayús+clic).
    pub mods: Mods,
    /// Campo en el que se está seleccionando con el ratón.
    selecting: Option<String>,
    /// Último clic (momento, punto y número de clics seguidos) para dobles y triples clics.
    last_click: Option<(Instant, Point, u8)>,
    /// El puntero está sobre un `chart` con zoom (para el cursor de agarrar).
    zoom_hover: bool,
    clipboard: Clipboard,
    /// Último texto escrito con el teclado, para no duplicarlo si el IME lo confirma también.
    last_typed: Option<(String, Instant)>,
    pub stats: FrameStats,
    /// Recuerda los nodos de los `@component` entre reconstrucciones.
    parser: spec::Parser,
    /// Contenedores `scroll` con `on_scroll` en el árbol actual.
    scroll_listeners: Vec<String>,
    /// Último evento entregado a cada uno: solo se avisa cuando cambia.
    scroll_seen: HashMap<String, ScrollEvent>,
    /// Zona pintada en cada uno de los últimos frames, del más reciente al más
    /// antiguo (`None`: nada). Con ella se pone al día un lienzo que se quedó
    /// unos frames atrás (ventanas con varios buffers).
    history: VecDeque<Option<Rect>>,
    /// Cuándo volver a grabar cada `canvas`.
    canvases: Canvases,
    /// Cuándo volver a grabar cada `chart`.
    charts: Charts,
    /// Inspector del árbol y profiler de frames.
    pub inspector: Inspector,
}

impl Runtime {
    pub fn new(build: Py<PyAny>, clipboard: Clipboard, inspector: bool) -> Self {
        Self {
            build,
            engine: Engine::new(),
            tree: None,
            dirty: true,
            pointer: None,
            drag: None,
            pan: None,
            grip: None,
            space_pressed: None,
            autofocus_seen: HashSet::new(),
            reveal_focus: false,
            mods: Mods::default(),
            selecting: None,
            last_click: None,
            zoom_hover: false,
            clipboard,
            last_typed: None,
            stats: FrameStats::default(),
            parser: spec::Parser::default(),
            scroll_listeners: Vec::new(),
            scroll_seen: HashMap::new(),
            history: VecDeque::new(),
            canvases: Canvases::default(),
            charts: Charts::default(),
            inspector: Inspector::new(inspector),
        }
    }

    pub fn has_tree(&self) -> bool {
        self.tree.is_some()
    }

    /// Si la vista tiene que reconstruirse (un manejador cambió estado).
    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    /// Si el próximo `sync` reconstruirá la vista (un manejador o un `Signal` la invalidó).
    pub fn needs_sync(&self) -> bool {
        self.dirty || WAKE_PENDING.load(Ordering::Acquire)
    }

    /// Pinta el frame. Entre la composición (que fija el desplazamiento y los
    /// límites de cada `scroll`) y la pintura avisa a los `on_scroll`: si un
    /// aviso invalida la vista (una lista virtual que cambia de rango visible),
    /// la reconstruye antes de pintar, una sola vez. Las filas nuevas aparecen
    /// sin un frame de retraso y el frame se pinta una sola vez.
    ///
    /// `age`: hace cuántos frames se pintó lo que contiene el lienzo (como la
    /// edad del buffer en softbuffer): 1 si es el último, 0 si no se sabe.
    /// Devuelve si cambió lo que hay bajo el puntero y la zona pintada.
    pub fn draw_frame(
        &mut self,
        canvas: &Canvas,
        width: f32,
        height: f32,
        scale: f32,
        age: u8,
    ) -> PyResult<(bool, Option<Rect>)> {
        let start = Instant::now();
        self.stats.layout = Duration::ZERO;
        self.stats.layout_cached = true;
        self.stats.draw = Duration::ZERO;
        self.update(width, height, scale);
        if let Some((key, top, bottom)) = self.inspector.reveal.take()
            && let Some(state) = self.engine.scroll.get_mut(&key)
        {
            state.reveal_content(top, bottom, 0.0);
        }
        let mut rebuild = Duration::ZERO;
        if self.notify_scroll()? && self.needs_sync() {
            let t = Instant::now();
            self.sync()?;
            rebuild = t.elapsed();
            self.update(width, height, scale);
            self.notify_scroll()?;
        }
        // Con el layout hecho se conoce el tamaño de cada `canvas` y cada `chart`.
        if let Some(tree) = &self.tree {
            let t = Instant::now();
            self.canvases
                .draw(tree, &mut self.engine, !self.stats.layout_cached)?;
            self.charts
                .draw(tree, &mut self.engine, !self.stats.layout_cached)?;
            self.stats.draw = t.elapsed();
        }
        // Lo que se pintó en los frames que este lienzo no vio también hay que pintarlo.
        let stale = match age as usize {
            1 => None,
            n if n == 0 || n > self.history.len() + 1 => Some(Rect::from_wh(width, height)),
            n => self
                .history
                .iter()
                .take(n - 1)
                .fold(None, |acc, d| join(acc, *d)),
        };
        self.engine.marks = self.marks();
        let damage = match &self.tree {
            Some(tree) => self.engine.paint(canvas, tree, width, height, stale),
            None => None,
        };
        self.stats.paint = start
            .elapsed()
            .saturating_sub(self.stats.layout + rebuild + self.stats.draw);
        self.stats.damage = damage;
        if self.inspector.enabled {
            self.inspector.record(self.stats);
        }
        self.history.push_front(damage);
        self.history.truncate(DAMAGE_HISTORY);
        // Tras una reconstrucción, lo que hay bajo el puntero puede haber cambiado
        // aunque el puntero no se mueva.
        let revealed = std::mem::take(&mut self.reveal_focus) && self.reveal_focused();
        Ok((self.refresh_hover() || revealed, damage))
    }

    /// Reconstruye la vista si algo la invalidó. Si la vista falla, se
    /// conserva el árbol anterior y se devuelve el error.
    pub fn sync(&mut self) -> PyResult<()> {
        if WAKE_PENDING.swap(false, Ordering::AcqRel) {
            self.dirty = true;
        }
        self.stats.build = Duration::ZERO;
        self.stats.parse = Duration::ZERO;
        self.stats.style = Duration::ZERO;
        self.stats.rebuilt = false;
        // Refresco periódico del panel: reconstruye aunque nada haya cambiado.
        if self.inspector.take_refresh() && self.dirty {
            self.inspector.cancel_refresh();
        }
        if !self.dirty && !self.inspector.refreshing() && self.tree.is_some() {
            return Ok(());
        }
        self.dirty = false;
        let selected_rect = self.inspector.selected.as_ref().and_then(|k| self.rect(k));
        self.inspector.selected_rect = selected_rect;
        let (build_fn, parser) = (&self.build, &mut self.parser);
        let (tree, build, parse) = inspect::lend(&mut self.inspector, || {
            Python::attach(|py| -> PyResult<_> {
                let start = Instant::now();
                let obj = build_fn.call0(py)?;
                let built = Instant::now();
                let tree = parser.parse(obj.bind(py))?;
                Ok((tree, built - start, built.elapsed()))
            })
        })?;
        self.stats.build = build;
        self.stats.parse = parse;
        self.stats.rebuilt = true;
        self.stats.nodes = tree.count();
        self.canvases.rebuilt();
        self.charts.rebuilt();

        // El foco se pierde si su nodo desaparece o deja de ser enfocable.
        if let Some(focused) = &self.engine.focused
            && tree.find(focused).is_none_or(|n| !n.is_focusable())
        {
            self.engine.focused = None;
        }
        let mut autofocus = Vec::new();
        collect_autofocus(&tree, &mut autofocus);
        self.scroll_listeners.clear();
        collect_scroll_listeners(&tree, &mut self.scroll_listeners);
        let appeared = autofocus
            .iter()
            .rev()
            .find(|k| !self.autofocus_seen.contains(*k))
            .cloned();
        self.engine.load_images(&tree)?;
        self.autofocus_seen = autofocus.into_iter().collect();
        self.engine.sync_inputs(&tree);
        let start = Instant::now();
        self.engine.restyle(self.tree.as_ref(), &tree);
        self.stats.style = start.elapsed();
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

    /// Si hay animaciones declarativas en curso. Las de layout y entrada
    /// empiezan al pintar (tras el layout), después de `tick`.
    pub fn animating(&self) -> bool {
        self.engine.animating()
    }

    /// Avanza el reloj real (parpadeo del cursor), independiente de las transiciones.
    pub fn advance_clock(&mut self, elapsed: f32) {
        self.inspector.advance(elapsed);
        if let Some(state) = self.focused_input() {
            state.blink += elapsed;
        }
        if self.engine.tip.key.is_some() {
            self.engine.tip.timer += elapsed;
        }
    }

    /// Layout y composición del árbol actual (ver `Engine::update`).
    fn update(&mut self, width: f32, height: f32, scale: f32) {
        if let Some(tree) = &self.tree {
            self.engine.update(tree, width, height, scale);
            self.stats.layout += self.engine.layout_time;
            self.stats.layout_cached &= self.engine.layout_cached;
        }
    }
}

impl Runtime {
    /// Segundos hasta el próximo parpadeo del cursor, si hay un campo enfocado.
    /// Segundos hasta el próximo cambio programado (parpadeo del cursor o
    /// aparición de un tooltip), para que el bucle duerma hasta entonces.
    pub fn next_wakeup(&self) -> Option<f32> {
        let blink = self
            .engine
            .focused
            .as_ref()
            .and_then(|key| self.engine.inputs.get(key))
            .map(InputState::until_blink);
        let tip = &self.engine.tip;
        let tooltip = (tip.key.is_some() && !tip.suppressed && tip.timer < TIP_DELAY)
            .then_some(TIP_DELAY - tip.timer);
        [blink, tooltip, self.inspector.next_refresh()]
            .into_iter()
            .flatten()
            .reduce(f32::min)
    }

    /// Texto del tooltip visible, si hay uno.
    pub fn tooltip(&self) -> Option<String> {
        let tip = &self.engine.tip;
        if !tip.ready() {
            return None;
        }
        let key = tip.key.as_ref()?;
        self.tree.as_ref()?.find(key)?.style.tooltip.clone()
    }
}

impl Runtime {
    /// Llama al manejador `event` del nodo `key`, con `arg` como único
    /// argumento si se indica. Devuelve `false` si el nodo no lo tiene.
    pub fn dispatch(&mut self, key: &str, event: &str, arg: Option<Py<PyAny>>) -> PyResult<bool> {
        self.call(key, event, arg).map(|ret| ret.is_some())
    }

    /// Como `dispatch`, pero devuelve lo que devolvió el manejador (`None` si no hay).
    ///
    /// Tras ejecutar un manejador la vista se marca para reconstruirse, aunque
    /// lance una excepción: el estado puede haber cambiado a medias.
    pub(super) fn call(
        &mut self,
        key: &str,
        event: &str,
        arg: Option<Py<PyAny>>,
    ) -> PyResult<Option<Py<PyAny>>> {
        let Some(cb) = self
            .tree
            .as_ref()
            .and_then(|tree| tree.find(key))
            .and_then(|node| node.handler(event))
        else {
            return Ok(None);
        };
        let result = inspect::lend(&mut self.inspector, || {
            Python::attach(|py| match arg {
                Some(arg) => cb.call1(py, (arg,)),
                None => cb.call0(py),
            })
        });
        self.dirty = true;
        result.map(Some)
    }

    /// Llama a los `on_scroll` cuyo desplazamiento o tamaño visible cambió en el
    /// último frame. Se llama después de pintar, cuando ya se conocen los límites.
    ///
    /// A diferencia de los demás manejadores, no marca la vista como sucia: se
    /// llama en cada frame de desplazamiento, y quien necesite reconstruir (una
    /// lista virtual que cambia de rango visible) cambia un `Signal`, que ya
    /// despierta el bucle. Devuelve `true` si llamó a alguno.
    pub fn notify_scroll(&mut self) -> PyResult<bool> {
        let Some(tree) = &self.tree else {
            return Ok(false);
        };
        self.scroll_seen
            .retain(|k, _| self.scroll_listeners.contains(k));
        let mut pending = Vec::new();
        for key in &self.scroll_listeners {
            let Some(state) = self.engine.scroll.get(key) else {
                continue;
            };
            let event = state.event();
            if self.scroll_seen.get(key) != Some(&event) {
                pending.push((key.clone(), event));
            }
        }
        for (key, event) in &pending {
            self.scroll_seen.insert(key.clone(), *event);
            if let Some(cb) = tree.find(key).and_then(|n| n.handler("scroll")) {
                Python::attach(|py| cb.call1(py, (Py::new(py, *event)?,)).map(drop))?;
            }
        }
        Ok(!pending.is_empty())
    }

    /// Rectángulo absoluto (píxeles lógicos) con el que se pintó `key` en el último frame.
    pub fn rect(&self, key: &str) -> Option<Rect> {
        self.engine
            .regions
            .iter()
            .rev()
            .find(|r| r.key == key)
            .map(|r| r.rect)
    }
}

/// Une dos zonas pintadas.
fn join(a: Option<Rect>, b: Option<Rect>) -> Option<Rect> {
    match (a, b) {
        (Some(a), Some(b)) => Some(Rect::new(
            a.left.min(b.left),
            a.top.min(b.top),
            a.right.max(b.right),
            a.bottom.max(b.bottom),
        )),
        (a, b) => a.or(b),
    }
}

fn collect_scroll_listeners(node: &Node, out: &mut Vec<String>) {
    if node.style.scroll.is_some() && node.handler("scroll").is_some() {
        out.push(node.key.clone());
    }
    for child in &node.children {
        collect_scroll_listeners(child, out);
    }
}

fn collect_autofocus(node: &Node, out: &mut Vec<String>) {
    if node.style.autofocus && node.is_focusable() {
        out.push(node.key.clone());
    }
    for child in &node.children {
        collect_autofocus(child, out);
    }
}
