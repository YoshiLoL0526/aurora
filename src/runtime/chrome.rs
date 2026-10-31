//! Ventanas sin marco: zonas que mueven o redimensionan la ventana.
//!
//! El `Runtime` no tiene ventana (lo comparte el piloto): aquí solo se decide
//! qué pide una pulsación —moverla, redimensionarla desde un borde o
//! maximizarla con doble clic— y se deja en `window_request` para que la
//! ventana del sistema lo haga (`window.rs`) o el piloto lo apunte.

use super::*;
use crate::spec::{Edge, WindowDrag};

/// Grosor de la franja de cada borde que redimensiona una ventana sin marco.
const EDGE: f32 = 5.0;
/// Lado de cada esquina: cerca de ella, la franja redimensiona en diagonal.
const CORNER: f32 = 12.0;

/// Lo que una pulsación pide a la ventana.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum WindowRequest {
    /// Empezar a moverla o a redimensionarla (el sistema sigue al puntero).
    Drag(WindowDrag),
    /// Doble clic en una zona que la mueve: maximizar o restaurar.
    ToggleMaximize,
}

impl WindowRequest {
    /// Como lo ve Python en `Pilot.window_requests`: `"move"`, `"resize-se"`, `"toggle-maximize"`.
    pub fn name(self) -> String {
        match self {
            WindowRequest::Drag(WindowDrag::Move) => "move".into(),
            WindowRequest::Drag(WindowDrag::Resize(edge)) => format!("resize-{}", edge.name()),
            WindowRequest::ToggleMaximize => "toggle-maximize".into(),
        }
    }
}

impl Runtime {
    /// Borde de la ventana bajo `(x, y)`, si los bordes redimensionan
    /// (`window_edges`: ventana sin marco, redimensionable y sin maximizar).
    fn edge_at(&self, x: f32, y: f32) -> Option<Edge> {
        if !self.window_edges {
            return None;
        }
        let (w, h) = self.size;
        let (left, right) = (x < EDGE, x >= w - EDGE);
        let (top, bottom) = (y < EDGE, y >= h - EDGE);
        if !(left || right || top || bottom) {
            return None;
        }
        // Cerca de una esquina, la franja de un borde también cuenta como la del otro.
        let side = left || right;
        let end = top || bottom;
        let north = top || (y < CORNER && side);
        let south = bottom || (y >= h - CORNER && side);
        let west = left || (x < CORNER && end);
        let east = right || (x >= w - CORNER && end);
        Some(match (north, south, west, east) {
            (true, _, true, _) => Edge::NorthWest,
            (true, _, _, true) => Edge::NorthEast,
            (_, true, true, _) => Edge::SouthWest,
            (_, true, _, true) => Edge::SouthEast,
            (true, ..) => Edge::North,
            (_, true, ..) => Edge::South,
            (_, _, true, _) => Edge::West,
            _ => Edge::East,
        })
    }

    /// Qué haría con la ventana pulsar en `(x, y)`: los bordes de una ventana
    /// sin marco y, si no, la zona `window_drag` más cercana bajo el puntero.
    /// Un control (algo interactivo, enfocable o editable) o una barrera
    /// (`capture`) por encima de la zona se queda la pulsación.
    pub(super) fn window_zone(&self, x: f32, y: f32) -> Option<WindowDrag> {
        if let Some(edge) = self.edge_at(x, y) {
            return Some(WindowDrag::Resize(edge));
        }
        let regions = &self.engine.regions;
        for r in ancestors(regions, topmost(regions, x, y)) {
            if let Some(zone) = r.window_drag {
                return Some(zone);
            }
            if r.interactive || r.focusable || r.editable || r.capture {
                return None;
            }
        }
        None
    }

    /// Una pulsación en una zona de la ventana: deja pedido lo que toca y
    /// devuelve `true` (la pulsación no llega a la vista).
    pub(super) fn press_window_zone(&mut self) -> bool {
        let Some((x, y)) = self.pointer else {
            return false;
        };
        let Some(zone) = self.window_zone(x, y) else {
            return false;
        };
        let double = zone == WindowDrag::Move && self.click_count(Point::new(x, y)) == 2;
        self.window_request = Some(if double {
            WindowRequest::ToggleMaximize
        } else {
            WindowRequest::Drag(zone)
        });
        self.engine.pressed = None;
        true
    }

    /// Lo que pidió la última pulsación a la ventana (se consume al leerlo).
    pub fn take_window_request(&mut self) -> Option<WindowRequest> {
        self.window_request.take()
    }

    /// El borde que redimensiona bajo el puntero, para su cursor.
    pub(super) fn resize_hover(&self) -> Option<Edge> {
        let (x, y) = self.pointer?;
        match self.window_zone(x, y)? {
            WindowDrag::Resize(edge) => Some(edge),
            WindowDrag::Move => None,
        }
    }
}
