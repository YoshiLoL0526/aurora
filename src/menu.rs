//! Menús nativos: descripción de Python (dicts, como las vistas) → menú de
//! `muda`. Los describen `aurora.menus` y se usan en tres sitios: el menú de
//! la bandeja, la barra de la app (Windows y macOS) y los menús contextuales.
//!
//! ```text
//! {"type": "item", "label": "Abrir…", "enabled": True, "action": fn, "shortcut": "ctrl+o"}
//! {"type": "separator"}
//! {"type": "submenu", "label": "Editar", "items": [...]}
//! {"type": "predefined", "name": "copy"}
//! ```
//!
//! Cada acción se guarda por el id del ítem de `muda` (`MenuId`): cuando el
//! usuario elige una opción, el evento trae ese id y se llama a su acción.

use std::collections::HashMap;
use std::sync::Mutex;

use muda::accelerator::{Accelerator, Code, Modifiers};
use muda::{IsMenuItem, Menu, MenuItem, PredefinedMenuItem, Submenu};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use winit::window::Window;
// Mostrar un menú contextual sobre el HWND/NSView es de `ContextMenu`, y el
// mango de la ventana se pide con `HasWindowHandle`: en Linux no hay menús
// nativos (requieren GTK) y estos imports no se usan.
#[cfg(any(target_os = "windows", target_os = "macos"))]
use muda::ContextMenu;
#[cfg(any(target_os = "windows", target_os = "macos"))]
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};

/// Un menú construido y sus acciones, listas para despachar.
pub struct Built {
    pub menu: Menu,
    pub actions: HashMap<String, Py<PyAny>>,
}

/// Acciones del último menú contextual abierto, por id de `muda`. El evento de
/// la opción elegida llega al bucle al cerrarse el menú, así que se guardan
/// hasta el siguiente.
static CONTEXT: Mutex<Option<HashMap<String, Py<PyAny>>>> = Mutex::new(None);

/// Construye el menú de una lista de entradas (los dicts de `aurora.menus`).
pub fn build(entries: &Bound<'_, PyAny>) -> PyResult<Built> {
    let menu = Menu::new();
    let mut actions = HashMap::new();
    fill(
        &|item| menu.append(item).map_err(string),
        entries,
        &mut actions,
    )?;
    Ok(Built { menu, actions })
}

/// Muestra un menú contextual nativo sobre la ventana, en la posición del
/// puntero. En Linux no hay menús nativos sin GTK: no hace nada (documentado).
pub fn show_context(window: &Window, entries: &Bound<'_, PyAny>) -> PyResult<()> {
    let built = build(entries)?;
    if let Ok(mut slot) = CONTEXT.lock() {
        *slot = Some(built.actions);
    }
    #[cfg(target_os = "windows")]
    if let Ok(handle) = window.window_handle()
        && let RawWindowHandle::Win32(win) = handle.as_raw()
    {
        // Modal hasta que se elige o se cierra; el evento llega por el bucle.
        unsafe { built.menu.show_context_menu_for_hwnd(win.hwnd.get(), None) };
    }
    #[cfg(target_os = "macos")]
    if let Ok(handle) = window.window_handle()
        && let RawWindowHandle::AppKit(view) = handle.as_raw()
    {
        unsafe {
            built
                .menu
                .show_context_menu_for_nsview(view.ns_view.as_ptr() as _, None)
        };
    }
    // En Linux no hay menús nativos (requieren GTK): no se muestra nada, pero la
    // acción queda registrada por si el id llegara desde el menú (no llegará: no
    // se dibuja). Se consume `window` para no dejar un parámetro sin usar.
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    let _ = window;
    Ok(())
}

/// Llama a la acción del último menú contextual con ese id. `false` si no hay.
pub fn call_context_action(py: Python<'_>, id: &str) -> bool {
    let Ok(slot) = CONTEXT.lock() else {
        return false;
    };
    let Some(actions) = slot.as_ref() else {
        return false;
    };
    let Some(callback) = actions.get(id) else {
        return false;
    };
    if let Err(err) = callback.call0(py) {
        err.print(py);
    }
    true
}

