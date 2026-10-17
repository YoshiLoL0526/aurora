//! Motor de layout (Taffy) + pintura (Skia) + estado de animación.
//!
//! Todo lo que ocurre por frame vive aquí, fuera del intérprete de Python.

use std::cell::RefCell;
use std::collections::{HashMap, HashSet};
use std::hash::{DefaultHasher, Hash, Hasher};
use std::rc::Rc;
use std::time::{Duration, Instant};

use skia_safe::{
    BlurStyle, Canvas, ClipOp, Color, Color4f, EncodedImageFormat, FilterMode, FontMgr, FontStyle,
    IRect, MaskFilter, MipmapMode, Paint, PaintStyle, Picture, PictureRecorder, Point, RRect, Rect,
    SamplingOptions, Surface, TileMode,
    font_style::{Slant, Weight, Width},
    gradient::{self, Colors as GradientColors, Gradient as SkGradient},
    surfaces,
    textlayout::{
        FontCollection, Paragraph, ParagraphBuilder, ParagraphStyle, TextAlign, TextStyle,
    },
};
use taffy::{
    AlignItems, AvailableSpace, Dimension, Display, FlexDirection, FlexWrap, JustifyContent,
    LengthPercentage, LengthPercentageAuto, NodeId, Overflow, Position, Size, TaffyTree,
    TraversePartialTree, compute_leaf_layout,
};

use crate::color::lerp;
use crate::image::{Decoded, Fit, ImageCache, ImageError, Loaded};
use crate::input::{CARET_WIDTH, InputFrame, InputState, caret_rect, range_rects};
use crate::motion::{IDENTITY, Timing, Track, Vec4};
use crate::scroll::{BAR_WIDTH, ScrollState};
use crate::spec::{Axis, Cursor, Edges, Kind, Len, Node, Style, TextProps};

/// Contexto de las hojas del árbol de layout.
pub enum Leaf {
    Text(TextCtx),
    /// Imagen: su tamaño natural, para medirla manteniendo la proporción.
    Image(skia_safe::Size),
}

/// Contexto de los nodos hoja de texto: el párrafo ya "shapeado" se reutiliza
/// para medir (durante el layout) y para pintar.
pub struct TextCtx {
    paragraph: Paragraph,
    /// Lo que determina el párrafo: permite reutilizarlo en el siguiente layout.
    key: ParagraphKey,
    /// Solo en campos de texto: cómo se mide y se maqueta el párrafo.
    input: Option<InputLeaf>,
    /// Mediciones ya hechas. Taffy mide cada hoja varias veces por layout (mín.,
    /// máx., definitivo…) y cada medición rehace el layout del párrafo en Skia:
    /// memorizarlas, y conservarlas con el párrafo entre frames, lo evita.
    measures: Vec<Measured>,
    /// Ancho con el que está maquetado el párrafo ahora mismo, si se conoce:
    /// `finalize_text` no lo repite si ya coincide.
    laid_out: Option<f32>,
}

/// Una medición memorizada: restricciones de Taffy → tamaño y baseline.
#[derive(Clone, Copy)]
struct Measured {
    key: MeasureKey,
    size: Size<f32>,
    baseline: f32,
}

/// Restricciones de una medición. El alto disponible no influye en el texto.
#[derive(Clone, Copy, PartialEq)]
struct MeasureKey {
    known: Size<Option<f32>>,
    avail_width: AvailableSpace,
    /// El mismo párrafo se mide distinto en un campo de texto.
    input: Option<InputLeaf>,
}

/// Mediciones que se memorizan por párrafo (los textos rara vez pasan de 3 o 4).
const MAX_MEASURES: usize = 8;

/// Todo lo que determina el shaping de un párrafo. Dos párrafos con la misma
/// clave son intercambiables, así que al rehacer el layout se reutilizan por
/// contenido (no por key): sobreviven a reordenaciones y a keys de ruta.
#[derive(Clone, PartialEq, Eq, Hash)]
struct ParagraphKey {
    text: String,
    family: String,
    color: u32,
    size: u32,
    weight: i32,
    line_height: Option<u32>,
    letter_spacing: u32,
    max_lines: Option<usize>,
    align: Option<String>,
}

impl ParagraphKey {
    fn new(text: &str, tp: &TextProps, style: &Style) -> Self {
        Self {
            text: text.to_owned(),
            family: tp.family.clone(),
            color: u32::from_be_bytes([tp.color.a(), tp.color.r(), tp.color.g(), tp.color.b()]),
            size: tp.size.to_bits(),
            weight: tp.weight,
            line_height: tp.line_height.map(f32::to_bits),
            letter_spacing: tp.letter_spacing.to_bits(),
            max_lines: style.max_lines,
            align: style.text_align.clone(),
        }
    }
}

/// Layout persistente entre frames. Se reutiliza tal cual mientras no cambie
/// nada de lo que lo determina (el árbol, el tamaño de la ventana y el texto de
/// los campos); si algo cambia, se reconcilia por key en vez de rehacerse.
struct LayoutCache {
    tree: TaffyTree<Leaf>,
    root: Option<LayoutNode>,
    width: f32,
    height: f32,
    inputs: u64,
}

impl Default for LayoutCache {
    fn default() -> Self {
        Self {
            tree: TaffyTree::new(),
            root: None,
            width: 0.0,
            height: 0.0,
            inputs: 0,
        }
    }
}

/// Nodos de Taffy del layout anterior, a la espera de reutilizarse por key.
#[derive(Default)]
struct Previous {
    by_key: HashMap<String, NodeId>,
    /// Sustituidos por uno nuevo: se eliminan al terminar.
    retired: Vec<NodeId>,
}

/// Lo que debe llevar una hoja del árbol de Taffy, antes de crearlo: así se
/// compara con lo que ya tiene sin repetir el shaping.
enum LeafSpec {
    Image(skia_safe::Size),
    Text {
        key: ParagraphKey,
        props: TextProps,
        input: Option<InputLeaf>,
    },
}

#[derive(Clone, Copy, PartialEq)]
struct InputLeaf {
    multiline: bool,
    rows: usize,
}

/// Ancho por defecto de un campo sin tamaño (como unos 25 caracteres).
const INPUT_WIDTH: f32 = 200.0;
const INPUT_MIN_WIDTH: f32 = 40.0;
/// Ancho "infinito" para maquetar texto sin saltos de línea.
const UNBOUNDED: f32 = 1.0e6;

/// Árbol de layout paralelo al árbol de nodos.
pub struct LayoutNode {
    id: NodeId,
    /// Key del nodo: identifica su nodo de Taffy al reconciliar el siguiente árbol.
    key: String,
    children: Vec<LayoutNode>,
    /// Hasta dónde puede pintar el subárbol (sombras, anillo de foco, texto que
    /// desborda…), en coordenadas locales de su capa. Las capas superiores que
    /// contiene no cuentan: se pintan aparte.
    ink: Rect,
    /// Lo que pinta el propio nodo, sin sus hijos (o todo el subárbol de un nodo
    /// que se escala al pulsarlo, si está dentro de él): lo que hay que repintar
    /// si cambia de geometría o de aspecto.
    own: Rect,
    /// El pintor no puede saltarse el subárbol aunque quede fuera de la zona a
    /// repintar: contiene capas superiores (se encolan al recorrerlo) o campos de
    /// texto (su geometría se recalcula al pintarlos).
    sticky: bool,
}

/// Capa de composición: lo que se desplaza junto. La raíz es la capa 0, cada
/// `scroll` abre una para su contenido y cada capa superior (`overlay`) otra,
/// que se desplaza con sus ancestros pero escapa de su recorte.
///
/// Las regiones y la tinta se guardan en coordenadas locales de su capa (las
/// que tendrían con todos los `scroll` en su origen): desplazar no rehace el
/// layout ni las regiones, solo recoloca las capas.
struct Layer {
    /// Identidad de la capa entre layouts: vacía la raíz, `scroll:<key>` o
    /// `overlay:<key>`.
    owner: String,
    parent: Option<usize>,
    scroll: Option<ScrollLayer>,
    /// Capa superior: no la recortan los `scroll` que la contienen.
    unclipped: bool,
    /// Lo que puede pintar la capa, en coordenadas locales de su padre: la zona
    /// visible de un `scroll` o la tinta de una capa superior.
    extent: Rect,
    /// Calculado en cada frame: desplazamiento acumulado, recorte absoluto y
    /// cómo se pintó (para saber si hay que repintar su zona).
    offset: Point,
    clip: Rect,
    painted: Option<LayerPaint>,
}

/// Contenedor `scroll` que desplaza una capa.
struct ScrollLayer {
    key: String,
    axis: Axis,
    max: Point,
    /// Caja de relleno del `scroll`, en coordenadas locales de la capa padre.
    viewport: Rect,
}

/// Lo que se pintó de una capa en el último frame.
#[derive(Clone, Copy, PartialEq)]
struct LayerPaint {
    offset: Point,
    extent: Rect,
    /// Visibilidad y arrastre de la barra.
    bar: (f32, bool),
    /// Lo que se puede desplazar (el tamaño de la barra depende de ello).
    max: Point,
}

/// Tooltip pintado en el último frame.
#[derive(Clone, PartialEq)]
struct TipPaint {
    ink: Rect,
    alpha: f32,
    text: String,
    colors: (Color, Color),
}

/// Nodo que el inspector resalta sobre la interfaz.
#[derive(Clone, Debug, PartialEq)]
pub struct Mark {
    /// Rectángulo absoluto del nodo (píxeles lógicos).
    pub rect: Rect,
    /// Su padding: el modo selección lo tiñe aparte del contenido.
    pub padding: Edges,
    /// Etiqueta: tipo, key y tamaño.
    pub label: String,
    /// Bajo el puntero en modo selección (relleno); si no, el nodo elegido (contorno).
    pub hovered: bool,
}

/// Rectángulo absoluto de cada nodo, en orden de pintura (para hit-testing).
pub struct HitRegion {
    pub key: String,
    /// Rectángulo absoluto, ya desplazado por los `scroll` que lo contienen.
    pub rect: Rect,
    /// Zona visible: la intersección de los contenedores `scroll` que lo recortan
    /// y de los ancestros con `overflow="hidden"`.
    pub clip: Rect,
    /// Recorte que imponen los ancestros con `overflow="hidden"` (antes de
    /// combinar con el de su capa de `scroll`).
    object_clip: Rect,
    /// Rectángulo y tinta del subárbol en coordenadas locales de su capa.
    local: Rect,
    ink: Rect,
    /// Lo que pinta el propio nodo (`LayoutNode::own`), en coordenadas locales.
    own: Rect,
    layer: usize,
    pub interactive: bool,
    pub capture: bool,
    pub focusable: bool,
    /// Campo de texto: cursor de texto al pasar y el clic coloca el cursor.
    pub editable: bool,
    /// Tiene `tooltip`.
    pub tooltip: bool,
    /// Propiedad `cursor` del nodo.
    pub cursor: Option<Cursor>,
    pub scroll: Option<Axis>,
    /// Índice del padre en el vector de regiones (para subir hasta un nodo interactivo).
    pub parent: Option<usize>,
}

impl HitRegion {
    fn contains(&self, x: f32, y: f32) -> bool {
        let inside = |r: &Rect| x >= r.left && x < r.right && y >= r.top && y < r.bottom;
        inside(&self.rect) && inside(&self.clip)
    }
}

/// Índice de la región pintada más arriba que contiene el punto (respetando recortes).
pub fn topmost(regions: &[HitRegion], x: f32, y: f32) -> Option<usize> {
    regions.iter().rposition(|r| r.contains(x, y))
}

/// Recorre la región y sus ancestros, de dentro hacia fuera.
pub fn ancestors(regions: &[HitRegion], idx: Option<usize>) -> impl Iterator<Item = &HitRegion> {
    std::iter::successors(idx.map(|i| &regions[i]), |r| r.parent.map(|p| &regions[p]))
}

/// Hit-testing: el nodo pintado más arriba bajo el cursor decide; el clic
/// burbujea hasta el ancestro interactivo más cercano o se detiene en una barrera.
pub fn hit_test(regions: &[HitRegion], x: f32, y: f32) -> Option<String> {
    let mut idx = topmost(regions, x, y)?;
    loop {
        let r = &regions[idx];
        if r.interactive {
            return Some(r.key.clone());
        }
        if r.capture {
            return None;
        }
        idx = r.parent?;
    }
}

#[derive(Default, Clone, Copy, Debug)]
pub struct AnimState {
    pub hover: f32,
    pub press: f32,
    /// Visibilidad del anillo de foco.
    pub focus: f32,
}

/// Animaciones declarativas en curso de un nodo (ver `motion.rs`).
#[derive(Default)]
struct Motion {
    /// Propiedades con `transition`: colores (`a, r, g, b`) y escalares.
    bg: Option<Track>,
    border: Option<Track>,
    /// Color del texto: el párrafo lleva el color dentro y se rehace cada frame
    /// mientras dura la transición (ver `recolor_texts`).
    text: Option<Track>,
    opacity: Option<Track>,
    radius: Option<Track>,
    /// Vaivén perpetuo de la opacidad (`pulse`): nunca termina.
    pulse: Option<Track>,
    /// Caja que se muestra (`l, t, r, b`, en coordenadas locales de su capa)
    /// mientras se desliza hacia la que le dio el layout (`animate_layout`).
    layout: Option<Track>,
    /// Efecto de entrada (`opacidad, x, y, escala`) camino de la identidad.
    enter: Option<Track>,
    /// Zona (absoluta y visible) en la que se pintó desplazado o transformado
    /// en el último frame: hay que repintarla cuando se mueve o termina.
    painted: Option<Rect>,
}

impl Motion {
    fn is_empty(&self) -> bool {
        !self.restyled() && !self.transformed()
    }

    /// Alguna propiedad de estilo está en transición.
    fn restyled(&self) -> bool {
        self.bg.is_some()
            || self.border.is_some()
            || self.text.is_some()
            || self.opacity.is_some()
            || self.radius.is_some()
            || self.pulse.is_some()
    }

    /// Se pinta fuera de su caja o transformado: desplazado por el layout o
    /// con el efecto de entrada.
    fn transformed(&self) -> bool {
        self.layout.is_some() || self.enter.is_some()
    }
}

/// Nodo que salió de la vista con `exit`: se pinta una instantánea suya (como
/// estaba al salir) mientras avanza su efecto de salida. No ocupa sitio en el
/// layout ni recibe eventos.
struct Ghost {
    key: String,
    picture: Picture,
    /// Caja que mostraba y su tinta, en coordenadas locales de su capa.
    rect: Rect,
    ink: Rect,
    /// Capa en la que estaba, con su desplazamiento y recorte al salir (por si
    /// la capa desaparece con él).
    layer: String,
    offset: Point,
    clip: Rect,
    /// Estaba dentro de una capa superior: se pinta por encima de ellas.
    overlay: bool,
    /// Efecto de salida, de la identidad a los valores de `exit`.
    track: Track,
    painted: Option<Rect>,
}

