//! Conversión del árbol declarativo que construye Python (dicts anidados)
//! a estructuras Rust tipadas. Es el único punto donde se cruza la frontera
//! Python → Rust por frame: un solo recorrido, sin llamadas de ida y vuelta.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use accesskit::{Live, Orientation, Role, SortDirection};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBytes, PyDict, PyList, PyString};
use skia_safe::Color;

use crate::color::parse_color;
use crate::image::{Fit, Source};
use crate::motion::{self, Effect, Timing};

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

/// Tramo de un texto enriquecido (`rich_text`): un trozo del texto del nodo
/// con su propio estilo. Lo que no fija lo hereda del nodo.
#[derive(Clone, Debug, PartialEq)]
pub struct Span {
    /// Longitud del tramo en caracteres (los tramos se suceden sin huecos).
    pub chars: usize,
    pub color: Option<Color>,
    /// Fondo detrás de los glifos (código en línea).
    pub bg: Option<Color>,
    pub weight: Option<i32>,
    pub size: Option<f32>,
    /// Familias en orden de preferencia (`"Cascadia Mono, Consolas"`).
    pub family: Option<Vec<String>>,
    pub italic: bool,
    pub underline: bool,
    pub strike: bool,
    /// Número de enlace: su clic llama a `on_link(número)` del nodo.
    pub link: Option<usize>,
}

/// Los tramos de un texto y una huella de todos ellos (para la caché de párrafos).
#[derive(Clone, Debug, PartialEq)]
pub struct Spans {
    pub list: Vec<Span>,
    pub hash: u64,
}

impl Spans {
    fn parse(v: &Bound<'_, PyAny>) -> PyResult<Self> {
        let invalid = || {
            PyValueError::new_err(
                "spans debe ser una secuencia de (chars, color, bg, weight, size, family, italic, underline, strike, link)",
            )
        };
        let mut list = Vec::new();
        for item in v.try_iter()? {
            let item = item?;
            #[allow(clippy::type_complexity)]
            let (chars, color, bg, weight, size, family, italic, underline, strike, link): (
                usize,
                Option<String>,
                Option<String>,
                Option<f32>,
                Option<f32>,
                Option<String>,
                bool,
                bool,
                bool,
                Option<usize>,
            ) = item.extract().map_err(|_| invalid())?;
            list.push(Span {
                chars,
                color: color.map(|c| parse_color(&c)).transpose()?,
                bg: bg.map(|c| parse_color(&c)).transpose()?,
                weight: weight.map(|w| w as i32),
                size,
                family: family.map(|f| f.split(',').map(|s| s.trim().to_owned()).collect()),
                italic,
                underline,
                strike,
                link,
            });
        }
        let mut h = std::hash::DefaultHasher::new();
        for s in &list {
            use std::hash::Hash;
            (s.chars, s.weight, s.size.map(f32::to_bits), &s.family).hash(&mut h);
            (s.italic, s.underline, s.strike, s.link).hash(&mut h);
            let argb = |c: Color| u32::from_be_bytes([c.a(), c.r(), c.g(), c.b()]);
            (s.color.map(argb), s.bg.map(argb)).hash(&mut h);
        }
        Ok(Self {
            list,
            hash: std::hash::Hasher::finish(&h),
        })
    }

    /// Cada tramo con su rango de bytes en `text` (los que se pasan del final
    /// quedan vacíos).
    pub fn ranges(&self, text: &str) -> Vec<(&Span, std::ops::Range<usize>)> {
        let bounds: Vec<usize> = text
            .char_indices()
            .map(|(i, _)| i)
            .chain([text.len()])
            .collect();
        let at = |chars: usize| bounds[chars.min(bounds.len() - 1)];
        let mut consumed = 0;
        self.list
            .iter()
            .map(|span| {
                let range = at(consumed)..at(consumed + span.chars);
                consumed += span.chars;
                (span, range)
            })
            .collect()
    }

    /// Si algún tramo es un enlace.
    pub fn has_links(&self) -> bool {
        self.list.iter().any(|s| s.link.is_some())
    }
}

/// Key de la región de una parte (una línea) de un enlace de un texto
/// enriquecido: no es un nodo, pero recibe clics como si lo fuera.
pub fn link_key(owner: &str, link: usize, part: usize) -> String {
    format!("{owner}#link-{link}-{part}")
}

/// El nodo dueño y el número de enlace de una key de `link_key`.
pub fn parse_link_key(key: &str) -> Option<(&str, usize)> {
    let (owner, rest) = key.rsplit_once("#link-")?;
    let (link, _part) = rest.split_once('-')?;
    Some((owner, link.parse().ok()?))
}

/// Key con la que se enfoca un enlace: la de su primera parte, sea cual sea
/// la línea de `key` (`None` si `key` no es de un enlace).
pub fn link_focus_key(key: &str) -> Option<String> {
    parse_link_key(key).map(|(owner, link)| link_key(owner, link, 0))
}

/// Lado del ancla en el que se coloca una capa superior con `placement`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Side {
    Top,
    Bottom,
    Left,
    Right,
}

/// Alineación con el ancla en el otro eje.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Align {
    Start,
    Center,
    End,
}

/// Colocación junto al ancla (`placement="bottom-start"`, `offset=6`): ver `render/place.rs`.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Placement {
    pub side: Side,
    pub align: Align,
    /// Distancia al ancla.
    pub gap: f32,
}

