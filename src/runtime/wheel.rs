//! Rueda, zoom de gráficos y barras de desplazamiento.

use super::*;

/// Factor de zoom por paso de rueda (`scroll::LINE` píxeles): 1,25×.
const ZOOM_RATE: f64 = 1.25;

impl Runtime {
    /// Rueda o trackpad sobre el puntero: sobre un `chart` con zoom, la rueda
    /// vertical acerca (el puntero es el ancla) y la horizontal desplaza la
    /// ventana; si ya está en el tope, la rueda pasa al `scroll` de fuera. Sin
    /// un gráfico debajo, desplaza el `scroll` más interno que aún pueda moverse
    /// en esa dirección (al llegar al límite, pasa al de fuera).
    /// `delta` en píxeles, positivo hacia el final del contenido. `smooth` anima
    /// el recorrido (rueda por pasos); sin él se aplica tal cual (trackpad).
    pub fn wheel(&mut self, delta: Point, smooth: bool) -> bool {
        if (delta.y != 0.0 || delta.x != 0.0)
            && let Some((key, t)) = self.zoom_at()
        {
            let factor = ZOOM_RATE.powf(f64::from(delta.y) / f64::from(LINE));
            let zoomed = delta.y != 0.0 && self.charts.zoom(&key, t, factor);
            let panned = delta.x != 0.0 && self.charts.pan(&key, -delta.x);
            if zoomed || panned {
                return true;
            }
        }
        let Some((x, y)) = self.pointer else {
            return false;
        };
        let idx = topmost(&self.engine.regions, x, y);
        let keys: Vec<String> = ancestors(&self.engine.regions, idx)
            .filter(|r| r.scroll.is_some())
            .map(|r| r.key.clone())
            .collect();
        keys.iter().any(|key| {
            self.engine
                .scroll
                .get_mut(key)
                .is_some_and(|state| state.scroll_by(delta, smooth))
        })
    }

    /// Ventana visible del eje x del `chart` con esa key (en unidades de datos).
    /// La usan el piloto y las pruebas; sin zoom es el dominio completo.
    pub fn chart_view(&self, key: &str) -> Option<(f64, f64)> {
        self.charts.view(key)
    }

    /// Un `chart` con zoom bajo el puntero, con la fracción del eje x (0..1)
    /// que hay en él. `None` si no hay ninguno.
    pub(super) fn zoom_at(&self) -> Option<(String, f32)> {
        let (px, py) = self.pointer?;
        let idx = topmost(&self.engine.regions, px, py)?;
        let region = ancestors(&self.engine.regions, Some(idx)).find(|r| self.zoomable(&r.key))?;
        let node = self.tree.as_ref()?.find(&region.key)?;
        let plot = self.charts.plot(&region.key)?;
        if plot.width() <= 0.0 {
            return None;
        }
        let (padding, border) = (node.style.padding, node.style.border_width);
        let left = region.rect.left + border + padding.left + plot.left;
        let t = ((px - left) / plot.width()).clamp(0.0, 1.0);
        Some((region.key.clone(), t))
    }

    /// Si el nodo `key` es un gráfico con zoom.
    fn zoomable(&self, key: &str) -> bool {
        self.tree
            .as_ref()
            .and_then(|tree| tree.find(key))
            .and_then(|node| node.chart.as_ref())
            .is_some_and(|chart| chart.zoom)
    }

    /// Desplazamiento actual del `scroll` con esa key.
    pub fn scroll_offset(&self, key: &str) -> Option<Point> {
        self.engine.scroll.get(key).map(|s| s.offset)
    }

    /// Barra (key del `scroll`, si es vertical) cuya franja está bajo el puntero.
    fn scrollbar_at(&self) -> Option<(String, bool)> {
        let (x, y) = self.pointer?;
        let inside = |r: Rect| x >= r.left && x < r.right && y >= r.top && y < r.bottom;
        ancestors(&self.engine.regions, topmost(&self.engine.regions, x, y))
            .filter(|r| r.scroll.is_some())
            .find_map(|r| {
                let state = self.engine.scroll.get(&r.key)?;
                [true, false]
                    .into_iter()
                    .find(|&v| state.track(v).is_some_and(inside))
                    .map(|v| (r.key.clone(), v))
            })
    }

    /// Muestra la barra bajo el puntero. Devuelve `true` si cambió algo visible.
    pub(super) fn hover_scrollbar(&mut self) -> bool {
        let target = self.scrollbar_at().map(|(key, _)| key);
        let mut changed = false;
        for (key, state) in self.engine.scroll.iter_mut() {
            let hovered = target.as_deref() == Some(key.as_str());
            if hovered != state.hovered || (hovered && state.bar < 1.0) {
                changed = true;
            }
            state.hovered = hovered;
            if hovered {
                state.poke();
            }
        }
        changed
    }

    /// Empieza a arrastrar una barra si se pulsa sobre su franja. Pulsar fuera
    /// del pulgar lo centra bajo el puntero.
    pub(super) fn start_drag(&mut self) -> bool {
        let (Some((key, vertical)), Some((x, y))) = (self.scrollbar_at(), self.pointer) else {
            return false;
        };
        let Some(state) = self.engine.scroll.get_mut(&key) else {
            return false;
        };
        let Some(thumb) = state.thumb(vertical) else {
            return false;
        };
        let (pos, start, len) = if vertical {
            (y, thumb.top, thumb.height())
        } else {
            (x, thumb.left, thumb.width())
        };
        let grab = if (start..start + len).contains(&pos) {
            pos - start
        } else {
            len / 2.0
        };
        state.dragging = true;
        state.drag_thumb_to(vertical, pos - grab);
        self.drag = Some(Drag {
            key,
            vertical,
            grab,
        });
        true
    }
}
