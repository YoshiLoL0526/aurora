//! Bucle de ventana (winit). El bucle corre SIN el GIL: Python solo se toma
//! al reconstruir el árbol o al despachar un callback. El estado de cada
//! ventana —su `Runtime`, su superficie y sus modificadores— vive en `View`;
//! aquí solo se traducen los eventos de winit y se presenta el frame.
//!
//! Una app puede tener varias ventanas (un `View` por `WindowId`): el bucle es
//! único y `wake()` despierta a todas. Python pide abrir, cerrar o cambiar una
//! ventana con los comandos de `UserEvent`, que es seguro enviar desde
//! cualquier hilo; la configuración viaja por `PENDING`.

use std::cell::RefCell;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use skia_safe::Point;
use tray_icon::menu::MenuEvent;
use tray_icon::{MouseButton as TrayButton, MouseButtonState, TrayIconEvent};
use winit::application::ApplicationHandler;
use winit::dpi::{LogicalPosition, LogicalSize};
use winit::event::{
    ElementState, Ime, KeyEvent, MouseButton, MouseScrollDelta, StartCause, WindowEvent,
};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::keyboard::Key;
use winit::window::{CursorIcon, Window, WindowId};

use crate::keys::{KeyInput, Mods};
use crate::runtime::{Clipboard, CursorKind, Runtime};
use crate::scroll::LINE;
use crate::surface::{self, Backend, Surface};

/// Evento propio del bucle: `wake()` desde otro hilo, un comando de Python, o
/// un evento de la bandeja o de sus menús.
#[derive(Debug)]
pub enum UserEvent {
    /// Alguien llamó a `wake()`: reconstruir las vistas que lo necesiten.
    Wake,
    /// Pedido desde Python (quizá desde otro hilo).
    Command(Command),
    /// Clic en la bandeja del sistema.
    Tray(TrayIconEvent),
    /// Opción elegida en el menú de la bandeja.
    Menu(MenuEvent),
    /// Un lector de pantalla (AccessKit) pide el árbol o una acción, o se va.
    Access(accesskit_winit::Event),
}

impl From<accesskit_winit::Event> for UserEvent {
    fn from(event: accesskit_winit::Event) -> Self {
        UserEvent::Access(event)
    }
}

/// Lo que Python puede pedir al bucle.
#[derive(Debug)]
pub enum Command {
    /// Abre la ventana con esa id (su configuración espera en `PENDING`).
    Open(u64),
    /// Cierra la ventana con esa id.
    Close(u64),
    /// Cambia el título de una ventana abierta.
    SetTitle(u64, String),
    /// Cambia el tamaño (píxeles lógicos) de una ventana abierta.
    SetSize(u64, f64, f64),
    /// Pone (o reemplaza) la bandeja con su configuración pendiente.
    TrayShow,
    /// Quita la bandeja.
    TrayHide,
    /// Muestra una notificación del sistema.
    Notify(crate::notify::Notify),
    /// Termina la app: cierra todas las ventanas y el bucle.
    Quit,
}

/// Proxy del bucle en marcha (si lo hay), para despertarlo desde cualquier hilo.
static PROXY: Mutex<Option<EventLoopProxy<UserEvent>>> = Mutex::new(None);

/// Despierta el bucle de eventos para que pinte un frame. Sin bucle, no hace nada.
pub fn notify() {
    if let Ok(proxy) = PROXY.lock()
        && let Some(proxy) = proxy.as_ref()
    {
        // Solo falla si el bucle ya terminó: no queda nada que despertar.
        let _ = proxy.send_event(UserEvent::Wake);
    }
}

/// Envía un comando al bucle, si hay uno en marcha.
pub(crate) fn send(command: Command) {
    if let Ok(proxy) = PROXY.lock()
        && let Some(proxy) = proxy.as_ref()
    {
        let _ = proxy.send_event(UserEvent::Command(command));
    }
}

/// Si hay un bucle de eventos en marcha.
pub fn running() -> bool {
    PROXY.lock().map(|proxy| proxy.is_some()).unwrap_or(false)
}

fn set_proxy(proxy: Option<EventLoopProxy<UserEvent>>) {
    if let Ok(mut slot) = PROXY.lock() {
        *slot = proxy;
    }
}

thread_local! {
    /// Pila de ventanas cuyo `Runtime` está ejecutando Python (construyendo la
    /// vista o corriendo un manejador). La última es la ventana «en curso».
    static CURRENT: RefCell<Vec<Arc<Window>>> = const { RefCell::new(Vec::new()) };
}

/// La ventana en cuyo contexto corre Python ahora mismo, si hay alguna. La
/// usan los diálogos nativos como padre (modal).
pub fn current() -> Option<Arc<Window>> {
    CURRENT.with(|c| c.borrow().last().cloned())
}