impl Placement {
    fn parse(name: &str, gap: f32) -> Option<Self> {
        let (side, align) = name.split_once('-').unwrap_or((name, "center"));
        let side = match side {
            "top" => Side::Top,
            "bottom" => Side::Bottom,
            "left" => Side::Left,
            "right" => Side::Right,
            _ => return None,
        };
        let align = match align {
            "start" => Align::Start,
            "center" => Align::Center,
            "end" => Align::End,
            _ => return None,
        };
        Some(Self { side, align, gap })
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
    /// top, right, bottom, left (solo con `position="absolute"`). Admite
    /// porcentajes del contenedor ("50%") como `width`/`height`.
    pub inset: [Option<Len>; 4],
    pub min_width: Option<f32>,
    pub max_width: Option<f32>,
    pub min_height: Option<f32>,
    pub max_height: Option<f32>,
    pub grow: f32,
    pub shrink: Option<f32>,
    pub wrap: bool,
    /// Recorta a sus hijos a la caja del nodo (con `overflow="hidden"`): el
    /// contenido que se sale se oculta y no recibe clics. No afecta al layout.
    pub clip: bool,
    /// Contenedor desplazable: recorta a sus hijos y se desplaza en estos ejes.
    pub scroll: Option<Axis>,
    /// Franja del contenido de un `scroll` (`top`, `bottom`, desde su inicio) que
    /// debe verse: cuando cambia, el contenedor se desplaza hasta mostrarla.
    pub reveal: Option<(f32, f32)>,
    /// Un `scroll` que mantiene quieto lo que se ve cuando cambia el alto del
    /// contenido de más arriba (filas que se miden, contenido que se carga).
    pub scroll_anchor: bool,
    /// Un `scroll` que, si estaba al final, sigue al final cuando el contenido
    /// crece (y empieza ahí): un chat o un registro.
    pub stick_to_end: bool,
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
    /// Capa superior colocada junto a su ancla (el hermano anterior en el flujo
    /// o, si no hay, el contenedor), volcada al lado opuesto si no cabe y sin
    /// salirse de la ventana.
    pub placement: Option<Placement>,
    /// Recibe el foco con Tab y con clic. Por defecto, los nodos con `on_click`.
    pub focusable: Option<bool>,
    /// Toma el foco al aparecer en la vista.
    pub autofocus: bool,
    // Texto (nivel párrafo, no heredable)
    /// Tramos con estilo propio de un texto enriquecido.
    pub spans: Option<Arc<Spans>>,
    pub max_lines: Option<usize>,
    pub text_align: Option<String>,
    // Campos de texto
    pub multiline: bool,
    /// Campo de contraseña: pinta un punto por carácter y no deja copiar el valor.
    pub password: bool,
    pub placeholder: Option<String>,
    pub placeholder_color: Option<Color>,
    pub selection_color: Option<Color>,
    /// Alto mínimo de un campo multilínea, en líneas.
    pub rows: usize,
    /// Texto de ayuda que aparece al dejar el puntero un momento encima.
    pub tooltip: Option<String>,
    /// Cursor del ratón sobre el nodo (y sus hijos, salvo que fijen otro).
    pub cursor: Option<Cursor>,
    /// Zona de la ventana: pulsar en ella (fuera de un control) la mueve o la
    /// redimensiona desde ese borde (barras de título propias).
    pub window_drag: Option<WindowDrag>,
    /// Zona de soltar: durante un `on_drag`, el evento dice si el puntero está
    /// sobre ella y en qué posición caería entre sus hijos arrastrables.
    pub drop_target: bool,
    // Imágenes
    pub src: Option<Source>,
    pub fit: Fit,
    // Animaciones declarativas (ver `motion.rs`)
    /// Curva con la que se animan los cambios de `bg`, `border_color`, `color`
    /// (el del texto), `opacity` y `radius` entre reconstrucciones.
    pub transition: Option<Timing>,
    /// Curva con la que el nodo se desliza a su nueva caja cuando el layout la cambia.
    pub animate_layout: Option<Timing>,
    /// Efecto con el que aparece y con el que desaparece de la vista.
    pub enter: Option<Effect>,
    pub exit: Option<Effect>,
    /// Opacidad en vaivén perpetuo (`animate.pulse()`): indicadores de carga.
    pub pulse: Option<Timing>,
}

/// Cursor del ratón. Lo eligen el runtime (según lo que hay bajo el puntero)
/// o la propiedad `cursor` de un nodo.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Cursor {
    Default,
    Pointer,
    Text,
    /// Sobre algo que se puede arrastrar (un `chart` con zoom).
    Grab,
    /// Arrastrando la ventana de un `chart`.
    Grabbing,
    /// Redimensionar en horizontal (bordes de columna).
    ColResize,
    /// Redimensionar en vertical.
    RowResize,
    /// Cruz de precisión (el modo selección del inspector).
    Crosshair,
    /// Redimensionar en vertical, en horizontal y en las dos diagonales
    /// (bordes y esquinas de una ventana sin marco).
    NsResize,
    EwResize,
    NeswResize,
    NwseResize,
}

impl Cursor {
    fn parse(name: &str) -> Option<Self> {
        Some(match name {
            "default" => Cursor::Default,
            "pointer" => Cursor::Pointer,
            "text" => Cursor::Text,
            "grab" => Cursor::Grab,
            "grabbing" => Cursor::Grabbing,
            "col-resize" => Cursor::ColResize,
            "row-resize" => Cursor::RowResize,
            "crosshair" => Cursor::Crosshair,
            "ns-resize" => Cursor::NsResize,
            "ew-resize" => Cursor::EwResize,
            "nesw-resize" => Cursor::NeswResize,
            "nwse-resize" => Cursor::NwseResize,
            _ => return None,
        })
    }
}

