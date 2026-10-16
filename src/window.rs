//! Bucle de ventana (winit). El bucle corre SIN el GIL: Python solo se toma
//! al reconstruir el árbol o al despachar un callback. El estado de la app vive
//! en `Runtime`; aquí solo se traducen los eventos de winit y se presenta el
//! frame en la `Surface` (GPU o CPU, ver `surface.rs`).

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use pyo3::prelude::*;
use skia_safe::Point;
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

/// Evento propio del bucle: alguien llamó a `wake()`, quizá desde otro hilo.
#[derive(Debug)]
pub struct Wake;

/// Proxy del bucle en marcha (si lo hay), para despertarlo desde cualquier hilo.
static PROXY: Mutex<Option<EventLoopProxy<Wake>>> = Mutex::new(None);

/// Despierta el bucle de eventos para que pinte un frame. Sin bucle, no hace nada.
pub fn notify() {
    if let Ok(proxy) = PROXY.lock()
        && let Some(proxy) = proxy.as_ref()
    {
        // Solo falla si el bucle ya terminó: no queda nada que despertar.
        let _ = proxy.send_event(Wake);
    }
}

fn set_proxy(proxy: Option<EventLoopProxy<Wake>>) {
    if let Ok(mut slot) = PROXY.lock() {
        *slot = proxy;
    }
}

struct App {
    rt: Runtime,
    title: String,
    size: (f64, f64),
    backend: Backend,
    window: Option<Arc<Window>>,
    surface: Option<Box<dyn Surface>>,
    mods: Mods,
    /// Si el IME del sistema está activado (solo mientras hay un campo enfocado).
    ime_allowed: bool,
    /// Próximo despertar programado (parpadeo, tooltip), si no hay animaciones en curso.
    wake_at: Option<Instant>,
    last_frame: Instant,
    /// Si el frame anterior dejó transiciones en curso.
    animating: bool,
    fatal: Option<String>,
}

impl App {
    fn redraw(&mut self) {
        if let Err(err) = self.rt.sync() {
            Python::attach(|py| err.print(py));
            if !self.rt.has_tree() {
                self.fatal = Some("la vista inicial falló al construirse".into());
            }
        }
        let (Some(window), Some(surface)) = (&self.window, &mut self.surface) else {
            return;
        };

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
        let presented = surface.present(window, &mut |canvas, age| {
            let size = canvas.base_layer_size();
            let (w, h) = (size.width as f32 / scale, size.height as f32 / scale);
            let result = rt.draw_frame(canvas, w, h, scale, age);
            let (hover, damage) = result.as_ref().map_or((false, None), |r| *r);
            hover_changed = hover;
            report(result.map(drop));
            damage
        });
        if let Err(err) = presented {
            // La GPU dejó de responder (dispositivo perdido, driver reiniciado):
            // se sigue pintando por CPU.
            let name = surface.name();
            match surface::cpu(window) {
                Ok(cpu) if name != "cpu" => {
                    eprintln!("aurora: el backend {name} falló ({err}); se usa la CPU");
                    self.surface = Some(cpu);
                    window.request_redraw();
                }
                _ => self.fatal = Some(format!("no se pudo presentar el frame: {err}")),
            }
        }

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

    /// El IME del sistema solo se activa con un campo enfocado, y su ventana
    /// de composición se coloca junto al cursor.
    fn update_ime(&mut self) {
        let Some(window) = &self.window else {
            return;
        };
        match self.rt.ime_area() {
            Some(caret) => {
                if !self.ime_allowed {
                    window.set_ime_allowed(true);
                    self.ime_allowed = true;
                }
                window.set_ime_cursor_area(
                    LogicalPosition::new(caret.left, caret.top),
                    LogicalSize::new(caret.width().max(1.0), caret.height()),
                );
            }
            None if self.ime_allowed => {
                window.set_ime_allowed(false);
                self.ime_allowed = false;
            }
            None => {}
        }
    }

    fn update_cursor(&self) {
        if let Some(window) = &self.window {
            window.set_cursor(match self.rt.cursor() {
                CursorKind::Pointer => CursorIcon::Pointer,
                CursorKind::Text => CursorIcon::Text,
                CursorKind::Grab => CursorIcon::Grab,
                CursorKind::Grabbing => CursorIcon::Grabbing,
                CursorKind::ColResize => CursorIcon::ColResize,
                CursorKind::RowResize => CursorIcon::RowResize,
                CursorKind::Default => CursorIcon::Default,
            });
        }
    }
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

impl ApplicationHandler<Wake> for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() {
            return;
        }
        let attrs = Window::default_attributes()
            .with_title(&self.title)
            .with_inner_size(LogicalSize::new(self.size.0, self.size.1));
        let window = match event_loop.create_window(attrs) {
            Ok(window) => Arc::new(window),
            Err(err) => {
                self.fatal = Some(format!("no se pudo crear la ventana: {err}"));
                event_loop.exit();
                return;
            }
        };
        match surface::create(event_loop, &window, self.backend) {
            Ok(surface) => self.surface = Some(surface),
            Err(err) => {
                self.fatal = Some(err);
                event_loop.exit();
                return;
            }
        }
        window.request_redraw();
        self.window = Some(window);
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let Some(window) = self.window.clone() else {
            return;
        };
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
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
                let (delta, smooth) = match delta {
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
                        self.rt.ime_preedit(&text);
                    }
                    Ime::Commit(text) => report(self.rt.ime_commit(&text).map(drop)),
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
                let Some(input) = key_input(&event, self.mods) else {
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
            WindowEvent::RedrawRequested => {
                self.redraw();
                if self.fatal.is_some() {
                    event_loop.exit();
                }
            }
            _ => {}
        }
    }

    fn new_events(&mut self, _event_loop: &ActiveEventLoop, cause: StartCause) {
        // Despertar programado: toca cambiar el parpadeo del cursor.
        if let StartCause::ResumeTimeReached { .. } = cause
            && let Some(window) = &self.window
        {
            window.request_redraw();
        }
    }

    fn about_to_wait(&mut self, event_loop: &ActiveEventLoop) {
        event_loop.set_control_flow(match self.wake_at {
            Some(at) => ControlFlow::WaitUntil(at),
            None => ControlFlow::Wait,
        });
    }

    fn user_event(&mut self, _event_loop: &ActiveEventLoop, _event: Wake) {
        // `Runtime::sync` consume la marca de `wake()` y reconstruye la vista.
        if let Some(window) = &self.window {
            window.request_redraw();
        }
    }
}

pub fn run(
    py: Python<'_>,
    build: Py<PyAny>,
    title: String,
    width: f64,
    height: f64,
    backend: &str,
) -> PyResult<()> {
    let backend = Backend::resolve(backend).map_err(pyo3::exceptions::PyValueError::new_err)?;
    let fatal = py.detach(move || -> Result<Option<String>, String> {
        let event_loop = EventLoop::<Wake>::with_user_event()
            .build()
            .map_err(|e| e.to_string())?;
        event_loop.set_control_flow(ControlFlow::Wait);
        let mut app = App {
            rt: Runtime::new(build, Clipboard::System(None)),
            title,
            size: (width, height),
            backend,
            window: None,
            surface: None,
            mods: Mods::default(),
            ime_allowed: false,
            wake_at: None,
            last_frame: Instant::now(),
            animating: false,
            fatal: None,
        };
        set_proxy(Some(event_loop.create_proxy()));
        let result = event_loop.run_app(&mut app).map_err(|e| e.to_string());
        set_proxy(None);
        result?;
        Ok(app.fatal)
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