/// Ejecuta `f` con `window` como ventana en curso (se restaura al salir).
fn with_current<R>(window: &Arc<Window>, f: impl FnOnce() -> R) -> R {
    struct Pop;
    impl Drop for Pop {
        fn drop(&mut self) {
            CURRENT.with(|c| {
                c.borrow_mut().pop();
            });
        }
    }
    CURRENT.with(|c| c.borrow_mut().push(window.clone()));
    let _pop = Pop;
    f()
}

/// Configuración de una ventana que aún no existe (llega desde Python).
pub struct WindowConfig {
    build: Py<PyAny>,
    title: String,
    width: f64,
    height: f64,
    resizable: bool,
    /// `on_close` del usuario: con un valor falso, la ventana no se cierra.
    on_close: Option<Py<PyAny>>,
    /// Aviso a Python (por id) cuando la ventana se cerró de verdad.
    on_closed: Option<Py<PyAny>>,
}

/// Ventanas pedidas desde Python y aún sin crear. Se vacía al abrir y al
/// terminar la app.
static PENDING: Mutex<Vec<(u64, WindowConfig)>> = Mutex::new(Vec::new());

fn take_pending(id: u64) -> Option<WindowConfig> {
    let mut pending = PENDING.lock().ok()?;
    let index = pending.iter().position(|(key, _)| *key == id)?;
    Some(pending.remove(index).1)
}

fn clear_pending() {
    if let Ok(mut pending) = PENDING.lock() {
        pending.clear();
    }
}

/// Abre una ventana nueva. Seguro desde cualquier hilo; si la app ya arrancó,
/// la ventana aparece en el siguiente evento del bucle.
#[pyfunction]
#[pyo3(signature = (id, build, title, size, resizable = true, on_close = None, on_closed = None))]
pub fn window_open(
    id: u64,
    build: Py<PyAny>,
    title: String,
    size: (f64, f64),
    resizable: bool,
    on_close: Option<Py<PyAny>>,
    on_closed: Option<Py<PyAny>>,
) {
    if let Ok(mut pending) = PENDING.lock() {
        pending.push((
            id,
            WindowConfig {
                build,
                title,
                width: size.0,
                height: size.1,
                resizable,
                on_close,
                on_closed,
            },
        ));
    }
    send(Command::Open(id));
}

/// Cierra la ventana con esa id. Seguro desde cualquier hilo.
#[pyfunction]
pub fn window_close(id: u64) {
    send(Command::Close(id));
}

/// Cambia el título, el tamaño (píxeles lógicos) o ambos de una ventana abierta.
#[pyfunction]
#[pyo3(signature = (id, title = None, size = None))]
pub fn window_set(id: u64, title: Option<String>, size: Option<(f64, f64)>) {
    if let Some(title) = title {
        send(Command::SetTitle(id, title));
    }
    if let Some((width, height)) = size {
        send(Command::SetSize(id, width, height));
    }
}

/// Termina la app: cierra todas las ventanas y el bucle. Seguro desde cualquier hilo.
#[pyfunction]
pub fn quit() {
    send(Command::Quit);
}

/// Estado de una ventana: su superficie, su `Runtime` y lo que solo tiene
/// sentido mientras está abierta.
struct View {
    /// Id con el que Python conoce esta ventana.
    id: u64,
    window: Arc<Window>,
    surface: Option<Box<dyn Surface>>,
    rt: Runtime,
    /// Adaptador de accesibilidad (AccessKit): el árbol nativo de esta ventana.
    a11y: accesskit_winit::Adapter,
    mods: Mods,
    /// Si el IME del sistema está activado (solo mientras hay un campo enfocado).
    ime_allowed: bool,
    /// Próximo despertar programado (parpadeo, tooltip), si no hay animaciones en curso.
    wake_at: Option<Instant>,
    last_frame: Instant,
    /// Si el frame anterior dejó transiciones en curso.
    animating: bool,
    /// Si la ventana ya se mostró. Se crea oculta y aparece con su primer
    /// frame presentado, para no enseñar el fondo vacío del sistema mientras
    /// arranca la GPU y se construye la vista.
    shown: bool,
    /// Error irrecuperable de esta ventana (se cierra).
    fatal: Option<String>,
    /// `on_close` del usuario: con un valor falso, la ventana no se cierra.
    on_close: Option<Py<PyAny>>,
    /// Aviso a Python (por id) cuando la ventana se cerró de verdad.
    on_closed: Option<Py<PyAny>>,
}

impl View {
    #[allow(clippy::too_many_arguments)]
    fn new(
        event_loop: &ActiveEventLoop,
        id: u64,
        window: Arc<Window>,
        backend: Backend,
        rt: Runtime,
        a11y_proxy: EventLoopProxy<UserEvent>,
        on_close: Option<Py<PyAny>>,
        on_closed: Option<Py<PyAny>>,
    ) -> Result<Self, String> {
        // El adaptador de accesibilidad tiene que existir antes de mostrar la
        // ventana (se crea oculta y se enseña con el primer frame presentado).
        let a11y = accesskit_winit::Adapter::with_event_loop_proxy(event_loop, &window, a11y_proxy);
        let surface = surface::create(event_loop, &window, backend)?;
        Ok(Self {
            id,
            window,
            surface: Some(surface),
            rt,
            a11y,
            mods: Mods::default(),
            ime_allowed: false,
            wake_at: None,
            last_frame: Instant::now(),
            animating: false,
            shown: false,
            fatal: None,
            on_close,
            on_closed,
        })
    }