/// Cuelga la barra de menús de la ventana (solo Windows; en macOS es de la app).
#[cfg(target_os = "windows")]
pub fn attach(window: &Window, bar: &Built) {
    if let Ok(handle) = window.window_handle()
        && let RawWindowHandle::Win32(win) = handle.as_raw()
        && let Err(err) = unsafe { bar.menu.init_for_hwnd(win.hwnd.get()) }
    {
        eprintln!("aurora: no se pudo colgar la barra de menús: {err}");
    }
}

/// El atajo de la barra (el HACCEL que usa el hook de mensajes de Windows).
#[cfg(target_os = "windows")]
pub fn haccel(bar: &Built) -> isize {
    bar.menu.haccel()
}

/// El submenú estándar de la app de macOS (Acerca de, Ocultar, Salir…), delante
/// de los que describa la app: es la convención del sistema.
#[cfg(target_os = "macos")]
pub fn prepend_app_menu(py: Python<'_>, entries: &Bound<'_, PyAny>, name: &str) -> PyResult<Built> {
    let built = build(entries)?;
    let app_menu = Submenu::new(name, true);
    app_menu
        .append_items(&[
            &PredefinedMenuItem::about(None, None),
            &PredefinedMenuItem::separator(),
            &PredefinedMenuItem::services(None),
            &PredefinedMenuItem::separator(),
            &PredefinedMenuItem::hide(None),
            &PredefinedMenuItem::hide_others(None),
            &PredefinedMenuItem::show_all(None),
            &PredefinedMenuItem::separator(),
            &PredefinedMenuItem::quit(None),
        ])
        .map_err(|err| PyValueError::new_err(err.to_string()))?;
    built
        .menu
        .prepend(&app_menu)
        .map_err(|err| PyValueError::new_err(err.to_string()))?;
    let _ = py;
    Ok(built)
}

fn string(err: muda::Error) -> String {
    err.to_string()
}

/// Añade las entradas al destino (`Menu` o `Submenu`), recursivamente.
fn fill(
    add: &dyn Fn(&dyn IsMenuItem) -> Result<(), String>,
    entries: &Bound<'_, PyAny>,
    actions: &mut HashMap<String, Py<PyAny>>,
) -> PyResult<()> {
    for entry in entries.try_iter()? {
        let entry = entry?;
        let dict = entry.cast::<PyDict>().map_err(|_| {
            PyValueError::new_err("cada entrada de un menú debe ser un dict de `aurora.menus`")
        })?;
        let kind: String = item(dict, "type")?.extract()?;
        match kind.as_str() {
            "item" => {
                let label: String = item(dict, "label")?.extract()?;
                let enabled: bool = item(dict, "enabled")?.extract()?;
                let action: Py<PyAny> = item(dict, "action")?.unbind();
                let accelerator = optional(dict, "shortcut")?
                    .map(|shortcut| accelerator(shortcut.extract()?))
                    .transpose()?;
                let menu_item = MenuItem::new(label, enabled, accelerator);
                actions.insert(menu_item.id().0.clone(), action);
                add(&menu_item).map_err(PyValueError::new_err)?;
            }
            "separator" => {
                let menu_item = PredefinedMenuItem::separator();
                add(&menu_item).map_err(PyValueError::new_err)?;
            }
            "submenu" => {
                let label: String = item(dict, "label")?.extract()?;
                let submenu = Submenu::new(label, true);
                let items = item(dict, "items")?;
                let add_child = |entry: &dyn IsMenuItem| submenu.append(entry).map_err(string);
                fill(&add_child, &items, actions)
                    .map_err(|err| PyValueError::new_err(format!("en un submenú: {err}")))?;
                // El submenú se cuelga de su padre, no de sí mismo.
                add(&submenu).map_err(PyValueError::new_err)?;
            }
            "predefined" => {
                let name: String = item(dict, "name")?.extract()?;
                let menu_item = predefined(&name)?;
                add(&menu_item).map_err(PyValueError::new_err)?;
            }
            other => {
                return Err(PyValueError::new_err(format!(
                    "tipo de entrada de menú desconocido: {other:?} \
                     (válidos: item, separator, submenu, predefined)"
                )));
            }
        }
    }
    Ok(())
}

