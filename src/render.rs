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
    MaskFilter, MipmapMode, Paint, PaintStyle, Point, RRect, Rect, SamplingOptions, Surface,
    TileMode,
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
use crate::scroll::{BAR_WIDTH, ScrollState};
use crate::spec::{Axis, Kind, Len, Node, Style, TextProps};

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
}

/// Rectángulo absoluto de cada nodo, en orden de pintura (para hit-testing).
pub struct HitRegion {
    pub key: String,
    pub rect: Rect,
    /// Zona visible: la intersección de los contenedores `scroll` que lo recortan.
    pub clip: Rect,
    pub interactive: bool,
    pub capture: bool,
    pub focusable: bool,
    /// Campo de texto: cursor de texto al pasar y el clic coloca el cursor.
    pub editable: bool,
    /// Tiene `tooltip`.
    pub tooltip: bool,
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

pub struct Engine {
    fonts: FontCollection,
    anim: HashMap<String, AnimState>,
    /// Estado de cada contenedor `scroll`, por key.
    pub scroll: HashMap<String, ScrollState>,
    /// Estado de cada campo de texto, por key.
    pub inputs: HashMap<String, InputState>,
    /// Imagen decodificada de cada nodo `image` del árbol actual, por key.
    images: HashMap<String, Rc<Loaded>>,
    image_cache: ImageCache,
    pub hovered: Option<String>,
    pub pressed: Option<String>,
    pub focused: Option<String>,
    /// El anillo de foco se muestra solo si se llegó con el teclado (como
    /// `:focus-visible` en CSS): un clic enfoca sin dibujar el anillo.
    pub focus_visible: bool,
    pub tip: Tip,
    /// Lo que tardó el layout del último `draw` (para las estadísticas del frame).
    pub layout_time: Duration,
    /// Si el último `draw` reutilizó el layout del frame anterior.
    pub layout_cached: bool,
    layout_cache: Option<LayoutCache>,
    /// El árbol cambió desde el último layout (`invalidate_layout`).
    tree_changed: bool,
    /// Párrafos del layout anterior, por contenido, a la espera de reutilizarse
    /// mientras se construye el siguiente.
    recycled: RefCell<HashMap<ParagraphKey, Vec<TextCtx>>>,
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
            scroll: HashMap::new(),
            inputs: HashMap::new(),
            images: HashMap::new(),
            image_cache: ImageCache::default(),
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