    /// Pinta un frame, con esta ventana como «la ventana en curso» de Python.
    fn redraw(&mut self) {
        let window = self.window.clone();
        with_current(&window, || self.redraw_inner());
    }

    fn redraw_inner(&mut self) {
        if let Err(err) = self.rt.sync() {
            Python::attach(|py| err.print(py));
            if !self.rt.has_tree() {
                self.fatal = Some("la vista inicial falló al construirse".into());
            }
        }
        let Some(surface) = &mut self.surface else {
            return;
        };
        let window = self.window.clone();

        let now = Instant::now();
        let elapsed = now.duration_since(self.last_frame).as_secs_f32();
        let dt = frame_dt(elapsed, self.animating);
        self.last_frame = now;
        let animating = self.rt.tick(dt);
        // El parpadeo usa el tiempo real: entre parpadeos el bucle está dormido.
        self.rt.advance_clock(elapsed.min(1.0));
        self.animating = animating;

        let scale = window.scale_factor() as f32;
        let mut hover_changed = false;
        let rt = &mut self.rt;
        let presented = surface.present(&window, &mut |canvas, age| {
            let size = canvas.base_layer_size();
            let (w, h) = (size.width as f32 / scale, size.height as f32 / scale);
            let result = rt.draw_frame(canvas, w, h, scale, age);
            let (hover, damage) = result.as_ref().map_or((false, None), |r| *r);
            hover_changed = hover;
            report(result.map(drop));
            damage
        });
        if presented.is_ok() && !self.shown {
            window.set_visible(true);
            self.shown = true;
        }
        if let Err(err) = presented {
            // La GPU dejó de responder (dispositivo perdido, driver reiniciado):
            // se sigue pintando por CPU.
            let name = surface.name();
            match surface::cpu(&window) {
                Ok(cpu) if name != "cpu" => {
                    eprintln!("aurora: el backend {name} falló ({err}); se usa la CPU");
                    self.surface = Some(cpu);
                    window.request_redraw();
                }
                _ => self.fatal = Some(format!("no se pudo presentar el frame: {err}")),
            }
        }

        // El árbol que ven los lectores de pantalla, con la geometría de este
        // frame. Sin lector conectado, AccessKit ni llama al constructor.
        self.sync_a11y();

        if hover_changed {
            self.update_cursor();
        }
        // Un layout puede haber puesto en marcha animaciones al pintar.
        let animating = animating || self.rt.animating();
        self.animating = animating;
        if animating || hover_changed {
            window.request_redraw();
        }
        self.wake_at = match self.rt.next_wakeup() {
            Some(secs) if !animating => Some(now + Duration::from_secs_f32(secs)),
            _ => None,
        };
        self.update_ime();
    }

    /// Publica el árbol de accesibilidad del último frame, si hay un lector
    /// conectado (sin lector, AccessKit ni ejecuta el constructor).
    fn sync_a11y(&mut self) {
        let scale = self.window.scale_factor() as f32;
        let size = self.window.inner_size();
        let (width, height) = (size.width as f32 / scale, size.height as f32 / scale);
        let View { a11y, rt, .. } = self;
        a11y.update_if_active(|| rt.a11y_build(width, height, scale).update);
    }

    /// El IME del sistema solo se activa con un campo enfocado, y su ventana
    /// de composición se coloca junto al cursor.
    fn update_ime(&mut self) {
        match self.rt.ime_area() {
            Some(caret) => {
                if !self.ime_allowed {
                    self.window.set_ime_allowed(true);
                    self.ime_allowed = true;
                }
                self.window.set_ime_cursor_area(
                    LogicalPosition::new(caret.left, caret.top),
                    LogicalSize::new(caret.width().max(1.0), caret.height()),
                );
            }
            None if self.ime_allowed => {
                self.window.set_ime_allowed(false);
                self.ime_allowed = false;
            }
            None => {}
        }
    }

    fn update_cursor(&self) {
        self.window.set_cursor(match self.rt.cursor() {
            CursorKind::Pointer => CursorIcon::Pointer,
            CursorKind::Text => CursorIcon::Text,
            CursorKind::Grab => CursorIcon::Grab,
            CursorKind::Grabbing => CursorIcon::Grabbing,
            CursorKind::ColResize => CursorIcon::ColResize,
            CursorKind::RowResize => CursorIcon::RowResize,
            CursorKind::Crosshair => CursorIcon::Crosshair,
            CursorKind::Default => CursorIcon::Default,
        });
    }

