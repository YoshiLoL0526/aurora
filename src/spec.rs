//! Conversión del árbol declarativo que construye Python (dicts anidados)
//! a estructuras Rust tipadas. Es el único punto donde se cruza la frontera
//! Python → Rust por frame: un solo recorrido, sin llamadas de ida y vuelta.

use std::collections::{HashMap, HashSet};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use skia_safe::Color;

use crate::color::parse_color;
use crate::image::{Fit, Source};

#[derive(Clone, Copy, Default, Debug, PartialEq)]
pub struct Edges {
    pub top: f32,
    pub right: f32,
    pub bottom: f32,
    pub left: f32,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Shadow {
    pub dx: f32,
    pub dy: f32,
    pub blur: f32,
    pub color: Color,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Gradient {
    pub from: Color,
    pub to: Color,
    /// Ángulo en grados (0 = izquierda→derecha, 90 = arriba→abajo).
    pub angle: f32,
}

/// Propiedades heredables (como en CSS): un nodo las hereda de su contenedor.
/// Casi todas son de texto; `focus_color` es como `accent-color` en CSS.
#[derive(Clone, Debug, PartialEq)]
pub struct TextProps {
    pub size: f32,
    pub weight: i32,
    pub color: Color,
    pub family: String,
    pub line_height: Option<f32>,
    pub letter_spacing: f32,
    /// Color del anillo de foco.
    pub focus_color: Color,
    /// Colores de la burbuja de los tooltips.
    pub tooltip_bg: Color,
    pub tooltip_color: Color,
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
            focus_color: Color::from_rgb(0x7C, 0x5C, 0xFF),
            tooltip_bg: Color::from_rgb(0xE6, 0xE8, 0xF0),
            tooltip_color: Color::from_rgb(0x0B, 0x0D, 0x14),
        }
    }
}

/// Ejes en los que un contenedor `scroll` se desplaza.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Axis {
    X,
    Y,
    Both,
}

impl Axis {
    pub fn x(self) -> bool {
        matches!(self, Axis::X | Axis::Both)
    }

    pub fn y(self) -> bool {
        matches!(self, Axis::Y | Axis::Both)
    }
}

/// Longitud: píxeles lógicos o porcentaje del contenedor ("50%").
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Len {
    Px(f32),
    Pct(f32),
}

#[derive(Clone, Debug, Default, PartialEq)]
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
    pub min_height: Option<f32>,
    pub max_height: Option<f32>,
    pub grow: f32,
    pub shrink: Option<f32>,
    pub wrap: bool,
    /// Contenedor desplazable: recorta a sus hijos y se desplaza en estos ejes.
    pub scroll: Option<Axis>,
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
    pub scrollbar_color: Option<Color>,
    /// Barrera de eventos: los clics dentro no llegan a los ancestros (modales).
    pub capture: bool,
    /// Capa superior: se maqueta en su sitio pero se pinta (y recibe eventos)
    /// después de todo el árbol (desplegables, tooltips, modales).
    pub overlay: bool,
    /// Recibe el foco con Tab y con clic. Por defecto, los nodos con `on_click`.
    pub focusable: Option<bool>,
    /// Toma el foco al aparecer en la vista.
    pub autofocus: bool,
    // Texto (nivel párrafo, no heredable)
    pub max_lines: Option<usize>,
    pub text_align: Option<String>,
    // Campos de texto
    pub multiline: bool,
    pub placeholder: Option<String>,
    pub placeholder_color: Option<Color>,
    pub selection_color: Option<Color>,
    /// Alto mínimo de un campo multilínea, en líneas.
    pub rows: usize,
    /// Texto de ayuda que aparece al dejar el puntero un momento encima.
    pub tooltip: Option<String>,
    // Imágenes
    pub src: Option<Source>,
    pub fit: Fit,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Box,
    Text,
    /// Campo de texto editable (`text_input`, `textarea`).
    Input,
    /// Imagen de un archivo o de bytes en memoria.
    Image,
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
    /// Manejadores de eventos por nombre (`"click"`, …), sin el prefijo `on_`.
    pub handlers: HashMap<String, Py<PyAny>>,
}