/// Borde (o esquina) desde el que se redimensiona una ventana.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Edge {
    North,
    South,
    East,
    West,
    NorthEast,
    NorthWest,
    SouthEast,
    SouthWest,
}

impl Edge {
    /// Como lo escribe Python: `"n"`, `"se"`…
    pub fn name(self) -> &'static str {
        match self {
            Edge::North => "n",
            Edge::South => "s",
            Edge::East => "e",
            Edge::West => "w",
            Edge::NorthEast => "ne",
            Edge::NorthWest => "nw",
            Edge::SouthEast => "se",
            Edge::SouthWest => "sw",
        }
    }

    fn parse(name: &str) -> Option<Self> {
        [
            Edge::North,
            Edge::South,
            Edge::East,
            Edge::West,
            Edge::NorthEast,
            Edge::NorthWest,
            Edge::SouthEast,
            Edge::SouthWest,
        ]
        .into_iter()
        .find(|e| e.name() == name)
    }

    /// El cursor que anuncia que se puede redimensionar por ahí.
    pub fn cursor(self) -> Cursor {
        match self {
            Edge::North | Edge::South => Cursor::NsResize,
            Edge::East | Edge::West => Cursor::EwResize,
            Edge::NorthEast | Edge::SouthWest => Cursor::NeswResize,
            Edge::NorthWest | Edge::SouthEast => Cursor::NwseResize,
        }
    }
}

/// Qué hace con la ventana pulsar en una zona con `window_drag`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WindowDrag {
    /// Moverla (una barra de título).
    Move,
    /// Redimensionarla desde ese borde.
    Resize(Edge),
}

impl WindowDrag {
    fn parse(name: &str) -> Option<Self> {
        match name {
            "move" => Some(WindowDrag::Move),
            other => Edge::parse(other).map(WindowDrag::Resize),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Box,
    Text,
    /// Campo de texto editable (`text_input`, `textarea`).
    Input,
    /// Imagen de un archivo o de bytes en memoria.
    Image,
    /// Lienzo de dibujo inmediato: Python graba sus comandos con `draw`.
    Canvas,
    /// Gráfico nativo: series de datos y ejes (ver `chart/`).
    Chart,
}

impl Kind {
    /// Nombre del tipo de nodo, como lo escribe Python (`"box"`, `"text"`…).
    pub fn name(self) -> &'static str {
        match self {
            Kind::Box => "box",
            Kind::Text => "text",
            Kind::Input => "input",
            Kind::Image => "image",
            Kind::Canvas => "canvas",
            Kind::Chart => "chart",
        }
    }
}

/// Semántica de accesibilidad declarada por Python (`role`, `label`, `checked`…).
/// El árbol nativo que ven los lectores de pantalla se construye en `a11y.rs`.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct A11y {
    /// Rol del nodo (`"button"`, `"tablist"`…). Ver `a11y::parse_role`.
    pub role: Option<Role>,
    /// Nombre accesible. En una imagen, `alt` es su alias.
    pub label: Option<String>,
    /// Texto secundario (ayuda o contexto), aparte del nombre.
    pub description: Option<String>,
    /// Valor declarado con `value=`: el texto de un desplegable o el número de
    /// un deslizador.
    pub value: Option<Value>,
    /// Estado de casillas, interruptores y radios.
    pub checked: Option<bool>,
    /// Estado de pestañas y opciones.
    pub selected: Option<bool>,
    /// Estado de desplegables y acordeones.
    pub expanded: Option<bool>,
    /// Región viva (`live="polite"`): sus cambios se anuncian solos.
    pub live: Option<Live>,
    /// Nivel de un `heading` (1 = título principal).
    pub level: Option<usize>,
    /// Posición y tamaño del conjunto: "elemento 3 de 100" (listas, tablas).
    pub position_in_set: Option<usize>,
    pub set_size: Option<usize>,
    /// Orden de una columna ordenable (`"ascending"`, `"descending"`).
    pub sort: Option<SortDirection>,
    /// Diálogo modal: bloquea el resto de la interfaz.
    pub modal: bool,
    /// Fuera del árbol: decorativo (un separador, un icono ya descrito por su texto).
    pub hidden: bool,
    /// Rango de un deslizador o una barra de progreso.
    pub value_min: Option<f64>,
    pub value_max: Option<f64>,
    /// Paso de las acciones Incrementar/Decrementar de un deslizador.
    pub value_step: Option<f64>,
    /// Orientación de un separador o una barra (`"horizontal"`, `"vertical"`).
    pub orientation: Option<Orientation>,
}

/// Valor de `value=`: texto (`"3 de 10"`) o número (`0.5`).
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Text(String),
    Number(f64),
}

impl A11y {
    fn parse(d: &Props<'_, '_>) -> PyResult<Self> {
        let value = match get(d, "value")? {
            None => None,
            Some(v) => Some(match v.extract::<String>() {
                Ok(text) => Value::Text(text),
                Err(_) => Value::Number(
                    v.extract()
                        .map_err(|_| PyValueError::new_err("value debe ser texto o número"))?,
                ),
            }),
        };
        Ok(Self {
            role: str_of(d, "role")?
                .map(|name| crate::a11y::parse_role(&name))
                .transpose()?,
            label: match str_of(d, "label")? {
                Some(label) => Some(label),
                None => str_of(d, "alt")?,
            },
            description: str_of(d, "description")?,
            value,
            checked: opt_bool_of(d, "checked")?,
            selected: opt_bool_of(d, "selected")?,
            expanded: opt_bool_of(d, "expanded")?,
            live: str_of(d, "live")?
                .map(|name| crate::a11y::parse_live(&name))
                .transpose()?,
            level: get(d, "level")?.map(|v| v.extract::<usize>()).transpose()?,
            position_in_set: get(d, "position_in_set")?
                .map(|v| v.extract::<usize>())
                .transpose()?,
            set_size: get(d, "set_size")?
                .map(|v| v.extract::<usize>())
                .transpose()?,
            sort: str_of(d, "sort")?
                .map(|name| crate::a11y::parse_sort(&name))
                .transpose()?,
            modal: bool_of(d, "modal")?,
            hidden: bool_of(d, "hidden")?,
            value_min: f64_of(d, "value_min")?,
            value_max: f64_of(d, "value_max")?,
            value_step: f64_of(d, "value_step")?,
            orientation: str_of(d, "orientation")?
                .map(|name| crate::a11y::parse_orientation(&name))
                .transpose()?,
        })
    }
}