/// Una clave obligatoria de la entrada.
fn item<'py>(dict: &Bound<'py, PyDict>, key: &str) -> PyResult<Bound<'py, PyAny>> {
    dict.get_item(key)?
        .ok_or_else(|| PyValueError::new_err(format!("a la entrada del menú le falta {key:?}")))
}

/// Una clave opcional de la entrada.
fn optional<'py>(dict: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    Ok(dict.get_item(key)?.filter(|value| !value.is_none()))
}

/// Un ítem estándar del sistema, por nombre.
fn predefined(name: &str) -> PyResult<PredefinedMenuItem> {
    Ok(match name {
        "copy" => PredefinedMenuItem::copy(None),
        "cut" => PredefinedMenuItem::cut(None),
        "paste" => PredefinedMenuItem::paste(None),
        "delete" => PredefinedMenuItem::delete(None),
        "select_all" => PredefinedMenuItem::select_all(None),
        "undo" => PredefinedMenuItem::undo(None),
        "redo" => PredefinedMenuItem::redo(None),
        "minimize" => PredefinedMenuItem::minimize(None),
        "maximize" => PredefinedMenuItem::maximize(None),
        "fullscreen" => PredefinedMenuItem::fullscreen(None),
        "hide" => PredefinedMenuItem::hide(None),
        "hide_others" => PredefinedMenuItem::hide_others(None),
        "show_all" => PredefinedMenuItem::show_all(None),
        "close_window" => PredefinedMenuItem::close_window(None),
        "quit" => PredefinedMenuItem::quit(None),
        "about" => PredefinedMenuItem::about(None, None),
        "services" => PredefinedMenuItem::services(None),
        "bring_all_to_front" => PredefinedMenuItem::bring_all_to_front(None),
        other => {
            return Err(PyValueError::new_err(format!(
                "entrada estándar desconocida: {other:?}"
            )));
        }
    })
}

/// `"ctrl+o"` → acelerador. `mod` es Control fuera de macOS y Comando en macOS.
fn accelerator(shortcut: &str) -> PyResult<Accelerator> {
    let mut mods = Modifiers::empty();
    let mut key = None;
    for part in shortcut
        .split('+')
        .map(|part| part.trim().to_ascii_lowercase())
    {
        match part.as_str() {
            "" => continue,
            "ctrl" | "control" => mods |= Modifiers::CONTROL,
            "shift" => mods |= Modifiers::SHIFT,
            "alt" | "option" => mods |= Modifiers::ALT,
            "super" | "cmd" | "command" => mods |= Modifiers::META,
            "mod" if cfg!(target_os = "macos") => mods |= Modifiers::META,
            "mod" => mods |= Modifiers::CONTROL,
            other => key = Some(code(other)?),
        }
    }
    let key = key.ok_or_else(|| {
        PyValueError::new_err(format!(
            "al atajo {shortcut:?} le falta la tecla (p. ej. \"ctrl+o\")"
        ))
    })?;
    Ok(Accelerator::new(mods, key))
}

