//! Superficies de la ventana: dónde pinta Skia cada frame y cómo se presenta.
//!
//! El bucle de ventana solo conoce el trait `Surface`. Hay una superficie por
//! CPU (softbuffer, la más portable) y una por GPU: Vulkan fuera de macOS y
//! Metal en macOS. La de GPU pinta en un lienzo propio que conserva el frame
//! anterior, de modo que el repintado parcial funciona igual en ambas.

use std::num::NonZeroU32;
use std::sync::Arc;

use skia_safe::gpu::{self, DirectContext};
use skia_safe::{Canvas, ImageInfo, Rect};
use winit::event_loop::ActiveEventLoop;
use winit::window::Window;

mod cpu;
#[cfg(target_os = "macos")]
mod metal;
#[cfg(not(target_os = "macos"))]
mod vulkan;

/// Pinta un frame. Recibe el lienzo (del tamaño físico de la ventana) y su
/// edad: hace cuántos frames se pintó lo que contiene (1 si es el último, 0 si
/// no se sabe). Devuelve la zona pintada en píxeles lógicos, o `None` si nada.
pub type Paint<'a> = &'a mut dyn FnMut(&Canvas, u8) -> Option<Rect>;

pub trait Surface {
    /// Nombre del backend (`"cpu"`, `"vulkan"`, `"metal"`).
    fn name(&self) -> &'static str;

    /// Pinta y presenta un frame del tamaño actual de la ventana. Con área cero
    /// no pinta nada. Un error significa que la superficie ya no sirve.
    fn present(&mut self, window: &Window, paint: Paint) -> Result<(), String>;
}

/// Backend de render pedido por la app.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Backend {
    /// GPU si se puede iniciar; si no, CPU.
    Auto,
    /// GPU o error.
    Gpu,
    Cpu,
}

impl Backend {
    /// Variable de entorno que elige el backend cuando la app pide `auto`.
    pub const ENV: &'static str = "AURORA_BACKEND";

    pub fn parse(name: &str) -> Option<Self> {
        match name.trim().to_ascii_lowercase().as_str() {
            "auto" | "" => Some(Self::Auto),
            "gpu" => Some(Self::Gpu),
            "cpu" => Some(Self::Cpu),
            _ => None,
        }
    }

    /// El backend pedido; con `auto` decide `AURORA_BACKEND` si está definida.
    pub fn resolve(name: &str) -> Result<Self, String> {
        let invalid = |source: &str, value: &str| {
            format!("{source} debe ser 'auto', 'gpu' o 'cpu', no {value:?}")
        };
        match Self::parse(name).ok_or_else(|| invalid("backend", name))? {
            Self::Auto => match std::env::var(Self::ENV) {
                Ok(value) => Self::parse(&value).ok_or_else(|| invalid(Self::ENV, &value)),
                Err(_) => Ok(Self::Auto),
            },
            backend => Ok(backend),
        }
    }
}

/// Crea la superficie de la ventana con el backend pedido.
pub fn create(
    event_loop: &ActiveEventLoop,
    window: &Arc<Window>,
    backend: Backend,
) -> Result<Box<dyn Surface>, String> {
    match backend {
        Backend::Cpu => cpu(window),
        Backend::Gpu => {
            gpu(event_loop, window).map_err(|e| format!("no se pudo iniciar la GPU: {e}"))
        }
        Backend::Auto => gpu(event_loop, window).or_else(|_| cpu(window)),
    }
}

pub fn cpu(window: &Arc<Window>) -> Result<Box<dyn Surface>, String> {
    Ok(Box::new(cpu::CpuSurface::new(window)?))
}

#[cfg(not(target_os = "macos"))]
fn gpu(event_loop: &ActiveEventLoop, window: &Arc<Window>) -> Result<Box<dyn Surface>, String> {
    Ok(Box::new(vulkan::VulkanSurface::new(event_loop, window)?))
}

#[cfg(target_os = "macos")]
fn gpu(_event_loop: &ActiveEventLoop, window: &Arc<Window>) -> Result<Box<dyn Surface>, String> {
    Ok(Box::new(metal::MetalSurface::new(window)?))
}

/// Tamaño físico de la ventana, o `None` si no tiene área (minimizada).
fn physical_size(window: &Window) -> Option<(NonZeroU32, NonZeroU32)> {
    let size = window.inner_size();
    Some((NonZeroU32::new(size.width)?, NonZeroU32::new(size.height)?))
}

/// Lienzo persistente en la GPU. Las imágenes que se presentan (swapchain,
/// drawables de Metal) no conservan el frame anterior, así que se pinta aquí,
/// solo lo que cambió, y luego se copia entero a la imagen: una copia de
/// textura es casi gratis en la GPU y el repintado parcial se conserva.
#[derive(Default)]
struct Backbuffer {
    surface: Option<skia_safe::Surface>,
}

impl Backbuffer {
    /// Pinta el frame en el lienzo (recreándolo si cambió el tamaño) y lo
    /// devuelve para copiarlo a la imagen que se presenta.
    fn paint(
        &mut self,
        context: &mut DirectContext,
        size: (i32, i32),
        paint: Paint,
    ) -> Result<&mut skia_safe::Surface, String> {
        let reuse = matches!(&self.surface, Some(s) if (s.width(), s.height()) == size);
        if !reuse {
            self.surface = None;
            let info = ImageInfo::new_n32_premul(size, None);
            let surface = gpu::surfaces::render_target(
                context,
                gpu::Budgeted::Yes,
                &info,
                None,
                gpu::SurfaceOrigin::TopLeft,
                None,
                false,
                None,
            );
            self.surface = Some(surface.ok_or("no se pudo crear el lienzo en la GPU")?);
        }
        let Some(surface) = self.surface.as_mut() else {
            return Err("no hay lienzo en la GPU".into());
        };
        paint(surface.canvas(), if reuse { 1 } else { 0 });
        Ok(surface)
    }

    /// Copia el lienzo entero a `target`, que tiene su mismo tamaño.
    fn blit(surface: &mut skia_safe::Surface, target: &Canvas) {
        let paint = skia_safe::Paint::default()
            .set_blend_mode(skia_safe::BlendMode::Src)
            .clone();
        surface.draw(
            target,
            (0, 0),
            skia_safe::SamplingOptions::default(),
            Some(&paint),
        );
    }
}

#[cfg(test)]
mod tests {
    use super::Backend;

    #[test]
    fn backend_names() {
        assert_eq!(Backend::parse("GPU"), Some(Backend::Gpu));
        assert_eq!(Backend::parse(" cpu "), Some(Backend::Cpu));
        assert_eq!(Backend::parse("auto"), Some(Backend::Auto));
        assert_eq!(Backend::parse("d3d"), None);
        assert!(Backend::resolve("opengl").is_err());
        assert_eq!(Backend::resolve("cpu"), Ok(Backend::Cpu));
    }
}