/// Qué contiene un subárbol, como bits: lo calcula el parser al montar cada nodo
/// (los subárboles compartidos ya lo traen), y lo usan los recorridos del árbol
/// entero para no bajar por ramas donde no hay nada que buscar.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Marks(u8);

impl Marks {
    /// Un nodo con `autofocus`.
    pub const AUTOFOCUS: Marks = Marks(1);
    /// `on_scroll` o `reveal` en un `scroll`, u `on_resize`.
    pub const LISTENERS: Marks = Marks(1 << 1);
    pub const IMAGE: Marks = Marks(1 << 2);
    /// Un campo de texto (`Kind::Input`).
    pub const INPUT: Marks = Marks(1 << 3);
    pub const CANVAS: Marks = Marks(1 << 4);
    pub const CHART: Marks = Marks(1 << 5);
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
    /// Semántica de accesibilidad: lo que ven los lectores de pantalla.
    pub a11y: A11y,
    /// Compartidos: un subárbol que Python no volvió a serializar (el mismo
    /// dict) se reutiliza sin copiarlo, y las fases siguientes lo saltan al
    /// ver el mismo puntero (`Arc::ptr_eq`).
    pub children: Vec<Arc<Node>>,
    /// El nodo o algún descendiente tiene `placement` (el layout solo recorre esas ramas).
    pub has_placement: bool,
    /// Número de nodos del subárbol, incluido este.
    pub size: usize,
    /// Qué hay en el subárbol (`Marks`): los recorridos que cada reconstrucción
    /// hace del árbol entero (inputs, imágenes, lienzos…) saltan las ramas sin nada.
    pub marks: Marks,
    /// Manejadores de eventos por nombre (`"click"`, …), sin el prefijo `on_`.
    pub handlers: HashMap<String, Py<PyAny>>,
    /// Solo en `Kind::Canvas`: `draw(width, height, force)` devuelve el lote de
    /// comandos (o `None` si lo anterior sigue valiendo). Ver `canvas.rs`.
    pub draw: Option<Py<PyAny>>,
    /// Solo en `Kind::Chart`: los datos y las opciones del gráfico, ya
    /// convertidos a vistas sin copia de los búferes. Ver `chart/`.
    pub chart: Option<Arc<crate::chart::Chart>>,
}

impl Node {
    /// Copia del nodo que comparte los hijos (los manejadores también: son
    /// referencias a Python).
    pub fn clone_ref(&self, py: Python<'_>) -> Node {
        Node {
            key: self.key.clone(),
            kind: self.kind,
            style: self.style.clone(),
            text: self.text.clone(),
            text_props: self.text_props.clone(),
            a11y: self.a11y.clone(),
            children: self.children.clone(),
            has_placement: self.has_placement,
            size: self.size,
            marks: self.marks,
            handlers: self
                .handlers
                .iter()
                .map(|(k, v)| (k.clone(), v.clone_ref(py)))
                .collect(),
            draw: self.draw.as_ref().map(|d| d.clone_ref(py)),
            chart: self.chart.clone(),
        }
    }

