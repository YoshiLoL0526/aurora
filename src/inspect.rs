//! Inspector visual del árbol y profiler de frames (herramientas de desarrollo).
//!
//! El panel se construye en Python (`aurora/inspector.py`) con las mismas
//! primitivas que cualquier app. Aquí vive lo que no puede vivir allí: el modo
//! selección (recorrer la interfaz con el ratón sin tocar Python), el
//! resaltado del nodo sobre la interfaz y el historial de frames con el coste
//! de cada fase.
//!
//! El estado pertenece a cada `Runtime`, que se lo presta a Python mientras
//! ejecuta la vista o un manejador (`lend`): las funciones `inspection`,
//! `inspect_open`, `inspect_pick` e `inspect_select` de `_core` leen y cambian
//! el del runtime en curso. Con el inspector desactivado no se presta nada y
//! el coste es nulo.

use std::cell::RefCell;
use std::collections::VecDeque;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use skia_safe::Rect;

use crate::runtime::FrameStats;

/// Key del panel del inspector: lo que hay dentro no se puede seleccionar.
pub const PANEL_KEY: &str = "aurora:inspector";

/// Frames que recuerda el profiler.
pub const HISTORY: usize = 240;

/// Cada cuánto (segundos) se refresca el panel mientras llegan frames nuevos.
pub const REFRESH: f32 = 0.25;

#[derive(Default)]
pub struct Inspector {
    /// La app lo permite (`App(inspector=True)` o `AURORA_INSPECTOR=1`).
    pub enabled: bool,
    /// El panel está abierto (F12).
    pub open: bool,
    /// Modo selección: pasar el ratón resalta nodos y un clic elige uno.
    pub pick: bool,
    /// Nodo elegido, por key.
    pub selected: Option<String>,
    /// Nodo bajo el puntero en modo selección.
    pub hovered: Option<String>,
    /// Coste de los últimos frames, del más antiguo al más reciente.
    pub frames: VecDeque<FrameStats>,
    /// Rectángulo del nodo elegido en el último frame (lo rellena el runtime
    /// antes de prestar el estado).
    pub selected_rect: Option<Rect>,
    /// Segundos hasta refrescar el panel con los frames nuevos.
    refresh_in: Option<f32>,
    /// Franja vertical `(top, bottom)` del contenido de un `scroll` que hay que
    /// mostrar tras el próximo layout (la fila del nodo elegido en el árbol,
    /// que en una lista virtual quizá aún no existe).
    pub reveal: Option<(String, f32, f32)>,
    /// La reconstrucción en curso es un refresco del panel: su frame no se
    /// registra (si no, cada refresco pediría otro).
    refreshing: bool,
}

impl Inspector {
    pub fn new(enabled: bool) -> Self {
        Self {
            enabled,
            ..Self::default()
        }
    }

    /// Abre o cierra el panel. Al cerrarlo se sale del modo selección.
    pub fn set_open(&mut self, open: bool) {
        self.open = open;
        if !open {
            self.set_pick(false);
            self.refresh_in = None;
        }
    }

    /// Entra o sale del modo selección. Entrar abre el panel.
    pub fn set_pick(&mut self, pick: bool) {
        self.pick = pick;
        if pick {
            self.open = true;
        } else {
            self.hovered = None;
        }
    }

    /// Registra el coste de un frame recién pintado. Los que no hicieron nada
    /// (ni reconstruir ni pintar) no cuentan.
    pub fn record(&mut self, stats: FrameStats) {
        if std::mem::take(&mut self.refreshing) || !stats.rebuilt && stats.damage.is_none() {
            return;
        }
        if self.frames.len() == HISTORY {
            self.frames.pop_front();
        }
        self.frames.push_back(stats);
        if self.open && self.refresh_in.is_none() {
            self.refresh_in = Some(REFRESH);
        }
    }

    /// Avanza el reloj del refresco.
    pub fn advance(&mut self, elapsed: f32) {
        if let Some(t) = &mut self.refresh_in {
            *t -= elapsed;
        }
    }

    /// Segundos hasta el próximo refresco, si hay uno pendiente.
    pub fn next_refresh(&self) -> Option<f32> {
        self.refresh_in.map(|t| t.max(0.0))
    }

    /// Si toca refrescar el panel. Lo consume: la próxima reconstrucción es el
    /// refresco y su frame no se registra.
    pub fn take_refresh(&mut self) -> bool {
        if self.open && self.refresh_in.is_some_and(|t| t <= 0.0) {
            self.refresh_in = None;
            self.refreshing = true;
            return true;
        }
        false
    }

    /// Si la reconstrucción en curso es un refresco del panel.
    pub fn refreshing(&self) -> bool {
        self.refreshing
    }

