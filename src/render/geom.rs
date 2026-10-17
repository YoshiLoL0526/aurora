//! Geometría y hit-testing: regiones, capas, tinta y zonas dañadas.

use super::*;

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
    pub(super) local: Rect,
    pub(super) ink: Rect,
    /// Lo que pinta el propio nodo (`LayoutNode::own`), en coordenadas locales.
    pub(super) own: Rect,
    pub(super) layer: usize,
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

/// Misma identidad, estructura, contenido y manejadores: lo que hay que comprobar
/// aunque el estilo no cambie.
pub(super) fn same_shape(a: &Node, b: &Node) -> bool {
    a.key == b.key
        && a.kind == b.kind
        && a.children.len() == b.children.len()
        && a.text == b.text
        && a.same_handlers(b)
}

/// Dos nodos con la misma forma (`same_shape`) y distinto estilo tienen la misma
/// geometría si coinciden en todo esto: el layout, las regiones y la tinta del
/// anterior valen para el nuevo.
pub(super) fn same_geometry(a: &Node, b: &Node) -> bool {
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
pub(super) fn compute_ink(
    tree: &TaffyTree<Leaf>,
    node: &Node,
    lnode: &mut LayoutNode,
    origin: Point,
) {
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

/// Nodo de layout con esa key.
pub(super) fn find_layout<'a>(lnode: &'a LayoutNode, key: &str) -> Option<&'a LayoutNode> {
    if lnode.key == key {
        return Some(lnode);
    }
    lnode.children.iter().find_map(|c| find_layout(c, key))
}

/// Si el árbol de layout tiene la misma forma (por keys) que el subárbol.
pub(super) fn same_keys(node: &Node, lnode: &LayoutNode) -> bool {
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
pub(super) fn repainted_nodes(old: &Node, new: &Node, out: &mut HashSet<String>) {
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

pub(super) fn no_clip() -> Rect {
    Rect::new(-1.0e9, -1.0e9, 1.0e9, 1.0e9)
}

pub(super) fn intersect(a: Rect, b: Rect) -> Rect {
    Rect::new(
        a.left.max(b.left),
        a.top.max(b.top),
        a.right.min(b.right),
        a.bottom.min(b.bottom),
    )
}

/// El menor rectángulo que contiene a ambos.
pub(super) fn join(a: Rect, b: Rect) -> Rect {
    Rect::new(
        a.left.min(b.left),
        a.top.min(b.top),
        a.right.max(b.right),
        a.bottom.max(b.bottom),
    )
}

pub(super) fn overlaps(a: Rect, b: Rect) -> bool {
    a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom
}

/// Une una zona a la dañada; las vacías no cuentan.
pub(super) fn union(damage: Option<Rect>, r: Option<Rect>) -> Option<Rect> {
    match (damage, r.filter(|r| r.width() > 0.0 && r.height() > 0.0)) {
        (Some(d), Some(r)) => Some(join(d, r)),
        (d, r) => d.or(r),
    }
}

/// Amplía la zona a píxeles físicos enteros: con un recorte alineado, lo
/// repintado es idéntico a lo que daría pintar el frame entero.
pub(super) fn pixel_align(r: Rect, scale: f32) -> Option<Rect> {
    let r = Rect::new(
        (r.left * scale).floor() / scale,
        (r.top * scale).floor() / scale,
        (r.right * scale).ceil() / scale,
        (r.bottom * scale).ceil() / scale,
    );
    (r.width() > 0.0 && r.height() > 0.0).then_some(r)
}

/// Alinea un desplazamiento a píxeles físicos (el texto no se emborrona).
pub(super) fn snap(p: Point, scale: f32) -> Point {
    Point::new((p.x * scale).round() / scale, (p.y * scale).round() / scale)
}

impl Engine {
    /// Recalcula las regiones de hit-testing y las capas tras un layout. Las
    /// regiones quedan en orden de pintura: las capas superiores, al final.
    /// Devuelve las regiones y capas anteriores; las capas que siguen existiendo
    /// conservan lo que se pintó de ellas.
    pub(super) fn geometry(
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
    pub(super) fn relayout_damage(
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
    pub(super) fn place_layers(&mut self, scale: f32, force: bool) -> Option<Rect> {
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
    pub(super) fn region_ink(&self, key: &str) -> Option<Rect> {
        let r = self.regions.iter().rev().find(|r| r.key == key)?;
        let ink = r.ink.with_offset(-self.layers[r.layer].offset);
        Some(intersect(ink, r.clip))
    }
}
