//! Estado de los contenedores `scroll`: desplazamiento, suavizado de la rueda
//! y geometría de la barra. Vive en el `Engine` indexado por la key del nodo,
//! así sobrevive a las reconstrucciones completas de la vista.

use pyo3::prelude::*;
use skia_safe::{Point, Rect};

use crate::spec::Axis;

/// Píxeles por "línea" de rueda (un paso de rueda de ratón suele ser 1 línea).
pub const LINE: f32 = 48.0;
/// Constante de tiempo del desplazamiento suave de la rueda (segundos).
const SMOOTH_TAU: f32 = 0.06;
/// Tiempo que la barra sigue visible tras la última actividad (segundos).
const BAR_HOLD: f32 = 0.8;
/// Constante de tiempo de la aparición/desaparición de la barra.
const BAR_TAU: f32 = 0.08;

pub const BAR_WIDTH: f32 = 6.0;
pub const BAR_INSET: f32 = 2.0;
/// Ancho de la franja sensible junto al borde: al pasar por ella aparece la barra.
const BAR_HIT: f32 = 12.0;
const MIN_THUMB: f32 = 24.0;

/// Lo que recibe un manejador `on_scroll`: desplazamiento actual y tamaño de
/// la zona visible, en píxeles lógicos.
#[pyclass(frozen, get_all, module = "aurora._core", name = "ScrollEvent")]
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ScrollEvent {
    pub x: f32,
    pub y: f32,
    pub width: f32,
    pub height: f32,
}

#[pymethods]
impl ScrollEvent {
    fn __repr__(&self) -> String {
        format!(
            "ScrollEvent(x={}, y={}, width={}, height={})",
            self.x, self.y, self.width, self.height
        )
    }
}

