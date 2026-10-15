//! Bucle de ventana (winit) con rasterizado Skia directo en el framebuffer
//! (softbuffer, sin copias). El bucle corre SIN el GIL: Python solo se toma
//! al reconstruir el árbol o al despachar un callback.

use std::num::NonZeroU32;
use std::rc::Rc;
use std::time::Instant;

use pyo3::prelude::*;
use skia_safe::{ImageInfo, surfaces};
use winit::application::ApplicationHandler;
use winit::dpi::LogicalSize;
use winit::event::{ElementState, MouseButton, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::window::{CursorIcon, Window, WindowId};

use crate::render::{Engine, HitRegion};
use crate::spec::{self, Node};

type SoftSurface = softbuffer::Surface<Rc<Window>, Rc<Window>>;

struct App {
    build: Py<PyAny>,
    title: String,
    size: (f64, f64),
    window: Option<Rc<Window>>,
    surface: Option<SoftSurface>,
    engine: Engine,
    tree: Option<Node>,
    regions: Vec<HitRegion>,
    dirty: bool,
    last_frame: Instant,
    fatal: Option<String>,
}

impl App {
    fn rebuild(&mut self) {
        let result = Python::attach(|py| -> PyResult<Node> {
            let obj = self.build.call0(py)?;
            spec::parse(obj.bind(py))
        });
        match result {
            Ok(tree) => self.tree = Some(tree),
            Err(err) => {
                Python::attach(|py| err.print(py));
                if self.tree.is_none() {
                    self.fatal = Some("la vista inicial falló al construirse".into());
                }
            }
        }
        self.dirty = false;
    }

    fn hit(&self, x: f32, y: f32) -> Option<String> {
        crate::render::hit_test(&self.regions, x, y)
    }

    fn dispatch_click(&mut self, key: &str) {
        let Some(tree) = &self.tree else { return };
        let Some(node) = find(tree, key) else { return };
        let Some(cb) = &node.on_click else { return };
        Python::attach(|py| {
            if let Err(err) = cb.call0(py) {
                err.print(py);
            }
        });
        // MVP: tras cualquier evento se reconstruye la vista completa.
        // Próximo paso: signals de grano fino que invaliden solo su rama.
        self.dirty = true;
    }

    fn redraw(&mut self) {
        if self.dirty || self.tree.is_none() {
            self.rebuild();
        }
        let (Some(window), Some(surface), Some(tree)) =
            (&self.window, &mut self.surface, &self.tree)
        else {
            return;
        };

        let now = Instant::now();
        let dt = now.duration_since(self.last_frame).as_secs_f32().min(0.1);
        self.last_frame = now;
        let animating = self.engine.tick(dt);

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
        if let Some(mut sk) = surfaces::wrap_pixels(&info, bytes, w.get() as usize * 4, None) {
            self.regions = self.engine.draw(
                sk.canvas(),
                tree,
                w.get() as f32 / scale,
                h.get() as f32 / scale,
                scale,
            );
        }
        buffer.present().expect("present");

        if animating {
            window.request_redraw();
        }
    }
}

fn find<'a>(node: &'a Node, key: &str) -> Option<&'a Node> {
    if node.key == key {
        return Some(node);
    }
    node.children.iter().find_map(|c| find(c, key))
}

impl ApplicationHandler for App {
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
                let hovered = self.hit(p.x, p.y);
                if hovered != self.engine.hovered {
                    window.set_cursor(if hovered.is_some() {
                        CursorIcon::Pointer
                    } else {
                        CursorIcon::Default
                    });
                    self.engine.hovered = hovered;
                    window.request_redraw();
                }
            }
            WindowEvent::CursorLeft { .. } => {
                self.engine.hovered = None;
                window.request_redraw();
            }
            WindowEvent::MouseInput {
                state,
                button: MouseButton::Left,
                ..
            } => {
                match state {
                    ElementState::Pressed => self.engine.pressed = self.engine.hovered.clone(),
                    ElementState::Released => {
                        if let Some(key) = self.engine.pressed.take()
                            && self.engine.hovered.as_deref() == Some(key.as_str())
                        {
                            self.dispatch_click(&key);
                        }
                    }
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
}

pub fn run(
    py: Python<'_>,
    build: Py<PyAny>,
    title: String,
    width: f64,
    height: f64,
) -> PyResult<()> {
    let fatal = py.detach(move || -> Result<Option<String>, String> {
        let event_loop = EventLoop::new().map_err(|e| e.to_string())?;
        event_loop.set_control_flow(ControlFlow::Wait);
        let mut app = App {
            build,
            title,
            size: (width, height),
            window: None,
            surface: None,
            engine: Engine::new(),
            tree: None,
            regions: Vec::new(),
            dirty: true,
            last_frame: Instant::now(),
            fatal: None,
        };
        event_loop.run_app(&mut app).map_err(|e| e.to_string())?;
        Ok(app.fatal)
    });
    match fatal {
        Ok(None) => Ok(()),
        Ok(Some(msg)) | Err(msg) => Err(pyo3::exceptions::PyRuntimeError::new_err(msg)),
    }
}