    /// Traduce un evento de winit del tamaño, el puntero, la rueda o el teclado.
    /// El cierre va aparte (`Host::window_event`): no depende solo de la ventana.
    fn event(&mut self, event: &WindowEvent) {
        let window = self.window.clone();
        with_current(&window, || self.event_inner(event));
    }

    fn event_inner(&mut self, event: &WindowEvent) {
        let window = self.window.clone();
        match event {
            WindowEvent::Resized(_) | WindowEvent::ScaleFactorChanged { .. } => {
                window.request_redraw()
            }
            WindowEvent::CursorMoved { position, .. } => {
                let p = position.to_logical::<f32>(window.scale_factor());
                let changed = self.rt.pointer_move(p.x, p.y).unwrap_or_else(|err| {
                    report(Err(err));
                    true
                });
                if changed {
                    self.update_cursor();
                    window.request_redraw();
                }
            }
            WindowEvent::MouseWheel { delta, .. } => {
                // winit: positivo = el contenido baja (se ve lo de arriba). Aurora usa
                // positivo = avanzar hacia el final, así que se invierte.
                let (delta, smooth) = match *delta {
                    MouseScrollDelta::LineDelta(x, y) => (Point::new(-x * LINE, -y * LINE), true),
                    MouseScrollDelta::PixelDelta(p) => {
                        let p = p.to_logical::<f32>(window.scale_factor());
                        (Point::new(-p.x, -p.y), false)
                    }
                };
                if self.rt.wheel(delta, smooth) {
                    window.request_redraw();
                }
            }
            WindowEvent::CursorLeft { .. } => {
                self.rt.pointer_leave();
                window.request_redraw();
            }
            WindowEvent::MouseInput {
                state,
                button: MouseButton::Left,
                ..
            } => {
                match state {
                    ElementState::Pressed => report(self.rt.pointer_down()),
                    ElementState::Released => report(self.rt.pointer_up()),
                }
                window.request_redraw();
            }
            WindowEvent::MouseInput {
                state: ElementState::Pressed,
                button: MouseButton::Right,
                ..
            } => {
                report(Python::attach(|py| -> PyResult<()> {
                    // El primer ancestro bajo el puntero con `on_context_menu`
                    // decide el menú (una lista, o un callable que la devuelve).
                    let Some(handler) = self.rt.context_menu() else {
                        return Ok(());
                    };
                    let spec = handler.call0(py)?;
                    crate::menu::show_context(&self.window, spec.bind(py))
                }));
                window.request_redraw();
            }
            WindowEvent::ModifiersChanged(m) => {
                let s = m.state();
                self.mods = Mods {
                    ctrl: s.control_key(),
                    shift: s.shift_key(),
                    alt: s.alt_key(),
                    meta: s.super_key(),
                };
                self.rt.mods = self.mods;
            }
            WindowEvent::Ime(ime) => {
                match ime {
                    Ime::Preedit(text, _) => {
                        self.rt.ime_preedit(text);
                    }
                    Ime::Commit(text) => report(self.rt.ime_commit(text).map(drop)),
                    Ime::Disabled => {
                        self.rt.ime_preedit("");
                    }
                    Ime::Enabled => {}
                }
                window.request_redraw();
            }
            WindowEvent::KeyboardInput {
                event,
                is_synthetic: false,
                ..
            } => {
                let Some(input) = key_input(event, self.mods) else {
                    return;
                };
                let pressed = event.state == ElementState::Pressed;
                let needs_frame = match self.rt.key_event(&input, pressed) {
                    Ok(changed) => changed,
                    Err(err) => {
                        report(Err(err));
                        true
                    }
                };
                if needs_frame || self.rt.is_dirty() {
                    window.request_redraw();
                }
            }
            _ => {}
        }
    }
}

/// Host del bucle: todas las ventanas de la app y lo que comparten.
struct Host {
    /// Ventanas que hay que abrir al arrancar (la primera manda: si no se crea,
    /// la app no arranca).
    initial: Option<Vec<(u64, WindowConfig)>>,
    views: HashMap<WindowId, View>,
    /// De id de Python a id de winit.
    by_id: HashMap<u64, WindowId>,
    backend: Backend,
    inspector: bool,
    /// Sin ventanas, la app sigue viva (bandeja, trabajo en segundo plano).
    keep_alive: bool,
    /// Se pidió terminar: al cerrar la última ventana no se queda viva.
    quitting: bool,
    /// La bandeja del sistema, si la hay.
    tray: Option<tray_icon::TrayIcon>,
    /// Acciones del menú de la bandeja, por id de `muda`.
    tray_actions: std::collections::HashMap<String, Py<PyAny>>,
    tray_on_click: Option<Py<PyAny>>,
    tray_on_double_click: Option<Py<PyAny>>,
    /// La barra de menús de la app, si la describió.
    bar: Option<crate::menu::Built>,
    /// Proxy para los eventos de accesibilidad (AccessKit) de cada ventana.
    a11y_proxy: EventLoopProxy<UserEvent>,
    fatal: Option<String>,
}

