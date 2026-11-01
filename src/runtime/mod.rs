//! Estado de una app en ejecución, independiente de la ventana: árbol de la
//! vista, regiones de hit-testing, puntero, foco, teclado y despacho de eventos.
//!
//! Lo comparten el bucle de winit (`window.rs`) y el piloto headless
//! (`pilot.rs`), así que lo que se prueba sin pantalla es exactamente lo que
//! ocurre con una ventana abierta. El código se reparte por dominio de
//! entrada: `pointer`, `keyboard`, `editing`, `focus`, `wheel` y `clipboard`.

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
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
use crate::spec::{self, Marks, Node};

pub use crate::spec::Cursor as CursorKind;

mod a11y;
mod chrome;
mod clipboard;
mod editing;
mod files;
mod focus;
mod keyboard;
mod pointer;
mod wheel;

pub use self::chrome::WindowRequest;
pub use self::clipboard::Clipboard;
pub use self::pointer::DragEvent;

use self::pointer::{Drag, Grip, Pan};

/// Sube con cada `wake()`. Cada `Runtime` recuerda la última que atendió: una
/// marca global (y no una bandera) deja que varias ventanas compartan el mismo
/// `wake()` sin que la primera que reconstruya la consuma para las demás.
static WAKE_EPOCH: AtomicU64 = AtomicU64::new(0);

/// Marca la vista como desactualizada y despierta el bucle de eventos si hay
/// uno en marcha. Seguro desde cualquier hilo; sin bucle no hace nada más.
pub fn wake() {
    WAKE_EPOCH.fetch_add(1, Ordering::Release);
    crate::window::notify();
}

/// Sube cada vez que el núcleo ejecuta código de usuario por un evento (un
/// manejador, una opción de menú, la bandeja, el cierre de una ventana…). Ese
/// código pudo cambiar estado normal de Python que lee la vista, así que la
/// siguiente reconstrucción de **cada** ventana es completa, no parcial
/// (`reactive.build_view`). Global por lo mismo que `WAKE_EPOCH`: un clic en
/// una ventana puede cambiar lo que lee otra.
static EVENT_EPOCH: AtomicU64 = AtomicU64::new(0);

/// Si la reconstrucción en curso puede ser parcial (la lee `build_partial`).
/// Solo vale `true` mientras `sync` llama a la vista; fuera (`render_png`,
/// una llamada directa) la reconstrucción es completa.
static BUILD_PARTIAL: AtomicBool = AtomicBool::new(false);

/// Si la reconstrucción en curso puede ser parcial (ver `EVENT_EPOCH`).
pub fn build_partial() -> bool {
    BUILD_PARTIAL.load(Ordering::Acquire)
}

