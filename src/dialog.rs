//! Diálogos nativos del sistema: abrir y guardar archivos y carpetas (`rfd`).
//!
//! Son **síncronos**: mientras el diálogo está abierto el sistema corre su
//! propio bucle de mensajes y el bucle de la app espera, pero el GIL se suelta
//! (`Python::detach`), así que los hilos y las corrutinas de Python siguen
//! trabajando. La ventana desde la que se llama (su vista o uno de sus
//! manejadores) es el padre del diálogo: sale modal sobre ella.

use std::path::PathBuf;

use pyo3::prelude::*;

use crate::window;

/// Filtros tal y como llegan de Python: pares `(nombre, extensiones)`.
type Filters = Option<Vec<(String, Vec<String>)>>;

fn dialog(title: Option<String>, directory: Option<PathBuf>, filters: Filters) -> rfd::FileDialog {
    let mut dialog = rfd::FileDialog::new();
    if let Some(title) = title {
        dialog = dialog.set_title(title);
    }
    if let Some(directory) = directory {
        dialog = dialog.set_directory(directory);
    }
    if let Some(filters) = filters {
        for (name, extensions) in filters {
            let extensions: Vec<&str> = extensions.iter().map(String::as_str).collect();
            dialog = dialog.add_filter(name, &extensions);
        }
    }
    dialog
}

/// Cuelga el diálogo de la ventana en curso (la que está ejecutando Python).
fn as_modal(dialog: rfd::FileDialog) -> rfd::FileDialog {
    match window::current() {
        Some(window) => dialog.set_parent(&*window),
        None => dialog,
    }
}

fn path_of(path: PathBuf) -> String {
    path.to_string_lossy().into_owned()
}

/// Pide un archivo existente. Devuelve su ruta, o `None` si se cancela.
#[pyfunction]
#[pyo3(signature = (title = None, directory = None, filters = None))]
pub fn open_file(
    py: Python<'_>,
    title: Option<String>,
    directory: Option<PathBuf>,
    filters: Filters,
) -> Option<String> {
    let dialog = dialog(title, directory, filters);
    py.detach(move || as_modal(dialog).pick_file().map(path_of))
}

/// Pide uno o varios archivos existentes. Devuelve sus rutas (vacío si se cancela).
#[pyfunction]
#[pyo3(signature = (title = None, directory = None, filters = None))]
pub fn open_files(
    py: Python<'_>,
    title: Option<String>,
    directory: Option<PathBuf>,
    filters: Filters,
) -> Vec<String> {
    let dialog = dialog(title, directory, filters);
    py.detach(move || {
        as_modal(dialog)
            .pick_files()
            .unwrap_or_default()
            .into_iter()
            .map(path_of)
            .collect()
    })
}

/// Pide dónde guardar. Devuelve la ruta elegida, o `None` si se cancela.
/// No escribe nada: guardar es cosa de quien llama.
#[pyfunction]
#[pyo3(signature = (title = None, directory = None, default_name = None, filters = None))]
pub fn save_file(
    py: Python<'_>,
    title: Option<String>,
    directory: Option<PathBuf>,
    default_name: Option<String>,
    filters: Filters,
) -> Option<String> {
    let mut dialog = dialog(title, directory, filters);
    if let Some(name) = default_name {
        dialog = dialog.set_file_name(name);
    }
    py.detach(move || as_modal(dialog).save_file().map(path_of))
}

/// Pide una carpeta. Devuelve su ruta, o `None` si se cancela.
#[pyfunction]
#[pyo3(signature = (title = None, directory = None))]
pub fn pick_folder(
    py: Python<'_>,
    title: Option<String>,
    directory: Option<PathBuf>,
) -> Option<String> {
    let dialog = dialog(title, directory, None);
    py.detach(move || as_modal(dialog).pick_folder().map(path_of))
}