impl Host {
    fn redraw(&mut self, id: WindowId) {
        if let Some(view) = self.views.get_mut(&id) {
            view.redraw();
        }
    }

    /// Crea una ventana con su runtime y la pinta por primera vez.
    fn create(
        &self,
        event_loop: &ActiveEventLoop,
        id: u64,
        config: WindowConfig,
    ) -> Result<View, String> {
        let attrs = Window::default_attributes()
            .with_title(&config.title)
            .with_inner_size(LogicalSize::new(config.width, config.height))
            .with_resizable(config.resizable)
            .with_visible(false);
        let window = Arc::new(
            event_loop
                .create_window(attrs)
                .map_err(|e| format!("no se pudo crear la ventana: {e}"))?,
        );
        let rt = Runtime::new(config.build, Clipboard::System(None), self.inspector);
        let mut view = View::new(
            event_loop,
            id,
            window,
            self.backend,
            rt,
            self.a11y_proxy.clone(),
            config.on_close,
            config.on_closed,
        )?;
        // La barra de menús se cuelga de cada ventana (en Windows es de la ventana).
        #[cfg(target_os = "windows")]
        if let Some(bar) = &self.bar {
            crate::menu::attach(&view.window, bar);
        }
        // El primer frame se pinta aquí mismo: una ventana oculta no recibe
        // `RedrawRequested` en todas las plataformas (en Windows, WM_PAINT).
        view.redraw();
        if let Some(msg) = view.fatal.take() {
            return Err(msg);
        }
        // Si el primer present no salió (p. ej. se cambió a la CPU y queda
        // pendiente repetirlo), se muestra igualmente para no quedar invisible.
        if !view.shown {
            view.window.set_visible(true);
            view.shown = true;
            view.window.request_redraw();
        }
        Ok(view)
    }

    /// Abre la ventana `id` con su configuración pendiente.
    fn open_window(&mut self, event_loop: &ActiveEventLoop, id: u64) {
        let Some(config) = take_pending(id) else {
            return;
        };
        if self.by_id.contains_key(&id) {
            return;
        }
        // Aviso de cierre (aunque no se llegue a crear): Python recupera su estado.
        let on_closed = Python::attach(|py| config.on_closed.as_ref().map(|cb| cb.clone_ref(py)));
        match self.create(event_loop, id, config) {
            Ok(view) => {
                self.by_id.insert(id, view.window.id());
                self.views.insert(view.window.id(), view);
            }
            Err(err) => {
                eprintln!("aurora: no se pudo abrir la ventana: {err}");
                if let Some(cb) = on_closed {
                    Python::attach(|py| {
                        if let Err(err) = cb.call1(py, (id,)) {
                            err.print(py);
                        }
                    });
                }
            }
        }
    }

    /// Cierra la ventana con el id de Python que dio `window_close`.
    fn close_window(&mut self, event_loop: &ActiveEventLoop, id: u64) {
        if let Some(window_id) = self.by_id.get(&id).copied() {
            self.drop_view(event_loop, window_id);
        }
    }

    /// El sistema pide cerrar la ventana: el `on_close` del usuario decide.
    fn close_requested(&mut self, event_loop: &ActiveEventLoop, window_id: WindowId) {
        let allowed = match self.views.get(&window_id) {
            Some(view) => match &view.on_close {
                Some(cb) => {
                    let window = view.window.clone();
                    with_current(&window, || {
                        Python::attach(|py| match cb.call0(py) {
                            Ok(ret) => ret.is_truthy(py).unwrap_or(true),
                            Err(err) => {
                                err.print(py);
                                true
                            }
                        })
                    })
                }
                None => true,
            },
            None => true,
        };
        if allowed {
            self.drop_view(event_loop, window_id);
        }
    }

    /// Quita una ventana (su ventana del sistema se destruye) y avisa a Python.
    /// Si era la última y la app no vive sin ventanas, termina el bucle.
    fn drop_view(&mut self, event_loop: &ActiveEventLoop, window_id: WindowId) {
        let Some(view) = self.views.remove(&window_id) else {
            return;
        };
        self.by_id.remove(&view.id);
        if let Some(cb) = &view.on_closed {
            Python::attach(|py| {
                if let Err(err) = cb.call1(py, (view.id,)) {
                    err.print(py);
                }
            });
        }
        if self.views.is_empty() && (!self.keep_alive || self.quitting) {
            // Se suelta la bandeja con el bucle todavía en marcha.
            self.hide_tray();
            event_loop.exit();
        }
    }

