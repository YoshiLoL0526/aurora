//! Notificaciones del sistema (`notify-rust`): avisos del Centro de
//! notificaciones de Windows y macOS y de los demonios libnotify de Linux/BSD.
//!
//! El aviso lo muestra el sistema, así que se envía desde el hilo del bucle
//! (macOS lo prefiere): `notify` manda un comando si hay uno en marcha y, si
//! no (scripts, tests), lo envía en el hilo que llama. Si el sistema no admite
//! notificaciones, se avisa por stderr y la app sigue.

use std::path::PathBuf;

use pyo3::prelude::*;

use crate::window::{self, Command};

/// Una notificación pedida desde Python (todo `Send`: viaja al bucle).
#[derive(Debug)]
pub struct Notify {
    pub summary: String,
    pub body: String,
    /// Un archivo de imagen (PNG/SVG); donde el sistema no lo admite, se ignora.
    pub icon: Option<PathBuf>,
    /// La identidad de la app en Windows (AUMID): sin ella el aviso lo firma
    /// el AUMID de reserva de PowerShell.
    pub app_id: Option<String>,
}

/// Envía la notificación en el hilo actual.
pub fn send(config: &Notify) -> Result<(), String> {
    let mut notification = notify_rust::Notification::new();
    notification.summary(&config.summary).body(&config.body);
    if let Some(icon) = &config.icon {
        let path = icon.to_string_lossy();
        // En el escritorio Linux el icono del aviso es `icon`; en Windows y
        // macOS `icon` no se usa y la imagen va como `image_path`.
        #[cfg(all(unix, not(target_os = "macos")))]
        notification.icon(&path);
        #[cfg(not(all(unix, not(target_os = "macos"))))]
        notification.image_path(&path);
    }
    #[cfg(target_os = "windows")]
    if let Some(app_id) = &config.app_id {
        notification.app_id(app_id);
    }
    #[cfg(not(target_os = "windows"))]
    let _ = &config.app_id;
    notification.show().map(drop).map_err(|err| err.to_string())
}

/// Muestra una notificación del sistema. Segura desde cualquier hilo.
#[pyfunction]
#[pyo3(signature = (summary, body = String::new(), icon = None, app_id = None))]
pub fn notify(summary: String, body: String, icon: Option<PathBuf>, app_id: Option<String>) {
    let config = Notify {
        summary,
        body,
        icon,
        app_id,
    };
    if window::running() {
        window::send(Command::Notify(config));
    } else if let Err(err) = send(&config) {
        eprintln!("aurora: no se pudo notificar: {err}");
    }
}
