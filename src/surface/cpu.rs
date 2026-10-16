//! Superficie por CPU: Skia raster directo en el framebuffer de softbuffer.

use std::num::NonZeroU32;
use std::sync::Arc;

use skia_safe::{ImageInfo, Rect, surfaces};
use winit::window::Window;

use super::{Paint, Surface, physical_size};

pub struct CpuSurface {
    surface: softbuffer::Surface<Arc<Window>, Arc<Window>>,
}

impl CpuSurface {
    pub fn new(window: &Arc<Window>) -> Result<Self, String> {
        let context = softbuffer::Context::new(window.clone()).map_err(|e| e.to_string())?;
        let surface =
            softbuffer::Surface::new(&context, window.clone()).map_err(|e| e.to_string())?;
        Ok(Self { surface })
    }
}

impl Surface for CpuSurface {
    fn name(&self) -> &'static str {
        "cpu"
    }

    fn present(&mut self, window: &Window, paint: Paint) -> Result<(), String> {
        let Some((w, h)) = physical_size(window) else {
            return Ok(());
        };
        self.surface.resize(w, h).map_err(|e| e.to_string())?;
        let mut buffer = self.surface.buffer_mut().map_err(|e| e.to_string())?;

        // softbuffer usa píxeles 0x00RRGGBB (u32 nativo); en little-endian coincide
        // byte a byte con el formato N32 (BGRA) de Skia, así que pintamos directo.
        let bytes = unsafe {
            std::slice::from_raw_parts_mut(buffer.as_mut_ptr() as *mut u8, buffer.len() * 4)
        };
        let info = ImageInfo::new_n32_premul((w.get() as i32, h.get() as i32), None);
        // El buffer puede conservar un frame anterior (según la plataforma): solo
        // se repinta y se presenta lo que cambió desde entonces.
        let age = buffer.age();
        let damage = surfaces::wrap_pixels(&info, bytes, w.get() as usize * 4, None)
            .and_then(|mut sk| paint(sk.canvas(), age));
        // Sin daño se presenta igualmente (todo el buffer): el sistema pudo pedir
        // el frame porque la ventana se descubrió.
        let scale = window.scale_factor() as f32;
        match damage.and_then(|d| physical_rect(d, scale, w, h)) {
            Some(rect) => buffer.present_with_damage(&[rect]),
            None => buffer.present(),
        }
        .map_err(|e| e.to_string())
    }
}

/// Zona pintada (píxeles lógicos) en píxeles físicos del buffer.
fn physical_rect(r: Rect, scale: f32, w: NonZeroU32, h: NonZeroU32) -> Option<softbuffer::Rect> {
    let (bw, bh) = (w.get() as f32, h.get() as f32);
    let left = (r.left * scale).floor().clamp(0.0, bw);
    let top = (r.top * scale).floor().clamp(0.0, bh);
    let right = (r.right * scale).ceil().clamp(0.0, bw);
    let bottom = (r.bottom * scale).ceil().clamp(0.0, bh);
    Some(softbuffer::Rect {
        x: left as u32,
        y: top as u32,
        width: NonZeroU32::new((right - left) as u32)?,
        height: NonZeroU32::new((bottom - top) as u32)?,
    })
}
