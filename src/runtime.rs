//! Estado de una app en ejecución, independiente de la ventana: árbol de la
//! vista, regiones de hit-testing, puntero, foco, teclado y despacho de eventos.
//!
//! Lo comparten el bucle de winit (`window.rs`) y el piloto headless
//! (`pilot.rs`), así que lo que se prueba sin pantalla es exactamente lo que
//! ocurre con una ventana abierta.

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Duration, Instant};

use pyo3::types::PyString;

use pyo3::prelude::*;
use skia_safe::{Canvas, Point, Rect};

use crate::canvas::Canvases;
use crate::input::InputState;
use crate::keys::{KeyEvent, KeyInput, Mods};
use crate::render::{Engine, TIP_DELAY, ancestors, hit_test, topmost};
use crate::scroll::{LINE, ScrollEvent};
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
}

/// Qué cursor del ratón corresponde a lo que hay bajo el puntero.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CursorKind {
    Default,
    Pointer,
    Text,
}

/// Portapapeles del sistema (ventana) o en memoria (piloto, tests deterministas).
pub enum Clipboard {
    System(Option<arboard::Clipboard>),
    Memory(String),
}

impl Clipboard {
    pub fn get(&mut self) -> Option<String> {
        match self {
            Clipboard::System(slot) => system(slot)?.get_text().ok(),
            Clipboard::Memory(text) => Some(text.clone()),
        }
    }

    pub fn set(&mut self, text: String) {
        match self {
            Clipboard::System(slot) => {
                if let Some(cb) = system(slot) {
                    let _ = cb.set_text(text);
                }
            }
            Clipboard::Memory(slot) => *slot = text,
        }
    }
}

/// El portapapeles del sistema se abre una vez y se conserva: en X11 su
/// contenido vive mientras viva el objeto.
fn system(slot: &mut Option<arboard::Clipboard>) -> Option<&mut arboard::Clipboard> {
    if slot.is_none() {
        *slot = arboard::Clipboard::new().ok();
    }
    slot.as_mut()
}

/// Dos clics más cerca que esto (en tiempo y distancia) cuentan como doble clic.
const MULTI_CLICK: Duration = Duration::from_millis(400);
const MULTI_CLICK_DISTANCE: f32 = 4.0;

struct Drag {
    key: String,
    vertical: bool,
    /// Distancia entre el puntero y el inicio del pulgar al agarrarlo.
    grab: f32,
}

