//! Conversión del árbol declarativo que construye Python (dicts anidados)
//! a estructuras Rust tipadas. Es el único punto donde se cruza la frontera
//! Python → Rust por frame: un solo recorrido, sin llamadas de ida y vuelta.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use skia_safe::Color;

use crate::color::parse_color;

#[derive(Clone, Copy, Default, Debug)]
pub struct Edges {
    pub top: f32,
    pub right: f32,
    pub bottom: f32,
    pub left: f32,
}

#[derive(Clone, Copy, Debug)]
pub struct Shadow {
    pub dx: f32,
    pub dy: f32,
    pub blur: f32,
    pub color: Color,
}

#[derive(Clone, Copy, Debug)]
pub struct Gradient {
    pub from: Color,
    pub to: Color,
    /// Ángulo en grados (0 = izquierda→derecha, 90 = arriba→abajo).
    pub angle: f32,
}

/// Propiedades de texto heredables (como en CSS): un `text` hereda del contenedor.
#[derive(Clone, Debug)]
pub struct TextProps {
    pub size: f32,
    pub weight: i32,
    pub color: Color,
    pub family: String,
    pub line_height: Option<f32>,
    pub letter_spacing: f32,
}

impl Default for TextProps {
    fn default() -> Self {
        Self {
            size: 14.0,
            weight: 400,
            color: Color::from_rgb(0xE6, 0xE8, 0xF0),
            family: "Inter".into(),
            line_height: None,
            letter_spacing: 0.0,
        }
    }
}

/// Longitud: píxeles lógicos o porcentaje del contenedor ("50%").
#[derive(Clone, Copy, Debug)]
pub enum Len {
    Px(f32),
    Pct(f32),
}

#[derive(Clone, Debug, Default)]
pub struct Style {
    // Layout
    pub row: bool,
    pub gap: f32,
    pub padding: Edges,
    pub align: Option<String>,
    pub justify: Option<String>,
    pub width: Option<Len>,
    pub height: Option<Len>,
    pub absolute: bool,
    /// top, right, bottom, left (solo con `position="absolute"`).
    pub inset: [Option<f32>; 4],
    pub min_width: Option<f32>,
    pub max_width: Option<f32>,
    pub grow: f32,
    pub shrink: Option<f32>,
    pub wrap: bool,
    // Visual
    pub bg: Option<Color>,
    pub bg_hover: Option<Color>,
    pub bg_pressed: Option<Color>,
    pub gradient: Option<Gradient>,
    pub radius: f32,
    pub border_width: f32,
    pub border_color: Option<Color>,
    pub shadow: Option<Shadow>,
    pub opacity: f32,
    pub press_scale: f32,
    /// Barrera de eventos: los clics dentro no llegan a los ancestros (modales).
    pub capture: bool,
    // Texto (nivel párrafo, no heredable)
    pub max_lines: Option<usize>,
    pub text_align: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Box,
    Text,
}

#[derive(Debug)]
pub struct Node {
    /// Identidad estable entre reconstrucciones (key explícita o ruta en el árbol).
    /// Permite conservar estado de animación aunque Python reconstruya el árbol.
    pub key: String,
    pub kind: Kind,
    pub style: Style,
    pub text: Option<String>,
    pub text_props: TextProps,
    pub children: Vec<Node>,
    pub on_click: Option<Py<PyAny>>,
}

impl Node {
    pub fn is_interactive(&self) -> bool {
        self.on_click.is_some()
    }
}

// ---------------------------------------------------------------------------
// Helpers de extracción: claves ausentes o `None` → valor por defecto.
// ---------------------------------------------------------------------------

fn get<'py>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    Ok(d.get_item(key)?.filter(|v| !v.is_none()))
}

fn f32_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<f32>> {
    get(d, key)?.map(|v| v.extract::<f32>()).transpose()
}

fn str_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    get(d, key)?.map(|v| v.extract::<String>()).transpose()
}

fn len_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<Len>> {
    let Some(v) = get(d, key)? else { return Ok(None) };
    if let Ok(px) = v.extract::<f32>() {
        return Ok(Some(Len::Px(px)));
    }
    let s: String = v.extract()?;
    s.strip_suffix('%')
        .and_then(|n| n.trim().parse::<f32>().ok())
        .map(|p| Some(Len::Pct(p / 100.0)))
        .ok_or_else(|| pyo3::exceptions::PyValueError::new_err(format!("longitud inválida: {s:?}")))
}

fn bool_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<bool> {
    Ok(get(d, key)?.map(|v| v.is_truthy()).transpose()?.unwrap_or(false))
}

fn color_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<Color>> {
    str_of(d, key)?.map(|s| parse_color(&s)).transpose()
}

