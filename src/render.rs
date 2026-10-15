//! Motor de layout (Taffy) + pintura (Skia) + estado de animación.
//!
//! Todo lo que ocurre por frame vive aquí, fuera del intérprete de Python.

use std::collections::{HashMap, HashSet};

use skia_safe::{
    BlurStyle, Canvas, ClipOp, Color, Color4f, EncodedImageFormat, FontMgr, FontStyle, MaskFilter,
    Paint, PaintStyle, Point, RRect, Rect, Surface, TileMode,
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
    compute_leaf_layout,
};

use crate::color::lerp;
use crate::scroll::{BAR_WIDTH, ScrollState};
use crate::spec::{Axis, Kind, Len, Node, Style, TextProps};

/// Contexto de los nodos hoja de texto: el párrafo ya "shapeado" se reutiliza
/// para medir (durante el layout) y para pintar.
pub struct TextCtx {
    paragraph: Paragraph,
}

/// Árbol de layout paralelo al árbol de nodos.
pub struct LayoutNode {
    id: NodeId,
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
    pub hovered: Option<String>,
    pub pressed: Option<String>,
    pub focused: Option<String>,
    /// El anillo de foco se muestra solo si se llegó con el teclado (como
    /// `:focus-visible` en CSS): un clic enfoca sin dibujar el anillo.
    pub focus_visible: bool,
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
            hovered: None,
            pressed: None,
            focused: None,
            focus_visible: false,
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

    // ----------------------------------------------------------------- layout

    /// `in_scroll`: el padre se desplaza a lo largo de su eje principal.
    fn build_layout(
        &self,
        tree: &mut TaffyTree<TextCtx>,
        node: &Node,
        in_scroll: bool,
    ) -> LayoutNode {
        let mut style = taffy_style(&node.style);
        // Dentro de un scroll los hijos no se encogen por defecto: el contenido que
        // no cabe se desplaza en vez de aplastarse.
        if in_scroll && node.style.shrink.is_none() {
            style.flex_shrink = 0.0;
        }
        if node.kind == Kind::Text {
            let paragraph = self.paragraph(
                node.text.as_deref().unwrap_or(""),
                &node.text_props,
                &node.style,
            );
            let id = tree
                .new_leaf_with_context(style, TextCtx { paragraph })
                .expect("taffy leaf");
            return LayoutNode {
                id,
                children: Vec::new(),
            };
        }
        let scrolls_main = node
            .style
            .scroll
            .is_some_and(|a| if node.style.row { a.x() } else { a.y() });
        let children: Vec<LayoutNode> = node
            .children
            .iter()
            .map(|c| self.build_layout(tree, c, scrolls_main))
            .collect();
        let ids: Vec<NodeId> = children.iter().map(|c| c.id).collect();
        let id = tree.new_with_children(style, &ids).expect("taffy node");
        LayoutNode { id, children }
    }

    pub fn layout(&self, root: &Node, width: f32, height: f32) -> (TaffyTree<TextCtx>, LayoutNode) {
        let mut tree: TaffyTree<TextCtx> = TaffyTree::new();
        let lroot = self.build_layout(&mut tree, root, false);

        // La raíz siempre ocupa la ventana completa.
        let mut root_style = tree.style(lroot.id).expect("root").clone();
        root_style.size = Size {
            width: Dimension::length(width),
            height: Dimension::length(height),
        };
        tree.set_style(lroot.id, root_style).expect("root style");

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
                        let Some(ctx) = ctx else { return Size::ZERO };
                        let size = measure_text(&mut ctx.paragraph, known, avail);
                        baseline = Some(ctx.paragraph.alphabetic_baseline());
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
        finalize_text(&mut tree, &lroot);
        (tree, lroot)
    }

    // -------------------------------------------------------------- animación

    /// Avanza las transiciones `dt` segundos. Devuelve `true` si alguna sigue en curso.
    pub fn tick(&mut self, dt: f32) -> bool {
        let ring = self.focused.clone().filter(|_| self.focus_visible);
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
        let (tree, lroot) = self.layout(root, width, height);
        canvas.clear(root.style.bg.unwrap_or(Color::from_rgb(0x0B, 0x0D, 0x14)));
        canvas.save();
        canvas.scale((scale, scale));
        let mut painter = Painter {
            engine: self,
            canvas,
            tree: &tree,
            scale,
            regions: Vec::new(),
            overlays: Vec::new(),
            scrolls: Vec::new(),
        };
        painter.paint(root, &lroot, Point::new(0.0, 0.0), None, no_clip());
        // Las capas superiores se pintan al final, en orden de aparición. Una capa
        // anidada dentro de otra se encola al pintar la primera y queda por encima.
        // Escapan del recorte de los `scroll` que las contienen.
        let mut i = 0;
        while let Some(&(node, lnode, origin, parent)) = painter.overlays.get(i) {
            painter.paint_node(node, lnode, origin, parent, no_clip());
            i += 1;
        }
        canvas.restore();
        let Painter {
            regions, scrolls, ..
        } = painter;
        self.sync_scroll(scrolls);
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
    tree: &'a TaffyTree<TextCtx>,
    /// Densidad de píxeles, para alinear el desplazamiento a píxeles físicos.
    scale: f32,
    regions: Vec<HitRegion>,
    /// Nodos con `layer="overlay"` aplazados hasta el final del frame.
    overlays: Vec<Deferred<'a>>,
    scrolls: Vec<ScrollMetrics>,
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
            interactive: node.is_interactive(),
            capture: node.style.capture,
            focusable: node.is_focusable(),
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
            && let Some(ctx) = self.tree.get_node_context(lnode.id)
        {
            let pad = layout.padding;
            ctx.paragraph
                .paint(canvas, (rect.left + pad.left, rect.top + pad.top));
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

fn measure_text(
    p: &mut Paragraph,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    const UNBOUNDED: f32 = 1.0e6;
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

fn finalize_text(tree: &mut TaffyTree<TextCtx>, lnode: &LayoutNode) {
    let layout = *tree.layout(lnode.id).expect("layout");
    if let Some(ctx) = tree.get_node_context_mut(lnode.id) {
        let w = layout.size.width - layout.padding.left - layout.padding.right;
        // +0.5 evita cortes de línea espurios por redondeo del layout.
        ctx.paragraph.layout(w + 0.5);
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
) -> Result<(), String> {
    let mut engine = Engine::new();
    let mut surface = raster_surface(width, height, scale)?;
    engine.draw(surface.canvas(), root, width, height, scale);
    write_png(&mut surface, path)
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
