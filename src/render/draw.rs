//! Dibujo de una figura: caja de contenido, imágenes, barras y anillo de foco.

use super::*;

/// Caja de relleno (dentro del borde) y caja de contenido (dentro del padding).
pub(super) fn content_box(rect: Rect, layout: &taffy::Layout) -> (Rect, Rect) {
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
pub(super) const FOCUS_GAP: f32 = 2.0;
pub(super) const FOCUS_WIDTH: f32 = 2.0;

/// Lo que sobresale el anillo de foco de su nodo.
pub(super) const FOCUS_OUTSET: f32 = FOCUS_GAP + FOCUS_WIDTH;

/// Anillo de foco: trazo de 2 px separado 2 px del borde, que sigue las esquinas.
pub(super) fn paint_focus_ring(canvas: &Canvas, rect: Rect, radius: f32, color: Color, t: f32) {
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

/// Pinta la imagen encajada (`fit`) en `content`, recortada a `clip` (las
/// esquinas redondeadas del nodo, para avatares y miniaturas).
pub(super) fn paint_image(canvas: &Canvas, loaded: &Loaded, fit: Fit, content: Rect, clip: RRect) {
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

pub(super) fn paint_scrollbars(canvas: &Canvas, state: &ScrollState, color: Option<Color>) {
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

pub(super) fn background_paint(s: &Style, rect: Rect, st: AnimState) -> Option<Paint> {
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