    /// Las keys del subárbol, en preorden.
    fn collect_keys<'a>(&'a self, out: &mut Vec<&'a str>) {
        out.push(&self.key);
        for child in &self.children {
            child.collect_keys(out);
        }
    }

    /// Número de nodos del subárbol, incluido este.
    pub fn count(&self) -> usize {
        self.size
    }

    /// Si en el subárbol hay algo de `marks` (alguno de sus bits).
    pub fn contains(&self, marks: Marks) -> bool {
        self.marks.0 & marks.0 != 0
    }

    /// Lo que el propio nodo aporta a `marks` (sin sus hijos).
    fn own_marks(&self) -> Marks {
        let mut m = 0;
        if self.style.autofocus {
            m |= Marks::AUTOFOCUS.0;
        }
        let scroll = self.style.scroll.is_some();
        if (scroll && (self.handler("scroll").is_some() || self.style.reveal.is_some()))
            || self.handler("resize").is_some()
        {
            m |= Marks::LISTENERS.0;
        }
        if self.kind == Kind::Image {
            m |= Marks::IMAGE.0;
        }
        if self.is_editable() {
            m |= Marks::INPUT.0;
        }
        if self.kind == Kind::Canvas {
            m |= Marks::CANVAS.0;
        }
        if self.chart.is_some() {
            m |= Marks::CHART.0;
        }
        Marks(m)
    }

    pub fn is_interactive(&self) -> bool {
        self.handlers.contains_key("click")
    }

    /// Tiene `on_drag`: recibe el arrastre que empieza sobre él.
    pub fn is_draggable(&self) -> bool {
        self.handlers.contains_key("drag")
    }

    pub fn is_editable(&self) -> bool {
        self.kind == Kind::Input
    }

    pub fn is_focusable(&self) -> bool {
        self.style
            .focusable
            .unwrap_or_else(|| self.is_interactive() || self.is_editable() || self.is_zoomable())
    }

    /// Es un `chart(zoom=True)`: se enfoca para hacer zoom con el teclado.
    pub fn is_zoomable(&self) -> bool {
        self.chart.as_ref().is_some_and(|chart| chart.zoom)
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

/// Claves que puede tener un spec, en el orden de su bit en `Props::mask`.
const KEYS: [&str; 98] = [
    "align",
    "alt",
    "animate_layout",
    "autofocus",
    "bg",
    "bg_hover",
    "bg_pressed",
    "border_color",
    "border_width",
    "bottom",
    "capture",
    "chart",
    "checked",
    "children",
    "color",
    "cursor",
    "description",
    "direction",
    "draw",
    "drop_target",
    "enter",
    "exit",
    "expanded",
    "fit",
    "focus_color",
    "focusable",
    "font_family",
    "font_size",
    "font_weight",
    "gap",
    "gradient",
    "grow",
    "handlers",
    "height",
    "hidden",
    "justify",
    "key",
    "kind",
    "label",
    "layer",
    "left",
    "letter_spacing",
    "level",
    "line_height",
    "live",
    "max_height",
    "max_lines",
    "max_width",
    "memo",
    "min_height",
    "min_width",
    "modal",
    "multiline",
    "offset",
    "opacity",
    "orientation",
    "overflow",
    "padding",
    "password",
    "placeholder",
    "placeholder_color",
    "placement",
    "position",
    "position_in_set",
    "press_scale",
    "pulse",
    "radius",
    "reveal",
    "right",
    "role",
    "rows",
    "scroll",
    "scroll_anchor",
    "scrollbar_color",
    "selected",
    "selection_color",
    "set_size",
    "shadow",
    "shrink",
    "sort",
    "spans",
    "src",
    "stick_to_end",
    "style",
    "text",
    "text_align",
    "tooltip",
    "tooltip_bg",
    "tooltip_color",
    "top",
    "transition",
    "value",
    "value_max",
    "value_min",
    "value_step",
    "width",
    "window_drag",
    "wrap",
];

const _: () = assert!(KEYS.len() <= 128, "la máscara de `Props` es un u128");

/// Posición de `key` en `KEYS`. Siempre en línea: con una clave literal, el
/// `match` se resuelve al compilar.
#[inline(always)]
fn slot(key: &str) -> Option<usize> {
    match key {
        "align" => Some(0),
        "alt" => Some(1),
        "animate_layout" => Some(2),
        "autofocus" => Some(3),
        "bg" => Some(4),
        "bg_hover" => Some(5),
        "bg_pressed" => Some(6),
        "border_color" => Some(7),
        "border_width" => Some(8),
        "bottom" => Some(9),
        "capture" => Some(10),
        "chart" => Some(11),
        "checked" => Some(12),
        "children" => Some(13),
        "color" => Some(14),
        "cursor" => Some(15),
        "description" => Some(16),
        "direction" => Some(17),
        "draw" => Some(18),
        "drop_target" => Some(19),
        "enter" => Some(20),
        "exit" => Some(21),
        "expanded" => Some(22),
        "fit" => Some(23),
        "focus_color" => Some(24),
        "focusable" => Some(25),
        "font_family" => Some(26),
        "font_size" => Some(27),
        "font_weight" => Some(28),
        "gap" => Some(29),
        "gradient" => Some(30),
        "grow" => Some(31),
        "handlers" => Some(32),
        "height" => Some(33),
        "hidden" => Some(34),
        "justify" => Some(35),
        "key" => Some(36),
        "kind" => Some(37),
        "label" => Some(38),
        "layer" => Some(39),
        "left" => Some(40),
        "letter_spacing" => Some(41),
        "level" => Some(42),
        "line_height" => Some(43),
        "live" => Some(44),
        "max_height" => Some(45),
        "max_lines" => Some(46),
        "max_width" => Some(47),
        "memo" => Some(48),
        "min_height" => Some(49),
        "min_width" => Some(50),
        "modal" => Some(51),
        "multiline" => Some(52),
        "offset" => Some(53),
        "opacity" => Some(54),
        "orientation" => Some(55),
        "overflow" => Some(56),
        "padding" => Some(57),
        "password" => Some(58),
        "placeholder" => Some(59),
        "placeholder_color" => Some(60),
        "placement" => Some(61),
        "position" => Some(62),
        "position_in_set" => Some(63),
        "press_scale" => Some(64),
        "pulse" => Some(65),
        "radius" => Some(66),
        "reveal" => Some(67),
        "right" => Some(68),
        "role" => Some(69),
        "rows" => Some(70),
        "scroll" => Some(71),
        "scroll_anchor" => Some(72),
        "scrollbar_color" => Some(73),
        "selected" => Some(74),
        "selection_color" => Some(75),
        "set_size" => Some(76),
        "shadow" => Some(77),
        "shrink" => Some(78),
        "sort" => Some(79),
        "spans" => Some(80),
        "src" => Some(81),
        "stick_to_end" => Some(82),
        "style" => Some(83),
        "text" => Some(84),
        "text_align" => Some(85),
        "tooltip" => Some(86),
        "tooltip_bg" => Some(87),
        "tooltip_color" => Some(88),
        "top" => Some(89),
        "transition" => Some(90),
        "value" => Some(91),
        "value_max" => Some(92),
        "value_min" => Some(93),
        "value_step" => Some(94),
        "width" => Some(95),
        "window_drag" => Some(96),
        "wrap" => Some(97),
        _ => None,
    }
}

/// `KEYS` como cadenas internadas de Python, creadas una vez.
fn interned(py: Python<'_>) -> &[Py<PyString>] {
    static INTERNED: PyOnceLock<Vec<Py<PyString>>> = PyOnceLock::new();
    INTERNED.get_or_init(py, || {
        KEYS.iter()
            .map(|k| PyString::intern(py, k).unbind())
            .collect()
    })
}

/// Un dict del spec y qué claves de `KEYS` contiene. En el parse de un nodo se
/// consultan ~100 claves y casi todas faltan: con la máscara, una clave que
/// falta no llega a buscarse en el dict, y la máscara cuesta lo que las claves
/// que sí tiene (pocas).
struct Props<'a, 'py> {
    dict: &'a Bound<'py, PyDict>,
    mask: u128,
}

impl<'a, 'py> Props<'a, 'py> {
    /// Lee las claves de `dict` para saber cuáles faltan.
    fn new(dict: &'a Bound<'py, PyDict>) -> Self {
        let mut mask = 0u128;
        for k in dict.keys() {
            if let Ok(name) = k.cast::<PyString>()
                && let Ok(name) = name.to_str()
                && let Some(i) = slot(name)
            {
                mask |= 1 << i;
            }
        }
        Self { dict, mask }
    }

    /// Sin máscara: todas las claves se buscan (dicts en los que casi todas están).
    fn all(dict: &'a Bound<'py, PyDict>) -> Self {
        Self {
            dict,
            mask: u128::MAX,
        }
    }
}

/// Consulta una clave del spec. Las de `KEYS` se buscan con su cadena
/// internada, y solo si la máscara dice que están; una clave fuera de la tabla
/// se crea al momento.
#[inline(always)]
fn get<'py>(d: &Props<'_, 'py>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    let py = d.dict.py();
    let item = match slot(key) {
        Some(i) if d.mask & (1 << i) == 0 => return Ok(None),
        Some(i) => d.dict.get_item(interned(py)[i].bind(py)),
        None => d.dict.get_item(PyString::new(py, key)),
    }?;
    Ok(item.filter(|v| !v.is_none()))
}