    /// Crea (o reemplaza) la bandeja con la configuración que dejó Python.
    fn show_tray(&mut self, py: Python<'_>) {
        let Some(config) = crate::tray::take_pending() else {
            return;
        };
        match crate::tray::create(py, config) {
            Ok(created) => {
                self.tray = Some(created.tray);
                self.tray_actions = created.actions;
                self.tray_on_click = created.on_click;
                self.tray_on_double_click = created.on_double_click;
            }
            Err(err) => eprintln!("aurora: no se pudo crear la bandeja: {err}"),
        }
    }

    /// Quita la bandeja del sistema (soltar el icono la elimina).
    fn hide_tray(&mut self) {
        self.tray = None;
        self.tray_actions.clear();
        self.tray_on_click = None;
        self.tray_on_double_click = None;
    }

    /// Un clic (o doble clic) en la bandeja: avisa a Python con el botón.
    fn tray_event(&mut self, event: TrayIconEvent) {
        let (callback, button) = match &event {
            TrayIconEvent::Click {
                button,
                button_state,
                ..
            } if *button_state == MouseButtonState::Up => {
                (&self.tray_on_click, button_name(*button))
            }
            TrayIconEvent::DoubleClick { button, .. } => {
                (&self.tray_on_double_click, button_name(*button))
            }
            _ => return,
        };
        if let Some(cb) = callback {
            Python::attach(|py| {
                if let Err(err) = cb.call1(py, (button,)) {
                    err.print(py);
                }
            });
        }
    }

    /// Una opción de un menú (el de la bandeja, la barra o un contextual):
    /// llama a su acción.
    fn menu_event(&mut self, event: MenuEvent) {
        let id = event.id.0.clone();
        let callback = self
            .tray_actions
            .get(&id)
            .or_else(|| self.bar.as_ref().and_then(|bar| bar.actions.get(&id)));
        match callback {
            Some(cb) => Python::attach(|py| {
                if let Err(err) = cb.call0(py) {
                    err.print(py);
                }
            }),
            None => Python::attach(|py| {
                crate::menu::call_context_action(py, &id);
            }),
        }
    }

    /// Un evento del lector de pantalla (AccessKit): pide el árbol, entrega una
    /// acción sobre un nodo o avisa de que se desconectó.
    fn a11y_event(&mut self, event: accesskit_winit::Event) {
        use accesskit_winit::WindowEvent as A11y;
        let Some(view) = self.views.get_mut(&event.window_id) else {
            return;
        };
        match event.window_event {
            // Primer árbol (o una reactivación): tiene que venir completo.
            A11y::InitialTreeRequested => {
                view.sync_a11y();
                view.window.request_redraw();
            }
            A11y::ActionRequested(request) => {
                let View { rt, window, .. } = view;
                match rt.a11y_action(request.target_node, request.action, request.data) {
                    Ok(_) => window.request_redraw(),
                    Err(err) => Python::attach(|py| err.print(py)),
                }
            }
            // El lector se desconectó: nada que soltar (los updates se saltan solos).
            A11y::AccessibilityDeactivated => {}
        }
    }

    /// Cierra las ventanas con error irrecuperable.
    fn reap(&mut self, event_loop: &ActiveEventLoop) {
        let failed: Vec<(WindowId, String)> = self
            .views
            .iter()
            .filter_map(|(id, v)| v.fatal.as_ref().map(|m| (*id, m.clone())))
            .collect();
        for (id, msg) in failed {
            eprintln!("aurora: {msg}");
            self.drop_view(event_loop, id);
        }
    }

    /// Atiende un comando pedido desde Python.
    fn command(&mut self, event_loop: &ActiveEventLoop, command: Command) {
        if self.quitting {
            return;
        }
        match command {
            Command::Open(id) => self.open_window(event_loop, id),
            Command::Close(id) => self.close_window(event_loop, id),
            Command::SetTitle(id, title) => {
                if let Some(view) = self.by_id.get(&id).and_then(|k| self.views.get_mut(k)) {
                    view.window.set_title(&title);
                }
            }
            Command::SetSize(id, width, height) => {
                if let Some(view) = self.by_id.get(&id).and_then(|k| self.views.get_mut(k)) {
                    let _ = view
                        .window
                        .request_inner_size(LogicalSize::new(width, height));
                }
            }
            Command::TrayShow => Python::attach(|py| self.show_tray(py)),
            Command::TrayHide => self.hide_tray(),
            Command::Notify(config) => {
                if let Err(err) = crate::notify::send(&config) {
                    eprintln!("aurora: no se pudo notificar: {err}");
                }
            }
            Command::Quit => {
                self.quitting = true;
                self.hide_tray();
                let ids: Vec<WindowId> = self.views.keys().copied().collect();
                for id in ids {
                    self.drop_view(event_loop, id);
                }
                event_loop.exit();
            }
        }
    }
}