pub struct Engine {
    fonts: FontCollection,
    anim: HashMap<String, AnimState>,
    /// Animaciones declarativas de cada nodo, por key.
    motion: HashMap<String, Motion>,
    /// Nodos que salieron con `exit` y aún se están yendo.
    ghosts: Vec<Ghost>,
    /// Nodos transformados por una animación y sus ancestros: el pintor no
    /// puede descartarlos por su tinta, que no cuenta con la transformación.
    moving: HashSet<String>,
    /// Estado de cada contenedor `scroll`, por key.
    pub scroll: HashMap<String, ScrollState>,
    /// Estado de cada campo de texto, por key.
    pub inputs: HashMap<String, InputState>,
    /// Imagen decodificada de cada nodo `image` del árbol actual, por key.
    images: HashMap<String, Rc<Loaded>>,
    image_cache: ImageCache,
    /// Dibujo grabado de cada `canvas`, por key (lo graba `canvas::Canvases`).
    pictures: HashMap<String, Picture>,
    /// Gráfico grabado de cada `chart`, por key (lo graba `chart::Charts`).
    charts: HashMap<String, Picture>,
    pub hovered: Option<String>,
    pub pressed: Option<String>,
    pub focused: Option<String>,
    /// El anillo de foco se muestra solo si se llegó con el teclado (como
    /// `:focus-visible` en CSS): un clic enfoca sin dibujar el anillo.
    pub focus_visible: bool,
    pub tip: Tip,
    /// Lo que tardó el layout del último `update` (para las estadísticas del frame).
    pub layout_time: Duration,
    /// Si el último `update` reutilizó el layout del frame anterior.
    pub layout_cached: bool,
    layout_cache: Option<LayoutCache>,
    /// El árbol cambió desde el último layout (lo decide `restyle`).
    tree_changed: bool,
    /// Párrafos del layout anterior, por contenido, a la espera de reutilizarse
    /// mientras se construye el siguiente.
    recycled: RefCell<HashMap<ParagraphKey, Vec<TextCtx>>>,
    /// Regiones de hit-testing del layout actual, en orden de pintura.
    pub regions: Vec<HitRegion>,
    layers: Vec<Layer>,
    /// Escala con la que se pintó el último frame.
    scale: f32,
    /// Nodos que cambiaron solo de aspecto al reconstruir (fase de estilo).
    restyled: Vec<String>,
    /// Nodos que cambiaron de aspecto en reconstrucciones que sí rehacen el
    /// layout, desde el último layout. `None`: no se sabe (primer frame, una
    /// imagen que cambió…) y el próximo layout lo repinta todo.
    repainted: Option<HashSet<String>>,
    /// Nodos cuya transición (hover, pressed, foco) avanzó desde el último frame.
    animated: Vec<String>,
    /// Huella visual de cada campo de texto en el último frame (cursor, selección…).
    inputs_painted: HashMap<String, u64>,
    tip_painted: Option<TipPaint>,
    /// Lo que resalta el inspector en el próximo frame (lo fija el runtime).
    pub marks: Vec<Mark>,
    /// Lo que resaltó en el último frame y la tinta de cada resaltado.
    marks_painted: Vec<(Mark, Rect)>,
    /// Zona repintada en el último `paint` (`None`: nada).
    pub damage: Option<Rect>,
    /// Lo que `update` deja pendiente para el próximo `paint`: repintarlo
    /// todo (tras un layout o un cambio de escala) o la zona de las capas que
    /// se movieron.
    full: bool,
    pending: Option<Rect>,
}

/// Retardo antes de mostrar un tooltip (segundos).
pub const TIP_DELAY: f32 = 0.5;

/// Tooltip del nodo bajo el puntero.
#[derive(Default)]
pub struct Tip {
    /// Nodo con `tooltip` bajo el puntero.
    pub key: Option<String>,
    /// Segundos (reales) que lleva el puntero encima.
    pub timer: f32,
    /// Visibilidad de la burbuja, de 0 a 1.
    pub alpha: f32,
    /// Tras un clic no se muestra hasta que el puntero cambie de nodo.
    pub suppressed: bool,
}

impl Tip {
    pub fn ready(&self) -> bool {
        self.key.is_some() && !self.suppressed && self.timer >= TIP_DELAY
    }

    /// Cambia el nodo bajo el puntero. Devuelve `true` si cambió.
    pub fn set_key(&mut self, key: Option<String>) -> bool {
        if self.key == key {
            return false;
        }
        self.key = key;
        self.timer = 0.0;
        self.alpha = 0.0;
        self.suppressed = false;
        true
    }
}

/// Constante de tiempo de las transiciones de estado (segundos).
const TRANSITION_TAU: f32 = 0.07;

impl Engine {
    pub fn new() -> Self {
        let mut fonts = FontCollection::new();
        fonts.set_default_font_manager(FontMgr::new(), "Inter");
        Self {
            fonts,
            anim: HashMap::new(),
            motion: HashMap::new(),
            ghosts: Vec::new(),
            moving: HashSet::new(),
            scroll: HashMap::new(),
            inputs: HashMap::new(),
            images: HashMap::new(),
            image_cache: ImageCache::default(),
            pictures: HashMap::new(),
            charts: HashMap::new(),
            hovered: None,
            pressed: None,
            focused: None,
            focus_visible: false,
            tip: Tip::default(),
            layout_time: Duration::ZERO,
            layout_cached: false,
            layout_cache: None,
            tree_changed: true,
            recycled: RefCell::default(),
            regions: Vec::new(),
            layers: Vec::new(),
            scale: 0.0,
            restyled: Vec::new(),
            repainted: None,
            animated: Vec::new(),
            inputs_painted: HashMap::new(),
            tip_painted: None,
            marks: Vec::new(),
            marks_painted: Vec::new(),
            damage: None,
            full: true,
            pending: None,
        }
    }

    // ------------------------------------------------------------------ texto

    fn paragraph(&self, text: &str, tp: &TextProps, style: &Style) -> Paragraph {
        let mut ts = TextStyle::new();
        ts.set_color(tp.color)
            .set_font_size(tp.size)
            .set_font_families(&[tp.family.as_str()])
            .set_letter_spacing(tp.letter_spacing)
            .set_font_style(FontStyle::new(
                Weight::from(tp.weight),
                Width::NORMAL,
                Slant::Upright,
            ));
        if let Some(lh) = tp.line_height {
            ts.set_height(lh).set_height_override(true);
        }
        let mut ps = ParagraphStyle::new();
        ps.set_text_style(&ts);
        if let Some(n) = style.max_lines {
            ps.set_max_lines(n).set_ellipsis("…");
        }
        ps.set_text_align(match style.text_align.as_deref() {
            Some("center") => TextAlign::Center,
            Some("right") => TextAlign::Right,
            _ => TextAlign::Left,
        });
        let mut builder = ParagraphBuilder::new(&ps, self.fonts.clone());
        builder.push_style(&ts);
        builder.add_text(text);
        builder.build()
    }

    /// Contexto de una hoja de texto. Reutiliza el shaping (y las mediciones)
    /// de un párrafo idéntico que haya quedado libre en este layout, si lo hay.
    fn text_ctx(
        &self,
        key: ParagraphKey,
        props: &TextProps,
        style: &Style,
        input: Option<InputLeaf>,
    ) -> TextCtx {
        if let Some(mut ctx) = self.recycled.borrow_mut().get_mut(&key).and_then(Vec::pop) {
            ctx.input = input;
            return ctx;
        }
        TextCtx {
            paragraph: self.paragraph(&key.text, props, style),
            key,
            input,
            measures: Vec::new(),
            laid_out: None,
        }
    }

    // ---------------------------------------------------------- campos de texto

    /// Lo que muestra un campo: su valor (con la composición del IME) o, si
    /// está vacío, el placeholder en un color atenuado. Devuelve el texto, sus
    /// propiedades y si es el placeholder.
    fn input_display(&self, node: &Node) -> (String, TextProps, bool) {
        let value = match self.inputs.get(&node.key) {
            Some(state) => state.display(),
            None => node.text.clone().unwrap_or_default(),
        };
        let s = &node.style;
        if !value.is_empty() {
            let mut text = value;
            if !s.multiline {
                text = text.replace('\n', " ");
            }
            return (text, node.text_props.clone(), false);
        }
        let tp = &node.text_props;
        let mut props = tp.clone();
        props.color = s
            .placeholder_color
            .unwrap_or_else(|| tp.color.with_a((tp.color.a() as f32 * 0.45) as u8));
        (s.placeholder.clone().unwrap_or_default(), props, true)
    }

    /// Huella del texto que muestran los campos: si cambia (se escribe, se
    /// compone o se deshace sin reconstruir la vista), el layout cacheado no vale.
    fn inputs_signature(&self) -> u64 {
        self.inputs.iter().fold(0u64, |acc, (key, state)| {
            let mut h = DefaultHasher::new();
            (key, state.display()).hash(&mut h);
            // Suma: no depende del orden de iteración del mapa.
            acc.wrapping_add(h.finish())
        })
    }

    /// Fase de estilo: compara el árbol nuevo con el anterior y decide en qué
    /// fase entra cada cambio. Si algún nodo cambia algo que afecta al layout
    /// o a la geometría (estructura, keys, estilo de Taffy, texto, métricas de
    /// fuente, manejadores, capas, sombra…), se rehace el layout. Si no, el
    /// layout y las regiones siguen valiendo y solo se repintan los nodos que
    /// cambiaron de aspecto; un texto que solo cambia de color se vuelve a
    /// "shapear" en su nodo, sin medirlo de nuevo.
    ///
    /// Si hay que rehacer el layout, se anotan además los nodos que cambiaron
    /// de aspecto (`repainted`): tras el layout, `update` repinta solo esos y
    /// los que cambiaron de geometría.
    pub fn restyle(&mut self, old: Option<&Node>, new: &Node) {
        let Some(old) = old else {
            self.tree_changed = true;
            self.repainted = None;
            return;
        };
        self.animate_changes(old, new);
        if !self.tree_changed
            && let Some(mut cache) = self.layout_cache.take()
        {
            let mut changed = Vec::new();
            let relayout = match &cache.root {
                Some(lroot) => self.restyle_node(&mut cache.tree, old, new, lroot, &mut changed),
                None => true,
            };
            self.layout_cache = Some(cache);
            if !relayout {
                self.restyled.extend(changed);
                return;
            }
        }
        // Con varias reconstrucciones antes del layout se acumula lo de cada una:
        // un nodo distinto del último maquetado lo es en alguno de los pasos.
        self.tree_changed = true;
        if let Some(repainted) = &mut self.repainted {
            repainted_nodes(old, new, repainted);
        }
    }

    // ------------------------------------------------- animaciones declarativas

    /// Lo que una reconstrucción pone en marcha antes del layout: las
    /// transiciones de estilo (`transition`) y las salidas (`exit`). Un nodo que
    /// vuelve mientras se iba deja de irse y entra desde donde estaba.
    fn animate_changes(&mut self, old: &Node, new: &Node) {
        let mut before: HashMap<&str, &Node> = HashMap::new();
        let mut stack = vec![old];
        while let Some(n) = stack.pop() {
            if n.style.transition.is_some() || n.style.exit.is_some() {
                before.insert(n.key.as_str(), n);
            }
            stack.extend(&n.children);
        }
        if before.is_empty() && self.motion.is_empty() && self.ghosts.is_empty() {
            return;
        }
        let mut present = HashSet::new();
        let mut stack = vec![new];
        while let Some(n) = stack.pop() {
            present.insert(n.key.as_str());
            if let Some(timing) = n.style.transition
                && let Some(o) = before.get(n.key.as_str())
            {
                self.retarget_style(o, n, timing);
            }
            stack.extend(&n.children);
        }
        let mut i = 0;
        while i < self.ghosts.len() {
            if !present.contains(self.ghosts[i].key.as_str()) {
                i += 1;
                continue;
            }
            let ghost = self.ghosts.remove(i);
            self.pending = union(self.pending, ghost.painted);
            if let Some(node) = new.find(&ghost.key)
                && let Some(enter) = node.style.enter
            {
                let timing = enter.timing.or(node.style.transition).unwrap_or_default();
                let m = self.motion.entry(ghost.key).or_default();
                m.enter = Some(Track::new(ghost.track.value(), IDENTITY, timing));
            }
        }
        // Solo el nodo más alto que sale: sus descendientes van en su instantánea.
        let mut exits = Vec::new();
        let mut stack = vec![old];
        while let Some(n) = stack.pop() {
            if n.style.exit.is_some() && !present.contains(n.key.as_str()) {
                exits.push(n);
            } else {
                stack.extend(&n.children);
            }
        }
        for node in exits {
            if let Some(ghost) = self.snapshot(node) {
                self.ghosts.push(ghost);
            }
        }
        let pending = &mut self.pending;
        self.motion.retain(|key, m| {
            let keep = present.contains(key.as_str());
            if !keep {
                *pending = union(*pending, m.painted);
            }
            keep
        });
    }

    /// Anima hacia el estilo nuevo las propiedades que cambiaron, desde lo que
    /// se ve ahora (una transición a medias cambia de destino sin saltos).
    fn retarget_style(&mut self, old: &Node, new: &Node, timing: Timing) {
        let (a, b) = (&old.style, &new.style);
        let scalar = |v: f32| Some([v, 0.0, 0.0, 0.0]);
        let changes = [
            color_pair(a.bg, b.bg),
            color_pair(a.border_color, b.border_color),
            color_pair(Some(old.text_props.color), Some(new.text_props.color)),
            (scalar(a.opacity), scalar(b.opacity)),
            (scalar(a.radius), scalar(b.radius)),
        ];
        // Lo habitual es que nada cambie: entonces no hace falta ni la entrada.
        if !self.motion.contains_key(&new.key) && changes.iter().all(|(from, to)| from == to) {
            return;
        }
        let m = self.motion.entry(new.key.clone()).or_default();
        let slots = [
            &mut m.bg,
            &mut m.border,
            &mut m.text,
            &mut m.opacity,
            &mut m.radius,
        ];
        for (slot, change) in slots.into_iter().zip(changes) {
            match (slot.as_mut(), change) {
                (Some(track), (_, Some(to))) => track.retarget(to, timing),
                (None, (Some(from), Some(to))) if from != to => {
                    *slot = Some(Track::new(from, to, timing));
                }
                _ => {}
            }
        }
        if m.is_empty() && m.painted.is_none() {
            self.motion.remove(&new.key);
        }
    }

    /// Instantánea de un nodo que sale con `exit`, tal como se pintó en el
    /// último frame (con su layout, que aún es el anterior). `None` si no se
    /// llegó a pintar.
    fn snapshot(&self, node: &Node) -> Option<Ghost> {
        let exit = node.style.exit?;
        let cache = self.layout_cache.as_ref()?;
        let lnode = find_layout(cache.root.as_ref()?, &node.key)?;
        // Con varias reconstrucciones antes del layout, el árbol anterior puede
        // no ser el que está maquetado.
        if !same_keys(node, lnode) {
            return None;
        }
        let region = self.regions.iter().rev().find(|r| r.key == node.key)?;
        let layout = cache.tree.layout(lnode.id).ok()?;
        let origin = Point::new(
            region.local.left - layout.location.x,
            region.local.top - layout.location.y,
        );
        let (rect, ink) = match self.motion.get(&node.key) {
            Some(m) => (shown_rect(m, region.local), motion_ink(m, region)),
            None => (region.local, region.ink),
        };
        let mut recorder = PictureRecorder::new();
        let canvas = recorder.begin_recording(ink, false);
        let mut painter = Painter {
            engine: self,
            canvas,
            tree: &cache.tree,
            scale: if self.scale > 0.0 { self.scale } else { 1.0 },
            damage: no_clip(),
            overlays: Vec::new(),
            inputs: Vec::new(),
            moved: Point::default(),
            cull: false,
        };
        painter.paint_node(node, lnode, origin, Point::default());
        let mut i = 0;
        while let Some(&(node, lnode, origin, shift)) = painter.overlays.get(i) {
            painter.paint_node(node, lnode, origin, shift);
            i += 1;
        }
        drop(painter);
        let picture = recorder.finish_recording_as_picture(None)?;
        let layer = &self.layers[region.layer];
        let timing = exit.timing.or(node.style.transition).unwrap_or_default();
        Some(Ghost {
            key: node.key.clone(),
            picture,
            rect,
            ink,
            layer: layer.owner.clone(),
            offset: layer.offset,
            clip: region.clip,
            overlay: self.in_overlay(region.layer),
            track: Track::new(IDENTITY, exit.values, timing),
            painted: None,
        })
    }