impl Runtime {
    pub fn new(build: Py<PyAny>, clipboard: Clipboard) -> Self {
        Self {
            build,
            engine: Engine::new(),
            tree: None,
            dirty: true,
            pointer: None,
            drag: None,
            space_pressed: None,
            autofocus_seen: HashSet::new(),
            reveal_focus: false,
            mods: Mods::default(),
            selecting: None,
            last_click: None,
            clipboard,
            last_typed: None,
            stats: FrameStats::default(),
            parser: spec::Parser::default(),
            scroll_listeners: Vec::new(),
            scroll_seen: HashMap::new(),
            history: VecDeque::new(),
            canvases: Canvases::default(),
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
        let mut rebuild = Duration::ZERO;
        if self.notify_scroll()? && self.needs_sync() {
            let t = Instant::now();
            self.sync()?;
            rebuild = t.elapsed();
            self.update(width, height, scale);
            self.notify_scroll()?;
        }
        // Con el layout hecho se conoce el tamaño de cada `canvas`.
        if let Some(tree) = &self.tree {
            let t = Instant::now();
            self.canvases
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
        let damage = match &self.tree {
            Some(tree) => self.engine.paint(canvas, tree, width, height, stale),
            None => None,
        };
        self.stats.paint = start
            .elapsed()
            .saturating_sub(self.stats.layout + rebuild + self.stats.draw);
        self.stats.damage = damage;
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
        if !self.dirty && self.tree.is_some() {
            return Ok(());
        }
        self.dirty = false;
        let (tree, build, parse) = Python::attach(|py| -> PyResult<_> {
            let start = Instant::now();
            let obj = self.build.call0(py)?;
            let built = Instant::now();
            let tree = self.parser.parse(obj.bind(py))?;
            Ok((tree, built - start, built.elapsed()))
        })?;
        self.stats.build = build;
        self.stats.parse = parse;
        self.stats.rebuilt = true;
        self.stats.nodes = tree.count();
        self.canvases.rebuilt();

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

    /// Avanza el reloj real (parpadeo del cursor), independiente de las transiciones.
    pub fn advance_clock(&mut self, elapsed: f32) {
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

    // ---------------------------------------------------------------- puntero

    pub fn hovered(&self) -> Option<&str> {
        self.engine.hovered.as_deref()
    }

    /// Devuelve `true` si hace falta pintar otro frame.
    pub fn pointer_move(&mut self, x: f32, y: f32) -> bool {
        self.pointer = Some((x, y));
        if let Some(key) = &self.selecting
            && let Some(state) = self.engine.inputs.get_mut(key)
        {
            if let Some(pos) = state.position_at(Point::new(x, y)) {
                state.editor.move_to(pos, true);
                state.blink = 0.0;
            }
            return true;
        }
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
        self.engine.tip.set_key(None);
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
        self.engine.tip.suppressed = true;
        self.engine.focus_visible = false;
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

    /// Clic en un campo: coloca el cursor (Mayús amplía la selección); doble
    /// clic selecciona la palabra y triple clic todo el texto.
    fn place_cursor(&mut self, key: String, at: Point) {
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
        if self.selecting.is_some() {
            return CursorKind::Text;
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
    fn focus_next(&mut self, back: bool) -> PyResult<()> {
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
    fn reveal_focused(&mut self) -> bool {
        let Some(idx) = self
            .engine
            .focused
            .as_ref()
            .and_then(|f| self.engine.regions.iter().rposition(|r| &r.key == f))
        else {
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
        self.engine.tip.suppressed = true;
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

    // -------------------------------------------------------- campos de texto

    /// Edición en el campo enfocado. Devuelve `true` si la tecla era suya.
    fn edit_key(&mut self, input: &KeyInput) -> PyResult<bool> {
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
            "Home" if multiline && !m.ctrl => line_edge(state, false, shift),
            "End" if multiline && !m.ctrl => line_edge(state, true, shift),
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
    fn after_edit(&mut self, key: &str, before: &str, submit: bool) -> PyResult<()> {
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

    fn focused_input(&mut self) -> Option<&mut InputState> {
        let key = self.engine.focused.as_ref()?;
        self.engine.inputs.get_mut(key)
    }

    /// Cursor del campo enfocado (para colocar la ventana del IME).
    pub fn ime_area(&self) -> Option<Rect> {
        let key = self.engine.focused.as_ref()?;
        self.engine.inputs.get(key)?.caret()
    }

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
        match (blink, tooltip) {
            (Some(a), Some(b)) => Some(a.min(b)),
            (a, b) => a.or(b),
        }
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

    /// Selección del campo `key` en caracteres (no bytes): `(inicio, fin)`.
    pub fn selection(&self, key: &str) -> Option<(usize, usize)> {
        let editor = &self.engine.inputs.get(key)?.editor;
        let chars = |b: usize| editor.text()[..b].chars().count();
        let r = editor.selection();
        Some((chars(r.start), chars(r.end)))
    }

    pub fn clipboard(&mut self) -> &mut Clipboard {
        &mut self.clipboard
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
        let idx = topmost(&self.engine.regions, x, y);
        let keys: Vec<String> = ancestors(&self.engine.regions, idx)
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
        ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
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
            .and_then(|(x, y)| hit_test(&self.engine.regions, x, y));
        let changed = hovered != self.engine.hovered;
        self.engine.hovered = hovered;
        let tip = self.pointer.and_then(|(x, y)| {
            ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
                .find(|r| r.tooltip)
                .map(|r| r.key.clone())
        });
        self.engine.tip.set_key(tip) || changed
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
            .and_then(|tree| tree.find(key))
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