#[inline(always)]
fn f32_of(d: &Props<'_, '_>, key: &str) -> PyResult<Option<f32>> {
    get(d, key)?.map(|v| v.extract::<f32>()).transpose()
}

#[inline(always)]
fn str_of(d: &Props<'_, '_>, key: &str) -> PyResult<Option<String>> {
    get(d, key)?.map(|v| v.extract::<String>()).transpose()
}

#[inline(always)]
fn len_of(d: &Props<'_, '_>, key: &str) -> PyResult<Option<Len>> {
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

#[inline(always)]
fn bool_of(d: &Props<'_, '_>, key: &str) -> PyResult<bool> {
    Ok(get(d, key)?
        .map(|v| v.is_truthy())
        .transpose()?
        .unwrap_or(false))
}

#[inline(always)]
fn opt_bool_of(d: &Props<'_, '_>, key: &str) -> PyResult<Option<bool>> {
    get(d, key)?.map(|v| v.is_truthy()).transpose()
}

#[inline(always)]
fn f64_of(d: &Props<'_, '_>, key: &str) -> PyResult<Option<f64>> {
    get(d, key)?.map(|v| v.extract::<f64>()).transpose()
}

#[inline(always)]
fn color_of(d: &Props<'_, '_>, key: &str) -> PyResult<Option<Color>> {
    str_of(d, key)?.map(|s| parse_color(&s)).transpose()
}

#[inline(always)]
fn edges_of(d: &Props<'_, '_>, key: &str) -> PyResult<Edges> {
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

fn parse_style(d: &Props<'_, '_>) -> PyResult<Style> {
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
    let transition = get(d, "transition")?
        .map(|v| motion::parse_timing(&v))
        .transpose()?;
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
            len_of(d, "top")?,
            len_of(d, "right")?,
            len_of(d, "bottom")?,
            len_of(d, "left")?,
        ],
        min_width: f32_of(d, "min_width")?,
        max_width: f32_of(d, "max_width")?,
        min_height: f32_of(d, "min_height")?,
        max_height: f32_of(d, "max_height")?,
        grow: f32_of(d, "grow")?.unwrap_or(0.0),
        shrink: f32_of(d, "shrink")?,
        wrap: bool_of(d, "wrap")?,
        clip: match str_of(d, "overflow")?.as_deref() {
            None | Some("visible") => false,
            Some("hidden") => true,
            Some(other) => {
                return Err(PyValueError::new_err(format!(
                    "overflow inválido: {other:?} (usa \"visible\" o \"hidden\")"
                )));
            }
        },
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
        reveal: get(d, "reveal")?
            .map(|v| {
                v.extract::<(f32, f32)>()
                    .map_err(|_| PyValueError::new_err("reveal debe ser (top, bottom)"))
            })
            .transpose()?,
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
        placement: match str_of(d, "placement")? {
            None => None,
            Some(name) => Some(
                Placement::parse(&name, f32_of(d, "offset")?.unwrap_or(0.0)).ok_or_else(|| {
                    PyValueError::new_err(format!(
                        "placement inválido: {name:?} (usa \"top\", \"bottom\", \"left\" o \"right\", con \"-start\", \"-center\" o \"-end\")"
                    ))
                })?,
            ),
        },
        spans: get(d, "spans")?
            .map(|v| Spans::parse(&v).map(Arc::new))
            .transpose()?,
        max_lines: f32_of(d, "max_lines")?.map(|n| n as usize),
        text_align: str_of(d, "text_align")?,
        multiline: bool_of(d, "multiline")?,
        password: bool_of(d, "password")?,
        placeholder: str_of(d, "placeholder")?,
        placeholder_color: color_of(d, "placeholder_color")?,
        selection_color: color_of(d, "selection_color")?,
        rows: f32_of(d, "rows")?.map_or(1, |n| n.max(1.0) as usize),
        tooltip: str_of(d, "tooltip")?.filter(|t| !t.is_empty()),
        cursor: match str_of(d, "cursor")? {
            None => None,
            Some(c) => Some(Cursor::parse(&c).ok_or_else(|| {
                PyValueError::new_err(format!(
                    "cursor inválido: {c:?} (usa \"default\", \"pointer\", \"text\", \"grab\", \"grabbing\", \"col-resize\", \"row-resize\", \"ns-resize\", \"ew-resize\", \"nesw-resize\" o \"nwse-resize\")"
                ))
            })?),
        },
        drop_target: bool_of(d, "drop_target")?,
        scroll_anchor: bool_of(d, "scroll_anchor")?,
        stick_to_end: bool_of(d, "stick_to_end")?,
        window_drag: match str_of(d, "window_drag")? {
            None => None,
            Some(name) => Some(WindowDrag::parse(&name).ok_or_else(|| {
                PyValueError::new_err(format!(
                    "window_drag inválido: {name:?} (usa \"move\" o un borde: \"n\", \"s\", \"e\", \"w\", \"ne\", \"nw\", \"se\" o \"sw\")"
                ))
            })?),
        },
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
        animate_layout: match get(d, "animate_layout")? {
            Some(v) => motion::parse_layout(&v, transition)?,
            None => None,
        },
        enter: get(d, "enter")?
            .map(|v| motion::parse_effect(&v, "enter"))
            .transpose()?,
        exit: get(d, "exit")?
            .map(|v| motion::parse_effect(&v, "exit"))
            .transpose()?,
        pulse: match get(d, "pulse")? {
            Some(v) => {
                let timing = motion::parse_timing(&v)?;
                if !matches!(timing, Timing::Pulse { .. }) {
                    return Err(PyValueError::new_err("pulse debe ser animate.pulse(...)"));
                }
                Some(timing)
            }
            None => None,
        },
        transition,
    })
}