/// Anota que se va a ejecutar código de usuario por un evento (ver `EVENT_EPOCH`).
pub fn user_event() {
    EVENT_EPOCH.fetch_add(1, Ordering::Release);
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
    /// Última época de `wake()` atendida por esta ventana.
    wake_seen: u64,
    /// La última `EVENT_EPOCH` que vio una reconstrucción.
    event_seen: u64,
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
    /// Último clic (momento en segundos de `clock`, punto, número de clics
    /// seguidos y lo que recibió la pulsación) para dobles y triples clics.
    last_click: Option<(f32, Point, u8, String)>,
    /// Reloj simulado (segundos) del piloto, que avanza con sus frames; `None`
    /// en una ventana real, que usa el tiempo del sistema (ver `clock`).
    pub virtual_clock: Option<f32>,
    /// Momento de creación: origen del reloj real.
    epoch: Instant,
    /// El puntero está sobre un `chart` con zoom (para el cursor de agarrar).
    zoom_hover: bool,
    /// Los bordes de la ventana la redimensionan (sin marco, redimensionable y
    /// sin maximizar): lo decide quien tiene la ventana.
    pub window_edges: bool,
    /// Tamaño de la vista en el último frame (píxeles lógicos), para los bordes.
    size: (f32, f32),
    /// Lo que pidió la última pulsación a la ventana (moverla, redimensionarla…).
    window_request: Option<WindowRequest>,
    /// Borde de la ventana bajo el puntero (para cambiar el cursor al entrar o salir).
    edge_hover: Option<crate::spec::Edge>,
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
    /// Nodos con `on_resize` en el árbol actual y el último tamaño que se les dio.
    resize_listeners: Vec<String>,
    resize_seen: HashMap<String, ResizeEvent>,
    /// Franja que cada `scroll` con `reveal` pide mostrar, y la última que se
    /// atendió: solo se desplaza cuando cambia (no pelea con la rueda).
    reveals: Vec<(String, (f32, f32))>,
    reveal_seen: HashMap<String, (f32, f32)>,
    /// Zona pintada en cada uno de los últimos frames, del más reciente al más
    /// antiguo (`None`: nada). Con ella se pone al día un lienzo que se quedó
    /// unos frames atrás (ventanas con varios buffers).
    history: VecDeque<Option<Rect>>,
    /// Cuándo volver a grabar cada `canvas`.
    canvases: Canvases,
    /// Cuándo volver a grabar cada `chart`.
    charts: Charts,
    /// Hay archivos del sistema arrastrándose sobre la ventana (`on_drop_hover`).
    files_hovering: bool,
    /// Inspector del árbol y profiler de frames.
    pub inspector: Inspector,
    /// Estado de accesibilidad: ids estables por key para el árbol nativo.
    pub a11y: crate::a11y::A11y,
}

impl Runtime {
    pub fn new(build: Py<PyAny>, clipboard: Clipboard, inspector: bool) -> Self {
        Self {
            build,
            engine: Engine::new(),
            tree: None,
            dirty: true,
            wake_seen: 0,
            event_seen: 0,
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
            virtual_clock: None,
            epoch: Instant::now(),
            zoom_hover: false,
            window_edges: false,
            size: (0.0, 0.0),
            window_request: None,
            edge_hover: None,
            clipboard,
            last_typed: None,
            stats: FrameStats::default(),
            parser: spec::Parser::default(),
            scroll_listeners: Vec::new(),
            scroll_seen: HashMap::new(),
            resize_listeners: Vec::new(),
            resize_seen: HashMap::new(),
            reveals: Vec::new(),
            reveal_seen: HashMap::new(),
            history: VecDeque::new(),
            canvases: Canvases::default(),
            charts: Charts::default(),
            files_hovering: false,
            inspector: Inspector::new(inspector),
            a11y: crate::a11y::A11y::default(),
        }
    }

    pub fn has_tree(&self) -> bool {
        self.tree.is_some()
    }

    /// El árbol del último frame, si ya se construyó.
    pub fn tree(&self) -> Option<&Node> {
        self.tree.as_ref()
    }

    /// Si la vista tiene que reconstruirse (un manejador cambió estado).
    pub fn is_dirty(&self) -> bool {
        self.dirty
    }