    /// Si la capa es una capa superior o está dentro de una.
    fn in_overlay(&self, layer: usize) -> bool {
        std::iter::successors(Some(layer), |&l| self.layers[l].parent)
            .any(|l| self.layers[l].unclipped)
    }

    /// Tras un layout: los nodos con `animate_layout` cuya caja cambió se
    /// deslizan desde la que mostraban, y los que aparecen con `enter` entran
    /// (salvo en el primer frame). Al cambiar el tamaño de la ventana el
    /// layout salta, sin animarse. `old`: regiones y capas del layout anterior.
    fn start_motions(
        &mut self,
        root: &Node,
        old: &[HitRegion],
        old_layers: &[Layer],
        resized: bool,
    ) {
        let mut nodes: HashMap<&str, &Node> = HashMap::new();
        let mut stack = vec![root];
        while let Some(n) = stack.pop() {
            if n.style.animate_layout.is_some()
                || n.style.enter.is_some()
                || n.style.pulse.is_some()
            {
                nodes.insert(n.key.as_str(), n);
            }
            stack.extend(&n.children);
        }
        // Un nodo que deja de tener `animate_layout` se queda en su caja.
        for (key, m) in &mut self.motion {
            if nodes
                .get(key.as_str())
                .is_none_or(|n| n.style.animate_layout.is_none())
            {
                m.layout = None;
            }
        }
        if nodes.is_empty() {
            return;
        }
        let first = old.is_empty();
        let before: HashMap<&str, usize> = old
            .iter()
            .enumerate()
            .filter(|(_, r)| nodes.contains_key(r.key.as_str()))
            .map(|(i, r)| (r.key.as_str(), i))
            .collect();
        for r in &self.regions {
            let Some(node) = nodes.get(r.key.as_str()) else {
                continue;
            };
            match before.get(r.key.as_str()) {
                Some(&i) => {
                    let Some(timing) = node.style.animate_layout else {
                        continue;
                    };
                    let o = &old[i];
                    let to = rect4(r.local);
                    let other_layer = old_layers[o.layer].owner != self.layers[r.layer].owner;
                    let m = self.motion.entry(r.key.clone()).or_default();
                    match &mut m.layout {
                        _ if resized || other_layer => m.layout = None,
                        Some(track) => track.retarget(to, timing),
                        None if o.local != r.local => {
                            m.layout = Some(Track::new(rect4(o.local), to, timing));
                        }
                        None => {}
                    }
                }
                None if !first => {
                    let Some(enter) = node.style.enter else {
                        continue;
                    };
                    let m = self.motion.entry(r.key.clone()).or_default();
                    if m.enter.is_none() {
                        let timing = enter.timing.or(node.style.transition).unwrap_or_default();
                        m.enter = Some(Track::new(enter.values, IDENTITY, timing));
                    }
                }
                None => {}
            }
        }
        // Los nodos con `pulse` laten desde el primer frame; su valor inicial
        // (t = 0) es opacidad plena, así que las capturas siguen siendo fijas.
        for r in &self.regions {
            let Some(node) = nodes.get(r.key.as_str()) else {
                continue;
            };
            let Some(timing @ Timing::Pulse { floor, .. }) = node.style.pulse else {
                continue;
            };
            let m = self.motion.entry(r.key.clone()).or_default();
            if m.pulse.is_none() {
                m.pulse = Some(Track::new(IDENTITY, [floor, 0.0, 0.0, 1.0], timing));
            }
        }
        self.motion
            .retain(|_, m| !m.is_empty() || m.painted.is_some());
    }

    /// Recalcula `moving`: los nodos transformados y sus ancestros.
    fn refresh_moving(&mut self) {
        self.moving.clear();
        if !self.motion.values().any(Motion::transformed) {
            return;
        }
        for r in &self.regions {
            if !self.motion.get(&r.key).is_some_and(Motion::transformed) {
                continue;
            }
            let mut at = Some(r);
            while let Some(region) = at {
                if !self.moving.insert(region.key.clone()) {
                    break;
                }
                at = region.parent.map(|p| &self.regions[p]);
            }
        }
    }

    /// Si queda alguna animación declarativa en curso (o un nodo saliendo).
    pub fn animating(&self) -> bool {
        !self.ghosts.is_empty() || self.motion.values().any(|m| !m.is_empty())
    }

    /// Zona que hay que repintar por las animaciones que transforman nodos (o
    /// los que salen): donde se pintaron en el último frame y donde se pintan
    /// en este, hasta que terminan.
    fn motion_damage(&mut self) -> Option<Rect> {
        let mut damage = None;
        let (regions, layers) = (&self.regions, &self.layers);
        let visible =
            |ink: Rect, r: &HitRegion| intersect(ink.with_offset(-layers[r.layer].offset), r.clip);
        for (key, m) in &mut self.motion {
            let now = if m.transformed() {
                regions
                    .iter()
                    .rev()
                    .find(|r| r.key == *key)
                    .map(|r| visible(motion_ink(m, r), r))
            } else {
                None
            };
            // Mientras se transforma se repinta en cada frame: la opacidad del
            // efecto de entrada cambia aunque su tinta no se mueva.
            damage = union(union(damage, m.painted), now);
            m.painted = now;
        }
        for i in 0..self.ghosts.len() {
            let g = &self.ghosts[i];
            let (offset, clip) = self.ghost_place(g);
            let ink = effect_rect(g.ink, g.rect.center(), g.track.value());
            let now = Some(intersect(
                ink.with_outset((1.0, 1.0)).with_offset(-offset),
                clip,
            ));
            let g = &mut self.ghosts[i];
            damage = union(union(damage, g.painted), now);
            g.painted = now;
        }
        damage
    }

    /// Desplazamiento y recorte de la capa de un nodo que sale: los actuales
    /// si la capa sigue existiendo y, si no, los que tenía al salir.
    fn ghost_place(&self, g: &Ghost) -> (Point, Rect) {
        self.layers
            .iter()
            .find(|l| l.owner == g.layer)
            .map_or((g.offset, g.clip), |l| (l.offset, l.clip))
    }

    /// Pinta las instantáneas de los nodos que salen: las de la capa base
    /// (`overlay = false`, antes de las capas superiores) o las de dentro de
    /// una capa superior (después de ellas).
    fn paint_ghosts(&self, canvas: &Canvas, overlay: bool) {
        for g in self.ghosts.iter().filter(|g| g.overlay == overlay) {
            let (offset, clip) = self.ghost_place(g);
            let v = g.track.value();
            let count = canvas.save();
            canvas.clip_rect(clip, ClipOp::Intersect, true);
            canvas.translate(-offset);
            apply_effect(canvas, g.rect, v);
            let alpha = v[0].clamp(0.0, 1.0);
            if alpha < 1.0 {
                canvas.save_layer_alpha_f(None, alpha);
            }
            canvas.draw_picture(&g.picture, None, None);
            canvas.restore_to_count(count);
        }
    }

    /// Devuelve `true` si el cambio de `old` a `new` necesita rehacer el layout.
    fn restyle_node(
        &self,
        tree: &mut TaffyTree<Leaf>,
        old: &Node,
        new: &Node,
        lnode: &LayoutNode,
        changed: &mut Vec<String>,
    ) -> bool {
        if !same_shape(old, new) {
            return true;
        }
        // Lo habitual es que el nodo no cambie: solo se mira qué cambió si el estilo difiere.
        if old.style != new.style || old.text_props != new.text_props {
            if !same_geometry(old, new) {
                return true;
            }
            if new.kind == Kind::Text && !self.recolor(tree, new, lnode.id) {
                return true;
            }
            changed.push(new.key.clone());
        }
        old.children
            .iter()
            .zip(&new.children)
            .zip(&lnode.children)
            .any(|((a, b), l)| self.restyle_node(tree, a, b, l, changed))
    }

    /// Rehace el párrafo de un texto cuyas métricas no cambiaron (solo su
    /// color): mismo ancho de maquetado y mismas mediciones. Devuelve `false`
    /// si no se puede y hay que rehacer el layout.
    fn recolor(&self, tree: &mut TaffyTree<Leaf>, node: &Node, id: NodeId) -> bool {
        let Some(Leaf::Text(ctx)) = tree.get_node_context_mut(id) else {
            return false;
        };
        let text = node.text.as_deref().unwrap_or("");
        let key = ParagraphKey::new(text, &node.text_props, &node.style);
        if ctx.key == key {
            return true;
        }
        let Some(width) = ctx.laid_out else {
            return false;
        };
        let mut paragraph = self.paragraph(text, &node.text_props, &node.style);
        paragraph.layout(width);
        ctx.paragraph = paragraph;
        ctx.key = key;
        true
    }

    /// Rehace los párrafos cuyo color está en transición: Skia guarda el color
    /// dentro del párrafo, así que cada frame se reescribe con el valor actual
    /// de la pista (mismo ancho medido). Solo corre mientras dura la transición.
    fn recolor_texts(&self, root: &Node, cache: &mut LayoutCache) {
        let moving: Vec<(&str, Vec4)> = self
            .motion
            .iter()
            .filter_map(|(key, m)| Some((key.as_str(), m.text.as_ref()?.value())))
            .collect();
        if moving.is_empty() {
            return;
        }
        let Some(lroot) = cache.root.as_ref() else {
            return;
        };
        for (key, value) in moving {
            let Some(node) = root.find(key) else {
                continue;
            };
            if node.kind != Kind::Text {
                continue;
            }
            let Some(lnode) = find_layout(lroot, key) else {
                continue;
            };
            let Some(Leaf::Text(ctx)) = cache.tree.get_node_context_mut(lnode.id) else {
                continue;
            };
            let text = node.text.as_deref().unwrap_or("");
            let props = TextProps {
                color: vec_color(value),
                ..node.text_props.clone()
            };
            let pk = ParagraphKey::new(text, &props, &node.style);
            if ctx.key == pk {
                continue;
            }
            let Some(width) = ctx.laid_out else {
                continue;
            };
            let mut paragraph = self.paragraph(text, &props, &node.style);
            paragraph.layout(width);
            ctx.paragraph = paragraph;
            ctx.key = pk;
        }
    }

    /// Deja el párrafo de una hoja que cambia en la reserva, para que otro nodo
    /// de este mismo layout pueda reutilizarlo (p. ej. al reordenar textos).
    fn recycle(&self, leaf: Leaf) {
        if let Leaf::Text(ctx) = leaf {
            self.recycled
                .borrow_mut()
                .entry(ctx.key.clone())
                .or_default()
                .push(ctx);
        }
    }

    /// Crea, actualiza o descarta el estado de los campos según el árbol nuevo.
    /// Si Python cambió el valor (p. ej. lo vació al enviar), se adopta.
    pub fn sync_inputs(&mut self, root: &Node) {
        let mut alive = HashSet::new();
        let mut stack = vec![root];
        while let Some(node) = stack.pop() {
            if node.is_editable() {
                let text = node.text.as_deref().unwrap_or("");
                let state = self
                    .inputs
                    .entry(node.key.clone())
                    .or_insert_with(|| InputState::new(text, node.style.multiline));
                state.editor.set_external(text);
                state.multiline = node.style.multiline;
                alive.insert(node.key.clone());
            }
            stack.extend(node.children.iter());
        }
        self.inputs.retain(|k, _| alive.contains(k));
    }

    /// Carga (o toma de la caché) las imágenes del árbol. Un archivo que falta
    /// o no se puede decodificar es un error de la vista, con la ruta en el mensaje.
    pub fn load_images(&mut self, root: &Node) -> Result<(), ImageError> {
        let mut images = HashMap::new();
        let mut stack = vec![root];
        while let Some(node) = stack.pop() {
            if node.kind == Kind::Image
                && let Some(src) = &node.style.src
            {
                images.insert(node.key.clone(), self.image_cache.load(src)?);
            }
            stack.extend(node.children.iter());
        }
        self.image_cache.trim(images.len());
        // Una imagen que cambió (otro archivo, o el mismo modificado) puede tener
        // otro tamaño natural: se rehace el layout.
        let same = images.len() == self.images.len()
            && images
                .iter()
                .all(|(k, v)| self.images.get(k).is_some_and(|old| Rc::ptr_eq(old, v)));
        if !same {
            self.tree_changed = true;
            // El archivo pudo cambiar sin que cambie el nodo: se repinta todo.
            self.repainted = None;
        }
        self.images = images;
        Ok(())
    }

    /// Graba el lote de comandos de un `canvas` (ver `canvas.rs`) y marca su
    /// nodo para repintarlo. `size`: tamaño de su caja de contenido.
    pub fn record_canvas(
        &mut self,
        key: &str,
        batch: &pyo3::Bound<'_, pyo3::PyAny>,
        size: (f32, f32),
    ) -> pyo3::PyResult<()> {
        let picture = crate::canvas::record(batch, size.0, size.1, &self.fonts)?;
        match picture {
            Some(p) => self.pictures.insert(key.to_owned(), p),
            None => self.pictures.remove(key),
        };
        self.restyled.push(key.to_owned());
        Ok(())
    }

    /// Olvida los dibujos de los `canvas` que ya no están en la vista.
    pub fn retain_canvases(&mut self, keep: impl Fn(&str) -> bool) {
        self.pictures.retain(|k, _| keep(k));
    }

    /// Graba el dibujo de un `chart` (lo calcula `chart::Charts`) y marca su
    /// nodo para repintarlo.
    pub fn record_chart(&mut self, key: &str, picture: Option<Picture>) {
        match picture {
            Some(p) => self.charts.insert(key.to_owned(), p),
            None => self.charts.remove(key),
        };
        self.restyled.push(key.to_owned());
    }

    /// Olvida los gráficos que ya no están en la vista.
    pub fn retain_charts(&mut self, keep: impl Fn(&str) -> bool) {
        self.charts.retain(|k, _| keep(k));
    }

    /// Rectángulo (caja de borde) de cada nodo del layout actual, por key.
    pub fn node_rects(&self) -> HashMap<&str, Rect> {
        self.regions
            .iter()
            .map(|r| (r.key.as_str(), r.rect))
            .collect()
    }

    /// La colección de fuentes con la que se maqueta y pinta (la comparten
    /// `canvas` y `chart` al grabar sus `Picture`).
    pub fn fonts(&self) -> &FontCollection {
        &self.fonts
    }

    /// Si el foco está en un campo de texto.
    pub fn focus_is_editable(&self) -> bool {
        self.focused
            .as_ref()
            .is_some_and(|f| self.inputs.contains_key(f))
    }

    // ----------------------------------------------------------------- layout

    /// Hoja que corresponde a `node` (ninguna si es un contenedor). Ajusta el
    /// estilo de las imágenes, que no se estiran en el eje cruzado.
    fn leaf_spec(&self, node: &Node, style: &mut taffy::Style) -> Option<LeafSpec> {
        match node.kind {
            Kind::Box | Kind::Canvas | Kind::Chart => None,
            Kind::Image => {
                // Sin ancho propio, una imagen no se estira en el eje cruzado: se
                // queda a su tamaño (o al que quepa) sin deformarse.
                if node.style.width.is_none() {
                    style.align_self = Some(AlignItems::FLEX_START);
                }
                let natural = self
                    .images
                    .get(&node.key)
                    .map_or(skia_safe::Size::default(), |l| l.size);
                Some(LeafSpec::Image(natural))
            }
            Kind::Text | Kind::Input => {
                let (text, props, input) = if node.is_editable() {
                    let (text, props, _) = self.input_display(node);
                    let leaf = InputLeaf {
                        multiline: node.style.multiline,
                        rows: node.style.rows,
                    };
                    (text, props, Some(leaf))
                } else {
                    let text = node.text.clone().unwrap_or_default();
                    (text, node.text_props.clone(), None)
                };
                let key = ParagraphKey::new(&text, &props, &node.style);
                Some(LeafSpec::Text { key, props, input })
            }
        }
    }