impl Node {
    /// Copia profunda (los manejadores se comparten: son referencias a Python).
    pub fn clone_ref(&self, py: Python<'_>) -> Node {
        Node {
            key: self.key.clone(),
            kind: self.kind,
            style: self.style.clone(),
            text: self.text.clone(),
            text_props: self.text_props.clone(),
            children: self.children.iter().map(|c| c.clone_ref(py)).collect(),
            handlers: self
                .handlers
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
        }
    }

    fn collect_keys(&self, out: &mut Vec<String>) {
        out.push(self.key.clone());
        for child in &self.children {
            child.collect_keys(out);
        }
    }

    /// Número de nodos del subárbol, incluido este.
    pub fn count(&self) -> usize {
        1 + self.children.iter().map(Node::count).sum::<usize>()
    }

    pub fn is_interactive(&self) -> bool {
        self.handlers.contains_key("click")
    }

    pub fn is_editable(&self) -> bool {
        self.kind == Kind::Input
    }

    pub fn is_focusable(&self) -> bool {
        self.style
            .focusable
            .unwrap_or_else(|| self.is_interactive() || self.is_editable())
    }

    pub fn handler(&self, event: &str) -> Option<&Py<PyAny>> {
        self.handlers.get(event)
    }

    /// Nodo del subárbol con esa key.
    pub fn find(&self, key: &str) -> Option<&Node> {
        if self.key == key {
            return Some(self);
        }
        self.children.iter().find_map(|c| c.find(key))
    }