/// El nombre de una tecla en un atajo (`"o"`, `"f5"`, `"left"`…).
fn code(name: &str) -> PyResult<Code> {
    let mut chars = name.chars();
    if let (Some(c), None) = (chars.next(), chars.next()) {
        if c.is_ascii_alphabetic() {
            return Ok(letter(c));
        }
        if c.is_ascii_digit() {
            return Ok(digit(c));
        }
    }
    Ok(match name {
        "space" => Code::Space,
        "enter" | "return" => Code::Enter,
        "escape" | "esc" => Code::Escape,
        "tab" => Code::Tab,
        "backspace" => Code::Backspace,
        "delete" | "del" => Code::Delete,
        "insert" => Code::Insert,
        "up" => Code::ArrowUp,
        "down" => Code::ArrowDown,
        "left" => Code::ArrowLeft,
        "right" => Code::ArrowRight,
        "home" => Code::Home,
        "end" => Code::End,
        "pageup" => Code::PageUp,
        "pagedown" => Code::PageDown,
        "comma" => Code::Comma,
        "period" => Code::Period,
        "minus" => Code::Minus,
        "equal" => Code::Equal,
        "slash" => Code::Slash,
        "backslash" => Code::Backslash,
        "bracketleft" => Code::BracketLeft,
        "bracketright" => Code::BracketRight,
        "backquote" => Code::Backquote,
        "f1" => Code::F1,
        "f2" => Code::F2,
        "f3" => Code::F3,
        "f4" => Code::F4,
        "f5" => Code::F5,
        "f6" => Code::F6,
        "f7" => Code::F7,
        "f8" => Code::F8,
        "f9" => Code::F9,
        "f10" => Code::F10,
        "f11" => Code::F11,
        "f12" => Code::F12,
        other => {
            return Err(PyValueError::new_err(format!(
                "tecla desconocida en el atajo: {other:?}"
            )));
        }
    })
}

/// La tecla de una letra del atajo.
fn letter(c: char) -> Code {
    match c.to_ascii_uppercase() {
        'A' => Code::KeyA,
        'B' => Code::KeyB,
        'C' => Code::KeyC,
        'D' => Code::KeyD,
        'E' => Code::KeyE,
        'F' => Code::KeyF,
        'G' => Code::KeyG,
        'H' => Code::KeyH,
        'I' => Code::KeyI,
        'J' => Code::KeyJ,
        'K' => Code::KeyK,
        'L' => Code::KeyL,
        'M' => Code::KeyM,
        'N' => Code::KeyN,
        'O' => Code::KeyO,
        'P' => Code::KeyP,
        'Q' => Code::KeyQ,
        'R' => Code::KeyR,
        'S' => Code::KeyS,
        'T' => Code::KeyT,
        'U' => Code::KeyU,
        'V' => Code::KeyV,
        'W' => Code::KeyW,
        'X' => Code::KeyX,
        'Y' => Code::KeyY,
        _ => Code::KeyZ,
    }
}

/// La tecla de un dígito del atajo.
fn digit(c: char) -> Code {
    match c {
        '0' => Code::Digit0,
        '1' => Code::Digit1,
        '2' => Code::Digit2,
        '3' => Code::Digit3,
        '4' => Code::Digit4,
        '5' => Code::Digit5,
        '6' => Code::Digit6,
        '7' => Code::Digit7,
        '8' => Code::Digit8,
        _ => Code::Digit9,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accelerators_parse_modifiers_and_keys() {
        let accel = accelerator("ctrl+shift+o").unwrap();
        assert!(accel.matches(Modifiers::CONTROL | Modifiers::SHIFT, Code::KeyO));
        let accel = accelerator("f5").unwrap();
        assert!(accel.matches(Modifiers::empty(), Code::F5));
        let accel = accelerator("mod+s").unwrap();
        #[cfg(target_os = "macos")]
        assert!(accel.matches(Modifiers::META, Code::KeyS));
        #[cfg(not(target_os = "macos"))]
        assert!(accel.matches(Modifiers::CONTROL, Code::KeyS));
    }

    #[test]
    fn unknown_accelerators_are_errors() {
        assert!(accelerator("ctrl+nope").is_err());
        assert!(accelerator("ctrl").is_err()); // sin tecla
    }

    #[test]
    fn predefined_names_resolve() {
        assert!(predefined("copy").is_ok());
        assert!(predefined("quit").is_ok());
        assert!(predefined("pegar").is_err());
    }
}