impl ScrollState {
    pub fn event(&self) -> ScrollEvent {
        ScrollEvent {
            x: self.offset.x,
            y: self.offset.y,
            width: self.viewport.width(),
            height: self.viewport.height(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct ScrollState {
    /// Desplazamiento pintado.
    pub offset: Point,
    /// Destino del desplazamiento suave (igual a `offset` si no hay animación).
    target: Point,
    /// Desplazamiento máximo en cada eje (0 si el contenido cabe).
    pub max: Point,
    /// Caja de relleno del contenedor en coordenadas absolutas (último frame).
    pub viewport: Rect,
    pub axis: Axis,
    /// Segundos desde la última actividad (para ocultar la barra).
    idle: f32,
    /// Visibilidad de la barra, de 0 a 1.
    pub bar: f32,
    pub dragging: bool,
    /// El puntero está sobre la franja de la barra: se mantiene visible.
    pub hovered: bool,
}

impl Default for ScrollState {
    fn default() -> Self {
        Self {
            offset: Point::default(),
            target: Point::default(),
            max: Point::default(),
            viewport: Rect::default(),
            axis: Axis::Y,
            idle: BAR_HOLD,
            bar: 0.0,
            dragging: false,
            hovered: false,
        }
    }
}

impl ScrollState {
    /// Actualiza los límites tras el layout y reajusta el desplazamiento si el
    /// contenido se ha encogido.
    pub fn set_limits(&mut self, axis: Axis, max: Point, viewport: Rect) {
        self.axis = axis;
        self.max = Point::new(
            if axis.x() { max.x.max(0.0) } else { 0.0 },
            if axis.y() { max.y.max(0.0) } else { 0.0 },
        );
        self.viewport = viewport;
        self.target = self.clamp(self.target);
        self.offset = self.clamp(self.offset);
    }

    fn clamp(&self, p: Point) -> Point {
        Point::new(p.x.clamp(0.0, self.max.x), p.y.clamp(0.0, self.max.y))
    }

    /// Desplaza `delta` píxeles (positivo = hacia el final del contenido).
    /// Devuelve `false` si el contenedor ya está en el límite en esa dirección,
    /// para que el desplazamiento pase al contenedor de fuera.
    pub fn scroll_by(&mut self, delta: Point, smooth: bool) -> bool {
        let mut delta = delta;
        // Una rueda vertical también sirve para listas solo horizontales.
        if self.axis == Axis::X && delta.x == 0.0 {
            delta = Point::new(delta.y, 0.0);
        }
        let before = self.target;
        self.target = self.clamp(before + delta);
        if self.target == before {
            return false;
        }
        if !smooth {
            self.offset = self.target;
        }
        self.poke();
        true
    }

    /// Desplaza (con suavizado) lo justo para que `rect`, en coordenadas del
    /// último frame, quede dentro de la zona visible con `margin` de holgura.
    /// Si no cabe, se alinea su inicio. Devuelve el desplazamiento aplicado.
    pub fn reveal(&mut self, rect: Rect, margin: f32) -> Point {
        let v = self.viewport;
        let fit = |start: f32, end: f32, vstart: f32, vend: f32| {
            if start - margin < vstart {
                start - margin - vstart
            } else if end + margin > vend {
                (end + margin - vend).min(start - margin - vstart)
            } else {
                0.0
            }
        };
        let wanted = Point::new(
            fit(rect.left, rect.right, v.left, v.right),
            fit(rect.top, rect.bottom, v.top, v.bottom),
        );
        // `rect` se pintó con `offset`: el nuevo destino se calcula desde ahí.
        let target = self.clamp(self.offset + wanted);
        let applied = target - self.offset;
        if target != self.target {
            self.target = target;
            self.poke();
        }
        applied
    }

    /// Como `reveal`, para una franja vertical del contenido medida desde su inicio.
    pub fn reveal_content(&mut self, top: f32, bottom: f32, margin: f32) -> Point {
        let y = self.viewport.top - self.offset.y;
        let rect = Rect::new(self.viewport.left, y + top, self.viewport.right, y + bottom);
        self.reveal(rect, margin)
    }

    /// Marca actividad: la barra se muestra un rato.
    pub fn poke(&mut self) {
        self.idle = 0.0;
    }

    /// Avanza la animación. Devuelve `true` si sigue en curso.
    pub fn tick(&mut self, dt: f32) -> bool {
        let mut animating = false;
        if self.offset != self.target {
            let k = 1.0 - (-dt / SMOOTH_TAU).exp();
            self.offset += (self.target - self.offset) * k;
            if (self.target - self.offset).length() < 0.5 {
                self.offset = self.target;
            } else {
                animating = true;
            }
        }
        self.idle += dt;
        let held = self.dragging || self.hovered;
        let shown = held || self.idle < BAR_HOLD;
        let goal = if shown && (self.max.x > 0.0 || self.max.y > 0.0) {
            1.0
        } else {
            0.0
        };
        let k = 1.0 - (-dt / BAR_TAU).exp();
        self.bar += (goal - self.bar) * k;
        if (goal - self.bar).abs() < 0.01 {
            self.bar = goal;
        } else {
            animating = true;
        }
        // Mientras la barra espera para ocultarse hacen falta frames que cuenten el
        // tiempo; si se mantiene visible (arrastre, hover) no.
        animating || (self.bar > 0.0 && !held)
    }

    /// Franja sensible de la barra de un eje (vertical = derecha, horizontal = abajo).
    pub fn track(&self, vertical: bool) -> Option<Rect> {
        let v = self.viewport;
        if vertical && self.max.y > 0.0 {
            Some(Rect::new(v.right - BAR_HIT, v.top, v.right, v.bottom))
        } else if !vertical && self.max.x > 0.0 {
            Some(Rect::new(v.left, v.bottom - BAR_HIT, v.right, v.bottom))
        } else {
            None
        }
    }

    /// Rectángulo del "pulgar" de la barra de un eje, en coordenadas absolutas.
    pub fn thumb(&self, vertical: bool) -> Option<Rect> {
        let (len, pos) = self.thumb_metrics(vertical)?;
        let v = self.viewport;
        Some(if vertical {
            let x = v.right - BAR_INSET - BAR_WIDTH;
            Rect::from_xywh(x, v.top + BAR_INSET + pos, BAR_WIDTH, len)
        } else {
            let y = v.bottom - BAR_INSET - BAR_WIDTH;
            Rect::from_xywh(v.left + BAR_INSET + pos, y, len, BAR_WIDTH)
        })
    }

    /// Longitud del pulgar y su posición dentro del carril.
    fn thumb_metrics(&self, vertical: bool) -> Option<(f32, f32)> {
        let (view, max, off) = if vertical {
            (self.viewport.height(), self.max.y, self.offset.y)
        } else {
            (self.viewport.width(), self.max.x, self.offset.x)
        };
        if max <= 0.0 {
            return None;
        }
        let rail = (view - 2.0 * BAR_INSET).max(0.0);
        let len = (rail * view / (view + max)).clamp(MIN_THUMB.min(rail), rail);
        Some((len, (rail - len) * off / max))
    }

    /// Coloca el desplazamiento para que el pulgar empiece en `pos` (coordenada
    /// absoluta del eje) al arrastrarlo.
    pub fn drag_thumb_to(&mut self, vertical: bool, pos: f32) {
        let Some((len, _)) = self.thumb_metrics(vertical) else {
            return;
        };
        let (start, view, max) = if vertical {
            (self.viewport.top, self.viewport.height(), self.max.y)
        } else {
            (self.viewport.left, self.viewport.width(), self.max.x)
        };
        let rail = (view - 2.0 * BAR_INSET - len).max(1.0);
        let off = ((pos - start - BAR_INSET) / rail * max).clamp(0.0, max);
        if vertical {
            self.offset.y = off;
        } else {
            self.offset.x = off;
        }
        self.target = self.offset;
        self.poke();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(max_y: f32) -> ScrollState {
        let mut s = ScrollState::default();
        s.set_limits(Axis::Y, Point::new(0.0, max_y), Rect::from_wh(100.0, 200.0));
        s
    }

    #[test]
    fn scroll_is_clamped_and_reports_limits() {
        let mut s = state(300.0);
        assert!(s.scroll_by(Point::new(0.0, 1000.0), false));
        assert_eq!(s.offset.y, 300.0);
        assert!(!s.scroll_by(Point::new(0.0, 10.0), false));
        assert!(s.scroll_by(Point::new(0.0, -10.0), false));
    }

    #[test]
    fn shrinking_content_clamps_offset() {
        let mut s = state(300.0);
        s.scroll_by(Point::new(0.0, 300.0), false);
        s.set_limits(Axis::Y, Point::new(0.0, 50.0), Rect::from_wh(100.0, 200.0));
        assert_eq!(s.offset.y, 50.0);
    }

    #[test]
    fn smooth_scroll_converges() {
        let mut s = state(300.0);
        s.scroll_by(Point::new(0.0, 100.0), true);
        assert_eq!(s.offset.y, 0.0);
        for _ in 0..120 {
            s.tick(1.0 / 60.0);
        }
        assert_eq!(s.offset.y, 100.0);
    }

    #[test]
    fn dragging_thumb_to_end_reaches_max() {
        let mut s = state(300.0);
        s.drag_thumb_to(true, 10_000.0);
        assert_eq!(s.offset.y, 300.0);
        let thumb = s.thumb(true).unwrap();
        assert!((thumb.bottom - (200.0 - BAR_INSET)).abs() < 0.01);
    }
}
