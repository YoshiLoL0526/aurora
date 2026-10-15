//! Piloto headless: conduce una app sin ventana, simulando el puntero frame a
//! frame. Usa el mismo `Runtime` que la ventana, así que un test que pasa con
//! el piloto ejercita el mismo hit-testing, burbujeo y reconstrucción.

use pyo3::exceptions::{PyLookupError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use skia_safe::Surface;

use crate::render::{raster_surface, write_png};
use crate::runtime::Runtime;

/// Paso de tiempo de un frame simulado.
const FRAME: f32 = 1.0 / 60.0;

#[pyclass(unsendable, module = "aurora._core")]
pub struct Pilot {
    rt: Runtime,
    width: f32,
    height: f32,
    scale: f32,
    surface: Surface,
}

impl Pilot {
    fn step(&mut self, dt: f32) -> PyResult<bool> {
        self.rt.sync()?;
        let animating = self.rt.tick(dt);
        let canvas = self.surface.canvas();
        let hover_changed = self.rt.draw(canvas, self.width, self.height, self.scale);
        Ok(animating || hover_changed)
    }
}

fn new_surface(width: f32, height: f32, scale: f32) -> PyResult<Surface> {
    if !(width > 0.0 && height > 0.0 && scale > 0.0) {
        return Err(PyValueError::new_err(
            "el tamaño y la escala del piloto deben ser positivos",
        ));
    }
    raster_surface(width, height, scale).map_err(PyRuntimeError::new_err)
}

#[pymethods]
impl Pilot {
    #[new]
    #[pyo3(signature = (build, width = 960.0, height = 640.0, scale = 1.0))]
    fn new(build: Py<PyAny>, width: f32, height: f32, scale: f32) -> PyResult<Self> {
        let mut pilot = Self {
            rt: Runtime::new(build),
            width,
            height,
            scale,
            surface: new_surface(width, height, scale)?,
        };
        pilot.step(FRAME)?;
        Ok(pilot)
    }

    /// Avanza un frame: reconstruye si algo cambió, anima y pinta.
    /// Devuelve `True` si queda trabajo pendiente (transiciones en curso).
    #[pyo3(signature = (dt = FRAME))]
    fn frame(&mut self, dt: f32) -> PyResult<bool> {
        self.step(dt)
    }

    /// Avanza frames hasta que no quede ninguna transición en curso.
    #[pyo3(signature = (max_frames = 600))]
    fn settle(&mut self, max_frames: usize) -> PyResult<()> {
        for _ in 0..max_frames {
            if !self.step(FRAME)? {
                return Ok(());
            }
        }
        Err(PyRuntimeError::new_err(format!(
            "la interfaz no se estabilizó en {max_frames} frames"
        )))
    }

    fn move_to(&mut self, x: f32, y: f32) -> PyResult<()> {
        self.rt.pointer_move(x, y);
        self.step(FRAME).map(|_| ())
    }

    fn leave(&mut self) -> PyResult<()> {
        self.rt.pointer_leave();
        self.step(FRAME).map(|_| ())
    }

    fn mouse_down(&mut self) -> PyResult<()> {
        self.rt.pointer_down();
        self.step(FRAME).map(|_| ())
    }

    fn mouse_up(&mut self) -> PyResult<()> {
        let result = self.rt.pointer_up();
        // El frame se pinta igualmente: el manejador pudo cambiar estado antes de fallar.
        self.step(FRAME)?;
        result
    }

    fn click_at(&mut self, x: f32, y: f32) -> PyResult<()> {
        self.move_to(x, y)?;
        self.mouse_down()?;
        self.mouse_up()
    }

    /// Clic en el centro del nodo `key`, como lo haría una persona: si otro
    /// nodo lo tapa, el clic llega a ese otro.
    fn click(&mut self, key: &str) -> PyResult<()> {
        let rect = self.rt.rect(key).ok_or_else(|| {
            PyLookupError::new_err(format!("no hay ningún nodo pintado con key {key:?}"))
        })?;
        let c = rect.center();
        self.click_at(c.x, c.y)
    }

    /// `(x, y, ancho, alto)` del nodo en el último frame, o `None` si no se pintó.
    fn rect(&self, key: &str) -> Option<(f32, f32, f32, f32)> {
        self.rt
            .rect(key)
            .map(|r| (r.left, r.top, r.width(), r.height()))
    }

    #[getter]
    fn hovered(&self) -> Option<String> {
        self.rt.hovered().map(str::to_owned)
    }

    fn resize(&mut self, width: f32, height: f32) -> PyResult<()> {
        self.surface = new_surface(width, height, self.scale)?;
        self.width = width;
        self.height = height;
        self.step(FRAME).map(|_| ())
    }

    /// Guarda el último frame pintado como PNG.
    fn png(&mut self, path: &str) -> PyResult<()> {
        write_png(&mut self.surface, path).map_err(PyRuntimeError::new_err)
    }
}
