//! Acciones de accesibilidad: lo que un lector de pantalla pide hacer sobre un
//! nodo (enfocar, activar, escribir un valor, ajustar un deslizador o
//! desplazarse hasta él). El adaptador de la ventana las recibe de AccessKit
//! (`window.rs`) y el piloto las simula en los tests.

use super::*;
use accesskit::{Action, ActionData, NodeId};
use pyo3::exceptions::PyValueError;
use pyo3::types::PyFloat;

impl Runtime {
    /// Atiende la acción pedida por un lector sobre el nodo `id`. Devuelve
    /// `false` si el nodo no está en el árbol o la acción no aplica.
    pub fn a11y_action(
        &mut self,
        id: NodeId,
        action: Action,
        data: Option<ActionData>,
    ) -> PyResult<bool> {
        let Some(key) = self.a11y.key_of(id).map(str::to_owned) else {
            return Ok(false);
        };
        match action {
            // El foco de un lector no enseña el anillo (no viene del teclado).
            Action::Focus => {
                self.reveal_focus = true;
                self.focus(Some(key))?;
                Ok(true)
            }
            Action::Blur => {
                if self.focused() == Some(key.as_str()) {
                    self.focus(None)?;
                }
                Ok(true)
            }
            // Activar, desplegar y plegar son el mismo clic del componente.
            Action::Click | Action::Expand | Action::Collapse => self.dispatch(&key, "click", None),
            Action::SetValue => self.a11y_set_value(&key, data),
            // Un deslizador se ajusta con las mismas teclas que a mano.
            Action::Increment => self.a11y_press(&key, "ArrowRight"),
            Action::Decrement => self.a11y_press(&key, "ArrowLeft"),
            Action::ScrollIntoView => Ok(self.reveal_key(&key)),
            _ => Ok(false),
        }
    }

    /// `SetValue`: escribe en un campo de texto, o fija el valor de un control
    /// que declara `on_value` (un deslizador).
    fn a11y_set_value(&mut self, key: &str, data: Option<ActionData>) -> PyResult<bool> {
        match data {
            Some(ActionData::Value(text)) => {
                let Some(state) = self.engine.inputs.get_mut(key) else {
                    return Ok(false);
                };
                let before = state.editor.text().to_owned();
                if before == *text {
                    return Ok(true);
                }
                state.editor.set_external(&text);
                self.after_edit(key, &before, false)?;
                Ok(true)
            }
            Some(ActionData::NumericValue(value)) => {
                let arg: Py<PyAny> =
                    Python::attach(|py| PyFloat::new(py, value).into_any().unbind());
                self.dispatch(key, "value", Some(arg))
            }
            _ => Ok(false),
        }
    }

    /// Pulsa una tecla como si `key` tuviera el foco (acciones de ajuste).
    fn a11y_press(&mut self, key: &str, combo: &str) -> PyResult<bool> {
        let input = KeyInput::from_combo(combo).map_err(PyValueError::new_err)?;
        self.dispatch_key_from(key, &input)
    }
}
