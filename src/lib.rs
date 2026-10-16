//! aurora._core — núcleo nativo: layout, render, eventos y animaciones.

mod canvas;
mod chart;
mod color;
mod edit;
mod image;
mod input;
mod keys;
mod pilot;
mod render;
mod runtime;
mod scroll;
mod spec;
mod surface;
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

/// Abre una ventana y ejecuta el bucle de eventos hasta que se cierre.
/// `build` es un callable sin argumentos que devuelve el árbol de la vista.
/// `backend`: `"auto"` (GPU si se puede, si no CPU), `"gpu"` o `"cpu"`.
#[pyfunction]
#[pyo3(signature = (build, title = "Aurora".to_string(), width = 960.0, height = 640.0, backend = "auto"))]
fn run(
    py: Python<'_>,
    build: Py<PyAny>,
    title: String,
    width: f64,
    height: f64,
    backend: &str,
) -> PyResult<()> {
    window::run(py, build, title, width, height, backend)
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
    m.add_class::<pilot::Pilot>()?;
    m.add_class::<keys::KeyEvent>()?;
    m.add_class::<scroll::ScrollEvent>()?;
    m.add_class::<runtime::DragEvent>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
