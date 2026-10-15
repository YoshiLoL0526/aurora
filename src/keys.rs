//! Teclado: el evento que reciben los manejadores `on_key` y las
//! combinaciones en texto (`"ctrl+s"`, `"shift+tab"`, `"mod+k"`).
//!
//! Los nombres de tecla siguen los de winit (y los de la web): `"Enter"`,
//! `"Tab"`, `"ArrowUp"`… y el carácter tal cual para las demás (`"a"`, `"A"`, `"?"`).

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[derive(Clone, Copy, Default, Debug, PartialEq, Eq)]
pub struct Mods {
    pub ctrl: bool,
    pub shift: bool,
    pub alt: bool,
    pub meta: bool,
}

/// Pulsación de tecla, ya independiente de winit.
#[derive(Clone, Debug)]
pub struct KeyInput {
    pub key: String,
    /// Texto que produce la tecla, si produce alguno.
    pub text: Option<String>,
    pub mods: Mods,
    pub repeat: bool,
}

/// Teclas con nombre que se aceptan en las combinaciones.
const NAMED: &[&str] = &[
    "Enter",
    "Tab",
    "Space",
    "Escape",
    "Backspace",
    "Delete",
    "Insert",
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "Home",
    "End",
    "PageUp",
    "PageDown",
    "F1",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "F10",
    "F11",
    "F12",
];

/// Nombre canónico de una tecla escrita por una persona (`"esc"` → `"Escape"`).
fn canonical(name: &str) -> Option<String> {
    let lower = name.to_lowercase();
    let alias = match lower.as_str() {
        "esc" => "escape",
        "return" => "enter",
        "del" => "delete",
        "up" => "arrowup",
        "down" => "arrowdown",
        "left" => "arrowleft",
        "right" => "arrowright",
        "pgup" => "pageup",
        "pgdn" => "pagedown",
        "plus" => "+",
        other => other,
    };
    if let Some(named) = NAMED.iter().find(|n| n.to_lowercase() == alias) {
        return Some((*named).to_owned());
    }
    (alias.chars().count() == 1).then(|| alias.to_owned())
}

/// Separa `"ctrl+shift+s"` en modificadores y tecla. `mod` es Cmd en macOS y
/// Ctrl en el resto, para escribir atajos portables.
pub fn parse_combo(combo: &str) -> Result<(Mods, String), String> {
    let parts: Vec<&str> = combo.split('+').map(str::trim).collect();
    let Some((key, modifiers)) = parts.split_last() else {
        return Err(format!("combinación vacía: {combo:?}"));
    };
    let mut mods = Mods::default();
    for m in modifiers {
        match m.to_lowercase().as_str() {
            "ctrl" | "control" => mods.ctrl = true,
            "shift" => mods.shift = true,
            "alt" | "option" => mods.alt = true,
            "meta" | "cmd" | "super" | "win" => mods.meta = true,
            "mod" if cfg!(target_os = "macos") => mods.meta = true,
            "mod" => mods.ctrl = true,
            other => return Err(format!("modificador desconocido {other:?} en {combo:?}")),
        }
    }
    let key = canonical(key).ok_or_else(|| format!("tecla desconocida {key:?} en {combo:?}"))?;
    Ok((mods, key))
}

impl KeyInput {
    /// Pulsación equivalente a escribir la combinación (para el piloto).
    pub fn from_combo(combo: &str) -> Result<Self, String> {
        let (mods, mut key) = parse_combo(combo)?;
        let plain = !(mods.ctrl || mods.alt || mods.meta);
        let mut text = None;
        if key.chars().count() == 1 {
            if mods.shift {
                key = key.to_uppercase();
            }
            if plain {
                text = Some(key.clone());
            }
        } else if key == "Space" && plain {
            text = Some(" ".into());
        }
        Ok(Self {
            key,
            text,
            mods,
            repeat: false,
        })
    }

    pub fn is(&self, name: &str) -> bool {
        self.key == name
    }
}

/// Evento de teclado que reciben los manejadores `on_key`.
#[pyclass(frozen, get_all, module = "aurora._core", name = "KeyEvent")]
pub struct KeyEvent {
    key: String,
    text: Option<String>,
    ctrl: bool,
    shift: bool,
    alt: bool,
    meta: bool,
    repeat: bool,
}

impl From<&KeyInput> for KeyEvent {
    fn from(k: &KeyInput) -> Self {
        Self {
            key: k.key.clone(),
            text: k.text.clone(),
            ctrl: k.mods.ctrl,
            shift: k.mods.shift,
            alt: k.mods.alt,
            meta: k.mods.meta,
            repeat: k.repeat,
        }
    }
}

#[pymethods]
impl KeyEvent {
    /// `True` si la pulsación es exactamente esa combinación (`"ctrl+s"`, `"mod+k"`,
    /// `"shift+tab"`). Las letras no distinguen mayúsculas; en los símbolos que
    /// requieren Shift (`"?"`) no hace falta escribirlo.
    fn matches(&self, combo: &str) -> PyResult<bool> {
        let (mods, key) = parse_combo(combo).map_err(PyValueError::new_err)?;
        let symbol = key.chars().count() == 1 && !key.chars().all(char::is_alphabetic);
        let mine = Mods {
            ctrl: self.ctrl,
            shift: self.shift && !symbol,
            alt: self.alt,
            meta: self.meta,
        };
        let wanted = Mods {
            shift: mods.shift && !symbol,
            ..mods
        };
        Ok(mine == wanted && self.key.to_lowercase() == key.to_lowercase())
    }

    fn __repr__(&self) -> String {
        let mut parts = Vec::new();
        for (on, name) in [
            (self.ctrl, "ctrl"),
            (self.alt, "alt"),
            (self.shift, "shift"),
            (self.meta, "meta"),
        ] {
            if on {
                parts.push(name);
            }
        }
        parts.push(&self.key);
        format!("KeyEvent({:?})", parts.join("+"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_modifiers_and_aliases() {
        let (mods, key) = parse_combo("Ctrl+Shift+esc").unwrap();
        assert!(mods.ctrl && mods.shift && !mods.alt);
        assert_eq!(key, "Escape");
        assert_eq!(parse_combo("up").unwrap().1, "ArrowUp");
        assert!(parse_combo("hyper+a").is_err());
        assert!(parse_combo("ctrl+nope").is_err());
    }

    #[test]
    fn combo_input_produces_text_only_without_shortcut_modifiers() {
        let a = KeyInput::from_combo("shift+a").unwrap();
        assert_eq!((a.key.as_str(), a.text.as_deref()), ("A", Some("A")));
        let save = KeyInput::from_combo("ctrl+s").unwrap();
        assert_eq!(save.text, None);
    }
}
