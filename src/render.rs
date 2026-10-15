//! Motor de layout (Taffy) + pintura (Skia) + estado de animación.
//!
//! Todo lo que ocurre por frame vive aquí, fuera del intérprete de Python.

use std::collections::HashMap;

use skia_safe::{
    BlurStyle, Canvas, Color, Color4f, EncodedImageFormat, FontMgr, FontStyle, MaskFilter, Paint,
    PaintStyle, Point, RRect, Rect, TileMode,
    font_style::{Slant, Weight, Width},
    gradient::{self, Colors as GradientColors, Gradient as SkGradient},
    surfaces,
    textlayout::{
        FontCollection, Paragraph, ParagraphBuilder, ParagraphStyle, TextAlign, TextStyle,
    },
};
use taffy::{
    AlignItems, AvailableSpace, Dimension, Display, FlexDirection, FlexWrap, JustifyContent,
    LengthPercentage, LengthPercentageAuto, NodeId, Position, Size, TaffyTree, compute_leaf_layout,
};

use crate::color::lerp;
use crate::spec::{Kind, Len, Node, Style, TextProps};

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
    pub interactive: bool,
    pub capture: bool,
    /// Índice del padre en el vector de regiones (para subir hasta un nodo interactivo).
    pub parent: Option<usize>,
}

/// Hit-testing: el nodo pintado más arriba bajo el cursor decide; el clic
/// burbujea hasta el ancestro interactivo más cercano o se detiene en una barrera.
pub fn hit_test(regions: &[HitRegion], x: f32, y: f32) -> Option<String> {
    let contains = |r: &Rect| x >= r.left && x < r.right && y >= r.top && y < r.bottom;
    let mut idx = regions.iter().rposition(|r| contains(&r.rect))?;
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
}

pub struct Engine {
    fonts: FontCollection,
    anim: HashMap<String, AnimState>,
    pub hovered: Option<String>,
    pub pressed: Option<String>,
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
            hovered: None,
            pressed: None,
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

    fn build_layout(&self, tree: &mut TaffyTree<TextCtx>, node: &Node) -> LayoutNode {
        let style = taffy_style(&node.style);
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
        let children: Vec<LayoutNode> = node
            .children
            .iter()
            .map(|c| self.build_layout(tree, c))
            .collect();
        let ids: Vec<NodeId> = children.iter().map(|c| c.id).collect();
        let id = tree.new_with_children(style, &ids).expect("taffy node");
        LayoutNode { id, children }
    }

    pub fn layout(&self, root: &Node, width: f32, height: f32) -> (TaffyTree<TextCtx>, LayoutNode) {
        let mut tree: TaffyTree<TextCtx> = TaffyTree::new();
        let lroot = self.build_layout(&mut tree, root);

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
        for key in [self.hovered.clone(), self.pressed.clone()]
            .into_iter()
            .flatten()
        {
            self.anim.entry(key).or_default();
        }
        let k = 1.0 - (-dt / TRANSITION_TAU).exp();
        let mut animating = false;
        let (hovered, pressed) = (self.hovered.as_deref(), self.pressed.as_deref());
        self.anim.retain(|key, s| {
            let th = if hovered == Some(key.as_str()) {
                1.0
            } else {
                0.0
            };
            let tp = if pressed == Some(key.as_str()) {
                1.0
            } else {
                0.0
            };
            s.hover += (th - s.hover) * k;
            s.press += (tp - s.press) * k;
            for (v, t) in [(&mut s.hover, th), (&mut s.press, tp)] {
                if (*v - t).abs() < 0.004 {
                    *v = t;
                } else {
                    animating = true;
                }
            }
            s.hover > 0.0 || s.press > 0.0 || th > 0.0 || tp > 0.0
        });
        animating
    }

    // ---------------------------------------------------------------- pintura

    /// Dibuja el árbol completo. `width`/`height` en píxeles lógicos.
    pub fn draw(
        &self,
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
            regions: Vec::new(),
        };
        painter.paint(root, &lroot, Point::new(0.0, 0.0), None);
        canvas.restore();
        painter.regions
    }
}

/// Contexto de un frame de pintura: recorre el árbol y registra las regiones de hit-testing.
struct Painter<'a> {
    engine: &'a Engine,
    canvas: &'a Canvas,
    tree: &'a TaffyTree<TextCtx>,
    regions: Vec<HitRegion>,
}

impl Painter<'_> {
    fn paint(&mut self, node: &Node, lnode: &LayoutNode, origin: Point, parent: Option<usize>) {
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
            interactive: node.is_interactive(),
            capture: node.style.capture,
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

        let child_origin = Point::new(rect.left, rect.top);
        for (child, lchild) in node.children.iter().zip(&lnode.children) {
            self.paint(child, lchild, child_origin, Some(my_index));
        }
        canvas.restore_to_count(save_count);
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
            height: LengthPercentageAuto::auto(),
        },
        max_size: Size {
            width: lpa(s.max_width),
            height: LengthPercentageAuto::auto(),
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
    let engine = Engine::new();
    let (pw, ph) = (
        (width * scale).round() as i32,
        (height * scale).round() as i32,
    );
    let mut surface =
        surfaces::raster_n32_premul((pw, ph)).ok_or("no se pudo crear la superficie")?;
    engine.draw(surface.canvas(), root, width, height, scale);
    let image = surface.image_snapshot();
    let data = image
        .encode(None, EncodedImageFormat::PNG, None)
        .ok_or("no se pudo codificar el PNG")?;
    std::fs::write(path, data.as_bytes()).map_err(|e| e.to_string())
}
