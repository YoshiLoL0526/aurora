//! Bandeja del sistema (`tray-icon`): icono, tooltip y menú.
//!
//! La bandeja se crea en el hilo del bucle (hace falta que haya uno corriendo)
//! con la configuración que deja `tray_show` en `PENDING`: si la app aún no
//! está en marcha, espera a `resumed`. Python no ve `TrayIcon`: solo configura
//! y recibe eventos (clic y opciones del menú) a través del host del bucle.

use std::collections::HashMap;
use std::sync::Mutex;

use pyo3::exceptions::{PyOSError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use tray_icon::{Icon, TrayIcon, TrayIconBuilder};

use crate::menu;
use crate::window::{self, Command};

/// Configuración de la bandeja pedida desde Python.
pub struct TrayConfig {
    /// Píxeles RGBA sin premultiplicar.
    pub rgba: Vec<u8>,
    pub width: u32,
    pub height: u32,
    pub tooltip: Option<String>,
    /// macOS: pintar el icono con el color del sistema (monocromo).
    pub template: bool,
    /// La descripción del menú (los dicts de `aurora.menus`).
    pub menu: Option<Py<PyAny>>,
    pub on_click: Option<Py<PyAny>>,
    pub on_double_click: Option<Py<PyAny>>,
}

/// Bandeja pedida y aún sin crear (hasta que el bucle la atienda).
static PENDING: Mutex<Option<TrayConfig>> = Mutex::new(None);

/// Guarda la configuración y pide al bucle que cree la bandeja.
pub fn request(config: TrayConfig) {
    if let Ok(mut slot) = PENDING.lock() {
        *slot = Some(config);
    }
    window::send(Command::TrayShow);
}

/// La configuración pendiente, si la hay (la consume).
pub fn take_pending() -> Option<TrayConfig> {
    PENDING.lock().ok().and_then(|mut slot| slot.take())
}

/// Lo que el host guarda de una bandeja creada: el icono, las acciones de su
/// menú (por id de `muda`) y los callbacks de clic.
pub struct Created {
    pub tray: TrayIcon,
    pub actions: HashMap<String, Py<PyAny>>,
    pub on_click: Option<Py<PyAny>>,
    pub on_double_click: Option<Py<PyAny>>,
}

/// Crea la bandeja (en el hilo del bucle, con Python tomado).
pub fn create(py: Python<'_>, config: TrayConfig) -> Result<Created, String> {
    let icon = Icon::from_rgba(config.rgba, config.width, config.height)
        .map_err(|err| format!("icono inválido: {err}"))?;
    let mut builder = TrayIconBuilder::new().with_icon(icon);
    if let Some(tooltip) = &config.tooltip {
        builder = builder.with_tooltip(tooltip);
    }
    // En macOS un icono «template» se pinta con el color del sistema.
    #[cfg(target_os = "macos")]
    if config.template {
        builder = builder.with_icon_as_template(true);
    }
    #[cfg(not(target_os = "macos"))]
    let _ = config.template;
    let mut actions = HashMap::new();
    if let Some(spec) = &config.menu {
        let built = menu::build(spec.bind(py)).map_err(|err| err.to_string())?;
        builder = builder.with_menu(Box::new(built.menu));
        actions = built.actions;
    }
    let tray = builder.build().map_err(|err| err.to_string())?;
    // macOS necesita un empujón al run loop para que el icono aparezca ya.
    #[cfg(target_os = "macos")]
    {
        use objc2_core_foundation::CFRunLoop;
        if let Some(run_loop) = CFRunLoop::main() {
            CFRunLoop::wake_up(&run_loop);
        }
    }
    Ok(Created {
        tray,
        actions,
        on_click: config.on_click,
        on_double_click: config.on_double_click,
    })
}

/// Los píxeles RGBA de un icono: una ruta (`str` u `os.PathLike`) o los bytes.
fn load_icon(source: &Bound<'_, PyAny>) -> PyResult<(Vec<u8>, u32, u32)> {
    let bytes = if let Ok(path) = source.extract::<std::path::PathBuf>() {
        std::fs::read(&path).map_err(|err| {
            PyOSError::new_err(format!(
                "no se pudo leer el icono {}: {err}",
                path.display()
            ))
        })?
    } else if let Ok(data) = source.extract::<Vec<u8>>() {
        data
    } else {
        return Err(PyTypeError::new_err(
            "el icono de la bandeja debe ser una ruta (str o Path) o los bytes de un PNG/SVG",
        ));
    };
    let image = skia_safe::Image::from_encoded(skia_safe::Data::new_copy(&bytes))
        .ok_or_else(|| PyValueError::new_err("no se pudo decodificar el icono de la bandeja"))?;
    let (width, height) = (image.width(), image.height());
    let info = skia_safe::ImageInfo::new(
        (width, height),
        skia_safe::ColorType::RGBA8888,
        skia_safe::AlphaType::Unpremul,
        None,
    );
    let mut rgba = vec![0u8; (width * height * 4) as usize];
    if !image.read_pixels(
        &info,
        &mut rgba,
        (width * 4) as usize,
        (0, 0),
        skia_safe::image::CachingHint::Allow,
    ) {
        return Err(PyValueError::new_err(
            "no se pudieron leer los píxeles del icono de la bandeja",
        ));
    }
    Ok((rgba, width as u32, height as u32))
}

/// Pone (o reemplaza) la bandeja del sistema. Segura desde cualquier hilo.
///
/// `icon`: ruta o bytes de un PNG/SVG. `menu`: la descripción de
/// `aurora.menus`. `on_click(button)` y `on_double_click(button)` reciben
/// `"left"`, `"right"` o `"middle"`. Con bandeja, la app sigue viva aunque se
/// cierren todas las ventanas.
#[pyfunction]
#[pyo3(signature = (icon, tooltip = None, menu = None, on_click = None, on_double_click = None, template = false))]
pub fn tray_show(
    icon: &Bound<'_, PyAny>,
    tooltip: Option<String>,
    menu: Option<Py<PyAny>>,
    on_click: Option<Py<PyAny>>,
    on_double_click: Option<Py<PyAny>>,
    template: bool,
) -> PyResult<()> {
    let (rgba, width, height) = load_icon(icon)?;
    request(TrayConfig {
        rgba,
        width,
        height,
        tooltip,
        template,
        menu,
        on_click,
        on_double_click,
    });
    Ok(())
}

/// Quita la bandeja del sistema. Segura desde cualquier hilo.
#[pyfunction]
pub fn tray_hide() {
    window::send(Command::TrayHide);
}
