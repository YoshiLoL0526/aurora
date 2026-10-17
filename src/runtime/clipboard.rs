//! Portapapeles del sistema o en memoria (piloto y tests deterministas).

use super::*;

/// Portapapeles del sistema (ventana) o en memoria (piloto, tests deterministas).
pub enum Clipboard {
    System(Option<arboard::Clipboard>),
    Memory(String),
}

impl Clipboard {
    pub fn get(&mut self) -> Option<String> {
        match self {
            Clipboard::System(slot) => system(slot)?.get_text().ok(),
            Clipboard::Memory(text) => Some(text.clone()),
        }
    }

    pub fn set(&mut self, text: String) {
        match self {
            Clipboard::System(slot) => {
                if let Some(cb) = system(slot) {
                    let _ = cb.set_text(text);
                }
            }
            Clipboard::Memory(slot) => *slot = text,
        }
    }
}

/// El portapapeles del sistema se abre una vez y se conserva: en X11 su
/// contenido vive mientras viva el objeto.
fn system(slot: &mut Option<arboard::Clipboard>) -> Option<&mut arboard::Clipboard> {
    if slot.is_none() {
        *slot = arboard::Clipboard::new().ok();
    }
    slot.as_mut()
}

impl Runtime {
    pub fn clipboard(&mut self) -> &mut Clipboard {
        &mut self.clipboard
    }
}
