//! Archivos arrastrados desde el sistema: `on_drop_hover` mientras pasan sobre
//! la ventana y `on_drop` al soltarlos.

use pyo3::types::PyList;

use super::*;

/// Claves de los nodos con manejador `event`, en orden del árbol.
fn with_handler(node: &Node, event: &str, out: &mut Vec<String>) {
    if node.handler(event).is_some() {
        out.push(node.key.clone());
    }
    for child in &node.children {
        with_handler(child, event, out);
    }
}

impl Runtime {
    /// Última posición conocida del puntero en la ventana (píxeles lógicos).
    pub fn pointer(&self) -> Option<(f32, f32)> {
        self.pointer
    }

    fn keys_with(&self, event: &str) -> Vec<String> {
        let mut keys = Vec::new();
        if let Some(tree) = &self.tree {
            with_handler(tree, event, &mut keys);
        }
        keys
    }

    /// Archivos que empiezan a pasar sobre la ventana (`Some`) o que dejan de
    /// hacerlo (`None`: se fueron o se soltaron). Avisa a todos los
    /// `on_drop_hover` de la vista: mientras se arrastra, el sistema no dice
    /// sobre qué punto está el puntero, así que el aviso es de toda la ventana.
    pub fn files_hover(&mut self, files: Option<&[String]>) -> PyResult<()> {
        if files.is_none() && !self.files_hovering {
            return Ok(());
        }
        self.files_hovering = files.is_some();
        let mut first_err = None;
        for key in self.keys_with("drop_hover") {
            let arg = Python::attach(|py| -> PyResult<Py<PyAny>> {
                Ok(match files {
                    Some(files) => PyList::new(py, files)?.into_any().unbind(),
                    None => py.None(),
                })
            })?;
            if let Err(err) = self.dispatch(&key, "drop_hover", Some(arg)) {
                first_err.get_or_insert(err);
            }
        }
        first_err.map_or(Ok(()), Err)
    }

    /// Suelta archivos sobre la ventana: los recibe el primer ancestro con
    /// `on_drop` del nodo bajo `at` (píxeles lógicos). Si el sistema no dio la
    /// posición, el primer `on_drop` de la vista. Devuelve si alguien los recibió.
    pub fn files_drop(&mut self, files: &[String], at: Option<(f32, f32)>) -> PyResult<bool> {
        let hover = self.files_hover(None);
        let target = match at {
            Some((x, y)) => self.tree.as_ref().and_then(|tree| {
                ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
                    .filter_map(|region| tree.find(&region.key))
                    .find(|node| node.handler("drop").is_some())
                    .map(|node| node.key.clone())
            }),
            None => self.keys_with("drop").into_iter().next(),
        };
        let Some(key) = target else {
            return hover.map(|_| false);
        };
        let arg = Python::attach(|py| PyList::new(py, files).map(|l| l.into_any().unbind()))?;
        let dropped = self.dispatch(&key, "drop", Some(arg))?;
        hover.map(|_| dropped)
    }
}
