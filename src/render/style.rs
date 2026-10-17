//! Fase de estilo y animaciones declarativas: qué cambió entre reconstrucciones.

use super::*;

#[derive(Default, Clone, Copy, Debug)]
pub struct AnimState {
    pub hover: f32,
    pub press: f32,
    /// Visibilidad del anillo de foco.
    pub focus: f32,
}

/// Animaciones declarativas en curso de un nodo (ver `motion.rs`).
#[derive(Default)]
pub(super) struct Motion {
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
    pub(super) layout: Option<Track>,
    /// Efecto de entrada (`opacidad, x, y, escala`) camino de la identidad.
    pub(super) enter: Option<Track>,
    /// Zona (absoluta y visible) en la que se pintó desplazado o transformado
    /// en el último frame: hay que repintarla cuando se mueve o termina.
    painted: Option<Rect>,
}

impl Motion {
    fn is_empty(&self) -> bool {
        !self.restyled() && !self.transformed()
    }

    /// Alguna propiedad de estilo está en transición.
    pub(super) fn restyled(&self) -> bool {
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
pub(super) struct Ghost {
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

/// Constante de tiempo de las transiciones de estado (segundos).
const TRANSITION_TAU: f32 = 0.07;

impl Engine {
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
    pub(super) fn start_motions(
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
    pub(super) fn refresh_moving(&mut self) {
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
    pub(super) fn motion_damage(&mut self) -> Option<Rect> {
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
    pub(super) fn paint_ghosts(&self, canvas: &Canvas, overlay: bool) {
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
    pub(super) fn recolor_texts(&self, root: &Node, cache: &mut LayoutCache) {
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
    pub(super) fn recycle(&self, leaf: Leaf) {
        if let Leaf::Text(ctx) = leaf {
            self.recycled
                .borrow_mut()
                .entry(ctx.key.clone())
                .or_default()
                .push(ctx);
        }
    }
}

impl Engine {
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
}

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
pub(super) fn animated_style(style: &Style, m: &Motion) -> Style {
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
pub(super) fn shown_rect(m: &Motion, local: Rect) -> Rect {
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
pub(super) fn apply_effect(canvas: &Canvas, rect: Rect, v: Vec4) {
    canvas.translate((v[1], v[2]));
    if v[3] != 1.0 {
        let c = rect.center();
        canvas.translate(c).scale((v[3], v[3])).translate(-c);
    }
}
