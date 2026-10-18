//! Notificaciones del sistema (`notify-rust`): avisos del Centro de
//! notificaciones de Windows y macOS y de los demonios libnotify de Linux/BSD.
//!
//! El aviso lo muestra el sistema, así que se envía desde el hilo del bucle
//! (macOS lo prefiere): `notify` manda un comando si hay uno en marcha y, si
//! no (scripts, tests), lo envía en el hilo que llama. Si el sistema no admite
//! notificaciones, se avisa por stderr y la app sigue.
//!
//! Con `on_click`, un hilo propio espera la respuesta del aviso y llama al
//! callback de Python (el clic en el cuerpo es la acción «default» en las tres
//! plataformas); sin él, el handle se suelta y no se espera nada.

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
    /// Callback sin argumentos al pulsar el aviso; `None` si no se espera clic.
    pub on_click: Option<Py<PyAny>>,
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
    // En Linux y BSD el clic en el cuerpo llega como la acción «default»: los
    // servidores solo la emiten si el aviso la declara (y no la dibujan como
    // botón; xfce4-notifyd, que no la asocia al cuerpo, le pone un icono).
    #[cfg(all(unix, not(target_os = "macos")))]
    if config.on_click.is_some() {
        notification.action("default", "");
    }
    let handle = notification.show().map_err(|err| err.to_string())?;
    let Some(callback) = &config.on_click else {
        // Sin callback no hay nada que esperar: en macOS, soltar el handle envía el aviso.
        drop(handle);
        return Ok(());
    };
    let callback = Python::attach(|py| callback.clone_ref(py));
    std::thread::Builder::new()
        .name("aurora-notify".into())
        .spawn(move || {
            let _ = handle.wait_for_response(|response: &notify_rust::NotificationResponse| {
                // Solo el clic en el cuerpo: cerrar el aviso (o una acción que
                // no sea «default») no llama a nada.
                if !response.is_default_action() {
                    return;
                }
                // La respuesta llega fuera del hilo de Python: se toma el GIL
                // para llamar al callback y se despierta el bucle, por si el
                // callback cambió algo (como con `app.spawn`).
                if Python::try_attach(|py| {
                    if let Err(err) = callback.call0(py) {
                        err.print(py);
                    }
                })
                .is_some()
                {
                    window::notify();
                }
            });
        })
        .map(drop)
        .map_err(|err| format!("no se pudo esperar el clic del aviso: {err}"))
}

/// Muestra una notificación del sistema. Segura desde cualquier hilo.
///
/// Con `on_click`, el clic en el cuerpo del aviso llama a ese callback (sin
/// argumentos) desde un hilo propio; el aviso en macOS se envía al esperar la
/// respuesta, así que hace falta el bucle de la app en marcha para recibirla.
#[pyfunction]
#[pyo3(signature = (summary, body = String::new(), icon = None, app_id = None, on_click = None))]
pub fn notify(
    summary: String,
    body: String,
    icon: Option<PathBuf>,
    app_id: Option<String>,
    on_click: Option<Py<PyAny>>,
) {
    let config = Notify {
        summary,
        body,
        icon,
        app_id,
        on_click,
    };
    if window::running() {
        window::send(Command::Notify(config));
    } else if let Err(err) = send(&config) {
        eprintln!("aurora: no se pudo notificar: {err}");
    }
}
