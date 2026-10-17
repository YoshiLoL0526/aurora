//! Motor de layout (Taffy) + pintura (Skia) + estado de animación.
//!
//! Todo lo que ocurre por frame vive aquí, fuera del intérprete de Python.
//! El código se reparte por fases del frame: `style` decide qué cambió,
//! `layout` mide con Taffy, `geom` calcula geometría y hit-testing, `paint`
//! pinta por zonas y `draw` dibuja una figura; `text` y `png` completan el resto.

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

mod draw;
mod geom;
mod layout;
mod paint;
mod png;
mod style;
mod text;

pub use self::draw::content_size;
pub use self::geom::{Mark, ancestors, hit_test, topmost};
pub use self::png::{raster_surface, render_png, write_png};

use self::draw::*;
use self::geom::*;
use self::layout::*;
use self::paint::*;
use self::style::*;
use self::text::*;

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
}

impl Engine {
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
}

impl Engine {
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