/// Configuración de las ventanas que llega de Python: una lista de dicts con
/// `id`, `build`, `title`, `size`, `resizable`, `on_close` y `on_closed`.
fn parse_windows(windows: &Bound<'_, PyAny>) -> PyResult<Vec<(u64, WindowConfig)>> {
    let mut out = Vec::new();
    for item in windows.try_iter()? {
        let item = item?;
        let id: u64 = item.get_item("id")?.extract()?;
        let (width, height): (f64, f64) = item.get_item("size")?.extract()?;
        let config = WindowConfig {
            build: item.get_item("build")?.unbind(),
            title: item.get_item("title")?.extract()?,
            width,
            height,
            resizable: item.get_item("resizable")?.extract()?,
            on_close: item.get_item("on_close")?.extract()?,
            on_closed: item.get_item("on_closed")?.extract()?,
        };
        out.push((id, config));
    }
    Ok(out)
}

/// Traduce una tecla de winit. Las teclas sin nombre ni carácter (muertas,
/// no identificadas) se ignoran.
fn key_input(event: &KeyEvent, mods: Mods) -> Option<KeyInput> {
    let key = match &event.logical_key {
        Key::Named(named) => format!("{named:?}"),
        Key::Character(c) => c.to_string(),
        _ => return None,
    };
    let text = event
        .text
        .as_ref()
        .map(|t| t.to_string())
        .filter(|t| !t.chars().all(char::is_control));
    Some(KeyInput {
        key,
        text,
        mods,
        repeat: event.repeat,
    })
}

/// Un error en un manejador del usuario se muestra y la app sigue viva.
fn report(result: PyResult<()>) {
    if let Err(err) = result {
        Python::attach(|py| err.print(py));
    }
}

/// El nombre con el que Python ve un botón del ratón.
fn button_name(button: TrayButton) -> &'static str {
    match button {
        TrayButton::Left => "left",
        TrayButton::Right => "right",
        TrayButton::Middle => "middle",
    }
}

/// La barra de menús de la app. En macOS lleva delante el submenú estándar
/// (Acerca de, Ocultar, Salir…), que es la convención del sistema.
fn build_bar(py: Python<'_>, spec: &Py<PyAny>, app_name: &str) -> PyResult<crate::menu::Built> {
    #[cfg(target_os = "macos")]
    {
        crate::menu::prepend_app_menu(py, spec.bind(py), app_name)
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = (py, app_name);
        crate::menu::build(spec.bind(py))
    }
}

/// Paso de tiempo para avanzar las transiciones.
///
/// Si no había ninguna transición en curso, el tiempo transcurrido es tiempo
/// ocioso: usarlo haría que una transición recién iniciada saltara casi al
/// final en su primer frame. En ese caso se avanza un frame nominal.
fn frame_dt(elapsed: f32, was_animating: bool) -> f32 {
    const NOMINAL: f32 = 1.0 / 60.0;
    if was_animating {
        elapsed.clamp(0.0, 0.1)
    } else {
        NOMINAL
    }
}

impl ApplicationHandler<UserEvent> for Host {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        let Some(initial) = self.initial.take() else {
            return;
        };
        for (i, (id, config)) in initial.into_iter().enumerate() {
            match self.create(event_loop, id, config) {
                Ok(view) => {
                    self.by_id.insert(id, view.window.id());
                    self.views.insert(view.window.id(), view);
                }
                // La primera ventana es la app: si no se crea, no hay nada que hacer.
                Err(err) if i == 0 => {
                    self.fatal = Some(err);
                    event_loop.exit();
                    return;
                }
                Err(err) => eprintln!("aurora: no se pudo abrir la ventana: {err}"),
            }
        }
        // Una bandeja pedida antes de `run()` espera a este momento.
        Python::attach(|py| self.show_tray(py));
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, id: WindowId, event: WindowEvent) {
        // El lector de pantalla ve el evento antes que la app (AccessKit:
        // posición y tamaño de la ventana, foco…).
        if let Some(view) = self.views.get_mut(&id) {
            view.a11y.process_event(&view.window, &event);
        }
        match event {
            WindowEvent::RedrawRequested => {
                self.redraw(id);
                self.reap(event_loop);
            }
            WindowEvent::CloseRequested => self.close_requested(event_loop, id),
            event => {
                if let Some(view) = self.views.get_mut(&id) {
                    view.event(&event);
                }
            }
        }
    }

    fn new_events(&mut self, _event_loop: &ActiveEventLoop, cause: StartCause) {
        // Despertar programado: toca cambiar el parpadeo del cursor.
        if let StartCause::ResumeTimeReached { .. } = cause {
            for view in self.views.values() {
                view.window.request_redraw();
            }
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        let next = self.views.values().filter_map(|v| v.wake_at).min();
        event_loop.set_control_flow(match next {
            Some(at) => ControlFlow::WaitUntil(at),
            None => ControlFlow::Wait,
        });
    }

    fn user_event(&mut self, event_loop: &ActiveEventLoop, event: UserEvent) {
        match event {
            // `Runtime::sync` consume la época de `wake()` y reconstruye la vista.
            UserEvent::Wake => {
                for view in self.views.values() {
                    view.window.request_redraw();
                }
            }
            UserEvent::Command(command) => self.command(event_loop, command),
            UserEvent::Tray(event) => self.tray_event(event),
            UserEvent::Menu(event) => self.menu_event(event),
            UserEvent::Access(event) => self.a11y_event(event),
        }
    }
}