    fn make_leaf(&self, spec: LeafSpec, style: &Style) -> Leaf {
        match spec {
            LeafSpec::Image(natural) => Leaf::Image(natural),
            LeafSpec::Text { key, props, input } => {
                Leaf::Text(self.text_ctx(key, &props, style, input))
            }
        }
    }

    /// Hace que el árbol de Taffy refleje `node`. Cada nodo reutiliza por key el
    /// nodo de Taffy del layout anterior (`old`) y solo lo marca sucio si cambia
    /// algo que afecte al layout: su estilo de Taffy, su contenido (texto o
    /// imagen) o sus hijos. Así Taffy conserva la caché de las ramas intactas, y
    /// un cambio que solo afecta a la pintura (colores, sombras…) no rehace el
    /// layout. `in_scroll`: el padre se desplaza a lo largo de su eje principal.
    fn reconcile(
        &self,
        tree: &mut TaffyTree<Leaf>,
        node: &Node,
        in_scroll: bool,
        root_size: Option<(f32, f32)>,
        old: &mut Previous,
    ) -> LayoutNode {
        let mut style = taffy_style(&node.style);
        // Dentro de un scroll los hijos no se encogen por defecto: el contenido que
        // no cabe se desplaza en vez de aplastarse.
        if in_scroll && node.style.shrink.is_none() {
            style.flex_shrink = 0.0;
        }
        // La raíz siempre ocupa la ventana completa.
        if let Some((width, height)) = root_size {
            style.size = Size {
                width: Dimension::length(width),
                height: Dimension::length(height),
            };
        }
        let spec = self.leaf_spec(node, &mut style);
        let children: Vec<LayoutNode> = if spec.is_some() {
            Vec::new()
        } else {
            let scrolls_main = node
                .style
                .scroll
                .is_some_and(|a| if node.style.row { a.x() } else { a.y() });
            node.children
                .iter()
                .map(|c| self.reconcile(tree, c, scrolls_main, None, old))
                .collect()
        };
        let ids: Vec<NodeId> = children.iter().map(|c| c.id).collect();

        let reused = match old.by_key.remove(&node.key) {
            // Taffy 0.15 maqueta un contenedor sin hijos como una hoja y entonces no
            // vacía su lista de hijos `absolute` ("hoisted"): si se queda sin hijos,
            // apuntaría a nodos borrados. Se sustituye por un nodo nuevo.
            Some(id) if ids.is_empty() && tree.child_count(id) > 0 => {
                old.retired.push(id);
                None
            }
            reused => reused,
        };
        let id = match reused {
            Some(id) => {
                if *tree.style(id).expect("taffy style") != style {
                    tree.set_style(id, style).expect("taffy style");
                }
                let same = match (tree.get_node_context(id), &spec) {
                    (None, None) => true,
                    (Some(Leaf::Image(a)), Some(LeafSpec::Image(b))) => a == b,
                    (Some(Leaf::Text(ctx)), Some(LeafSpec::Text { key, input, .. })) => {
                        ctx.key == *key && ctx.input == *input
                    }
                    _ => false,
                };
                if !same {
                    if let Some(leaf) = tree.get_node_context_mut(id) {
                        let placeholder = Leaf::Image(skia_safe::Size::default());
                        self.recycle(std::mem::replace(leaf, placeholder));
                    }
                    let leaf = spec.map(|spec| self.make_leaf(spec, &node.style));
                    tree.set_node_context(id, leaf).expect("taffy context");
                }
                id
            }
            None => match spec {
                Some(spec) => {
                    let leaf = self.make_leaf(spec, &node.style);
                    tree.new_leaf_with_context(style, leaf).expect("taffy leaf")
                }
                None => tree.new_leaf(style).expect("taffy node"),
            },
        };
        // `set_children` (y no `new_with_children`) desengancha a cada hijo de su
        // padre anterior: un nodo reutilizado puede haber cambiado de padre.
        let unchanged = tree.child_count(id) == ids.len()
            && (ids.is_empty() || tree.children(id).expect("taffy children") == ids);
        if !unchanged {
            tree.set_children(id, &ids).expect("taffy children");
        }
        LayoutNode {
            id,
            key: node.key.clone(),
            children,
            ink: Rect::default(),
            own: Rect::default(),
            sticky: false,
        }
    }

    /// Actualiza el layout persistente para el árbol `root` y lo calcula.
    fn update_layout(&self, cache: &mut LayoutCache, root: &Node, width: f32, height: f32) {
        let tree = &mut cache.tree;
        let mut old = Previous::default();
        if let Some(previous) = cache.root.take() {
            let mut stack = vec![previous];
            while let Some(lnode) = stack.pop() {
                old.by_key.insert(lnode.key, lnode.id);
                stack.extend(lnode.children);
            }
        }
        let lroot = self.reconcile(tree, root, false, Some((width, height)), &mut old);
        // Los nodos que ya no existen (o que se sustituyeron) salen del árbol.
        for id in old.by_key.into_values().chain(old.retired) {
            tree.remove(id).expect("taffy remove");
        }

        tree.compute_layout_with_measure(
            lroot.id,
            Size {
                width: AvailableSpace::Definite(width),
                height: AvailableSpace::Definite(height),
            },
            |inputs, _id, ctx, style| {
                let mut baseline = None;
                let mut out = compute_leaf_layout(
                    inputs,
                    style,
                    |_, _| 0.0,
                    |known, avail| {
                        let ctx = match ctx {
                            Some(Leaf::Text(ctx)) => ctx,
                            Some(Leaf::Image(natural)) => {
                                return measure_image(*natural, known, avail);
                            }
                            None => return Size::ZERO,
                        };
                        let key = MeasureKey {
                            known,
                            avail_width: avail.width,
                            input: ctx.input,
                        };
                        if let Some(m) = ctx.measures.iter().find(|m| m.key == key) {
                            baseline = Some(m.baseline);
                            return m.size;
                        }
                        let size = match ctx.input {
                            Some(leaf) => measure_input(&mut ctx.paragraph, leaf, known, avail),
                            None => measure_text(&mut ctx.paragraph, known, avail),
                        };
                        // Medir cambia el ancho con el que está maquetado el párrafo.
                        ctx.laid_out = None;
                        let b = ctx.paragraph.alphabetic_baseline();
                        if ctx.measures.len() == MAX_MEASURES {
                            ctx.measures.remove(0);
                        }
                        ctx.measures.push(Measured {
                            key,
                            size,
                            baseline: b,
                        });
                        baseline = Some(b);
                        size
                    },
                );
                // Exponer la baseline permite `align="baseline"` entre textos de distinto tamaño.
                if let Some(b) = baseline {
                    out.baselines.first = Some(b);
                }
                out
            },
        )
        .expect("layout");

        // Layout final de cada párrafo con su ancho de contenido definitivo.
        finalize_text(tree, &lroot);
        cache.root = Some(lroot);
    }

    // -------------------------------------------------------------- animación

    /// Avanza las transiciones `dt` segundos. Devuelve `true` si alguna sigue en curso.
    pub fn tick(&mut self, dt: f32) -> bool {
        // En un campo de texto el foco siempre se marca (como `:focus-visible` en CSS).
        let ring = self
            .focused
            .clone()
            .filter(|_| self.focus_visible || self.focus_is_editable());
        for key in [self.hovered.clone(), self.pressed.clone(), ring.clone()]
            .into_iter()
            .flatten()
        {
            self.anim.entry(key).or_default();
        }
        let k = 1.0 - (-dt / TRANSITION_TAU).exp();
        let mut animating = false;
        let (hovered, pressed, ring) = (
            self.hovered.as_deref(),
            self.pressed.as_deref(),
            ring.as_deref(),
        );
        let animated = &mut self.animated;
        self.anim.retain(|key, s| {
            let on = |k: Option<&str>| if k == Some(key.as_str()) { 1.0 } else { 0.0 };
            let (th, tp, tf) = (on(hovered), on(pressed), on(ring));
            let mut moved = false;
            for (v, t) in [(&mut s.hover, th), (&mut s.press, tp), (&mut s.focus, tf)] {
                let before = *v;
                *v += (t - *v) * k;
                if (*v - t).abs() < 0.004 {
                    *v = t;
                } else {
                    animating = true;
                }
                moved |= *v != before;
            }
            if moved {
                animated.push(key.clone());
            }
            s.hover > 0.0 || s.press > 0.0 || s.focus > 0.0 || th + tp + tf > 0.0
        });
        let goal = if self.tip.ready() { 1.0 } else { 0.0 };
        self.tip.alpha += (goal - self.tip.alpha) * k;
        if (goal - self.tip.alpha).abs() < 0.01 {
            self.tip.alpha = goal;
        } else {
            animating = true;
        }
        for s in self.scroll.values_mut() {
            animating |= s.tick(dt);
        }
        animating |= self.tick_motions(dt);
        animating
    }

    /// Avanza las animaciones declarativas. Las propiedades de estilo que
    /// cambian, y los nodos que terminan de transformarse, se repintan en su
    /// caja (`animated`); lo transformado lo repinta `motion_damage`.
    fn tick_motions(&mut self, dt: f32) -> bool {
        let mut animating = false;
        for (key, m) in &mut self.motion {
            let mut repaint = false;
            for slot in [
                &mut m.bg,
                &mut m.border,
                &mut m.text,
                &mut m.opacity,
                &mut m.radius,
                &mut m.pulse,
            ] {
                if let Some(track) = slot {
                    repaint |= track.step(dt);
                    if track.done() {
                        *slot = None;
                    } else {
                        animating = true;
                    }
                }
            }
            for slot in [&mut m.layout, &mut m.enter] {
                if let Some(track) = slot {
                    track.step(dt);
                    if track.done() {
                        *slot = None;
                        repaint = true;
                    } else {
                        animating = true;
                    }
                }
            }
            if repaint {
                self.animated.push(key.clone());
            }
        }
        self.motion
            .retain(|_, m| !m.is_empty() || m.painted.is_some());
        let pending = &mut self.pending;
        self.ghosts.retain_mut(|g| {
            g.track.step(dt);
            if g.track.done() {
                *pending = union(*pending, g.painted);
            }
            !g.track.done()
        });
        self.refresh_moving();
        animating || !self.ghosts.is_empty()
    }

    // ---------------------------------------------------------------- pintura

    /// Fases de layout y composición de un frame (la de estilo ya ocurrió al
    /// reconstruir, en `restyle`):
    ///
    /// 1. **Layout**, si cambió el árbol, el tamaño o el texto de los campos.
    ///    Tras él se recalcula la geometría (regiones, capas y tinta) y se
    ///    compara por key con la anterior: queda pendiente de repintar la tinta
    ///    de los nodos que cambiaron (`relayout_damage`). Se repinta todo si
    ///    cambió el tamaño o no se sabe qué nodos cambiaron de aspecto.
    /// 2. **Composición**: cada capa se recoloca según el desplazamiento de su
    ///    `scroll`; las regiones se mueven sin recalcularse y la zona de las
    ///    capas que se movieron queda pendiente de repintar.
    ///
    /// Se puede llamar más de una vez antes de pintar (p. ej. si un `on_scroll`
    /// reconstruye la vista): lo pendiente se acumula. `width`/`height` en
    /// píxeles lógicos.
    pub fn update(&mut self, root: &Node, width: f32, height: f32, scale: f32) {
        let start = Instant::now();
        let inputs = self.inputs_signature();
        let mut cache = self.layout_cache.take().unwrap_or_default();
        let reuse = !self.tree_changed
            && cache.root.is_some()
            && cache.width == width
            && cache.height == height
            && cache.inputs == inputs;
        // Geometría anterior y nodos que cambiaron de aspecto, para comparar
        // tras un layout incremental.
        let mut previous = None;
        if !reuse {
            let resized = cache.width != width || cache.height != height;
            self.update_layout(&mut cache, root, width, height);
            // Lo que no se reutilizó ya no corresponde a ningún nodo.
            self.recycled.borrow_mut().clear();
            (cache.width, cache.height, cache.inputs) = (width, height, inputs);
            self.tree_changed = false;
            let lroot = cache.root.as_mut().expect("layout calculado");
            compute_ink(&cache.tree, root, lroot, Point::default());
            let old = self.geometry(&cache.tree, root, lroot);
            self.start_motions(root, &old.0, &old.1, resized);
            self.refresh_moving();
            match self.repainted.replace(HashSet::new()) {
                Some(repainted) if !resized && !self.full => previous = Some((old, repainted)),
                _ => self.full = true,
            }
        }
        if scale != self.scale {
            self.scale = scale;
            self.full = true;
        }
        // Textos con el color en transición: el párrafo se rehace con el valor
        // que toca pintar (Skia guarda el color dentro del párrafo).
        self.recolor_texts(root, &mut cache);
        self.layout_cache = Some(cache);
        self.layout_cached = reuse;
        // Tras un layout las regiones son nuevas: hay que colocarlas aunque no
        // se mueva ninguna capa.
        let moved = self.place_layers(scale, self.full || previous.is_some());
        self.pending = union(self.pending, moved);
        if let Some(((regions, layers), repainted)) = previous
            && !self.full
        {
            match self.relayout_damage(&regions, &layers, &repainted) {
                Some(damage) => self.pending = union(self.pending, damage),
                None => self.full = true,
            }
        }
        self.layout_time = start.elapsed();
    }

    /// Fase de pintura: repinta solo la zona dañada (lo pendiente de `update`,
    /// lo que cambió de aspecto en la fase de estilo, las transiciones, los
    /// campos de texto y el tooltip), sin recorrer los subárboles cuya tinta
    /// queda fuera.
    ///
    /// `stale`: zona del lienzo que no contiene el último frame pintado y hay
    /// que repintar igualmente (todo el lienzo si es nuevo). Devuelve la zona
    /// repintada, alineada a píxeles físicos, o `None` si no había nada que pintar.
    pub fn paint(
        &mut self,
        canvas: &Canvas,
        root: &Node,
        width: f32,
        height: f32,
        stale: Option<Rect>,
    ) -> Option<Rect> {
        let scale = self.scale;
        let screen = Rect::from_wh(width, height);
        let full = std::mem::take(&mut self.full);
        let mut damage = union(stale, self.pending.take());
        let changed = [
            std::mem::take(&mut self.restyled),
            std::mem::take(&mut self.animated),
        ];
        if !full {
            for key in changed.iter().flatten() {
                damage = union(damage, self.region_ink(key));
            }
        }
        damage = union(damage, self.inputs_damage());
        damage = union(damage, self.motion_damage());
        let tip = self.tooltip(root, width, height);
        let tip_paint = tip.as_ref().map(|t| t.paint.clone());
        if tip_paint != self.tip_painted {
            for old_or_new in [&self.tip_painted, &tip_paint].into_iter().flatten() {
                damage = union(damage, Some(old_or_new.ink));
            }
            self.tip_painted = tip_paint;
        }
        let marks = self.mark_labels(width, height);
        if marks
            .iter()
            .map(|m| (&m.mark, m.ink))
            .ne(self.marks_painted.iter().map(|(m, ink)| (m, *ink)))
        {
            for ink in self.marks_painted.iter().map(|(_, ink)| *ink) {
                damage = union(damage, Some(ink));
            }
            for m in &marks {
                damage = union(damage, Some(m.ink));
            }
            self.marks_painted = marks.iter().map(|m| (m.mark.clone(), m.ink)).collect();
        }
        let mut damage = damage.map(|d| intersect(d, screen));
        // Si queda poco sin dañar, pintar directamente sale más barato que la
        // superficie aparte de `paint_partial` y la copia.
        let area = |r: Rect| r.width().max(0.0) * r.height().max(0.0);
        if full || damage.is_some_and(|d| area(d) > FULL_PAINT_RATIO * area(screen)) {
            damage = Some(screen);
        }
        let damage = damage.and_then(|d| pixel_align(d, scale));
        self.damage = damage;
        let clip = damage?;
        // Sin `update` previo no hay nada que pintar.
        let cache = self.layout_cache.take()?;

        let frame = Frame {
            root,
            tree: &cache.tree,
            lroot: cache.root.as_ref().expect("layout calculado"),
            scale,
            tip: tip.as_ref(),
            marks: &marks,
        };
        let inputs = if pixel_align(screen, scale) == Some(clip) {
            self.paint_area(canvas, &frame, clip, clip)
        } else {
            self.paint_partial(canvas, &frame, clip, screen)
        };
        self.layout_cache = Some(cache);
        for (key, scroll_x, frame) in inputs {
            if let Some(state) = self.inputs.get_mut(&key) {
                state.scroll_x = scroll_x;
                state.frame = Some(frame);
            }
        }
        Some(clip)
    }