    /// Si el próximo `sync` reconstruirá la vista (un manejador o un `Signal` la invalidó).
    pub fn needs_sync(&self) -> bool {
        self.dirty || self.wake_seen != WAKE_EPOCH.load(Ordering::Acquire)
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
        self.size = (width, height);
        self.stats.layout = Duration::ZERO;
        self.stats.layout_cached = true;
        self.stats.draw = Duration::ZERO;
        self.update(width, height, scale);
        if let Some((key, top, bottom)) = self.inspector.reveal.take()
            && let Some(state) = self.engine.scroll.get_mut(&key)
        {
            state.reveal_content(top, bottom, 0.0);
        }
        self.apply_reveals();
        let mut rebuild = Duration::ZERO;
        if (self.notify_scroll()? | self.notify_resize()?) && self.needs_sync() {
            let t = Instant::now();
            self.sync()?;
            rebuild = t.elapsed();
            self.update(width, height, scale);
            self.notify_scroll()?;
            self.notify_resize()?;
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
        let epoch = WAKE_EPOCH.load(Ordering::Acquire);
        if epoch != self.wake_seen {
            self.wake_seen = epoch;
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
        // Parcial solo si desde la última reconstrucción no corrió código de
        // usuario por un evento: lo que cambió llegó solo por `Signal`.
        let events = EVENT_EPOCH.load(Ordering::Acquire);
        let partial = events == self.event_seen;
        self.event_seen = events;
        let (build_fn, parser) = (&self.build, &mut self.parser);
        let (tree, build, parse) = inspect::lend(&mut self.inspector, || {
            Python::attach(|py| -> PyResult<_> {
                let start = Instant::now();
                BUILD_PARTIAL.store(partial, Ordering::Release);
                let obj = build_fn.call0(py);
                BUILD_PARTIAL.store(false, Ordering::Release);
                let obj = obj?;
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

        // El foco se pierde si su nodo desaparece de la vista. Un nodo que sigue
        // ahí pero dejó de ser enfocable (o que enfocó un lector de pantalla)
        // conserva el foco: el anillo solo lo pinta el foco de teclado.
        if let Some(focused) = &self.engine.focused
            && tree.find(focused).is_none()
            && !has_link(&tree, focused)
        {
            self.engine.focused = None;
        }
        let mut autofocus = Vec::new();
        collect_autofocus(&tree, &mut autofocus);
        self.scroll_listeners.clear();
        self.resize_listeners.clear();
        self.reveals.clear();
        collect_listeners(
            &tree,
            &mut self.scroll_listeners,
            &mut self.resize_listeners,
            &mut self.reveals,
        );
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
        if let Some(t) = &mut self.virtual_clock {
            *t += elapsed;
        }
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
    /// Segundos desde que se creó el runtime: el reloj simulado en el piloto
    /// (los clics de un guion no dependen de lo rápido que se ejecute) y el
    /// real en una ventana (los eventos llegan entre frames, antes de que
    /// `advance_clock` se ponga al día).
    pub(super) fn clock(&self) -> f32 {
        self.virtual_clock
            .unwrap_or_else(|| self.epoch.elapsed().as_secs_f32())
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

    /// La descripción del menú contextual (`on_context_menu`) del primer
    /// ancestro bajo el puntero que la tenga, si la hay.
    pub fn context_menu(&self) -> Option<&Py<PyAny>> {
        let (x, y) = self.pointer?;
        let tree = self.tree.as_ref()?;
        ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
            .filter_map(|region| tree.find(&region.key))
            .find_map(|node| node.handler("context_menu"))
    }
}

impl Runtime {
    /// Árbol de accesibilidad completo del frame actual (ver `a11y::build`).
    /// Lo usan el adaptador de la ventana y el piloto.
    pub fn a11y_build(&mut self, width: f32, height: f32, scale: f32) -> crate::a11y::Built {
        let Self {
            tree,
            engine,
            a11y,
            charts,
            ..
        } = self;
        crate::a11y::build(a11y, tree.as_ref(), engine, charts, width, height, scale)
    }

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
        let Some(tree) = self.tree.as_ref() else {
            return Ok(None);
        };
        let mut arg = arg;
        let cb = match tree.find(key) {
            Some(node) => node.handler(event),
            // El clic en un enlace de un texto enriquecido es `on_link(número)` del texto.
            None => match spec::parse_link_key(key) {
                Some((owner, link)) if event == "click" => {
                    arg = Some(Python::attach(|py| {
                        link.into_pyobject(py).map(|n| n.into_any().unbind())
                    })?);
                    tree.find(owner).and_then(|node| node.handler("link"))
                }
                _ => None,
            },
        };
        let Some(cb) = cb else {
            return Ok(None);
        };
        user_event();
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
                user_event();
                Python::attach(|py| cb.call1(py, (Py::new(py, *event)?,)).map(drop))?;
            }
        }
        Ok(!pending.is_empty())
    }

    /// Llama a los `on_resize` cuyo nodo cambió de tamaño en el último layout
    /// (también la primera vez que se maqueta). Como `notify_scroll`, no marca
    /// la vista como sucia. Devuelve `true` si llamó a alguno.
    pub fn notify_resize(&mut self) -> PyResult<bool> {
        let Some(tree) = &self.tree else {
            return Ok(false);
        };
        if self.resize_listeners.is_empty() && self.resize_seen.is_empty() {
            return Ok(false);
        }
        self.resize_seen
            .retain(|k, _| self.resize_listeners.contains(k));
        let mut pending = Vec::new();
        for key in &self.resize_listeners {
            let Some(rect) = self.rect(key) else {
                continue;
            };
            let event = ResizeEvent {
                width: rect.width(),
                height: rect.height(),
            };
            if self.resize_seen.get(key) != Some(&event) {
                pending.push((key.clone(), event));
            }
        }
        for (key, event) in &pending {
            self.resize_seen.insert(key.clone(), *event);
            if let Some(cb) = tree.find(key).and_then(|n| n.handler("resize")) {
                user_event();
                Python::attach(|py| cb.call1(py, (Py::new(py, *event)?,)).map(drop))?;
            }
        }
        Ok(!pending.is_empty())
    }

    /// Desplaza los `scroll` cuyo `reveal` cambió hasta mostrar su franja. Se
    /// llama tras el layout, cuando el contenedor ya conoce su zona visible.
    fn apply_reveals(&mut self) {
        let alive = &self.reveals;
        self.reveal_seen
            .retain(|k, _| alive.iter().any(|(key, _)| key == k));
        for (key, band) in &self.reveals {
            if self.reveal_seen.get(key) == Some(band) {
                continue;
            }
            if let Some(state) = self.engine.scroll.get_mut(key) {
                state.reveal_content(band.0, band.1, 0.0);
                self.reveal_seen.insert(key.clone(), *band);
            }
        }
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

fn collect_listeners(
    node: &Node,
    scroll: &mut Vec<String>,
    resize: &mut Vec<String>,
    reveals: &mut Vec<(String, (f32, f32))>,
) {
    if !node.contains(Marks::LISTENERS) {
        return;
    }
    if node.style.scroll.is_some() && node.handler("scroll").is_some() {
        scroll.push(node.key.clone());
    }
    if node.style.scroll.is_some()
        && let Some(band) = node.style.reveal
    {
        reveals.push((node.key.clone(), band));
    }
    if node.handler("resize").is_some() {
        resize.push(node.key.clone());
    }
    for child in &node.children {
        collect_listeners(child, scroll, resize, reveals);
    }
}

/// Lo que recibe un manejador `on_resize`: el tamaño (caja de borde) con el
/// que se maquetó el nodo, en píxeles lógicos.
#[pyclass(frozen, get_all, module = "aurora._core", name = "ResizeEvent")]
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ResizeEvent {
    pub width: f32,
    pub height: f32,
}

#[pymethods]
impl ResizeEvent {
    fn __repr__(&self) -> String {
        format!("ResizeEvent(width={}, height={})", self.width, self.height)
    }
}

/// Si `key` es un enlace (`spec::link_key`) que sigue en el texto de su dueño.
fn has_link(tree: &Node, key: &str) -> bool {
    spec::parse_link_key(key).is_some_and(|(owner, link)| {
        tree.find(owner)
            .and_then(|node| node.style.spans.as_ref())
            .is_some_and(|spans| spans.list.iter().any(|s| s.link == Some(link)))
    })
}

fn collect_autofocus(node: &Node, out: &mut Vec<String>) {
    if !node.contains(Marks::AUTOFOCUS) {
        return;
    }
    if node.style.autofocus && node.is_focusable() {
        out.push(node.key.clone());
    }
    for child in &node.children {
        collect_autofocus(child, out);
    }
}
