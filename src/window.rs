//! Bucle de ventana (winit) con rasterizado Skia directo en el framebuffer
//! (softbuffer, sin copias). El bucle corre SIN el GIL: Python solo se toma
//! al reconstruir el árbol o al despachar un callback. El estado de la app vive
//! en `Runtime`; aquí solo se traducen los eventos de winit y se presenta el frame.

use std::num::NonZeroU32;
use std::rc::Rc;
use std::sync::Mutex;
use std::time::Instant;

use pyo3::prelude::*;
use skia_safe::{ImageInfo, Point, surfaces};
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::{ElementState, MouseButton, MouseScrollDelta, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, EventLoopProxy};
use winit::window::{CursorIcon, Window, WindowId};

use crate::runtime::Runtime;
use crate::scroll::LINE;

type SoftSurface = softbuffer::Surface<Rc<Window>, Rc<Window>>;

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
    window: Option<Rc<Window>>,
    surface: Option<SoftSurface>,
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
        let dt = frame_dt(
            now.duration_since(self.last_frame).as_secs_f32(),
            self.animating,
        );
        self.last_frame = now;
        let animating = self.rt.tick(dt);
        self.animating = animating;

        let size = window.inner_size();
        let (Some(w), Some(h)) = (NonZeroU32::new(size.width), NonZeroU32::new(size.height)) else {
            return;
        };
        surface.resize(w, h).expect("resize");
        let mut buffer = surface.buffer_mut().expect("buffer");

        // softbuffer usa píxeles 0x00RRGGBB (u32 nativo); en little-endian coincide
        // byte a byte con el formato N32 (BGRA) de Skia, así que pintamos directo.
        let bytes = unsafe {
            std::slice::from_raw_parts_mut(buffer.as_mut_ptr() as *mut u8, buffer.len() * 4)
        };
        let info = ImageInfo::new_n32_premul((w.get() as i32, h.get() as i32), None);
        let scale = window.scale_factor() as f32;
        let mut hover_changed = false;
        if let Some(mut sk) = surfaces::wrap_pixels(&info, bytes, w.get() as usize * 4, None) {
            hover_changed = self.rt.draw(
                sk.canvas(),
                w.get() as f32 / scale,
                h.get() as f32 / scale,
                scale,
            );
        }
        buffer.present().expect("present");

        if hover_changed {
            self.update_cursor();
        }
        if animating || hover_changed {
            window.request_redraw();
        }
    }

    fn update_cursor(&self) {
        if let Some(window) = &self.window {
            window.set_cursor(if self.rt.hovered().is_some() {
                CursorIcon::Pointer
            } else {
                CursorIcon::Default
            });
        }
    }
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
        let window = Rc::new(event_loop.create_window(attrs).expect("crear ventana"));
        let context = softbuffer::Context::new(window.clone()).expect("contexto softbuffer");
        self.surface = Some(SoftSurface::new(&context, window.clone()).expect("superficie"));
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
                if self.rt.pointer_move(p.x, p.y) {
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
                    ElementState::Pressed => self.rt.pointer_down(),
                    ElementState::Released => report(self.rt.pointer_up()),
                }
                window.request_redraw();
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
) -> PyResult<()> {
    let fatal = py.detach(move || -> Result<Option<String>, String> {
        let event_loop = EventLoop::<Wake>::with_user_event()
            .build()
            .map_err(|e| e.to_string())?;
        event_loop.set_control_flow(ControlFlow::Wait);
        let mut app = App {
            rt: Runtime::new(build),
            title,
            size: (width, height),
            window: None,
            surface: None,
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