    /// Repinta `clip` (más pequeño que el lienzo). Skia recorta las aristas de
    /// una figura al borde del recorte y el antialiasing cerca del corte sale
    /// algo distinto del de la figura entera: si se recortara justo a la zona
    /// dañada, sus bordes no casarían con lo que la rodea. Por eso se pinta con
    /// un margen en una superficie aparte y se copia solo la zona dañada.
    fn paint_partial(
        &self,
        canvas: &Canvas,
        frame: &Frame,
        clip: Rect,
        screen: Rect,
    ) -> Vec<(String, f32, InputFrame)> {
        let scale = frame.scale;
        let px = |r: Rect| {
            IRect::new(
                (r.left * scale).round() as i32,
                (r.top * scale).round() as i32,
                (r.right * scale).round() as i32,
                (r.bottom * scale).round() as i32,
            )
        };
        let outer = intersect(clip.with_outset((CLIP_MARGIN, CLIP_MARGIN)), screen);
        let Some(outer) = pixel_align(outer, scale) else {
            return Vec::new();
        };
        let (area, inner) = (px(outer), px(clip));
        let Some(mut off) = surfaces::raster_n32_premul(area.size()) else {
            return self.paint_area(canvas, frame, clip, clip);
        };
        off.canvas()
            .translate((-area.left as f32, -area.top as f32));
        let inputs = self.paint_area(off.canvas(), frame, outer, clip);
        let copied = off.peek_pixels().and_then(|pixmap| {
            let sub = pixmap.extract_subset(inner.with_offset((-area.left, -area.top)))?;
            canvas
                .write_pixels(
                    sub.info(),
                    sub.bytes()?,
                    sub.row_bytes(),
                    (inner.left, inner.top),
                )
                .then_some(())
        });
        if copied.is_none() {
            return self.paint_area(canvas, frame, clip, clip);
        }
        inputs
    }

    /// Pinta lo que cae en `area` (recortando a ella) saltándose los
    /// subárboles cuya tinta no toca `cull`. Devuelve la geometría de los
    /// campos de texto pintados.
    fn paint_area(
        &self,
        canvas: &Canvas,
        frame: &Frame,
        area: Rect,
        cull: Rect,
    ) -> Vec<(String, f32, InputFrame)> {
        // `restore_to_count` al final: un frame nunca deja la pila del canvas
        // desequilibrada (la superficie del piloto se reutiliza entre frames).
        let base = canvas.save();
        canvas.scale((frame.scale, frame.scale));
        canvas.clip_rect(area, ClipOp::Intersect, false);
        canvas.clear(
            frame
                .root
                .style
                .bg
                .unwrap_or(Color::from_rgb(0x0B, 0x0D, 0x14)),
        );
        let mut painter = Painter {
            engine: self,
            canvas,
            tree: frame.tree,
            scale: frame.scale,
            damage: cull,
            overlays: Vec::new(),
            inputs: Vec::new(),
            moved: Point::default(),
            cull: true,
        };
        painter.paint(frame.root, frame.lroot, Point::default(), Point::default());
        // Los nodos que salen se pintan encima de la capa en la que estaban.
        self.paint_ghosts(canvas, false);
        // Las capas superiores se pintan al final, en orden de aparición. Una capa
        // anidada dentro de otra se encola al pintar la primera y queda por encima.
        // Escapan del recorte de los `scroll` que las contienen (y de las
        // animaciones de sus ancestros).
        let mut i = 0;
        while let Some(&(node, lnode, origin, shift)) = painter.overlays.get(i) {
            (painter.moved, painter.cull) = (Point::default(), true);
            painter.paint_node(node, lnode, origin, shift);
            i += 1;
        }
        self.paint_ghosts(canvas, true);
        // El tooltip va por encima de todo, capas incluidas, y no recibe eventos.
        if let Some(tip) = frame.tip {
            paint_tooltip(canvas, tip);
        }
        // Y el resaltado del inspector por encima del tooltip.
        for mark in frame.marks {
            paint_mark(canvas, mark);
        }
        canvas.restore_to_count(base);
        painter.inputs
    }

    /// Recalcula las regiones de hit-testing y las capas tras un layout. Las
    /// regiones quedan en orden de pintura: las capas superiores, al final.
    /// Devuelve las regiones y capas anteriores; las capas que siguen existiendo
    /// conservan lo que se pintó de ellas.
    fn geometry(
        &mut self,
        tree: &TaffyTree<Leaf>,
        root: &Node,
        lroot: &LayoutNode,
    ) -> (Vec<HitRegion>, Vec<Layer>) {
        let mut g = Geometry {
            tree,
            regions: Vec::new(),
            layers: vec![Layer::new(String::new(), None, None, false, no_clip())],
            overlays: Vec::new(),
        };
        g.collect(root, lroot, Point::default(), None, 0, no_clip());
        let mut i = 0;
        while let Some(&(node, lnode, origin, parent, layer)) = g.overlays.get(i) {
            let own = g.layers.len();
            let owner = format!("overlay:{}", node.key);
            g.layers
                .push(Layer::new(owner, Some(layer), None, true, lnode.ink));
            // Las capas superiores se pintan por encima, sin recortes heredados.
            g.collect_node(node, lnode, origin, parent, own, no_clip());
            i += 1;
        }
        let alive: HashSet<&str> = g
            .layers
            .iter()
            .filter_map(|l| l.scroll.as_ref().map(|s| s.key.as_str()))
            .collect();
        self.scroll.retain(|k, _| alive.contains(k.as_str()));
        let painted: HashMap<&str, LayerPaint> = self
            .layers
            .iter()
            .filter_map(|l| Some((l.owner.as_str(), l.painted?)))
            .collect();
        for layer in &mut g.layers {
            layer.painted = painted.get(layer.owner.as_str()).copied();
        }
        drop(painted);
        (
            std::mem::replace(&mut self.regions, g.regions),
            std::mem::replace(&mut self.layers, g.layers),
        )
    }

    /// Zona dañada por un layout incremental: la tinta propia, vieja y nueva,
    /// de los nodos que cambiaron de geometría, de capa o de aspecto, y la de
    /// los que aparecen o desaparecen (lo que cambia en sus hijos lo cubren las
    /// regiones de estos). Si un nodo cambia de padre o de hermano anterior,
    /// puede quedar por encima o por debajo de otro: se repinta la tinta de todo
    /// su subárbol. Las capas que se movieron ya las repinta `place_layers`.
    /// Devuelve `None` si cambió tanto que sale más a cuenta repintarlo todo (o
    /// si había keys repetidas y no se pueden emparejar los nodos anteriores).
    fn relayout_damage(
        &self,
        old: &[HitRegion],
        old_layers: &[Layer],
        repainted: &HashSet<String>,
    ) -> Option<Option<Rect>> {
        let visible = |rect: Rect, r: &HitRegion, layers: &[Layer]| {
            intersect(rect.with_offset(-layers[r.layer].offset), r.clip)
        };
        let mut before: HashMap<&str, usize> = HashMap::with_capacity(old.len());
        for (i, r) in old.iter().enumerate() {
            if before.insert(r.key.as_str(), i).is_some() {
                return None;
            }
        }
        let (old_order, new_order) = (sibling_order(old), sibling_order(&self.regions));
        // Más de la mitad de los nodos: repintar todo cuesta lo mismo y no
        // hace falta seguir comparando.
        let limit = (old.len() + self.regions.len()) / 2;
        let mut changed = 0;
        let mut damage = None;
        for (j, r) in self.regions.iter().enumerate() {
            let now = visible(r.own, r, &self.layers);
            // Una key repetida en el árbol nuevo empareja solo su primera
            // aparición; las demás cuentan como nuevas.
            let Some(i) = before.remove(r.key.as_str()) else {
                changed += 1;
                damage = union(damage, Some(now));
                continue;
            };
            let o = &old[i];
            let then = visible(o.own, o, old_layers);
            if region_key(old, o.parent) != region_key(&self.regions, r.parent)
                || region_key(old, old_order[i]) != region_key(&self.regions, new_order[j])
            {
                changed += 1;
                damage = union(damage, Some(visible(o.ink, o, old_layers)));
                damage = union(damage, Some(visible(r.ink, r, &self.layers)));
            } else if o.local != r.local
                || o.own != r.own
                || then != now
                || old_layers[o.layer].owner != self.layers[r.layer].owner
                || repainted.contains(&r.key)
            {
                changed += 1;
                damage = union(damage, Some(then));
                damage = union(damage, Some(now));
            }
            if changed > limit {
                return None;
            }
        }
        for &i in before.values() {
            damage = union(damage, Some(visible(old[i].own, &old[i], old_layers)));
        }
        if changed + before.len() > limit {
            return None;
        }
        Some(damage)
    }

    /// Composición: coloca cada capa según el desplazamiento de su `scroll` (y
    /// actualiza los límites de este), y mueve las regiones si alguna capa se
    /// movió. Devuelve la zona que hay que repintar: la de las capas que se
    /// movieron o cuya barra cambió.
    fn place_layers(&mut self, scale: f32, force: bool) -> Option<Rect> {
        let mut damage = None;
        let mut moved = force;
        for i in 0..self.layers.len() {
            let (base, base_clip) = match self.layers[i].parent {
                Some(p) => (self.layers[p].offset, self.layers[p].clip),
                None => (Point::default(), no_clip()),
            };
            let layer = &mut self.layers[i];
            let mut clip = if layer.unclipped {
                no_clip()
            } else {
                base_clip
            };
            let mut own = Point::default();
            let mut bar = (0.0, false);
            let mut max = Point::default();
            if let Some(s) = &layer.scroll {
                let viewport = s.viewport.with_offset(-base);
                let state = self.scroll.entry(s.key.clone()).or_default();
                state.set_limits(s.axis, s.max, viewport);
                own = snap(state.offset, scale);
                bar = (state.bar, state.dragging);
                max = state.max;
                clip = intersect(clip, viewport);
            }
            let painted = LayerPaint {
                offset: base + own,
                extent: layer.extent.with_offset(-base),
                bar,
                max,
            };
            if layer.painted != Some(painted) {
                damage = union(damage, Some(painted.extent));
                damage = union(damage, layer.painted.map(|p| p.extent));
            }
            moved |= layer.offset != painted.offset || layer.clip != clip;
            layer.offset = painted.offset;
            layer.clip = clip;
            layer.painted = Some(painted);
        }
        if moved {
            for r in &mut self.regions {
                let layer = &self.layers[r.layer];
                r.rect = r.local.with_offset(-layer.offset);
                r.clip = intersect(layer.clip, r.object_clip);
            }
        }
        damage
    }

    /// Zona (absoluta y visible) que puede pintar el subárbol de `key`.
    fn region_ink(&self, key: &str) -> Option<Rect> {
        let r = self.regions.iter().rev().find(|r| r.key == key)?;
        let ink = r.ink.with_offset(-self.layers[r.layer].offset);
        Some(intersect(ink, r.clip))
    }

    /// Campos de texto cuyo aspecto cambió desde el último frame sin cambiar
    /// el layout: cursor, parpadeo, selección, composición o foco.
    fn inputs_damage(&mut self) -> Option<Rect> {
        let mut damage = None;
        let mut painted = HashMap::with_capacity(self.inputs.len());
        for (key, state) in &self.inputs {
            let mut h = DefaultHasher::new();
            (
                state.display(),
                state.editor.cursor(),
                state.editor.selection(),
                &state.preedit,
                state.caret_visible(),
                self.focused.as_deref() == Some(key.as_str()),
            )
                .hash(&mut h);
            let visual = h.finish();
            if self.inputs_painted.get(key) != Some(&visual) {
                damage = union(damage, self.region_ink(key));
            }
            painted.insert(key.clone(), visual);
        }
        self.inputs_painted = painted;
        damage
    }

    /// Burbuja del tooltip visible, debajo del nodo (o encima, si no cabe),
    /// centrada y sin salirse de la ventana. Colores heredables: `tooltip_bg` y
    /// `tooltip_color`.
    fn tooltip(&self, root: &Node, width: f32, height: f32) -> Option<Tooltip> {
        const PAD: (f32, f32) = (10.0, 6.0);
        const GAP: f32 = 8.0;
        const MARGIN: f32 = 8.0;
        const MAX_WIDTH: f32 = 260.0;
        if self.tip.alpha <= 0.0 {
            return None;
        }
        let key = self.tip.key.as_deref()?;
        let owner = self
            .regions
            .iter()
            .rev()
            .find(|r| r.key == key && r.tooltip)?
            .rect;
        let node = root.find(key)?;
        let text = node.style.tooltip.as_deref()?;
        let tp = &node.text_props;
        let mut props = tp.clone();
        props.size = 12.0;
        props.weight = 500;
        props.color = tp.tooltip_color;
        props.line_height = None;
        props.letter_spacing = 0.0;
        let mut p = self.paragraph(text, &props, &Style::default());
        p.layout(MAX_WIDTH);
        let (tw, th) = (
            p.max_intrinsic_width().min(MAX_WIDTH).ceil(),
            p.height().ceil(),
        );
        p.layout(tw + 0.5);
        let (w, h) = (tw + 2.0 * PAD.0, th + 2.0 * PAD.1);
        let x = (owner.center_x() - w / 2.0).clamp(MARGIN, (width - MARGIN - w).max(MARGIN));
        let below = owner.bottom + GAP;
        let y = if below + h <= height - MARGIN {
            below
        } else {
            (owner.top - GAP - h).max(MARGIN)
        };
        let bubble = Rect::from_xywh(x, y, w, h);
        let shadow = bubble
            .with_offset((0.0, TIP_SHADOW_DY))
            .with_outset((3.0 * TIP_SHADOW_SIGMA + 1.0, 3.0 * TIP_SHADOW_SIGMA + 1.0));
        Some(Tooltip {
            paragraph: p,
            text_at: Point::new(x + PAD.0, y + PAD.1),
            bubble,
            paint: TipPaint {
                ink: join(bubble, shadow),
                alpha: self.tip.alpha,
                text: text.to_owned(),
                colors: (tp.tooltip_bg, tp.tooltip_color),
            },
        })
    }
}

/// Lo que se pinta en un frame.
struct Frame<'a> {
    root: &'a Node,
    tree: &'a TaffyTree<Leaf>,
    lroot: &'a LayoutNode,
    scale: f32,
    tip: Option<&'a Tooltip>,
    marks: &'a [MarkLabel],
}

/// Fracción de la ventana a partir de la cual una zona dañada se repinta
/// entera, sin superficie aparte.
const FULL_PAINT_RATIO: f32 = 0.7;

/// Margen (píxeles lógicos) con el que se pinta una zona dañada antes de
/// copiarla: el antialiasing de una figura cortada por el recorte solo cambia
/// cerca del corte.
const CLIP_MARGIN: f32 = 32.0;

/// Sombra de la burbuja del tooltip.
const TIP_SHADOW_SIGMA: f32 = 6.0;
const TIP_SHADOW_DY: f32 = 3.0;

/// Tooltip listo para pintar.
struct Tooltip {
    paragraph: Paragraph,
    text_at: Point,
    bubble: Rect,
    paint: TipPaint,
}