    /// El árbol de nodos cambió: el próximo `draw` rehace el layout.
    pub fn invalidate_layout(&mut self) {
        self.tree_changed = true;
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
        self.images = images;
        Ok(())
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
            Kind::Box => None,
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
        self.anim.retain(|key, s| {
            let on = |k: Option<&str>| if k == Some(key.as_str()) { 1.0 } else { 0.0 };
            let (th, tp, tf) = (on(hovered), on(pressed), on(ring));
            for (v, t) in [(&mut s.hover, th), (&mut s.press, tp), (&mut s.focus, tf)] {
                *v += (t - *v) * k;
                if (*v - t).abs() < 0.004 {
                    *v = t;
                } else {
                    animating = true;
                }
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
        animating
    }

    // ---------------------------------------------------------------- pintura

    /// Dibuja el árbol completo. `width`/`height` en píxeles lógicos.
    pub fn draw(
        &mut self,
        canvas: &Canvas,
        root: &Node,
        width: f32,
        height: f32,
        scale: f32,
    ) -> Vec<HitRegion> {
        let start = Instant::now();
        let inputs = self.inputs_signature();
        let mut cache = self.layout_cache.take().unwrap_or_default();
        let reuse = !self.tree_changed
            && cache.root.is_some()
            && cache.width == width
            && cache.height == height
            && cache.inputs == inputs;
        if !reuse {
            self.update_layout(&mut cache, root, width, height);
            // Lo que no se reutilizó ya no corresponde a ningún nodo.
            self.recycled.borrow_mut().clear();
            (cache.width, cache.height, cache.inputs) = (width, height, inputs);
            self.tree_changed = false;
        }
        self.layout_cached = reuse;
        self.layout_time = start.elapsed();
        let tree = &cache.tree;
        let lroot = cache.root.as_ref().expect("layout calculado");
        canvas.clear(root.style.bg.unwrap_or(Color::from_rgb(0x0B, 0x0D, 0x14)));
        // `restore_to_count` al final: un frame nunca deja la pila del canvas
        // desequilibrada (la superficie del piloto se reutiliza entre frames).
        let base = canvas.save();
        canvas.scale((scale, scale));
        let mut painter = Painter {
            engine: self,
            canvas,
            tree,
            scale,
            regions: Vec::new(),
            overlays: Vec::new(),
            scrolls: Vec::new(),
            inputs: Vec::new(),
            tip: None,
        };
        painter.paint(root, lroot, Point::new(0.0, 0.0), None, no_clip());
        // Las capas superiores se pintan al final, en orden de aparición. Una capa
        // anidada dentro de otra se encola al pintar la primera y queda por encima.
        // Escapan del recorte de los `scroll` que las contienen.
        let mut i = 0;
        while let Some(&(node, lnode, origin, parent)) = painter.overlays.get(i) {
            painter.paint_node(node, lnode, origin, parent, no_clip());
            i += 1;
        }
        // El tooltip va por encima de todo, capas incluidas, y no recibe eventos.
        if let Some((rect, node)) = painter.tip.take() {
            self.paint_tooltip(canvas, rect, node, width, height);
        }
        canvas.restore_to_count(base);
        let Painter {
            regions,
            scrolls,
            inputs,
            ..
        } = painter;
        self.layout_cache = Some(cache);
        self.sync_scroll(scrolls);
        for (key, scroll_x, frame) in inputs {
            if let Some(state) = self.inputs.get_mut(&key) {
                state.scroll_x = scroll_x;
                state.frame = Some(frame);
            }
        }
        regions
    }

    /// Guarda los límites medidos en este frame y olvida los `scroll` que ya no existen.
    fn sync_scroll(&mut self, seen: Vec<ScrollMetrics>) {
        let mut alive = HashSet::new();
        for m in seen {
            self.scroll
                .entry(m.key.clone())
                .or_default()
                .set_limits(m.axis, m.max, m.viewport);
            alive.insert(m.key);
        }
        self.scroll.retain(|k, _| alive.contains(k));
    }
}

/// Límites de un contenedor `scroll` medidos durante la pintura.
struct ScrollMetrics {
    key: String,
    axis: Axis,
    max: Point,
    viewport: Rect,
}

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

/// Nodo de la capa superior pendiente de pintar: nodo, layout, origen absoluto y región padre.
type Deferred<'a> = (&'a Node, &'a LayoutNode, Point, Option<usize>);

/// Contexto de un frame de pintura: recorre el árbol y registra las regiones de hit-testing.
struct Painter<'a> {
    engine: &'a Engine,
    canvas: &'a Canvas,
    tree: &'a TaffyTree<Leaf>,
    /// Densidad de píxeles, para alinear el desplazamiento a píxeles físicos.
    scale: f32,
    regions: Vec<HitRegion>,
    /// Nodos con `layer="overlay"` aplazados hasta el final del frame.
    overlays: Vec<Deferred<'a>>,
    scrolls: Vec<ScrollMetrics>,
    /// Nodo cuyo tooltip hay que pintar al final del frame, con su rectángulo.
    tip: Option<(Rect, &'a Node)>,
    /// Geometría de cada campo pintado: key, desplazamiento horizontal y frame.
    inputs: Vec<(String, f32, InputFrame)>,
}

impl<'a> Painter<'a> {
    fn paint(
        &mut self,
        node: &'a Node,
        lnode: &'a LayoutNode,
        origin: Point,
        parent: Option<usize>,
        clip: Rect,
    ) {
        if node.style.overlay {
            self.overlays.push((node, lnode, origin, parent));
            return;
        }
        self.paint_node(node, lnode, origin, parent, clip);
    }

    /// Pinta el nodo y sus hijos. Una capa aplazada se pinta en coordenadas
    /// absolutas: no hereda la opacidad ni la escala de sus ancestros.
    fn paint_node(
        &mut self,
        node: &'a Node,
        lnode: &'a LayoutNode,
        origin: Point,
        parent: Option<usize>,
        clip: Rect,
    ) {
        let canvas = self.canvas;
        let layout = self.tree.layout(lnode.id).expect("layout");
        let rect = Rect::from_xywh(
            origin.x + layout.location.x,
            origin.y + layout.location.y,
            layout.size.width,
            layout.size.height,
        );
        let my_index = self.regions.len();
        self.regions.push(HitRegion {
            key: node.key.clone(),
            rect,
            clip,
            interactive: node.is_interactive() || node.is_editable(),
            capture: node.style.capture,
            focusable: node.is_focusable(),
            editable: node.is_editable(),
            tooltip: node.style.tooltip.is_some(),
            scroll: node.style.scroll,
            parent,
        });

        let s = &node.style;
        let st = self.engine.anim.get(&node.key).copied().unwrap_or_default();

        let save_count = canvas.save();
        if s.opacity < 1.0 {
            canvas.save_layer_alpha_f(None, s.opacity);
        }
        if s.press_scale != 1.0 && st.press > 0.0 {
            let k = 1.0 + (s.press_scale - 1.0) * st.press;
            let c = rect.center();
            canvas.translate(c).scale((k, k)).translate(-c);
        }

        let rrect = RRect::new_rect_xy(rect, s.radius, s.radius);

        if let Some(sh) = s.shadow {
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(sh.color);
            if let Some(mf) = MaskFilter::blur(BlurStyle::Normal, sh.blur / 2.0, false) {
                p.set_mask_filter(mf);
            }
            canvas.draw_rrect(rrect.with_offset((sh.dx, sh.dy)), &p);
        }

        if let Some(paint) = background_paint(s, rect, st) {
            canvas.draw_rrect(rrect, &paint);
        }

        if node.kind == Kind::Image
            && let Some(loaded) = self.engine.images.get(&node.key)
        {
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
            let r = (s.radius - s.border_width).max(0.0);
            paint_image(
                canvas,
                loaded,
                s.fit,
                content,
                RRect::new_rect_xy(inner, r, r),
            );
        }

        if s.border_width > 0.0
            && let Some(color) = s.border_color
        {
            let half = s.border_width / 2.0;
            let inner = RRect::new_rect_xy(
                rect.with_inset((half, half)),
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

        let mut child_origin = Point::new(rect.left, rect.top);
        let mut child_clip = clip;
        let mut bars = None;
        if let Some(axis) = s.scroll {
            // Se recorta a la caja de relleno (dentro del borde) y los hijos se
            // desplazan; la barra se pinta encima, sin ocupar espacio en el layout.
            let bw = s.border_width;
            let viewport = rect.with_inset((bw, bw));
            let max = Point::new(layout.scroll_width(), layout.scroll_height());
            let mut state = self
                .engine
                .scroll
                .get(&node.key)
                .cloned()
                .unwrap_or_default();
            state.set_limits(axis, max, viewport);
            let snap = |v: f32| (v * self.scale).round() / self.scale;
            let offset = Point::new(snap(state.offset.x), snap(state.offset.y));
            canvas.save();
            let r = (s.radius - bw).max(0.0);
            canvas.clip_rrect(RRect::new_rect_xy(viewport, r, r), ClipOp::Intersect, true);
            child_origin -= offset;
            child_clip = intersect(clip, viewport);
            self.scrolls.push(ScrollMetrics {
                key: node.key.clone(),
                axis,
                max,
                viewport,
            });
            bars = Some(state);
        }
        for (child, lchild) in node.children.iter().zip(&lnode.children) {
            self.paint(child, lchild, child_origin, Some(my_index), child_clip);
        }
        if let Some(state) = bars {
            canvas.restore();
            paint_scrollbars(canvas, &state, s.scrollbar_color);
        }
        if self.engine.tip.alpha > 0.0
            && node.style.tooltip.is_some()
            && self.engine.tip.key.as_deref() == Some(node.key.as_str())
        {
            self.tip = Some((rect, node));
        }
        if st.focus > 0.0 {
            paint_focus_ring(
                canvas,
                rect,
                s.radius,
                node.text_props.focus_color,
                st.focus,
            );
        }
        canvas.restore_to_count(save_count);
    }
}

impl Engine {
    /// Burbuja del tooltip debajo del nodo (o encima, si no cabe), centrada y
    /// sin salirse de la ventana. Colores heredables: `tooltip_bg` y `tooltip_color`.
    fn paint_tooltip(&self, canvas: &Canvas, owner: Rect, node: &Node, width: f32, height: f32) {
        const PAD: (f32, f32) = (10.0, 6.0);
        const GAP: f32 = 8.0;
        const MARGIN: f32 = 8.0;
        const MAX_WIDTH: f32 = 260.0;
        let Some(text) = node.style.tooltip.as_deref() else {
            return;
        };
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
        let bubble = RRect::new_rect_xy(Rect::from_xywh(x, y, w, h), 8.0, 8.0);

        canvas.save_layer_alpha_f(None, self.tip.alpha);
        let mut shadow = Paint::default();
        shadow
            .set_anti_alias(true)
            .set_color(Color::from_argb(60, 0, 0, 0));
        if let Some(mf) = MaskFilter::blur(BlurStyle::Normal, 6.0, false) {
            shadow.set_mask_filter(mf);
        }
        canvas.draw_rrect(bubble.with_offset((0.0, 3.0)), &shadow);
        let mut bg = Paint::default();
        bg.set_anti_alias(true).set_color(tp.tooltip_bg);
        canvas.draw_rrect(bubble, &bg);
        p.paint(canvas, (x + PAD.0, y + PAD.1));
        canvas.restore();
    }
}

/// Anillo de foco: trazo de 2 px separado 2 px del borde, que sigue las esquinas.
fn paint_focus_ring(canvas: &Canvas, rect: Rect, radius: f32, color: Color, t: f32) {
    const GAP: f32 = 2.0;
    const WIDTH: f32 = 2.0;
    let out = GAP + WIDTH / 2.0;
    let r = if radius > 0.0 { radius + out } else { 0.0 };
    let ring = RRect::new_rect_xy(rect.with_outset((out, out)), r, r);
    let mut p = Paint::default();
    p.set_anti_alias(true)
        .set_style(PaintStyle::Stroke)
        .set_stroke_width(WIDTH)
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
    let inset = |v: Option<f32>| {
        v.map(LengthPercentageAuto::length)
            .unwrap_or(LengthPercentageAuto::auto())
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
    engine.draw(surface.canvas(), root, width, height, scale);
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