    /// Si los dos nodos tienen manejadores para los mismos eventos.
    pub fn same_handlers(&self, other: &Node) -> bool {
        self.handlers.len() == other.handlers.len()
            && self.handlers.keys().all(|k| other.handlers.contains_key(k))
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
    let Some(v) = get(d, key)? else {
        return Ok(None);
    };
    if let Ok(px) = v.extract::<f32>() {
        return Ok(Some(Len::Px(px)));
    }
    let s: String = v.extract()?;
    s.strip_suffix('%')
        .and_then(|n| n.trim().parse::<f32>().ok())
        .map(|p| Some(Len::Pct(p / 100.0)))
        .ok_or_else(|| PyValueError::new_err(format!("longitud inválida: {s:?}")))
}

fn bool_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<bool> {
    Ok(get(d, key)?
        .map(|v| v.is_truthy())
        .transpose()?
        .unwrap_or(false))
}

fn color_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<Color>> {
    str_of(d, key)?.map(|s| parse_color(&s)).transpose()
}

fn edges_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Edges> {
    let Some(v) = get(d, key)? else {
        return Ok(Edges::default());
    };
    if let Ok(all) = v.extract::<f32>() {
        return Ok(Edges {
            top: all,
            right: all,
            bottom: all,
            left: all,
        });
    }
    let vals: Vec<f32> = v.extract()?;
    Ok(match vals.as_slice() {
        [y, x] => Edges {
            top: *y,
            right: *x,
            bottom: *y,
            left: *x,
        },
        [t, r, b, l] => Edges {
            top: *t,
            right: *r,
            bottom: *b,
            left: *l,
        },
        _ => {
            return Err(PyValueError::new_err(
                "padding debe ser un número, (vertical, horizontal) o (top, right, bottom, left)",
            ));
        }
    })
}

fn parse_style(d: &Bound<'_, PyDict>) -> PyResult<Style> {
    let shadow = match get(d, "shadow")? {
        Some(v) => {
            let (dx, dy, blur, color): (f32, f32, f32, String) = v.extract()?;
            Some(Shadow {
                dx,
                dy,
                blur,
                color: parse_color(&color)?,
            })
        }
        None => None,
    };
    let gradient = match get(d, "gradient")? {
        Some(v) => {
            let (from, to, angle): (String, String, f32) = v.extract()?;
            Some(Gradient {
                from: parse_color(&from)?,
                to: parse_color(&to)?,
                angle,
            })
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
        inset: [
            f32_of(d, "top")?,
            f32_of(d, "right")?,
            f32_of(d, "bottom")?,
            f32_of(d, "left")?,
        ],
        min_width: f32_of(d, "min_width")?,
        max_width: f32_of(d, "max_width")?,
        min_height: f32_of(d, "min_height")?,
        max_height: f32_of(d, "max_height")?,
        grow: f32_of(d, "grow")?.unwrap_or(0.0),
        shrink: f32_of(d, "shrink")?,
        wrap: bool_of(d, "wrap")?,
        scroll: match str_of(d, "scroll")?.as_deref() {
            None => None,
            Some("x") => Some(Axis::X),
            Some("y") => Some(Axis::Y),
            Some("both") => Some(Axis::Both),
            Some(other) => {
                return Err(PyValueError::new_err(format!(
                    "scroll inválido: {other:?} (usa \"x\", \"y\" o \"both\")"
                )));
            }
        },
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
        scrollbar_color: color_of(d, "scrollbar_color")?,
        capture: bool_of(d, "capture")?,
        focusable: get(d, "focusable")?.map(|v| v.is_truthy()).transpose()?,
        autofocus: bool_of(d, "autofocus")?,
        overlay: match str_of(d, "layer")?.as_deref() {
            None | Some("base") => false,
            Some("overlay") => true,
            Some(other) => {
                return Err(PyValueError::new_err(format!(
                    "layer inválida: {other:?} (usa \"base\" u \"overlay\")"
                )));
            }
        },
        max_lines: f32_of(d, "max_lines")?.map(|n| n as usize),
        text_align: str_of(d, "text_align")?,
        multiline: bool_of(d, "multiline")?,
        placeholder: str_of(d, "placeholder")?,
        placeholder_color: color_of(d, "placeholder_color")?,
        selection_color: color_of(d, "selection_color")?,
        rows: f32_of(d, "rows")?.map_or(1, |n| n.max(1.0) as usize),
        tooltip: str_of(d, "tooltip")?.filter(|t| !t.is_empty()),
        src: match get(d, "src")? {
            Some(v) if v.is_instance_of::<PyBytes>() => Some(Source::Bytes(v.extract()?)),
            Some(v) => Some(Source::Path(v.extract::<String>().map_err(|_| {
                PyValueError::new_err("src debe ser una ruta (str o Path) o bytes")
            })?)),
            None => None,
        },
        fit: match str_of(d, "fit")? {
            None => Fit::default(),
            Some(f) => Fit::parse(&f).ok_or_else(|| {
                PyValueError::new_err(format!(
                    "fit inválido: {f:?} (usa \"contain\", \"cover\", \"fill\" o \"none\")"
                ))
            })?,
        },
    })
}

fn inherit_text(d: &Bound<'_, PyDict>, parent: &TextProps) -> PyResult<TextProps> {
    Ok(TextProps {
        size: f32_of(d, "font_size")?.unwrap_or(parent.size),
        weight: f32_of(d, "font_weight")?
            .map(|w| w as i32)
            .unwrap_or(parent.weight),
        color: color_of(d, "color")?.unwrap_or(parent.color),
        family: str_of(d, "font_family")?.unwrap_or_else(|| parent.family.clone()),
        line_height: f32_of(d, "line_height")?.or(parent.line_height),
        letter_spacing: f32_of(d, "letter_spacing")?.unwrap_or(parent.letter_spacing),
        focus_color: color_of(d, "focus_color")?.unwrap_or(parent.focus_color),
        tooltip_bg: color_of(d, "tooltip_bg")?.unwrap_or(parent.tooltip_bg),
        tooltip_color: color_of(d, "tooltip_color")?.unwrap_or(parent.tooltip_color),
    })
}

/// Punto de entrada: convierte el árbol de Python en un `Node`.
///
/// Las keys deben ser únicas en todo el árbol: identifican al nodo para
/// despachar clics y conservar el estado de animación. Una key repetida
/// haría que el clic llegara al callback de otro nodo, así que se rechaza.
///
/// Un nodo sin key recibe la de su padre seguida de su posición (`"0/1/2"`, o
/// `"fila-7/0"` bajo un nodo con key): así su identidad no cambia si su padre
/// con key se mueve de sitio.
pub fn parse(obj: &Bound<'_, PyAny>) -> PyResult<Node> {
    Parser::default().parse(obj)
}

/// Parser con memoria entre reconstrucciones. Los dicts de los `@component`
/// que no cambiaron llegan como el **mismo objeto** de Python (marcados con
/// `memo`): su `Node` se copia del parseo anterior en vez de volver a leer
/// cada propiedad de cada dict.
#[derive(Default)]
pub struct Parser {
    memo: HashMap<usize, Memo>,
}

/// Nodo parseado de un dict memorizado.
struct Memo {
    /// Mantiene vivo el dict: mientras exista, su dirección no se reutiliza.
    _dict: Py<PyAny>,
    /// Key resuelta de la raíz: de ella salen las de todo el subárbol.
    key: String,
    /// Lo heredado del padre también forma parte del resultado.
    inherited: TextProps,
    node: Node,
    keys: Vec<String>,
}

struct Ctx<'a> {
    seen: HashSet<String>,
    /// Memoria del parseo anterior (se consume) y la de este (se rellena).
    old: &'a mut HashMap<usize, Memo>,
    new: HashMap<usize, Memo>,
}

