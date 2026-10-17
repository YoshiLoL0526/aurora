//! Fase de layout: el árbol de Taffy y su reconciliación incremental.

use super::*;

/// Layout persistente entre frames. Se reutiliza tal cual mientras no cambie
/// nada de lo que lo determina (el árbol, el tamaño de la ventana y el texto de
/// los campos); si algo cambia, se reconcilia por key en vez de rehacerse.
pub(super) struct LayoutCache {
    pub(super) tree: TaffyTree<Leaf>,
    pub(super) root: Option<LayoutNode>,
    pub(super) width: f32,
    pub(super) height: f32,
    pub(super) inputs: u64,
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

/// Árbol de layout paralelo al árbol de nodos.
pub struct LayoutNode {
    pub(super) id: NodeId,
    /// Key del nodo: identifica su nodo de Taffy al reconciliar el siguiente árbol.
    pub(super) key: String,
    pub(super) children: Vec<LayoutNode>,
    /// Hasta dónde puede pintar el subárbol (sombras, anillo de foco, texto que
    /// desborda…), en coordenadas locales de su capa. Las capas superiores que
    /// contiene no cuentan: se pintan aparte.
    pub(super) ink: Rect,
    /// Lo que pinta el propio nodo, sin sus hijos (o todo el subárbol de un nodo
    /// que se escala al pulsarlo, si está dentro de él): lo que hay que repintar
    /// si cambia de geometría o de aspecto.
    pub(super) own: Rect,
    /// El pintor no puede saltarse el subárbol aunque quede fuera de la zona a
    /// repintar: contiene capas superiores (se encolan al recorrerlo) o campos de
    /// texto (su geometría se recalcula al pintarlos).
    pub(super) sticky: bool,
}

impl Engine {
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
    pub(super) fn update_layout(
        &self,
        cache: &mut LayoutCache,
        root: &Node,
        width: f32,
        height: f32,
    ) {
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
}

fn overflow(scrolls: bool) -> Overflow {
    if scrolls {
        Overflow::Hidden
    } else {
        Overflow::Visible
    }
}

pub(super) fn taffy_style(s: &Style) -> taffy::Style {
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
