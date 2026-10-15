//! aurora._core — núcleo nativo: layout, render, eventos y animaciones.

mod color;
mod render;
mod spec;
mod window;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

/// Renderiza un árbol de vista a PNG sin abrir ventana.
#[pyfunction]
#[pyo3(signature = (tree, width, height, path, scale = 2.0))]
fn render_png(tree: &Bound<'_, PyAny>, width: f32, height: f32, path: &str, scale: f32) -> PyResult<()> {
    let node = spec::parse(tree)?;
    render::render_png(&node, width, height, scale, path).map_err(PyRuntimeError::new_err)
}

/// Abre una ventana y ejecuta el bucle de eventos hasta que se cierre.
/// `build` es un callable sin argumentos que devuelve el árbol de la vista.
#[pyfunction]
#[pyo3(signature = (build, title = "Aurora".to_string(), width = 960.0, height = 640.0))]
fn run(py: Python<'_>, build: Py<PyAny>, title: String, width: f64, height: f64) -> PyResult<()> {
    window::run(py, build, title, width, height)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(render_png, m)?)?;
    m.add_function(wrap_pyfunction!(run, m)?)?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