impl Parser {
    pub fn parse(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<Node> {
        let mut ctx = Ctx {
            seen: HashSet::new(),
            old: &mut self.memo,
            new: HashMap::new(),
        };
        let node = parse_node(obj, "0", &TextProps::default(), &mut ctx)?;
        self.memo = ctx.new;
        Ok(node)
    }
}

fn check_unique(seen: &mut HashSet<String>, key: &str) -> PyResult<()> {
    if !seen.insert(key.to_owned()) {
        return Err(PyValueError::new_err(format!(
            "key duplicada en el árbol de la vista: {key:?}"
        )));
    }
    Ok(())
}

fn parse_node(
    obj: &Bound<'_, PyAny>,
    path: &str,
    inherited: &TextProps,
    ctx: &mut Ctx<'_>,
) -> PyResult<Node> {
    let d = obj.cast::<PyDict>()?;
    if !bool_of(d, "memo")? {
        return parse_fresh(d, path, inherited, ctx);
    }
    let id = obj.as_ptr() as usize;
    let key = str_of(d, "key")?.unwrap_or_else(|| path.to_owned());
    let hit = ctx
        .old
        .remove(&id)
        .filter(|m| m.key == key && m.inherited == *inherited);
    let memo = match hit {
        Some(memo) => {
            for k in &memo.keys {
                check_unique(&mut ctx.seen, k)?;
            }
            memo
        }
        None => {
            let node = parse_fresh(d, path, inherited, ctx)?;
            let mut keys = Vec::new();
            node.collect_keys(&mut keys);
            Memo {
                _dict: obj.clone().unbind(),
                key,
                inherited: inherited.clone(),
                node,
                keys,
            }
        }
    };
    let node = memo.node.clone_ref(obj.py());
    ctx.new.insert(id, memo);
    Ok(node)
}

fn parse_fresh(
    d: &Bound<'_, PyDict>,
    path: &str,
    inherited: &TextProps,
    ctx: &mut Ctx<'_>,
) -> PyResult<Node> {
    let kind = match str_of(d, "kind")?.as_deref() {
        Some("text") => Kind::Text,
        Some("input") => Kind::Input,
        Some("image") => Kind::Image,
        _ => Kind::Box,
    };
    let style_dict = match get(d, "style")? {
        Some(s) => s.cast_into::<PyDict>()?,
        None => PyDict::new(d.py()),
    };
    let style = parse_style(&style_dict)?;
    let text_props = inherit_text(&style_dict, inherited)?;
    let key = str_of(d, "key")?.unwrap_or_else(|| path.to_owned());
    check_unique(&mut ctx.seen, &key)?;

    let children = match get(d, "children")? {
        Some(list) => list
            .cast::<PyList>()?
            .iter()
            .enumerate()
            .map(|(i, child)| parse_node(&child, &format!("{key}/{i}"), &text_props, ctx))
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
        handlers: parse_handlers(d)?,
    })
}

fn parse_handlers(d: &Bound<'_, PyDict>) -> PyResult<HashMap<String, Py<PyAny>>> {
    let Some(obj) = get(d, "handlers")? else {
        return Ok(HashMap::new());
    };
    let mut handlers = HashMap::new();
    for (name, cb) in obj.cast::<PyDict>()?.iter() {
        if cb.is_none() {
            continue;
        }
        if !cb.is_callable() {
            return Err(PyValueError::new_err(format!(
                "el manejador on_{} debe ser callable",
                name.extract::<String>()?
            )));
        }
        handlers.insert(name.extract::<String>()?, cb.unbind());
    }
    Ok(handlers)
}
