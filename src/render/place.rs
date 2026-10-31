//! Colocación de lo que flota junto a otro elemento: las capas superiores con
//! `placement` (popovers y desplegables) y la burbuja del tooltip.
//!
//! Se pide un lado y una alineación; si en ese lado no cabe y en el opuesto sí
//! (o cabe más), se vuelca, y en el otro eje se desplaza lo justo para no
//! salirse de la ventana.

use super::*;
use crate::spec::{Align, Placement, Side};

/// Margen que se deja con el borde de la ventana.
pub(super) const WINDOW_MARGIN: f32 = 8.0;

/// Esquina superior izquierda de una caja de `size` junto a `anchor`, dentro de
/// `bounds`.
pub(super) fn place(anchor: Rect, size: (f32, f32), p: Placement, bounds: Rect) -> Point {
    let (w, h) = size;
    let vertical = matches!(p.side, Side::Top | Side::Bottom);
    // Espacio libre a cada lado del ancla, en el eje principal.
    let (before, after) = if vertical {
        (anchor.top - bounds.top, bounds.bottom - anchor.bottom)
    } else {
        (anchor.left - bounds.left, bounds.right - anchor.right)
    };
    let need = if vertical { h } else { w } + p.gap;
    let wants_after = matches!(p.side, Side::Bottom | Side::Right);
    let (room, other) = if wants_after {
        (after, before)
    } else {
        (before, after)
    };
    let after_side = if room >= need || room >= other {
        wants_after
    } else {
        !wants_after
    };
    // En el eje cruzado: alineada con el ancla y sin salirse.
    let cross = |start: f32, end: f32, len: f32, lo: f32, hi: f32| {
        let at = match p.align {
            Align::Start => start,
            Align::Center => (start + end - len) / 2.0,
            Align::End => end - len,
        };
        at.min(hi - len).max(lo)
    };
    if vertical {
        let y = if after_side {
            anchor.bottom + p.gap
        } else {
            anchor.top - p.gap - h
        };
        Point::new(
            cross(anchor.left, anchor.right, w, bounds.left, bounds.right),
            y.min(bounds.bottom - h).max(bounds.top),
        )
    } else {
        let x = if after_side {
            anchor.right + p.gap
        } else {
            anchor.left - p.gap - w
        };
        Point::new(
            x.min(bounds.right - w).max(bounds.left),
            cross(anchor.top, anchor.bottom, h, bounds.top, bounds.bottom),
        )
    }
}

impl Engine {
    /// Coloca las capas superiores con `placement` junto a su ancla (el hermano
    /// anterior en el flujo o, si no hay, el contenedor) y guarda en su `LayoutNode::shift` lo que se mueven respecto a
    /// donde las dejó Taffy. Se calcula en coordenadas de la ventana, con el
    /// desplazamiento actual de los `scroll` que las contienen.
    pub(super) fn place_anchored(
        &self,
        tree: &TaffyTree<Leaf>,
        root: &Node,
        lroot: &mut LayoutNode,
        width: f32,
        height: f32,
    ) {
        if !root.has_placement {
            return;
        }
        let bounds = Rect::new(0.0, 0.0, width, height).with_inset((WINDOW_MARGIN, WINDOW_MARGIN));
        self.place_node(tree, root, lroot, Point::default(), Rect::default(), bounds);
    }

    fn place_node(
        &self,
        tree: &TaffyTree<Leaf>,
        node: &Node,
        lnode: &mut LayoutNode,
        origin: Point,
        anchor: Rect,
        bounds: Rect,
    ) {
        let layout = tree.layout(lnode.id).expect("layout");
        let mut at = Point::new(origin.x + layout.location.x, origin.y + layout.location.y);
        let size = (layout.size.width, layout.size.height);
        if node.style.overlay
            && let Some(p) = node.style.placement
        {
            let placed = place(anchor, size, p, bounds);
            lnode.shift = placed - at;
            at = placed;
        }
        let rect = Rect::from_xywh(at.x, at.y, size.0, size.1);
        let mut child_origin = at;
        if node.style.scroll.is_some()
            && let Some(state) = self.scroll.get(&node.key)
        {
            child_origin -= state.offset;
        }
        // El ancla de cada hijo con `placement` es su hermano anterior más
        // cercano que ocupa sitio en el flujo (el disparador), o este nodo.
        let mut last_in_flow = None;
        for (child, lchild) in node.children.iter().zip(&mut lnode.children) {
            if child.has_placement {
                let anchor = last_in_flow.map_or(rect, |id| {
                    let l = tree.layout(id).expect("layout");
                    Rect::from_xywh(
                        child_origin.x + l.location.x,
                        child_origin.y + l.location.y,
                        l.size.width,
                        l.size.height,
                    )
                });
                self.place_node(tree, child, lchild, child_origin, anchor, bounds);
            }
            if !child.style.absolute && !child.style.overlay {
                last_in_flow = Some(lchild.id);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn p(side: Side, align: Align) -> Placement {
        Placement {
            side,
            align,
            gap: 4.0,
        }
    }

    const BOUNDS: Rect = Rect {
        left: 0.0,
        top: 0.0,
        right: 400.0,
        bottom: 300.0,
    };

    #[test]
    fn debajo_y_alineado_al_inicio() {
        let anchor = Rect::from_xywh(50.0, 20.0, 100.0, 30.0);
        let at = place(anchor, (120.0, 80.0), p(Side::Bottom, Align::Start), BOUNDS);
        assert_eq!(at, Point::new(50.0, 54.0));
    }

    #[test]
    fn se_vuelca_si_no_cabe() {
        let anchor = Rect::from_xywh(50.0, 250.0, 100.0, 30.0);
        let at = place(anchor, (120.0, 80.0), p(Side::Bottom, Align::Start), BOUNDS);
        assert_eq!(at, Point::new(50.0, 166.0));
    }

    #[test]
    fn no_se_sale_por_los_lados() {
        let anchor = Rect::from_xywh(350.0, 20.0, 40.0, 30.0);
        let at = place(
            anchor,
            (120.0, 80.0),
            p(Side::Bottom, Align::Center),
            BOUNDS,
        );
        assert_eq!(at.x, 280.0);
        let at = place(anchor, (120.0, 80.0), p(Side::Right, Align::Start), BOUNDS);
        // A la derecha no cabe: se vuelca a la izquierda.
        assert_eq!(at, Point::new(226.0, 20.0));
    }
}