/// Colores del resaltado del inspector (como los de las devtools de los navegadores).
const MARK_CONTENT: Color = Color::from_argb(0x55, 0x6F, 0xA8, 0xDC);
const MARK_PADDING: Color = Color::from_argb(0x55, 0x93, 0xC4, 0x7D);
const MARK_HOVER: Color = Color::from_rgb(0x3D, 0x8B, 0xFF);
const MARK_SELECTED: Color = Color::from_rgb(0xFF, 0x5C, 0xA8);
const MARK_LABEL_BG: Color = Color::from_rgb(0x1B, 0x1F, 0x2B);
const MARK_LABEL_FG: Color = Color::from_rgb(0xF2, 0xF4, 0xF8);

/// Resaltado del inspector listo para pintar: la marca y su etiqueta.
struct MarkLabel {
    mark: Mark,
    paragraph: Paragraph,
    /// Caja de la etiqueta.
    chip: Rect,
    /// Todo lo que pinta (contorno y etiqueta).
    ink: Rect,
}

impl Engine {
    /// Etiquetas de los resaltados del inspector: encima del nodo si caben y,
    /// si no, debajo o dentro; siempre dentro de la ventana.
    fn mark_labels(&self, width: f32, height: f32) -> Vec<MarkLabel> {
        const PAD: (f32, f32) = (6.0, 3.0);
        const GAP: f32 = 4.0;
        self.marks
            .iter()
            .map(|mark| {
                let props = TextProps {
                    size: 11.0,
                    weight: 500,
                    color: MARK_LABEL_FG,
                    ..TextProps::default()
                };
                let mut paragraph = self.paragraph(&mark.label, &props, &Style::default());
                paragraph.layout(f32::INFINITY);
                let (tw, th) = (
                    paragraph.max_intrinsic_width().ceil(),
                    paragraph.height().ceil(),
                );
                let (w, h) = (tw + 2.0 * PAD.0, th + 2.0 * PAD.1);
                let r = mark.rect;
                let x = r.left.clamp(0.0, (width - w).max(0.0));
                let y = if r.top - GAP - h >= 0.0 {
                    r.top - GAP - h
                } else if r.bottom + GAP + h <= height {
                    r.bottom + GAP
                } else {
                    r.top.max(0.0)
                };
                let chip = Rect::from_xywh(x, y, w, h);
                MarkLabel {
                    mark: mark.clone(),
                    paragraph,
                    chip,
                    ink: join(r.with_outset((2.0, 2.0)), chip),
                }
            })
            .collect()
    }
}

fn paint_mark(canvas: &Canvas, m: &MarkLabel) {
    let r = m.mark.rect;
    let mut paint = Paint::default();
    paint.set_anti_alias(true);
    let accent = if m.mark.hovered {
        let p = m.mark.padding;
        let content = Rect::new(
            r.left + p.left,
            r.top + p.top,
            r.right - p.right,
            r.bottom - p.bottom,
        );
        // El padding: el marco entre la caja y el contenido.
        canvas.save();
        if content.width() > 0.0 && content.height() > 0.0 {
            canvas.clip_rect(content, ClipOp::Difference, false);
        }
        paint.set_color(MARK_PADDING);
        canvas.draw_rect(r, &paint);
        canvas.restore();
        if content.width() > 0.0 && content.height() > 0.0 {
            paint.set_color(MARK_CONTENT);
            canvas.draw_rect(content, &paint);
        }
        MARK_HOVER
    } else {
        MARK_SELECTED
    };
    paint
        .set_style(PaintStyle::Stroke)
        .set_stroke_width(1.5)
        .set_color(accent);
    canvas.draw_rect(r.with_inset((0.75, 0.75)), &paint);
    let mut bg = Paint::default();
    bg.set_anti_alias(true).set_color(MARK_LABEL_BG);
    canvas.draw_rrect(RRect::new_rect_xy(m.chip, 4.0, 4.0), &bg);
    let mut bar = Paint::default();
    bar.set_anti_alias(true).set_color(accent);
    canvas.draw_rect(
        Rect::from_xywh(m.chip.left, m.chip.top, 2.0, m.chip.height()),
        &bar,
    );
    m.paragraph
        .paint(canvas, Point::new(m.chip.left + 6.0, m.chip.top + 3.0));
}

fn paint_tooltip(canvas: &Canvas, tip: &Tooltip) {
    let bubble = RRect::new_rect_xy(tip.bubble, 8.0, 8.0);
    canvas.save_layer_alpha_f(None, tip.paint.alpha);
    let mut shadow = Paint::default();
    shadow
        .set_anti_alias(true)
        .set_color(Color::from_argb(60, 0, 0, 0));
    if let Some(mf) = MaskFilter::blur(BlurStyle::Normal, TIP_SHADOW_SIGMA, false) {
        shadow.set_mask_filter(mf);
    }
    canvas.draw_rrect(bubble.with_offset((0.0, TIP_SHADOW_DY)), &shadow);
    let mut bg = Paint::default();
    bg.set_anti_alias(true).set_color(tip.paint.colors.0);
    canvas.draw_rrect(bubble, &bg);
    tip.paragraph.paint(canvas, tip.text_at);
    canvas.restore();
}

impl Layer {
    fn new(
        owner: String,
        parent: Option<usize>,
        scroll: Option<ScrollLayer>,
        unclipped: bool,
        extent: Rect,
    ) -> Self {
        Self {
            owner,
            parent,
            scroll,
            unclipped,
            extent,
            offset: Point::default(),
            clip: no_clip(),
            painted: None,
        }
    }
}

/// Misma identidad, estructura, contenido y manejadores: lo que hay que comprobar
/// aunque el estilo no cambie.
fn same_shape(a: &Node, b: &Node) -> bool {
    a.key == b.key
        && a.kind == b.kind
        && a.children.len() == b.children.len()
        && a.text == b.text
        && a.same_handlers(b)
}

/// Dos nodos con la misma forma (`same_shape`) y distinto estilo tienen la misma
/// geometría si coinciden en todo esto: el layout, las regiones y la tinta del
/// anterior valen para el nuevo.
fn same_geometry(a: &Node, b: &Node) -> bool {
    let (sa, sb) = (&a.style, &b.style);
    let content = match b.kind {
        // El dibujo de un `canvas` o un `chart` no afecta a su caja.
        Kind::Box | Kind::Canvas | Kind::Chart => true,
        // Las métricas del texto; el color se cambia en el propio párrafo.
        Kind::Text => {
            let (ta, tb) = (&a.text_props, &b.text_props);
            ta.size == tb.size
                && ta.weight == tb.weight
                && ta.family == tb.family
                && ta.line_height == tb.line_height
                && ta.letter_spacing == tb.letter_spacing
                && sa.max_lines == sb.max_lines
                && sa.text_align == sb.text_align
        }
        // Su párrafo depende de demasiadas cosas (placeholder, colores…) y la imagen
        // se carga por `src`: cualquier cambio rehace el layout.
        Kind::Input | Kind::Image => sa == sb && a.text_props == b.text_props,
    };
    content
        && taffy_style(sa) == taffy_style(sb)
        // Lo que cambia las regiones o la tinta.
        && sa.overlay == sb.overlay
        && sa.capture == sb.capture
        && sa.focusable == sb.focusable
        && sa.tooltip.is_some() == sb.tooltip.is_some()
        && sa.scroll == sb.scroll
        && sa.clip == sb.clip
        && sa.shadow == sb.shadow
        && sa.press_scale == sb.press_scale
}

/// Tinta (hasta dónde puede pintar) y `sticky` de cada nodo del subárbol, en
/// coordenadas locales de su capa. Se calcula tras cada layout.
fn compute_ink(tree: &TaffyTree<Leaf>, node: &Node, lnode: &mut LayoutNode, origin: Point) {
    let layout = tree.layout(lnode.id).expect("layout");
    let rect = Rect::from_xywh(
        origin.x + layout.location.x,
        origin.y + layout.location.y,
        layout.size.width,
        layout.size.height,
    );
    let s = &node.style;
    let mut ink = rect;
    if let Some(sh) = s.shadow {
        // `MaskFilter::blur` con sigma = blur / 2: el difuminado llega a 3 sigmas.
        let spread = 1.5 * sh.blur;
        ink = join(
            ink,
            rect.with_offset((sh.dx, sh.dy))
                .with_outset((spread, spread)),
        );
    }
    if matches!(node.kind, Kind::Text | Kind::Input) {
        // Glifos que desbordan su caja (interlineado ajustado, acentos, cursivas).
        let m = node.text_props.size * 0.5;
        ink = join(ink, rect.with_outset((m, m)));
    }
    if node.is_focusable() {
        ink = join(ink, rect.with_outset((FOCUS_OUTSET, FOCUS_OUTSET)));
    }
    let own = ink;
    let mut sticky = node.is_editable() || s.overlay;
    let child_origin = Point::new(rect.left, rect.top);
    for (child, lchild) in node.children.iter().zip(&mut lnode.children) {
        compute_ink(tree, child, lchild, child_origin);
        sticky |= lchild.sticky;
        // Un `scroll` recorta a sus hijos a su caja; las capas superiores se pintan aparte.
        if !child.style.overlay && s.scroll.is_none() {
            ink = join(ink, lchild.ink);
        }
    }
    // Margen para el antialiasing.
    lnode.own = own.with_outset((1.0, 1.0));
    if s.press_scale > 1.0 {
        let (c, k) = (rect.center(), s.press_scale);
        ink = Rect::new(
            c.x + (ink.left - c.x) * k,
            c.y + (ink.top - c.y) * k,
            c.x + (ink.right - c.x) * k,
            c.y + (ink.bottom - c.y) * k,
        );
        // Al pulsarlo se escala con sus hijos: cualquier cambio en ellos puede
        // pintar en toda la tinta escalada.
        cover(node, lnode, ink.with_outset((1.0, 1.0)));
    }
    lnode.ink = ink.with_outset((1.0, 1.0));
    lnode.sticky = sticky;
}

// ------------------------------------------------------ animaciones declarativas

fn color4(c: Color) -> Vec4 {
    [c.a() as f32, c.r() as f32, c.g() as f32, c.b() as f32]
}

fn vec_color(v: Vec4) -> Color {
    let byte = |x: f32| x.round().clamp(0.0, 255.0) as u8;
    Color::from_argb(byte(v[0]), byte(v[1]), byte(v[2]), byte(v[3]))
}

/// Origen y destino de la transición de un color. Aparecer o desaparecer es
/// ir desde, o hacia, el mismo color transparente.
fn color_pair(a: Option<Color>, b: Option<Color>) -> (Option<Vec4>, Option<Vec4>) {
    match (a, b) {
        (Some(a), Some(b)) => (Some(color4(a)), Some(color4(b))),
        (Some(a), None) => (Some(color4(a)), Some(color4(a.with_a(0)))),
        (None, Some(b)) => (Some(color4(b.with_a(0))), Some(color4(b))),
        (None, None) => (None, None),
    }
}

fn rect4(r: Rect) -> Vec4 {
    [r.left, r.top, r.right, r.bottom]
}

/// Estilo con los valores que muestran sus transiciones en curso.
fn animated_style(style: &Style, m: &Motion) -> Style {
    let mut s = style.clone();
    if let Some(t) = &m.bg {
        s.bg = Some(vec_color(t.value()));
    }
    if let Some(t) = &m.border {
        s.border_color = Some(vec_color(t.value()));
    }
    if let Some(t) = &m.opacity {
        s.opacity = t.value()[0].clamp(0.0, 1.0);
    }
    if let Some(t) = &m.pulse {
        s.opacity = (s.opacity * t.value()[0]).clamp(0.0, 1.0);
    }
    if let Some(t) = &m.radius {
        s.radius = t.value()[0].max(0.0);
    }
    s
}

/// Caja que muestra un nodo cuya caja final es `local` (coordenadas locales
/// de su capa): la de su animación de layout, si está en curso.
fn shown_rect(m: &Motion, local: Rect) -> Rect {
    match &m.layout {
        Some(t) => {
            let [l, t, r, b] = t.value();
            Rect::new(l, t, r.max(l), b.max(t))
        }
        None => local,
    }
}

/// Tinta (coordenadas locales de su capa) de un nodo transformado por sus
/// animaciones: desplazada con su caja, ampliada a la caja que se muestra (el
/// fondo se dibuja con ella) y con el efecto de entrada aplicado.
fn motion_ink(m: &Motion, r: &HitRegion) -> Rect {
    let shown = shown_rect(m, r.local);
    let mut ink = r
        .ink
        .with_offset((shown.left - r.local.left, shown.top - r.local.top));
    if m.layout.is_some() {
        let margin = [
            r.local.left - r.ink.left,
            r.local.top - r.ink.top,
            r.ink.right - r.local.right,
            r.ink.bottom - r.local.bottom,
        ]
        .into_iter()
        .fold(0.0, f32::max);
        ink = join(ink, shown.with_outset((margin, margin)));
    }
    if let Some(t) = &m.enter {
        ink = effect_rect(ink, shown.center(), t.value());
    }
    ink.with_outset((1.0, 1.0))
}

/// Rectángulo transformado por un efecto (`opacidad, x, y, escala`): escalado
/// alrededor de `center` y desplazado.
fn effect_rect(r: Rect, center: Point, v: Vec4) -> Rect {
    let (c, k) = (center, v[3]);
    Rect::new(
        c.x + (r.left - c.x) * k,
        c.y + (r.top - c.y) * k,
        c.x + (r.right - c.x) * k,
        c.y + (r.bottom - c.y) * k,
    )
    .with_offset((v[1], v[2]))
}

/// Aplica al lienzo el desplazamiento y la escala (alrededor del centro de
/// `rect`) de un efecto. La opacidad la aplica quien llama.
fn apply_effect(canvas: &Canvas, rect: Rect, v: Vec4) {
    canvas.translate((v[1], v[2]));
    if v[3] != 1.0 {
        let c = rect.center();
        canvas.translate(c).scale((v[3], v[3])).translate(-c);
    }
}

/// Nodo de layout con esa key.
fn find_layout<'a>(lnode: &'a LayoutNode, key: &str) -> Option<&'a LayoutNode> {
    if lnode.key == key {
        return Some(lnode);
    }
    lnode.children.iter().find_map(|c| find_layout(c, key))
}

/// Si el árbol de layout tiene la misma forma (por keys) que el subárbol.
fn same_keys(node: &Node, lnode: &LayoutNode) -> bool {
    node.key == lnode.key
        && node.children.len() == lnode.children.len()
        && node
            .children
            .iter()
            .zip(&lnode.children)
            .all(|(c, l)| same_keys(c, l))
}

fn region_key(regions: &[HitRegion], i: Option<usize>) -> Option<&str> {
    i.map(|i| regions[i].key.as_str())
}

/// Hermano anterior de cada región (en orden de pintura, entre las que tienen
/// el mismo padre).
fn sibling_order(regions: &[HitRegion]) -> Vec<Option<usize>> {
    let mut last = vec![None; regions.len()];
    let mut last_root = None;
    regions
        .iter()
        .enumerate()
        .map(|(i, r)| {
            let slot = match r.parent {
                Some(p) => &mut last[p],
                None => &mut last_root,
            };
            slot.replace(i)
        })
        .collect()
}

/// Amplía la tinta propia del nodo y de sus descendientes hasta `ink`, sin
/// entrar en capas (`scroll` y capas superiores: tienen otras coordenadas).
fn cover(node: &Node, lnode: &mut LayoutNode, ink: Rect) {
    lnode.own = join(lnode.own, ink);
    if node.style.scroll.is_some() {
        return;
    }
    for (child, lchild) in node.children.iter().zip(&mut lnode.children) {
        if !child.style.overlay {
            cover(child, lchild, ink);
        }
    }
}