fn edges_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Edges> {
    let Some(v) = get(d, key)? else {
        return Ok(Edges::default());
    };
    if let Ok(all) = v.extract::<f32>() {
        return Ok(Edges { top: all, right: all, bottom: all, left: all });
    }
    let vals: Vec<f32> = v.extract()?;
    Ok(match vals.as_slice() {
        [y, x] => Edges { top: *y, right: *x, bottom: *y, left: *x },
        [t, r, b, l] => Edges { top: *t, right: *r, bottom: *b, left: *l },
        _ => {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "padding debe ser un número, (vertical, horizontal) o (top, right, bottom, left)",
            ))
        }
    })
}

fn parse_style(d: &Bound<'_, PyDict>) -> PyResult<Style> {
    let shadow = match get(d, "shadow")? {
        Some(v) => {
            let (dx, dy, blur, color): (f32, f32, f32, String) = v.extract()?;
            Some(Shadow { dx, dy, blur, color: parse_color(&color)? })
        }
        None => None,
    };
    let gradient = match get(d, "gradient")? {
        Some(v) => {
            let (from, to, angle): (String, String, f32) = v.extract()?;
            Some(Gradient { from: parse_color(&from)?, to: parse_color(&to)?, angle })
        }
        None => None,
    };
    Ok(Style {
        row: str_of(d, "direction")?.as_deref() == Some("row"),
        gap: f32_of(d, "gap")?.unwrap_or(0.0),
        padding: edges_of(d, "padding")?,
        align: str_of(d, "align")?,
        justify: str_of(d, "justify")?,
        width: len_of(d, "width")?,
        height: len_of(d, "height")?,
        absolute: str_of(d, "position")?.as_deref() == Some("absolute"),
        inset: [f32_of(d, "top")?, f32_of(d, "right")?, f32_of(d, "bottom")?, f32_of(d, "left")?],
        min_width: f32_of(d, "min_width")?,
        max_width: f32_of(d, "max_width")?,
        grow: f32_of(d, "grow")?.unwrap_or(0.0),
        shrink: f32_of(d, "shrink")?,
        wrap: bool_of(d, "wrap")?,
        bg: color_of(d, "bg")?,
        bg_hover: color_of(d, "bg_hover")?,
        bg_pressed: color_of(d, "bg_pressed")?,
        gradient,
        radius: f32_of(d, "radius")?.unwrap_or(0.0),
        border_width: f32_of(d, "border_width")?.unwrap_or(0.0),
        border_color: color_of(d, "border_color")?,
        shadow,
        opacity: f32_of(d, "opacity")?.unwrap_or(1.0),
        press_scale: f32_of(d, "press_scale")?.unwrap_or(1.0),
        capture: bool_of(d, "capture")?,
        max_lines: f32_of(d, "max_lines")?.map(|n| n as usize),
        text_align: str_of(d, "text_align")?,
    })
}

fn inherit_text(d: &Bound<'_, PyDict>, parent: &TextProps) -> PyResult<TextProps> {
    Ok(TextProps {
        size: f32_of(d, "font_size")?.unwrap_or(parent.size),
        weight: f32_of(d, "font_weight")?.map(|w| w as i32).unwrap_or(parent.weight),
        color: color_of(d, "color")?.unwrap_or(parent.color),
        family: str_of(d, "font_family")?.unwrap_or_else(|| parent.family.clone()),
        line_height: f32_of(d, "line_height")?.or(parent.line_height),
        letter_spacing: f32_of(d, "letter_spacing")?.unwrap_or(parent.letter_spacing),
    })
}

/// Punto de entrada: convierte el árbol de Python en un `Node`.
pub fn parse(obj: &Bound<'_, PyAny>) -> PyResult<Node> {
    parse_node(obj, "0", &TextProps::default())
}

fn parse_node(obj: &Bound<'_, PyAny>, path: &str, inherited: &TextProps) -> PyResult<Node> {
    let d = obj.cast::<PyDict>()?;
    let kind = match str_of(d, "kind")?.as_deref() {
        Some("text") => Kind::Text,
        _ => Kind::Box,
    };
    let style_dict = match get(d, "style")? {
        Some(s) => s.cast_into::<PyDict>()?,
        None => PyDict::new(d.py()),
    };
    let style = parse_style(&style_dict)?;
    let text_props = inherit_text(&style_dict, inherited)?;
    let key = str_of(d, "key")?.unwrap_or_else(|| path.to_owned());

    let children = match get(d, "children")? {
        Some(list) => list
            .cast::<PyList>()?
            .iter()
            .enumerate()
            .map(|(i, child)| parse_node(&child, &format!("{path}/{i}"), &text_props))
            .collect::<PyResult<Vec<_>>>()?,
        None => Vec::new(),
    };

    Ok(Node {
        key,
        kind,
        style,
        text: str_of(d, "text")?,
        text_props,
        children,
        on_click: get(d, "on_click")?.map(|f| f.unbind()),
    })
}
