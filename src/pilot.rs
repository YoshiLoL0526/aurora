//! Piloto headless: conduce una app sin ventana, simulando el puntero frame a
//! frame. Usa el mismo `Runtime` que la ventana, así que un test que pasa con
//! el piloto ejercita el mismo hit-testing, burbujeo y reconstrucción.

use pyo3::exceptions::{PyLookupError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;
use skia_safe::{Point, Surface};

use crate::keys::KeyInput;
use crate::render::{raster_surface, write_png};
use crate::runtime::{Clipboard, Runtime};
use crate::scroll::LINE;

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
    fn center(&self, key: &str) -> PyResult<Point> {
        self.rt.rect(key).map(|r| r.center()).ok_or_else(|| {
            PyLookupError::new_err(format!("no hay ningún nodo pintado con key {key:?}"))
        })
    }

    fn step(&mut self, dt: f32) -> PyResult<bool> {
        self.rt.sync()?;
        let animating = self.rt.tick(dt);
        self.rt.advance_clock(dt);
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
            rt: Runtime::new(build, Clipboard::Memory(String::new())),
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
        let result = self.rt.pointer_down();
        self.step(FRAME)?;
        result
    }

    /// Pulsa y suelta una tecla o combinación: `"tab"`, `"shift+tab"`,
    /// `"enter"`, `"ctrl+s"`, `"a"`…
    fn press(&mut self, combo: &str) -> PyResult<()> {
        self.key_down(combo)?;
        self.key_up(combo)
    }

    /// Mantiene pulsada una tecla (sin soltarla).
    fn key_down(&mut self, combo: &str) -> PyResult<()> {
        let input = KeyInput::from_combo(combo).map_err(PyValueError::new_err)?;
        let result = self.rt.key_event(&input, true);
        self.step(FRAME)?;
        result.map(drop)
    }

    fn key_up(&mut self, combo: &str) -> PyResult<()> {
        let input = KeyInput::from_combo(combo).map_err(PyValueError::new_err)?;
        let result = self.rt.key_event(&input, false);
        self.step(FRAME)?;
        result.map(drop)
    }

    /// Escribe texto en el campo enfocado, grafema a grafema, como desde el teclado.
    fn r#type(&mut self, text: &str) -> PyResult<()> {
        use unicode_segmentation::UnicodeSegmentation;
        for g in text.graphemes(true) {
            let input = match g {
                "\n" => KeyInput::from_combo("enter").map_err(PyValueError::new_err)?,
                " " => KeyInput::from_combo("space").map_err(PyValueError::new_err)?,
                _ => KeyInput {
                    key: g.to_owned(),
                    text: Some(g.to_owned()),
                    mods: Default::default(),
                    repeat: false,
                },
            };
            let down = self.rt.key_event(&input, true);
            self.rt.key_event(&input, false)?;
            self.step(FRAME)?;
            down?;
        }
        Ok(())
    }

    /// Simula la composición de un IME (texto aún sin confirmar).
    fn ime_preedit(&mut self, text: &str) -> PyResult<()> {
        self.rt.ime_preedit(text);
        self.step(FRAME).map(drop)
    }

    /// Simula que el IME confirma texto.
    fn ime_commit(&mut self, text: &str) -> PyResult<()> {
        let result = self.rt.ime_commit(text);
        self.step(FRAME)?;
        result.map(drop)
    }

    /// Selección del campo `key` en caracteres: `(inicio, fin)`; iguales si solo hay cursor.
    fn selection(&self, key: &str) -> Option<(usize, usize)> {
        self.rt.selection(key)
    }

    /// Portapapeles del piloto (en memoria, no toca el del sistema).
    #[getter]
    fn get_clipboard(&mut self) -> String {
        self.rt.clipboard().get().unwrap_or_default()
    }

    #[setter]
    fn set_clipboard(&mut self, text: String) {
        self.rt.clipboard().set(text);
    }

    /// Enfoca `key` como si se llegara con el teclado. `LookupError` si no se
    /// pintó o no es enfocable.
    fn focus(&mut self, key: &str) -> PyResult<()> {
        if !self.rt.focus_key(key)? {
            return Err(PyLookupError::new_err(format!(
                "no hay ningún nodo enfocable pintado con key {key:?}"
            )));
        }
        self.step(FRAME).map(drop)
    }

    /// Texto del tooltip visible, o `None`.
    #[getter]
    fn tooltip(&self) -> Option<String> {
        self.rt.tooltip()
    }

    /// Key del nodo enfocado, o `None`.
    #[getter]
    fn focused(&self) -> Option<String> {
        self.rt.focused().map(str::to_owned)
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
        let c = self.center(key)?;
        self.click_at(c.x, c.y)
    }

    /// Rueda bajo el puntero. Positivo = hacia el final del contenido. Con
    /// `lines=True` cuenta pasos de rueda de ratón (animados); si no, píxeles
    /// de trackpad (inmediatos).
    #[pyo3(signature = (dy = 0.0, dx = 0.0, lines = false))]
    fn wheel(&mut self, dy: f32, dx: f32, lines: bool) -> PyResult<()> {
        let unit = if lines { LINE } else { 1.0 };
        self.rt.wheel(Point::new(dx * unit, dy * unit), lines);
        self.step(FRAME).map(|_| ())
    }

    /// Mueve el puntero al centro de `key` y desplaza `dy`/`dx` píxeles.
    #[pyo3(signature = (key, dy = 0.0, dx = 0.0))]
    fn scroll(&mut self, key: &str, dy: f32, dx: f32) -> PyResult<()> {
        let c = self.center(key)?;
        self.move_to(c.x, c.y)?;
        self.wheel(dy, dx, false)
    }

    /// `(x, y)` desplazados del contenedor `scroll` con esa key, o `None`.
    fn scroll_offset(&self, key: &str) -> Option<(f32, f32)> {
        self.rt.scroll_offset(key).map(|p| (p.x, p.y))
    }

    /// `(x, y, ancho, alto)` del nodo en el último frame, o `None` si no se pintó.
    fn rect(&self, key: &str) -> Option<(f32, f32, f32, f32)> {
        self.rt
            .rect(key)
            .map(|r| (r.left, r.top, r.width(), r.height()))
    }

    /// Coste por fases del último frame, en milisegundos: `build` (Python),
    /// `parse`, `layout` y `paint`; además `nodes`, `rebuilt` y `layout_cached`.
    #[getter]
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let s = self.rt.stats;
        let ms = |d: std::time::Duration| d.as_secs_f64() * 1000.0;
        let out = PyDict::new(py);
        out.set_item("build", ms(s.build))?;
        out.set_item("parse", ms(s.parse))?;
        out.set_item("layout", ms(s.layout))?;
        out.set_item("paint", ms(s.paint))?;
        out.set_item("nodes", s.nodes)?;
        out.set_item("rebuilt", s.rebuilt)?;
        out.set_item("layout_cached", s.layout_cached)?;
        Ok(out)
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