/// Añade a `out` los nodos de `new` que se pintan distinto que su pareja (por
/// key) en `old`: otro tipo, estilo, texto o propiedades de texto. Los que no
/// tienen pareja entre los hijos del mismo padre (nuevos o que cambiaron de
/// padre) cuentan como cambiados, con todo su subárbol.
fn repainted_nodes(old: &Node, new: &Node, out: &mut HashSet<String>) {
    if old.kind != new.kind
        || old.text != new.text
        || old.style != new.style
        || old.text_props != new.text_props
    {
        out.insert(new.key.clone());
    }
    let paired = old.children.len() == new.children.len()
        && old
            .children
            .iter()
            .zip(&new.children)
            .all(|(a, b)| a.key == b.key);
    if paired {
        for (a, b) in old.children.iter().zip(&new.children) {
            repainted_nodes(a, b, out);
        }
        return;
    }
    let by_key: HashMap<&str, &Node> = old.children.iter().map(|c| (c.key.as_str(), c)).collect();
    for child in &new.children {
        match by_key.get(child.key.as_str()) {
            Some(before) => repainted_nodes(before, child, out),
            None => {
                let mut stack = vec![child];
                while let Some(n) = stack.pop() {
                    out.insert(n.key.clone());
                    stack.extend(n.children.iter());
                }
            }
        }
    }
}

/// Nodo de la capa superior pendiente de recorrer: nodo, layout, origen local,
/// región padre y capa en la que está.
type GeometryDeferred<'a> = (&'a Node, &'a LayoutNode, Point, Option<usize>, usize);

/// Recorrido del árbol que registra las regiones y las capas, en el mismo orden
/// en que se pinta.
struct Geometry<'a> {
    tree: &'a TaffyTree<Leaf>,
    regions: Vec<HitRegion>,
    layers: Vec<Layer>,
    overlays: Vec<GeometryDeferred<'a>>,
}

impl<'a> Geometry<'a> {
    fn collect(
        &mut self,
        node: &'a Node,
        lnode: &'a LayoutNode,
        origin: Point,
        parent: Option<usize>,
        layer: usize,
        clip: Rect,
    ) {
        if node.style.overlay {
            self.overlays.push((node, lnode, origin, parent, layer));
            return;
        }
        self.collect_node(node, lnode, origin, parent, layer, clip);
    }

    fn collect_node(
        &mut self,
        node: &'a Node,
        lnode: &'a LayoutNode,
        origin: Point,
        parent: Option<usize>,
        layer: usize,
        clip: Rect,
    ) {
        let layout = self.tree.layout(lnode.id).expect("layout");
        let rect = Rect::from_xywh(
            origin.x + layout.location.x,
            origin.y + layout.location.y,
            layout.size.width,
            layout.size.height,
        );
        let index = self.regions.len();
        self.regions.push(HitRegion {
            key: node.key.clone(),
            rect,
            clip,
            object_clip: clip,
            local: rect,
            ink: lnode.ink,
            own: lnode.own,
            layer,
            interactive: node.is_interactive() || node.is_draggable() || node.is_editable(),
            capture: node.style.capture,
            focusable: node.is_focusable(),
            editable: node.is_editable(),
            tooltip: node.style.tooltip.is_some(),
            cursor: node.style.cursor,
            scroll: node.style.scroll,
            parent,
        });
        let mut child_layer = layer;
        if let Some(axis) = node.style.scroll {
            let bw = node.style.border_width;
            let viewport = rect.with_inset((bw, bw));
            let scroll = ScrollLayer {
                key: node.key.clone(),
                axis,
                max: Point::new(layout.scroll_width(), layout.scroll_height()),
                viewport,
            };
            child_layer = self.layers.len();
            let owner = format!("scroll:{}", node.key);
            self.layers.push(Layer::new(
                owner,
                Some(layer),
                Some(scroll),
                false,
                viewport,
            ));
        }
        // `overflow="hidden"`: los hijos viven recortados a la caja del nodo.
        let child_clip = if node.style.clip {
            let bw = node.style.border_width;
            intersect(clip, rect.with_inset((bw, bw)))
        } else {
            clip
        };
        let child_origin = Point::new(rect.left, rect.top);
        for (child, lchild) in node.children.iter().zip(&lnode.children) {
            self.collect(
                child,
                lchild,
                child_origin,
                Some(index),
                child_layer,
                child_clip,
            );
        }
    }
}

/// Lo que sobresale el anillo de foco de su nodo.
const FOCUS_OUTSET: f32 = FOCUS_GAP + FOCUS_WIDTH;

fn no_clip() -> Rect {
    Rect::new(-1.0e9, -1.0e9, 1.0e9, 1.0e9)
}

fn intersect(a: Rect, b: Rect) -> Rect {
    Rect::new(
        a.left.max(b.left),
        a.top.max(b.top),
        a.right.min(b.right),
        a.bottom.min(b.bottom),
    )
}

/// El menor rectángulo que contiene a ambos.
fn join(a: Rect, b: Rect) -> Rect {
    Rect::new(
        a.left.min(b.left),
        a.top.min(b.top),
        a.right.max(b.right),
        a.bottom.max(b.bottom),
    )
}

fn overlaps(a: Rect, b: Rect) -> bool {
    a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom
}

/// Une una zona a la dañada; las vacías no cuentan.
fn union(damage: Option<Rect>, r: Option<Rect>) -> Option<Rect> {
    match (damage, r.filter(|r| r.width() > 0.0 && r.height() > 0.0)) {
        (Some(d), Some(r)) => Some(join(d, r)),
        (d, r) => d.or(r),
    }
}

/// Amplía la zona a píxeles físicos enteros: con un recorte alineado, lo
/// repintado es idéntico a lo que daría pintar el frame entero.
fn pixel_align(r: Rect, scale: f32) -> Option<Rect> {
    let r = Rect::new(
        (r.left * scale).floor() / scale,
        (r.top * scale).floor() / scale,
        (r.right * scale).ceil() / scale,
        (r.bottom * scale).ceil() / scale,
    );
    (r.width() > 0.0 && r.height() > 0.0).then_some(r)
}

/// Alinea un desplazamiento a píxeles físicos (el texto no se emborrona).
fn snap(p: Point, scale: f32) -> Point {
    Point::new((p.x * scale).round() / scale, (p.y * scale).round() / scale)
}

/// Nodo de la capa superior pendiente de pintar: nodo, layout, origen absoluto
/// y desplazamiento acumulado de los `scroll` que lo contienen.
type Deferred<'a> = (&'a Node, &'a LayoutNode, Point, Point);

/// Contexto de un frame de pintura: recorre el árbol saltándose lo que queda
/// fuera de la zona dañada.
struct Painter<'a> {
    engine: &'a Engine,
    canvas: &'a Canvas,
    tree: &'a TaffyTree<Leaf>,
    /// Densidad de píxeles, para alinear el desplazamiento a píxeles físicos.
    scale: f32,
    /// Zona a repintar (absoluta).
    damage: Rect,
    /// Nodos con `layer="overlay"` aplazados hasta el final del frame.
    overlays: Vec<Deferred<'a>>,
    /// Geometría de cada campo pintado: key, desplazamiento horizontal y frame.
    inputs: Vec<(String, f32, InputFrame)>,
    /// Desplazamiento que ya aplicaron al lienzo las animaciones de layout de
    /// los ancestros (un hijo que también se anima solo añade la diferencia).
    moved: Point,
    /// Si se descartan los subárboles cuya tinta queda fuera de la zona a
    /// repintar. Dentro de un nodo transformado no se puede: su tinta no cuenta
    /// con la transformación.
    cull: bool,
}

impl<'a> Painter<'a> {
    /// `origin`: esquina absoluta del padre; `shift`: desplazamiento acumulado
    /// de los `scroll` que lo contienen (local = absoluto + `shift`).
    fn paint(&mut self, node: &'a Node, lnode: &'a LayoutNode, origin: Point, shift: Point) {
        if node.style.overlay {
            self.overlays.push((node, lnode, origin, shift));
            return;
        }
        self.paint_node(node, lnode, origin, shift);
    }

    /// Pinta el nodo y sus hijos. Una capa aplazada se pinta en coordenadas
    /// absolutas: no hereda la opacidad ni la escala de sus ancestros.
    fn paint_node(&mut self, node: &'a Node, lnode: &'a LayoutNode, origin: Point, shift: Point) {
        if self.cull
            && !lnode.sticky
            && !overlaps(lnode.ink.with_offset(-shift), self.damage)
            && !self.engine.moving.contains(&node.key)
        {
            return;
        }
        let canvas = self.canvas;
        let layout = self.tree.layout(lnode.id).expect("layout");
        let rect = Rect::from_xywh(
            origin.x + layout.location.x,
            origin.y + layout.location.y,
            layout.size.width,
            layout.size.height,
        );

        let motion = self.engine.motion.get(&node.key);
        let animated;
        let s = match motion.filter(|m| m.restyled()) {
            Some(m) => {
                animated = animated_style(&node.style, m);
                &animated
            }
            None => &node.style,
        };
        let st = self.engine.anim.get(&node.key).copied().unwrap_or_default();

        let save_count = canvas.save();
        let (outer_moved, outer_cull) = (self.moved, self.cull);
        // Caja que se dibuja (fondo, borde, sombra, anillo): la del layout o,
        // mientras se desliza hacia ella, la que se muestra.
        let mut deco = rect;
        let mut alpha = s.opacity;
        if let Some(m) = motion {
            if m.layout.is_some() {
                // Las cajas animadas van en coordenadas locales de la capa.
                let local = rect.with_offset(shift);
                let shown = shown_rect(m, local);
                let d = Point::new(shown.left - local.left, shown.top - local.top);
                canvas.translate(d - self.moved);
                self.moved = d;
                deco = Rect::from_xywh(rect.left, rect.top, shown.width(), shown.height());
                self.cull = false;
            }
            if let Some(track) = &m.enter {
                let v = track.value();
                alpha *= v[0].clamp(0.0, 1.0);
                apply_effect(canvas, deco, v);
                self.cull = false;
            }
        }
        if alpha < 1.0 {
            canvas.save_layer_alpha_f(None, alpha);
        }
        if s.press_scale != 1.0 && st.press > 0.0 {
            let k = 1.0 + (s.press_scale - 1.0) * st.press;
            let c = deco.center();
            canvas.translate(c).scale((k, k)).translate(-c);
        }

        let rrect = RRect::new_rect_xy(deco, s.radius, s.radius);

        if let Some(sh) = s.shadow {
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(sh.color);
            if let Some(mf) = MaskFilter::blur(BlurStyle::Normal, sh.blur / 2.0, false) {
                p.set_mask_filter(mf);
            }
            canvas.draw_rrect(rrect.with_offset((sh.dx, sh.dy)), &p);
        }

        if let Some(paint) = background_paint(s, deco, st) {
            canvas.draw_rrect(rrect, &paint);
        }

        if node.kind == Kind::Image
            && let Some(loaded) = self.engine.images.get(&node.key)
        {
            let (inner, content) = content_box(rect, layout);
            let r = (s.radius - s.border_width).max(0.0);
            paint_image(
                canvas,
                loaded,
                s.fit,
                content,
                RRect::new_rect_xy(inner, r, r),
            );
        }

        // Un `canvas` o un `chart` se pintan de su `Picture` grabado (ver
        // `canvas.rs` y `chart.rs`), recortado a la caja de contenido.
        let recorded = match node.kind {
            Kind::Canvas => self.engine.pictures.get(&node.key),
            Kind::Chart => self.engine.charts.get(&node.key),
            _ => None,
        };
        if let Some(recorded) = recorded {
            let (inner, content) = content_box(rect, layout);
            let r = (s.radius - s.border_width).max(0.0);
            canvas.save();
            canvas.clip_rrect(RRect::new_rect_xy(inner, r, r), ClipOp::Intersect, true);
            canvas.clip_rect(content, ClipOp::Intersect, true);
            canvas.translate((content.left, content.top));
            canvas.draw_picture(recorded, None, None);
            canvas.restore();
        }

        if s.border_width > 0.0
            && let Some(color) = s.border_color
        {
            let half = s.border_width / 2.0;
            let inner = RRect::new_rect_xy(
                deco.with_inset((half, half)),
                s.radius - half,
                s.radius - half,
            );
            let mut p = Paint::default();
            p.set_anti_alias(true)
                .set_style(PaintStyle::Stroke)
                .set_stroke_width(s.border_width)
                .set_color(color);
            canvas.draw_rrect(inner, &p);
        }

        if node.kind == Kind::Text
            && let Some(Leaf::Text(ctx)) = self.tree.get_node_context(lnode.id)
        {
            let pad = layout.padding;
            ctx.paragraph
                .paint(canvas, (rect.left + pad.left, rect.top + pad.top));
        }
        if node.is_editable() {
            self.paint_input(node, lnode, rect);
        }

        // `overflow="hidden"`: se recorta el subárbol a la caja que se muestra
        // (deco sigue la animación de layout, así un despliegue se revela solo).
        if s.clip {
            let bw = s.border_width;
            let viewport = deco.with_inset((bw, bw));
            let r = (s.radius - bw).max(0.0);
            canvas.clip_rrect(RRect::new_rect_xy(viewport, r, r), ClipOp::Intersect, true);
        }

        let mut child_origin = Point::new(rect.left, rect.top);
        let mut child_shift = shift;
        let mut bars = None;
        if s.scroll.is_some() {
            // Se recorta a la caja de relleno (dentro del borde) y los hijos se
            // desplazan; la barra se pinta encima, sin ocupar espacio en el layout.
            // Los límites ya los fijó la composición (`place_layers`).
            let bw = s.border_width;
            let viewport = rect.with_inset((bw, bw));
            let state = self
                .engine
                .scroll
                .get(&node.key)
                .cloned()
                .unwrap_or_default();
            let offset = snap(state.offset, self.scale);
            canvas.save();
            let r = (s.radius - bw).max(0.0);
            canvas.clip_rrect(RRect::new_rect_xy(viewport, r, r), ClipOp::Intersect, true);
            child_origin -= offset;
            child_shift += offset;
            bars = Some(state);
        }
        for (child, lchild) in node.children.iter().zip(&lnode.children) {
            self.paint(child, lchild, child_origin, child_shift);
        }
        if let Some(state) = bars {
            canvas.restore();
            paint_scrollbars(canvas, &state, s.scrollbar_color);
        }
        if st.focus > 0.0 {
            paint_focus_ring(
                canvas,
                deco,
                s.radius,
                node.text_props.focus_color,
                st.focus,
            );
        }
        canvas.restore_to_count(save_count);
        (self.moved, self.cull) = (outer_moved, outer_cull);
    }
}

/// Caja de relleno (dentro del borde) y caja de contenido (dentro del padding).
fn content_box(rect: Rect, layout: &taffy::Layout) -> (Rect, Rect) {
    let (b, pad) = (layout.border, layout.padding);
    let inner = Rect::new(
        rect.left + b.left,
        rect.top + b.top,
        rect.right - b.right,
        rect.bottom - b.bottom,
    );
    let content = Rect::new(
        inner.left + pad.left,
        inner.top + pad.top,
        inner.right - pad.right,
        inner.bottom - pad.bottom,
    );
    (inner, content)
}

/// Tamaño de la caja de contenido de un nodo (dentro del padding y del borde),
/// que es lo que reciben `draw` de un `canvas` y los ejes de un `chart`.
pub fn content_size(node: &Node, rect: Rect) -> (f32, f32) {
    let (pad, bw) = (node.style.padding, node.style.border_width);
    (
        (rect.width() - pad.left - pad.right - 2.0 * bw).max(0.0),
        (rect.height() - pad.top - pad.bottom - 2.0 * bw).max(0.0),
    )
}

/// Separación y grosor del anillo de foco.
const FOCUS_GAP: f32 = 2.0;
const FOCUS_WIDTH: f32 = 2.0;