fn inherit_text(d: &Props<'_, '_>, parent: &TextProps) -> PyResult<TextProps> {
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

/// Parser con memoria entre reconstrucciones. Los dicts que Python no volvió
/// a serializar (ramas de un `@component` o de la vista que no cambiaron)
/// llegan como el **mismo objeto** marcado con `memo`: su `Node` se comparte
/// con el parseo anterior en vez de volver a leer cada propiedad.
///
/// La memoria sobrevive a los parseos en que su dict no aparece (puede estar
/// dentro de otro reutilizado entero) y se poda cuando Python ya no guarda el
/// dict: entonces solo lo mantiene vivo esta memoria.
#[derive(Default)]
pub struct Parser {
    memo: HashMap<usize, Memo>,
    /// Tamaño de la memoria tras la última poda (se poda al doblarse).
    pruned: usize,
    /// Último árbol devuelto y sus keys: las de uno nuevo se comprueban solo en
    /// lo que cambió respecto a él (ver `key_changes`).
    prev: Option<Arc<Node>>,
    keys: HashSet<String>,
}

/// Nodo parseado de un dict memorizado.
struct Memo {
    /// Mantiene vivo el dict: mientras exista, su dirección no se reutiliza.
    dict: Py<PyAny>,
    /// Key resuelta de la raíz: de ella salen las de todo el subárbol.
    key: String,
    /// Lo heredado del padre también forma parte del resultado.
    inherited: TextProps,
    node: Arc<Node>,
}

/// Memorias por debajo de las cuales no merece la pena podar.
const PRUNE_MIN: usize = 256;

impl Parser {
    pub fn parse(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<Node> {
        let root = parse_node(obj, "0", &TextProps::default(), &mut self.memo)?;
        self.check_keys(&root)?;
        if self.memo.len() > PRUNE_MIN.max(self.pruned * 2) {
            // Coste amortizado: solo cuando la memoria dobla lo que quedó en la poda anterior.
            // SAFETY: con el GIL tomado (`obj` lo demuestra), y el dict está vivo:
            // lo mantiene esta misma memoria.
            self.memo
                .retain(|_, m| unsafe { pyo3::ffi::Py_REFCNT(m.dict.as_ptr()) } > 1);
            self.pruned = self.memo.len();
        }
        // Copia de la raíz sin sus hijos (que se comparten): la otra se queda en `prev`.
        let node = root.clone_ref(obj.py());
        self.prev = Some(root);
        Ok(node)
    }

    /// Falla si el árbol nuevo repite alguna key. Un árbol válido no repite
    /// ninguna, así que basta con mirar las que entran: no pueden estar entre
    /// las del árbol anterior que siguen, ni repetirse entre ellas.
    fn check_keys(&mut self, root: &Node) -> PyResult<()> {
        let (mut removed, mut added) = (Vec::new(), Vec::new());
        match &self.prev {
            Some(prev) => key_changes(prev, root, &mut removed, &mut added),
            None => root.collect_keys(&mut added),
        }
        let removed: HashSet<&str> = removed.into_iter().collect();
        let mut fresh = HashSet::with_capacity(added.len());
        for key in &added {
            let kept = self.keys.contains(*key) && !removed.contains(key);
            if kept || !fresh.insert(*key) {
                return Err(PyValueError::new_err(format!(
                    "key duplicada en el árbol de la vista: {key:?}"
                )));
            }
        }
        for key in removed {
            self.keys.remove(key);
        }
        self.keys.extend(added.into_iter().map(str::to_owned));
        Ok(())
    }
}

/// Keys que salen (`removed`) y que entran (`added`) al pasar de `old` a `new`,
/// sin recorrer los subárboles compartidos (el mismo `Arc`): cuesta lo que
/// cambió más los hijos de los nodos que cambiaron.
fn key_changes<'a>(
    old: &'a Node,
    new: &'a Node,
    removed: &mut Vec<&'a str>,
    added: &mut Vec<&'a str>,
) {
    if old.key != new.key {
        removed.push(&old.key);
        added.push(&new.key);
    }
    let (a, b) = (&old.children, &new.children);
    // Lo habitual: los mismos hijos en el mismo orden (compartidos o con la misma key).
    if a.len() == b.len() && a.iter().zip(b).all(|(x, y)| x.key == y.key) {
        for (x, y) in a.iter().zip(b) {
            if !Arc::ptr_eq(x, y) {
                key_changes(x, y, removed, added);
            }
        }
        return;
    }
    let before: HashSet<*const Node> = a.iter().map(Arc::as_ptr).collect();
    let mut after = HashSet::with_capacity(b.len());
    for child in b {
        if !after.insert(Arc::as_ptr(child)) {
            // El mismo subárbol dos veces entre hermanos: sus keys se repiten.
            child.collect_keys(added);
        }
    }
    // Los hijos que no siguen, por key: uno nuevo con la misma key se compara con él.
    let mut gone: HashMap<&str, &Node> = a
        .iter()
        .filter(|c| !after.contains(&Arc::as_ptr(c)))
        .map(|c| (c.key.as_str(), &**c))
        .collect();
    for child in b.iter().filter(|c| !before.contains(&Arc::as_ptr(c))) {
        match gone.remove(child.key.as_str()) {
            Some(was) => key_changes(was, child, removed, added),
            None => child.collect_keys(added),
        }
    }
    for was in gone.into_values() {
        was.collect_keys(removed);
    }
}

fn parse_node(
    obj: &Bound<'_, PyAny>,
    path: &str,
    inherited: &TextProps,
    memo: &mut HashMap<usize, Memo>,
) -> PyResult<Arc<Node>> {
    let d = &Props::all(obj.cast::<PyDict>()?);
    if !bool_of(d, "memo")? {
        return Ok(Arc::new(parse_fresh(d, path, inherited, memo)?));
    }
    let id = obj.as_ptr() as usize;
    let key = str_of(d, "key")?.unwrap_or_else(|| path.to_owned());
    if let Some(m) = memo.get(&id)
        && m.key == key
        && m.inherited == *inherited
    {
        return Ok(m.node.clone());
    }
    let node = Arc::new(parse_fresh(d, path, inherited, memo)?);
    memo.insert(
        id,
        Memo {
            dict: obj.clone().unbind(),
            key,
            inherited: inherited.clone(),
            node: node.clone(),
        },
    );
    Ok(node)
}

fn parse_fresh(
    d: &Props<'_, '_>,
    path: &str,
    inherited: &TextProps,
    memo: &mut HashMap<usize, Memo>,
) -> PyResult<Node> {
    let kind = match str_of(d, "kind")?.as_deref() {
        Some("text") => Kind::Text,
        Some("input") => Kind::Input,
        Some("image") => Kind::Image,
        Some("canvas") => Kind::Canvas,
        Some("chart") => Kind::Chart,
        _ => Kind::Box,
    };
    let style_dict = match get(d, "style")? {
        Some(s) => s.cast_into::<PyDict>()?,
        None => PyDict::new(d.dict.py()),
    };
    let props = Props::new(&style_dict);
    let style = parse_style(&props)?;
    let a11y = A11y::parse(&props)?;
    let text_props = inherit_text(&props, inherited)?;
    let key = str_of(d, "key")?.unwrap_or_else(|| path.to_owned());

    let children = match get(d, "children")? {
        Some(list) => list
            .cast::<PyList>()?
            .iter()
            .enumerate()
            .map(|(i, child)| parse_node(&child, &format!("{key}/{i}"), &text_props, memo))
            .collect::<PyResult<Vec<_>>>()?,
        None => Vec::new(),
    };

    let draw = match get(d, "draw")? {
        Some(cb) if cb.is_callable() => Some(cb.unbind()),
        Some(_) => return Err(PyValueError::new_err("draw debe ser callable")),
        None if kind == Kind::Canvas => {
            return Err(PyValueError::new_err("un canvas necesita una función draw"));
        }
        None => None,
    };

    let chart = match get(d, "chart")? {
        Some(obj) => {
            let dict = obj.cast_into::<PyDict>()?;
            Some(Arc::new(crate::chart::parse(&dict)?))
        }
        None if kind == Kind::Chart => {
            return Err(PyValueError::new_err("un chart necesita datos"));
        }
        None => None,
    };

    let has_placement = style.placement.is_some() || children.iter().any(|c| c.has_placement);
    let size = 1 + children.iter().map(|c| c.size).sum::<usize>();
    let below = children.iter().fold(0, |m, c| m | c.marks.0);
    let mut node = Node {
        key,
        kind,
        style,
        text: str_of(d, "text")?,
        text_props,
        a11y,
        children,
        has_placement,
        size,
        marks: Marks(0),
        handlers: parse_handlers(d)?,
        draw,
        chart,
    };
    node.marks = Marks(node.own_marks().0 | below);
    Ok(node)
}

fn parse_handlers(d: &Props<'_, '_>) -> PyResult<HashMap<String, Py<PyAny>>> {
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
