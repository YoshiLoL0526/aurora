//! Piloto headless: conduce una app sin ventana, simulando el puntero frame a
//! frame. Usa el mismo `Runtime` que la ventana, así que un test que pasa con
//! el piloto ejercita el mismo hit-testing, burbujeo y reconstrucción.

use std::path::PathBuf;

use pyo3::exceptions::{PyLookupError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use skia_safe::{Point, Surface};

use crate::keys::KeyInput;
use crate::render::{raster_surface, write_png};
use crate::runtime::{Clipboard, Runtime};
use crate::scroll::LINE;
use accesskit::{Action, ActionData};

/// Paso de tiempo de un frame simulado.
const FRAME: f32 = 1.0 / 60.0;

#[pyclass(unsendable, module = "aurora._core")]
pub struct Pilot {
    rt: Runtime,
    width: f32,
    height: f32,
    scale: f32,
    surface: Surface,
    /// La superficie es nueva (aún no tiene ningún frame): se pinta entera.
    fresh: bool,
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
        // La superficie conserva el último frame: solo se repinta lo que cambió.
        let age = if std::mem::take(&mut self.fresh) {
            0
        } else {
            1
        };
        let (hover_changed, _) =
            self.rt
                .draw_frame(canvas, self.width, self.height, self.scale, age)?;
        // Un `on_scroll` puede haber vuelto a cambiar un `Signal`: queda otro frame.
        Ok(animating || hover_changed || self.rt.needs_sync() || self.rt.animating())
    }
}

