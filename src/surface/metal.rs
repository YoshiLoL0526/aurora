//! Superficie por GPU con Metal (macOS), vía Skia Ganesh y una `CAMetalLayer`.
//!
//! Cada frame se pinta en el `Backbuffer` y se copia al drawable de la capa,
//! que se presenta en la misma cola de Metal que usa Skia.

use std::sync::Arc;

use objc2::rc::{Retained, autoreleasepool};
use objc2::runtime::ProtocolObject;
use objc2_app_kit::NSView;
use objc2_core_foundation::CGSize;
use objc2_metal::{
    MTLCommandBuffer, MTLCommandQueue, MTLCreateSystemDefaultDevice, MTLDevice, MTLDrawable,
    MTLPixelFormat,
};
use objc2_quartz_core::{CAMetalDrawable, CAMetalLayer};
use skia_safe::ColorType;
use skia_safe::gpu::{self, DirectContext, SurfaceOrigin, backend_render_targets, mtl};
use winit::raw_window_handle::{HasWindowHandle, RawWindowHandle};
use winit::window::Window;

use super::{Backbuffer, Paint, Surface, physical_size};

pub struct MetalSurface {
    // Orden de destrucción: el lienzo y el contexto de Skia antes que la cola.
    backbuffer: Backbuffer,
    context: DirectContext,
    queue: Retained<ProtocolObject<dyn MTLCommandQueue>>,
    layer: Retained<CAMetalLayer>,
}

impl MetalSurface {
    pub fn new(window: &Arc<Window>) -> Result<Self, String> {
        let device = MTLCreateSystemDefaultDevice().ok_or("no hay ningún dispositivo Metal")?;
        let queue = device
            .newCommandQueue()
            .ok_or("no se pudo crear la cola de Metal")?;

        let layer = CAMetalLayer::new();
        layer.setDevice(Some(&device));
        layer.setPixelFormat(MTLPixelFormat::BGRA8Unorm);
        layer.setPresentsWithTransaction(false);
        // Permite que Skia lea y copie el drawable, no solo pintar en él.
        layer.setFramebufferOnly(false);
        layer.setContentsScale(window.scale_factor());

        let handle = window.window_handle().map_err(|e| e.to_string())?;
        let RawWindowHandle::AppKit(appkit) = handle.as_raw() else {
            return Err("la ventana no es de AppKit".into());
        };
        // SAFETY: winit garantiza que la vista vive mientras viva la ventana, y
        // `resumed` (donde se crea la superficie) corre en el hilo principal.
        let view = unsafe { &*(appkit.ns_view.as_ptr() as *const NSView) };
        view.setWantsLayer(true);
        view.setLayer(Some(&layer.clone().into_super()));

        let backend = unsafe {
            mtl::BackendContext::new(
                Retained::as_ptr(&device) as mtl::Handle,
                Retained::as_ptr(&queue) as mtl::Handle,
            )
        };
        let context = gpu::direct_contexts::make_metal(&backend, None)
            .ok_or("Skia no pudo usar el dispositivo Metal")?;
        Ok(Self {
            backbuffer: Backbuffer::default(),
            context,
            queue,
            layer,
        })
    }
}

impl Surface for MetalSurface {
    fn name(&self) -> &'static str {
        "metal"
    }

    fn present(&mut self, window: &Window, paint: Paint) -> Result<(), String> {
        let Some((w, h)) = physical_size(window) else {
            return Ok(());
        };
        let size = (w.get() as i32, h.get() as i32);
        // Los objetos de Metal de cada frame se liberan al acabar el frame.
        autoreleasepool(|_| {
            let drawable_size = CGSize::new(w.get() as f64, h.get() as f64);
            let current = self.layer.drawableSize();
            if current.width != drawable_size.width || current.height != drawable_size.height {
                self.layer.setDrawableSize(drawable_size);
            }
            self.layer.setContentsScale(window.scale_factor());
            let Some(drawable) = self.layer.nextDrawable() else {
                // No quedan drawables libres (la ventana está oculta): otro intento luego.
                window.request_redraw();
                return Ok(());
            };

            let source = self.backbuffer.paint(&mut self.context, size, paint)?;
            let texture = drawable.texture();
            let info = unsafe { mtl::TextureInfo::new(Retained::as_ptr(&texture) as mtl::Handle) };
            let target = backend_render_targets::make_mtl(size, &info);
            let mut target = gpu::surfaces::wrap_backend_render_target(
                &mut self.context,
                &target,
                SurfaceOrigin::TopLeft,
                ColorType::BGRA8888,
                None,
                None,
            )
            .ok_or("Skia no pudo pintar en el drawable de Metal")?;
            Backbuffer::blit(source, target.canvas());
            self.context.flush_and_submit();
            drop(target);

            // Misma cola que Skia: el drawable se presenta después de pintarlo.
            let commands = self
                .queue
                .commandBuffer()
                .ok_or("no se pudo crear un command buffer de Metal")?;
            let drawable: Retained<ProtocolObject<dyn MTLDrawable>> = (&drawable).into();
            commands.presentDrawable(&drawable);
            commands.commit();
            Ok(())
        })
    }
}