/// Anillo de foco: trazo de 2 px separado 2 px del borde, que sigue las esquinas.
fn paint_focus_ring(canvas: &Canvas, rect: Rect, radius: f32, color: Color, t: f32) {
    let out = FOCUS_GAP + FOCUS_WIDTH / 2.0;
    let r = if radius > 0.0 { radius + out } else { 0.0 };
    let ring = RRect::new_rect_xy(rect.with_outset((out, out)), r, r);
    let mut p = Paint::default();
    p.set_anti_alias(true)
        .set_style(PaintStyle::Stroke)
        .set_stroke_width(FOCUS_WIDTH)
        .set_color(color.with_a((color.a() as f32 * t).round() as u8));
    canvas.draw_rrect(ring, &p);
}

impl<'a> Painter<'a> {
    /// Campo de texto: selección, texto (o placeholder), subrayado de la
    /// composición del IME y cursor, recortados a la caja de relleno. Un campo
    /// de una línea se desplaza en horizontal para que el cursor siempre se vea.
    fn paint_input(&mut self, node: &Node, lnode: &LayoutNode, rect: Rect) {
        let Some(Leaf::Text(ctx)) = self.tree.get_node_context(lnode.id) else {
            return;
        };
        let layout = self.tree.layout(lnode.id).expect("layout");
        let canvas = self.canvas;
        let (s, tp) = (&node.style, &node.text_props);
        let (b, pad) = (layout.border, layout.padding);
        let padding_box = Rect::new(
            rect.left + b.left,
            rect.top + b.top,
            rect.right - b.right,
            rect.bottom - b.bottom,
        );
        let content = Rect::new(
            padding_box.left + pad.left,
            padding_box.top + pad.top,
            padding_box.right - pad.right,
            padding_box.bottom - pad.bottom,
        );
        let state = self.engine.inputs.get(&node.key);
        let focused = self.engine.focused.as_deref() == Some(node.key.as_str());
        let (display, props, placeholder) = self.engine.input_display(node);
        let mut copy = self.engine.paragraph(&display, &props, s);
        let paragraph = &ctx.paragraph;

        let cursor = match state {
            Some(st) if !placeholder => {
                st.editor.cursor() + st.preedit.as_ref().map_or(0, String::len)
            }
            _ => 0,
        };
        let caret = if placeholder {
            caret_rect(paragraph, "", 0)
        } else {
            caret_rect(paragraph, &display, cursor)
        };

        let mut scroll_x = 0.0;
        if !s.multiline {
            scroll_x = state.map_or(0.0, |st| st.scroll_x);
            let view = content.width();
            if focused {
                if caret.left - scroll_x > view - CARET_WIDTH {
                    scroll_x = caret.left - view + CARET_WIDTH;
                }
                if caret.left - scroll_x < 0.0 {
                    scroll_x = caret.left;
                }
            }
            let text_width = if placeholder {
                0.0
            } else {
                paragraph.longest_line()
            };
            scroll_x = scroll_x.clamp(0.0, (text_width + CARET_WIDTH - view).max(0.0));
        }
        let origin = Point::new(content.left - scroll_x, content.top);

        canvas.save();
        canvas.clip_rect(padding_box, ClipOp::Intersect, true);
        if focused
            && let Some(st) = state
            && st.editor.has_selection()
            && st.preedit.is_none()
        {
            let color = s
                .selection_color
                .unwrap_or_else(|| tp.focus_color.with_a(110));
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(color);
            for r in range_rects(paragraph, &display, st.editor.selection()) {
                canvas.draw_rect(r.with_offset(origin), &p);
            }
        }
        paragraph.paint(canvas, origin);
        let mut ink = Paint::default();
        ink.set_anti_alias(true).set_color(tp.color);
        if let Some(st) = state
            && let Some(pre) = &st.preedit
            && !placeholder
        {
            let start = st.editor.cursor();
            for r in range_rects(paragraph, &display, start..start + pre.len()) {
                let r = r.with_offset(origin);
                canvas.draw_rect(
                    Rect::new(r.left, r.bottom - 1.5, r.right, r.bottom - 0.5),
                    &ink,
                );
            }
        }
        if focused && state.is_some_and(|st| st.caret_visible() && !st.editor.has_selection()) {
            canvas.draw_rect(caret.with_offset(origin), &ink);
        }
        canvas.restore();

        // Copia del párrafo para resolver clics y teclas hasta el próximo frame.
        copy.layout(if s.multiline {
            content.width() + 0.5
        } else {
            UNBOUNDED
        });
        self.inputs.push((
            node.key.clone(),
            scroll_x,
            InputFrame {
                paragraph: copy,
                display,
                placeholder,
                origin,
                caret: caret.with_offset(origin),
            },
        ));
    }
}

/// Pinta la imagen encajada (`fit`) en `content`, recortada a `clip` (las
/// esquinas redondeadas del nodo, para avatares y miniaturas).
fn paint_image(canvas: &Canvas, loaded: &Loaded, fit: Fit, content: Rect, clip: RRect) {
    let dest = fit.place(loaded.size, content);
    canvas.save();
    canvas.clip_rrect(clip, ClipOp::Intersect, true);
    match &loaded.decoded {
        Decoded::Raster(image) => {
            let sampling = SamplingOptions::new(FilterMode::Linear, MipmapMode::Linear);
            let mut p = Paint::default();
            p.set_anti_alias(true);
            canvas.draw_image_rect_with_sampling_options(image, None, dest, sampling, &p);
        }
        Decoded::Svg(dom) => {
            let (sx, sy) = (
                dest.width() / loaded.size.width.max(1e-3),
                dest.height() / loaded.size.height.max(1e-3),
            );
            canvas.translate((dest.left, dest.top)).scale((sx, sy));
            dom.render(canvas);
        }
    }
    canvas.restore();
}

fn paint_scrollbars(canvas: &Canvas, state: &ScrollState, color: Option<Color>) {
    if state.bar <= 0.0 {
        return;
    }
    let color = color.unwrap_or(Color::from_rgb(0x80, 0x88, 0xA0));
    let strength = if state.dragging { 0.85 } else { 0.55 };
    let alpha = (color.a() as f32 * state.bar * strength).round() as u8;
    let mut p = Paint::default();
    p.set_anti_alias(true).set_color(color.with_a(alpha));
    for vertical in [true, false] {
        if let Some(thumb) = state.thumb(vertical) {
            let r = BAR_WIDTH / 2.0;
            canvas.draw_rrect(RRect::new_rect_xy(thumb, r, r), &p);
        }
    }
}

fn background_paint(s: &Style, rect: Rect, st: AnimState) -> Option<Paint> {
    let mut p = Paint::default();
    p.set_anti_alias(true);
    if let Some(g) = s.gradient {
        let (sin, cos) = g.angle.to_radians().sin_cos();
        let c = rect.center();
        let half = Point::new(cos * rect.width() / 2.0, sin * rect.height() / 2.0);
        let colors = [Color4f::from(g.from), Color4f::from(g.to)];
        let grad = SkGradient::new(
            GradientColors::new_evenly_spaced(&colors, TileMode::Clamp, None),
            gradient::Interpolation::default(),
        );
        p.set_shader(gradient::shaders::linear_gradient(
            (c - half, c + half),
            &grad,
            None,
        ));
        // Las capas de hover/pressed se superponen como un velo translúcido.
        if st.hover > 0.0 || st.press > 0.0 {
            let veil = Color::from_argb((st.hover * 24.0 + st.press * 24.0) as u8, 255, 255, 255);
            p.set_color_filter(skia_safe::color_filters::blend(
                veil,
                skia_safe::BlendMode::SrcATop,
            ));
        }
        return Some(p);
    }
    let base = s.bg?;
    let mut color = base;
    if let Some(h) = s.bg_hover {
        color = lerp(color, h, st.hover);
    }
    if let Some(pr) = s.bg_pressed {
        color = lerp(color, pr, st.press);
    }
    p.set_color(color);
    Some(p)
}

/// Un campo ocupa el ancho que le den (o `INPUT_WIDTH`) y el alto de una línea;
/// uno multilínea crece con el texto, con un mínimo de `rows` líneas.
fn measure_input(
    p: &mut Paragraph,
    leaf: InputLeaf,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    let width = known.width.unwrap_or(match avail.width {
        AvailableSpace::Definite(w) => INPUT_WIDTH.min(w).max(INPUT_MIN_WIDTH.min(w)),
        AvailableSpace::MinContent => INPUT_MIN_WIDTH,
        AvailableSpace::MaxContent => INPUT_WIDTH,
    });
    p.layout(if leaf.multiline {
        width.max(1.0)
    } else {
        UNBOUNDED
    });
    let line = p.height() / p.line_number().max(1) as f32;
    let height = if leaf.multiline {
        p.height().max(leaf.rows as f32 * line)
    } else {
        line
    };
    Size {
        width,
        height: known.height.unwrap_or(height.ceil()),
    }
}

/// Una imagen mantiene su proporción: con un lado fijado, el otro sale de él;
/// sin ninguno, ocupa su tamaño natural sin pasar del ancho disponible.
fn measure_image(
    natural: skia_safe::Size,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    let ratio = if natural.height > 0.0 {
        natural.width / natural.height
    } else {
        1.0
    };
    let (width, height) = match (known.width, known.height) {
        (Some(w), Some(h)) => (w, h),
        (Some(w), None) => (w, w / ratio),
        (None, Some(h)) => (h * ratio, h),
        (None, None) => {
            let max = match avail.width {
                AvailableSpace::Definite(w) => w,
                // Como `max-width: 100%`: en una fila sin sitio, la imagen se encoge.
                AvailableSpace::MinContent => 0.0,
                AvailableSpace::MaxContent => f32::INFINITY,
            };
            let w = natural.width.min(max);
            (w, w / ratio)
        }
    };
    Size { width, height }
}

fn measure_text(
    p: &mut Paragraph,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    let max_w = known.width.unwrap_or(match avail.width {
        AvailableSpace::Definite(w) => w,
        AvailableSpace::MinContent => {
            p.layout(UNBOUNDED);
            p.min_intrinsic_width()
        }
        AvailableSpace::MaxContent => UNBOUNDED,
    });
    p.layout(max_w.max(1.0));
    Size {
        width: known
            .width
            .unwrap_or_else(|| p.max_intrinsic_width().min(max_w).ceil()),
        height: known.height.unwrap_or_else(|| p.height().ceil()),
    }
}

fn finalize_text(tree: &mut TaffyTree<Leaf>, lnode: &LayoutNode) {
    let layout = *tree.layout(lnode.id).expect("layout");
    if let Some(Leaf::Text(ctx)) = tree.get_node_context_mut(lnode.id) {
        let w = layout.content_box_width();
        // +0.5 evita cortes de línea espurios por redondeo del layout.
        let w = match ctx.input {
            Some(leaf) if !leaf.multiline => UNBOUNDED,
            _ => w + 0.5,
        };
        if ctx.laid_out != Some(w) {
            ctx.paragraph.layout(w);
            ctx.laid_out = Some(w);
        }
    }
    for child in &lnode.children {
        finalize_text(tree, child);
    }
}

fn overflow(scrolls: bool) -> Overflow {
    if scrolls {
        Overflow::Hidden
    } else {
        Overflow::Visible
    }
}

fn taffy_style(s: &Style) -> taffy::Style {
    let len = LengthPercentage::length;
    let dim = |v: Option<Len>| match v {
        Some(Len::Px(px)) => Dimension::length(px),
        Some(Len::Pct(p)) => Dimension::percent(p),
        None => Dimension::auto(),
    };
    let inset = |v: Option<Len>| match v {
        Some(Len::Px(px)) => LengthPercentageAuto::length(px),
        Some(Len::Pct(p)) => LengthPercentageAuto::percent(p),
        None => LengthPercentageAuto::auto(),
    };
    let lpa = |v: Option<f32>| {
        v.map(LengthPercentageAuto::length)
            .unwrap_or(LengthPercentageAuto::auto())
    };
    taffy::Style {
        display: Display::Flex,
        position: if s.absolute {
            Position::Absolute
        } else {
            Position::Relative
        },
        inset: taffy::Rect {
            top: inset(s.inset[0]),
            right: inset(s.inset[1]),
            bottom: inset(s.inset[2]),
            left: inset(s.inset[3]),
        },
        flex_direction: if s.row {
            FlexDirection::Row
        } else {
            FlexDirection::Column
        },
        flex_wrap: if s.wrap {
            FlexWrap::Wrap
        } else {
            FlexWrap::NoWrap
        },
        gap: Size {
            width: len(s.gap),
            height: len(s.gap),
        },
        padding: taffy::Rect {
            left: len(s.padding.left),
            right: len(s.padding.right),
            top: len(s.padding.top),
            bottom: len(s.padding.bottom),
        },
        border: taffy::Rect {
            left: len(s.border_width),
            right: len(s.border_width),
            top: len(s.border_width),
            bottom: len(s.border_width),
        },
        align_items: match s.align.as_deref() {
            Some("start") => AlignItems::FLEX_START,
            Some("end") => AlignItems::FLEX_END,
            Some("center") => AlignItems::CENTER,
            Some("baseline") => AlignItems::BASELINE,
            _ => AlignItems::STRETCH,
        },
        justify_content: match s.justify.as_deref() {
            Some("center") => JustifyContent::CENTER,
            Some("end") => JustifyContent::FLEX_END,
            Some("between") => JustifyContent::SPACE_BETWEEN,
            Some("around") => JustifyContent::SPACE_AROUND,
            Some("evenly") => JustifyContent::SPACE_EVENLY,
            _ => JustifyContent::FLEX_START,
        },
        size: Size {
            width: dim(s.width),
            height: dim(s.height),
        },
        min_size: Size {
            width: lpa(s.min_width),
            height: lpa(s.min_height),
        },
        max_size: Size {
            width: lpa(s.max_width),
            height: lpa(s.max_height),
        },
        // `Hidden` (sin reservar hueco para la barra): la barra se superpone al contenido.
        overflow: taffy::Point {
            x: overflow(s.scroll.is_some_and(Axis::x)),
            y: overflow(s.scroll.is_some_and(Axis::y)),
        },
        flex_grow: s.grow,
        flex_shrink: s.shrink.unwrap_or(1.0),
        ..Default::default()
    }
}

/// Renderiza sin ventana a un PNG: útil para tests de snapshot y CI.
pub fn render_png(
    root: &Node,
    width: f32,
    height: f32,
    scale: f32,
    path: &str,
) -> pyo3::PyResult<()> {
    use pyo3::exceptions::PyRuntimeError;
    let mut engine = Engine::new();
    engine.load_images(root)?;
    let mut surface = raster_surface(width, height, scale).map_err(PyRuntimeError::new_err)?;
    engine.update(root, width, height, scale);
    let mut canvases = crate::canvas::Canvases::default();
    canvases.rebuilt();
    canvases.draw(root, &mut engine, true)?;
    let mut charts = crate::chart::Charts::default();
    charts.rebuilt();
    charts.draw(root, &mut engine, true)?;
    engine.paint(surface.canvas(), root, width, height, None);
    write_png(&mut surface, path).map_err(PyRuntimeError::new_err)
}

/// Superficie en memoria de `width × height` píxeles lógicos a la escala dada.
pub fn raster_surface(width: f32, height: f32, scale: f32) -> Result<Surface, String> {
    let (pw, ph) = (
        (width * scale).round() as i32,
        (height * scale).round() as i32,
    );
    surfaces::raster_n32_premul((pw.max(1), ph.max(1)))
        .ok_or_else(|| "no se pudo crear la superficie".into())
}

pub fn write_png(surface: &mut Surface, path: &str) -> Result<(), String> {
    let image = surface.image_snapshot();
    let data = image
        .encode(None, EncodedImageFormat::PNG, None)
        .ok_or("no se pudo codificar el PNG")?;
    std::fs::write(path, data.as_bytes()).map_err(|e| e.to_string())
}