fn paths(files: Vec<PathBuf>) -> Vec<String> {
    files
        .into_iter()
        .map(|p| p.to_string_lossy().into_owned())
        .collect()
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
    #[pyo3(signature = (build, width = 960.0, height = 640.0, scale = 1.0, inspector = false))]
    fn new(
        build: Py<PyAny>,
        width: f32,
        height: f32,
        scale: f32,
        inspector: bool,
    ) -> PyResult<Self> {
        let mut pilot = Self {
            rt: Runtime::new(build, Clipboard::Memory(String::new()), inspector),
            width,
            height,
            scale,
            surface: new_surface(width, height, scale)?,
            fresh: true,
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
        let result = self.rt.pointer_move(x, y);
        self.step(FRAME)?;
        result.map(drop)
    }

    /// Arrastra desde el centro de `key` desplazando `(dx, dy)` en `steps`
    /// movimientos, y suelta.
    #[pyo3(signature = (key, dx = 0.0, dy = 0.0, steps = 4))]
    fn drag(&mut self, key: &str, dx: f32, dy: f32, steps: u32) -> PyResult<()> {
        let from = self.center(key)?;
        self.move_to(from.x, from.y)?;
        self.mouse_down()?;
        let steps = steps.max(1);
        for i in 1..=steps {
            let t = i as f32 / steps as f32;
            self.move_to(from.x + dx * t, from.y + dy * t)?;
        }
        self.mouse_up()
    }

    /// Cursor del ratón en el último frame (`"default"`, `"pointer"`, `"col-resize"`…).
    #[getter]
    fn cursor(&self) -> &'static str {
        use crate::runtime::CursorKind as C;
        match self.rt.cursor() {
            C::Default => "default",
            C::Pointer => "pointer",
            C::Text => "text",
            C::Grab => "grab",
            C::Grabbing => "grabbing",
            C::ColResize => "col-resize",
            C::RowResize => "row-resize",
            C::Crosshair => "crosshair",
        }
    }

    /// Archivos del sistema que empiezan a pasar sobre la ventana, o `None`
    /// cuando el arrastre sale sin soltar (avisa a los `on_drop_hover`).
    fn hover_files(&mut self, files: Option<Vec<PathBuf>>) -> PyResult<()> {
        let files = files.map(paths);
        let result = self.rt.files_hover(files.as_deref());
        self.step(FRAME)?;
        result
    }

    /// Suelta archivos del sistema sobre el centro de `key`, en `at=(x, y)` o,
    /// sin ninguno de los dos, sin posición (como en macOS y Linux, donde el
    /// sistema no la da). Devuelve si algún `on_drop` los recibió.
    #[pyo3(signature = (files, key = None, at = None))]
    fn drop_files(
        &mut self,
        files: Vec<PathBuf>,
        key: Option<&str>,
        at: Option<(f32, f32)>,
    ) -> PyResult<bool> {
        let at = match key {
            Some(key) => {
                let c = self.center(key)?;
                Some((c.x, c.y))
            }
            None => at,
        };
        let result = self.rt.files_drop(&paths(files), at);
        self.step(FRAME)?;
        result
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

    /// Árbol de accesibilidad del último frame: lo que ve un lector de pantalla.
    /// Una lista de dicts por nodo con `id`, `key`, `role`, `label`, `value`,
    /// estados (`checked`, `selected`, `expanded`…), `bounds` en píxeles lógicos,
    /// `actions`, `children` y `focused`. Lo decorativo y lo `hidden` no aparece.
    fn a11y_tree<'py>(&mut self, py: Python<'py>) -> PyResult<Bound<'py, PyList>> {
        let built = self.rt.a11y_build(self.width, self.height, self.scale);
        crate::a11y::to_dicts(py, &built, self.scale)
    }

    /// Pide una acción de accesibilidad sobre el nodo `key`, como la pediría un
    /// lector de pantalla: `"click"`, `"focus"`, `"blur"`, `"set_value"` (con
    /// `value`: texto o número), `"increment"`, `"decrement"`, `"expand"`,
    /// `"collapse"` o `"scroll_into_view"`. `LookupError` si el nodo no está en
    /// el árbol de accesibilidad.
    #[pyo3(signature = (key, action, value = None))]
    fn a11y_action(
        &mut self,
        key: &str,
        action: &str,
        value: Option<Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let action = match action {
            "click" => Action::Click,
            "focus" => Action::Focus,
            "blur" => Action::Blur,
            "set_value" => Action::SetValue,
            "increment" => Action::Increment,
            "decrement" => Action::Decrement,
            "expand" => Action::Expand,
            "collapse" => Action::Collapse,
            "scroll_into_view" => Action::ScrollIntoView,
            other => {
                return Err(PyValueError::new_err(format!(
                    "acción desconocida: {other:?} (click, focus, blur, set_value, increment, \
                     decrement, expand, collapse, scroll_into_view)"
                )));
            }
        };
        let data = match value {
            None => None,
            Some(v) => match v.extract::<String>() {
                Ok(text) => Some(ActionData::Value(text.into_boxed_str())),
                Err(_) => {
                    Some(ActionData::NumericValue(v.extract().map_err(|_| {
                        PyValueError::new_err("value debe ser texto o número")
                    })?))
                }
            },
        };
        let Some(id) = self.rt.a11y.node_id(key).or_else(|| {
            // El árbol puede no haberse construido todavía: construirlo lo registra.
            let _ = self.rt.a11y_build(self.width, self.height, self.scale);
            self.rt.a11y.node_id(key)
        }) else {
            return Err(PyLookupError::new_err(format!(
                "no hay ningún nodo de accesibilidad con key {key:?}"
            )));
        };
        self.rt.a11y_action(id, action, data)?;
        self.step(FRAME).map(drop)
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

    /// Ventana visible del eje x del `chart` con esa key, en unidades de datos
    /// (sin zoom, su dominio completo). `None` si no hay un gráfico con esa key.
    fn chart_view(&self, key: &str) -> Option<(f64, f64)> {
        self.rt.chart_view(key)
    }

    /// `(x, y, ancho, alto)` del nodo en el último frame, o `None` si no se pintó.
    fn rect(&self, key: &str) -> Option<(f32, f32, f32, f32)> {
        self.rt
            .rect(key)
            .map(|r| (r.left, r.top, r.width(), r.height()))
    }

    /// Coste por fases del último frame, en milisegundos: `build` (Python),
    /// `parse`, `style`, `layout`, `draw` (los `canvas` y los `chart`), `paint`
    /// y `total` (su suma); además `nodes`, `rebuilt`, `layout_cached` y
    /// `damage`, la zona repintada `(x, y, ancho, alto)` o `None` si no se pintó nada.
    #[getter]
    fn stats<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        self.rt.stats.to_dict(py)
    }

    /// Estado del inspector (como `_core.inspection()` dentro de la vista), o
    /// `None` si el piloto se creó sin inspector.
    #[getter]
    fn inspection<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyDict>>> {
        let inspector = &self.rt.inspector;
        inspector.enabled.then(|| inspector.to_dict(py)).transpose()
    }

    #[getter]
    fn hovered(&self) -> Option<String> {
        self.rt.hovered().map(str::to_owned)
    }

    fn resize(&mut self, width: f32, height: f32) -> PyResult<()> {
        self.surface = new_surface(width, height, self.scale)?;
        self.fresh = true;
        self.width = width;
        self.height = height;
        self.step(FRAME).map(|_| ())
    }

    /// Guarda el último frame pintado como PNG.
    fn png(&mut self, path: &str) -> PyResult<()> {
        write_png(&mut self.surface, path).map_err(PyRuntimeError::new_err)
    }
}