    /// Una reconstrucción que no era el refresco (un evento llegó a la vez)
    /// sí se registra.
    pub fn cancel_refresh(&mut self) {
        self.refreshing = false;
    }

    /// Estado que ve Python, como dict. Los frames solo con el panel abierto.
    pub fn to_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let out = PyDict::new(py);
        out.set_item("open", self.open)?;
        out.set_item("pick", self.pick)?;
        out.set_item("selected", self.selected.as_deref())?;
        out.set_item("hovered", self.hovered.as_deref())?;
        out.set_item(
            "rect",
            self.selected_rect
                .map(|r| (r.left, r.top, r.width(), r.height())),
        )?;
        let frames = PyList::empty(py);
        if self.open {
            for f in &self.frames {
                frames.append(f.to_dict(py)?)?;
            }
        }
        out.set_item("frames", frames)?;
        Ok(out)
    }
}

thread_local! {
    /// Estado del runtime que está ejecutando Python ahora mismo. La ventana,
    /// el piloto y la vista corren en el mismo hilo.
    static CURRENT: RefCell<Option<Inspector>> = const { RefCell::new(None) };
}

/// Presta el estado a Python mientras dura `f` (si el inspector está activado).
pub fn lend<R>(inspector: &mut Inspector, f: impl FnOnce() -> R) -> R {
    if !inspector.enabled {
        return f();
    }
    let outer = CURRENT.with(|c| c.replace(Some(std::mem::take(inspector))));
    let result = f();
    *inspector = CURRENT.with(|c| c.replace(outer)).unwrap_or_default();
    result
}

fn with_current<R>(f: impl FnOnce(&mut Inspector) -> R) -> PyResult<R> {
    CURRENT.with(|c| match c.borrow_mut().as_mut() {
        Some(inspector) => Ok(f(inspector)),
        None => Err(PyRuntimeError::new_err(
            "el inspector solo se controla desde la vista o un manejador de una app \
             con el inspector activado",
        )),
    })
}

/// Estado del inspector de la app en curso, o `None` si no hay ninguna app
/// construyendo la vista o ejecutando un manejador con el inspector activado.
#[pyfunction]
pub fn inspection(py: Python<'_>) -> PyResult<Option<Bound<'_, PyDict>>> {
    CURRENT.with(|c| c.borrow().as_ref().map(|i| i.to_dict(py)).transpose())
}

/// Abre o cierra el panel del inspector.
#[pyfunction]
pub fn inspect_open(open: bool) -> PyResult<()> {
    with_current(|i| i.set_open(open))
}

/// Entra o sale del modo selección.
#[pyfunction]
pub fn inspect_pick(pick: bool) -> PyResult<()> {
    with_current(|i| i.set_pick(pick))
}

/// Elige el nodo `key` (o ninguno).
#[pyfunction]
#[pyo3(signature = (key))]
pub fn inspect_select(key: Option<String>) -> PyResult<()> {
    with_current(|i| i.selected = key)
}

/// Desplaza el `scroll` con esa key para mostrar la franja `top..bottom` de su
/// contenido (en píxeles desde su inicio) tras el próximo layout.
#[pyfunction]
pub fn inspect_reveal(key: String, top: f32, bottom: f32) -> PyResult<()> {
    with_current(|i| i.reveal = Some((key, top, bottom)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn busy() -> FrameStats {
        FrameStats {
            rebuilt: true,
            ..FrameStats::default()
        }
    }

    fn open() -> Inspector {
        let mut i = Inspector::new(true);
        i.set_open(true);
        i
    }

    #[test]
    fn history_keeps_only_the_last_frames() {
        let mut i = open();
        for _ in 0..HISTORY + 10 {
            i.record(busy());
        }
        assert_eq!(i.frames.len(), HISTORY);
    }

    #[test]
    fn a_refresh_frame_is_not_recorded_and_does_not_ask_for_another() {
        let mut i = open();
        i.record(busy());
        assert_eq!(i.next_refresh(), Some(REFRESH));
        i.advance(REFRESH);
        assert!(i.take_refresh());
        i.record(busy());
        assert_eq!(i.frames.len(), 1);
        assert_eq!(i.next_refresh(), None);
    }

    #[test]
    fn frames_that_did_nothing_are_not_recorded() {
        let mut i = open();
        i.record(FrameStats::default());
        assert!(i.frames.is_empty());
    }

    #[test]
    fn closing_leaves_pick_mode() {
        let mut i = Inspector::new(true);
        i.set_pick(true);
        assert!(i.open);
        i.hovered = Some("a".into());
        i.set_open(false);
        assert!(!i.pick && i.hovered.is_none());
    }
}