pub fn run(
    py: Python<'_>,
    windows: &Bound<'_, PyAny>,
    backend: &str,
    inspector: bool,
    keep_alive: bool,
    menu_spec: Option<Py<PyAny>>,
) -> PyResult<()> {
    let backend = Backend::resolve(backend).map_err(PyValueError::new_err)?;
    let initial = parse_windows(windows)?;
    if initial.is_empty() && !keep_alive {
        return Err(PyValueError::new_err("no hay ninguna ventana que abrir"));
    }
    let app_name = initial
        .first()
        .map(|(_, config)| config.title.clone())
        .unwrap_or_else(|| "Aurora".to_string());
    let fatal = py.detach(move || -> Result<Option<String>, String> {
        let mut builder = EventLoop::<UserEvent>::with_user_event();
        // En macOS los menús los pone muda, no winit.
        #[cfg(target_os = "macos")]
        {
            use winit::platform::macos::EventLoopBuilderExtMacOS;
            builder.with_default_menu(false);
        }
        // La barra se construye antes del bucle: en Windows su HACCEL va en el
        // hook de mensajes (los aceleradores del sistema).
        let bar = match &menu_spec {
            Some(spec) => Some(
                Python::attach(|py| build_bar(py, spec, &app_name))
                    .map_err(|err| err.to_string())?,
            ),
            None => None,
        };
        #[cfg(target_os = "windows")]
        if let Some(bar) = &bar {
            use winit::platform::windows::EventLoopBuilderExtWindows;
            let haccel = crate::menu::haccel(bar);
            builder.with_msg_hook(move |msg| {
                use windows::Win32::UI::WindowsAndMessaging::{HACCEL, MSG, TranslateAcceleratorW};
                unsafe {
                    let msg = msg as *const MSG;
                    TranslateAcceleratorW((*msg).hwnd, HACCEL(haccel as _), msg) != 0
                }
            });
        }
        #[cfg(not(any(target_os = "windows", target_os = "macos")))]
        if bar.is_some() {
            eprintln!(
                "aurora: la barra de menús nativa no está disponible en este sistema; \
                 usa el componente `menu` dentro de la app"
            );
        }
        let event_loop = builder.build().map_err(|e| e.to_string())?;
        // En macOS la barra es de la aplicación entera.
        #[cfg(target_os = "macos")]
        if let Some(bar) = &bar {
            bar.menu.init_for_nsapp();
        }
        event_loop.set_control_flow(ControlFlow::Wait);
        let a11y_proxy = event_loop.create_proxy();
        let mut host = Host {
            initial: Some(initial),
            views: HashMap::new(),
            by_id: HashMap::new(),
            backend,
            inspector,
            keep_alive,
            quitting: false,
            tray: None,
            tray_actions: HashMap::new(),
            tray_on_click: None,
            tray_on_double_click: None,
            bar,
            a11y_proxy,
            fatal: None,
        };
        // Los eventos de la bandeja y de sus menús despiertan al bucle.
        let proxy = event_loop.create_proxy();
        TrayIconEvent::set_event_handler(Some(move |event: TrayIconEvent| {
            let _ = proxy.send_event(UserEvent::Tray(event));
        }));
        let proxy = event_loop.create_proxy();
        MenuEvent::set_event_handler(Some(move |event: MenuEvent| {
            let _ = proxy.send_event(UserEvent::Menu(event));
        }));
        set_proxy(Some(event_loop.create_proxy()));
        let result = event_loop.run_app(&mut host).map_err(|e| e.to_string());
        set_proxy(None);
        // El bucle ya no atiende bandeja ni menús.
        TrayIconEvent::set_event_handler(None::<fn(TrayIconEvent)>);
        MenuEvent::set_event_handler(None::<fn(MenuEvent)>);
        clear_pending();
        result?;
        Ok(host.fatal)
    });
    match fatal {
        Ok(None) => Ok(()),
        Ok(Some(msg)) | Err(msg) => Err(pyo3::exceptions::PyRuntimeError::new_err(msg)),
    }
}

#[cfg(test)]
mod tests {
    use super::frame_dt;

    #[test]
    fn idle_time_does_not_skip_the_start_of_a_transition() {
        assert_eq!(frame_dt(5.0, false), 1.0 / 60.0);
    }

    #[test]
    fn running_transitions_use_elapsed_time_capped() {
        assert_eq!(frame_dt(0.02, true), 0.02);
        assert_eq!(frame_dt(3.0, true), 0.1);
    }
}
