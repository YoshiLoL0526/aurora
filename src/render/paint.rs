//! Fase de pintura: repintado por zonas y recorrido del árbol.

use super::*;

/// Tooltip pintado en el último frame.
#[derive(Clone, PartialEq)]
pub(super) struct TipPaint {
    ink: Rect,
    alpha: f32,
    text: String,
    colors: (Color, Color),
}

impl Engine {
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
}

impl Engine {
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

/// Nodo de la capa superior pendiente de pintar: nodo, layout, origen absoluto
/// y desplazamiento acumulado de los `scroll` que lo contienen.
pub(super) type Deferred<'a> = (&'a Node, &'a LayoutNode, Point, Point);

/// Contexto de un frame de pintura: recorre el árbol saltándose lo que queda
/// fuera de la zona dañada.
pub(super) struct Painter<'a> {
    pub(super) engine: &'a Engine,
    pub(super) canvas: &'a Canvas,
    pub(super) tree: &'a TaffyTree<Leaf>,
    /// Densidad de píxeles, para alinear el desplazamiento a píxeles físicos.
    pub(super) scale: f32,
    /// Zona a repintar (absoluta).
    pub(super) damage: Rect,
    /// Nodos con `layer="overlay"` aplazados hasta el final del frame.
    pub(super) overlays: Vec<Deferred<'a>>,
    /// Geometría de cada campo pintado: key, desplazamiento horizontal y frame.
    pub(super) inputs: Vec<(String, f32, InputFrame)>,
    /// Desplazamiento que ya aplicaron al lienzo las animaciones de layout de
    /// los ancestros (un hijo que también se anima solo añade la diferencia).
    pub(super) moved: Point,
    /// Si se descartan los subárboles cuya tinta queda fuera de la zona a
    /// repintar. Dentro de un nodo transformado no se puede: su tinta no cuenta
    /// con la transformación.
    pub(super) cull: bool,
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
    pub(super) fn paint_node(
        &mut self,
        node: &'a Node,
        lnode: &'a LayoutNode,
        origin: Point,
        shift: Point,
    ) {
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
        // `canvas.rs` y `chart/`), recortado a la caja de contenido.
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
