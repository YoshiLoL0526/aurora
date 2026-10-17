//! aurora._core — núcleo nativo: layout, render, eventos y animaciones.

mod canvas;
mod chart;
mod color;
mod dialog;
mod edit;
mod identity;
mod image;
mod input;
mod inspect;
mod keys;
mod menu;
mod motion;
mod notify;
mod pilot;
mod render;
mod runtime;
mod scroll;
mod spec;
mod surface;
mod tray;
mod window;

use pyo3::prelude::*;

/// Renderiza un árbol de vista a PNG sin abrir ventana.
#[pyfunction]
#[pyo3(signature = (tree, width, height, path, scale = 2.0))]
fn render_png(
    tree: &Bound<'_, PyAny>,
    width: f32,
    height: f32,
    path: &str,
    scale: f32,
) -> PyResult<()> {
    let node = spec::parse(tree)?;
    render::render_png(&node, width, height, scale, path)
}

/// Abre las ventanas de la app y ejecuta el bucle de eventos hasta que se cierren.
/// `windows` es una lista de dicts (ver `window::parse_windows`); el primero es
/// la ventana principal: si no se puede crear, `run` falla.
/// `backend`: `"auto"` (GPU si se puede, si no CPU), `"gpu"` o `"cpu"`.
/// `inspector` permite abrir el inspector con F12 en cada ventana.
/// `keep_alive`: la app sigue viva (sin ventanas) hasta que se llame a `quit()`.
#[pyfunction]
#[pyo3(signature = (windows, backend = "auto", inspector = false, keep_alive = false, menu = None))]
fn run(
    py: Python<'_>,
    windows: &Bound<'_, PyAny>,
    backend: &str,
    inspector: bool,
    keep_alive: bool,
    menu: Option<Py<PyAny>>,
) -> PyResult<()> {
    window::run(py, windows, backend, inspector, keep_alive, menu)
}

/// Pide reconstruir la vista y despierta el bucle de eventos. Seguro desde
/// cualquier hilo; sin ventana abierta solo deja la marca para el próximo frame.
#[pyfunction]
fn wake() {
    runtime::wake();
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(render_png, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    m.add_function(wrap_pyfunction!(wake, m)?)?;
    m.add_function(wrap_pyfunction!(window::window_open, m)?)?;
    m.add_function(wrap_pyfunction!(window::window_close, m)?)?;
    m.add_function(wrap_pyfunction!(window::window_set, m)?)?;
    m.add_function(wrap_pyfunction!(window::quit, m)?)?;
    m.add_function(wrap_pyfunction!(dialog::open_file, m)?)?;
    m.add_function(wrap_pyfunction!(dialog::open_files, m)?)?;
    m.add_function(wrap_pyfunction!(dialog::save_file, m)?)?;
    m.add_function(wrap_pyfunction!(dialog::pick_folder, m)?)?;
    m.add_function(wrap_pyfunction!(tray::tray_show, m)?)?;
    m.add_function(wrap_pyfunction!(tray::tray_hide, m)?)?;
    m.add_function(wrap_pyfunction!(notify::notify, m)?)?;
    m.add_function(wrap_pyfunction!(identity::app_id_set, m)?)?;
    m.add_function(wrap_pyfunction!(identity::app_id_register, m)?)?;
    m.add_function(wrap_pyfunction!(inspect::inspection, m)?)?;
    m.add_function(wrap_pyfunction!(inspect::inspect_open, m)?)?;
    m.add_function(wrap_pyfunction!(inspect::inspect_pick, m)?)?;
    m.add_function(wrap_pyfunction!(inspect::inspect_select, m)?)?;
    m.add_function(wrap_pyfunction!(inspect::inspect_reveal, m)?)?;
    m.add_class::<pilot::Pilot>()?;
    m.add_class::<keys::KeyEvent>()?;
    m.add_class::<scroll::ScrollEvent>()?;
    m.add_class::<runtime::DragEvent>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
