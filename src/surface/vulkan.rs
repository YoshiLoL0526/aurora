//! Superficie por GPU con Vulkan (Windows y Linux), vía vulkano y Skia Ganesh.
//!
//! La biblioteca de Vulkan se carga en tiempo de ejecución: si no hay driver,
//! `new` falla y la ventana usa la CPU. Cada frame se pinta en el `Backbuffer`
//! y se copia a la imagen de la swapchain, que se presenta con vsync (FIFO).

use std::ptr;
use std::sync::Arc;

use ash::vk::Handle;
use skia_safe::ColorType;
use skia_safe::gpu::{self, DirectContext, backend_render_targets, direct_contexts, vk};
use vulkano::device::physical::{PhysicalDevice, PhysicalDeviceType};
use vulkano::device::{
    Device, DeviceCreateInfo, DeviceExtensions, Queue, QueueCreateInfo, QueueFlags,
};
use vulkano::format::Format;
use vulkano::image::{Image, ImageUsage};
use vulkano::instance::{Instance, InstanceCreateInfo};
use vulkano::swapchain::{
    CompositeAlpha, PresentMode, Swapchain, SwapchainCreateInfo, SwapchainPresentInfo,
    acquire_next_image,
};
use vulkano::sync::{self, GpuFuture};
use vulkano::{Validated, VulkanError, VulkanLibrary, VulkanObject};
use winit::event_loop::ActiveEventLoop;
use winit::window::Window;

use super::{Backbuffer, Paint, Surface, physical_size};

pub struct VulkanSurface {
    // Orden de destrucción: el lienzo y el contexto de Skia antes que los
    // objetos de Vulkan con los que trabajan.
    backbuffer: Backbuffer,
    context: DirectContext,
    /// Último frame enviado: retiene sus recursos hasta que la GPU termina.
    last_frame: Option<Box<dyn GpuFuture>>,
    images: Vec<Arc<Image>>,
    swapchain: Arc<Swapchain>,
    /// La swapchain dejó de corresponder a la ventana y hay que recrearla.
    stale: bool,
    queue: Arc<Queue>,
}

impl VulkanSurface {
    pub fn new(event_loop: &ActiveEventLoop, window: &Arc<Window>) -> Result<Self, String> {
        let library = VulkanLibrary::new().map_err(|e| e.to_string())?;
        let required = vulkano::swapchain::Surface::required_extensions(event_loop)
            .map_err(|e| e.to_string())?;
        let instance = Instance::new(
            library.clone(),
            InstanceCreateInfo {
                enabled_extensions: required,
                ..Default::default()
            },
        )
        .map_err(|e| e.to_string())?;
        let surface = vulkano::swapchain::Surface::from_window(instance.clone(), window.clone())
            .map_err(|e| e.to_string())?;

        let extensions = DeviceExtensions {
            khr_swapchain: true,
            ..DeviceExtensions::empty()
        };
        let (physical, family) = instance
            .enumerate_physical_devices()
            .map_err(|e| e.to_string())?
            .filter(|p| p.supported_extensions().contains(&extensions))
            .filter_map(|p| {
                let family =
                    p.queue_family_properties()
                        .iter()
                        .enumerate()
                        .position(|(i, q)| {
                            q.queue_flags.intersects(QueueFlags::GRAPHICS)
                                && p.surface_support(i as u32, &surface).unwrap_or(false)
                        })?;
                Some((p, family as u32))
            })
            .min_by_key(|(p, _)| device_rank(p))
            .ok_or("ninguna GPU con Vulkan puede pintar en la ventana")?;
        // Un dispositivo por software (llvmpipe, SwiftShader) es más lento que Skia raster.
        if physical.properties().device_type == PhysicalDeviceType::Cpu {
            return Err("la única implementación de Vulkan es por software".into());
        }

        let (device, mut queues) = Device::new(
            physical.clone(),
            DeviceCreateInfo {
                enabled_extensions: extensions,
                queue_create_infos: vec![QueueCreateInfo {
                    queue_family_index: family,
                    ..Default::default()
                }],
                ..Default::default()
            },
        )
        .map_err(|e| e.to_string())?;
        let queue = queues.next().ok_or("el dispositivo no creó ninguna cola")?;

        let caps = physical
            .surface_capabilities(&surface, Default::default())
            .map_err(|e| e.to_string())?;
        let format = physical
            .surface_formats(&surface, Default::default())
            .map_err(|e| e.to_string())?
            .into_iter()
            .map(|(format, _)| format)
            .find(|f| skia_format(*f).is_some())
            .ok_or("la ventana no admite un formato de 8 bits BGRA ni RGBA")?;
        let composite_alpha = if caps
            .supported_composite_alpha
            .contains_enum(CompositeAlpha::Opaque)
        {
            CompositeAlpha::Opaque
        } else {
            caps.supported_composite_alpha
                .into_iter()
                .next()
                .ok_or("la ventana no admite ningún modo de transparencia")?
        };
        // Las copias de textura son más rápidas que un dibujo si la imagen las admite.
        let transfer =
            caps.supported_usage_flags & (ImageUsage::TRANSFER_SRC | ImageUsage::TRANSFER_DST);
        let size = window.inner_size();
        let (swapchain, images) = Swapchain::new(
            device.clone(),
            surface,
            SwapchainCreateInfo {
                min_image_count: caps.min_image_count.max(2),
                image_format: format,
                image_extent: [size.width.max(1), size.height.max(1)],
                image_usage: ImageUsage::COLOR_ATTACHMENT | transfer,
                composite_alpha,
                present_mode: PresentMode::Fifo,
                ..Default::default()
            },
        )
        .map_err(|e| e.to_string())?;

        let context = skia_context(&library, &instance, &device, &queue)?;
        Ok(Self {
            backbuffer: Backbuffer::default(),
            context,
            last_frame: Some(sync::now(device).boxed()),
            images,
            swapchain,
            stale: false,
            queue,
        })
    }

    /// Recrea la swapchain si cambió el tamaño de la ventana o quedó obsoleta.
    fn prepare(&mut self, extent: [u32; 2]) -> Result<(), String> {
        if let Some(last) = self.last_frame.as_mut() {
            last.cleanup_finished();
        }
        if !self.stale && self.swapchain.image_extent() == extent {
            return Ok(());
        }
        let (swapchain, images) = self
            .swapchain
            .recreate(SwapchainCreateInfo {
                image_extent: extent,
                ..self.swapchain.create_info()
            })
            .map_err(|e| e.to_string())?;
        self.swapchain = swapchain;
        self.images = images;
        self.stale = false;
        Ok(())
    }
}

impl Surface for VulkanSurface {
    fn name(&self) -> &'static str {
        "vulkan"
    }

    fn present(&mut self, window: &Window, paint: Paint) -> Result<(), String> {
        let Some((w, h)) = physical_size(window) else {
            return Ok(());
        };
        let extent = [w.get(), h.get()];
        self.prepare(extent)?;
        // Con la swapchain obsoleta (redimensionado en curso) se recrea y se reintenta una vez.
        let mut acquired = None;
        for _ in 0..2 {
            match acquire_next_image(self.swapchain.clone(), None).map_err(Validated::unwrap) {
                Ok((index, suboptimal, future)) => {
                    self.stale = suboptimal;
                    acquired = Some((index, future));
                    break;
                }
                Err(VulkanError::OutOfDate) => {
                    self.stale = true;
                    self.prepare(extent)?;
                }
                Err(e) => return Err(e.to_string()),
            }
        }
        let Some((index, acquire)) = acquired else {
            // Se pintará cuando la ventana termine de cambiar de tamaño.
            window.request_redraw();
            return Ok(());
        };
        // La imagen puede seguir en pantalla hasta que la swapchain la libere:
        // Skia pinta fuera de los futures de vulkano, así que se espera en la CPU.
        acquire.wait(None).map_err(|e| e.to_string())?;

        let size = (w.get() as i32, h.get() as i32);
        let source = self.backbuffer.paint(&mut self.context, size, paint)?;
        let image = &self.images[index as usize];
        let mut target = wrap_image(&mut self.context, image, size)?;
        Backbuffer::blit(source, target.canvas());
        let present = gpu::vk::mutable_texture_states::new_vulkan(
            vk::ImageLayout::PRESENT_SRC_KHR,
            self.queue.queue_family_index(),
        );
        self.context.flush_surface_with_texture_state(
            &mut target,
            &gpu::FlushInfo::default(),
            Some(&present),
        );
        // Skia y vulkano comparten la cola: se espera a que Skia termine antes de presentar.
        self.context.submit(gpu::SubmitInfo {
            sync: gpu::SyncCpu::Yes,
            ..gpu::SubmitInfo::default()
        });
        if self.context.is_device_lost() {
            return Err("se perdió el dispositivo Vulkan".into());
        }
        drop(target);

        let last = self
            .last_frame
            .take()
            .unwrap_or_else(|| sync::now(self.queue.device().clone()).boxed());
        let presented = last
            .join(acquire)
            .then_swapchain_present(
                self.queue.clone(),
                SwapchainPresentInfo::swapchain_image_index(self.swapchain.clone(), index),
            )
            .then_signal_fence_and_flush()
            .map_err(Validated::unwrap);
        match presented {
            Ok(future) => self.last_frame = Some(future.boxed()),
            Err(VulkanError::OutOfDate) => {
                self.stale = true;
                window.request_redraw();
            }
            Err(e) => return Err(e.to_string()),
        }
        Ok(())
    }
}

/// Preferencia entre GPUs: dedicada, integrada, virtual, por software.
fn device_rank(device: &PhysicalDevice) -> u8 {
    match device.properties().device_type {
        PhysicalDeviceType::DiscreteGpu => 0,
        PhysicalDeviceType::IntegratedGpu => 1,
        PhysicalDeviceType::VirtualGpu => 2,
        PhysicalDeviceType::Cpu => 3,
        _ => 4,
    }
}

/// Formato de Vulkan equivalente en Skia (solo los de 8 bits por canal sin sRGB:
/// el render por CPU tampoco convierte el espacio de color).
fn skia_format(format: Format) -> Option<(vk::Format, ColorType)> {
    match format {
        Format::B8G8R8A8_UNORM => Some((vk::Format::B8G8R8A8_UNORM, ColorType::BGRA8888)),
        Format::R8G8B8A8_UNORM => Some((vk::Format::R8G8B8A8_UNORM, ColorType::RGBA8888)),
        _ => None,
    }
}

/// Contexto de Skia sobre el dispositivo y la cola de vulkano.
fn skia_context(
    library: &VulkanLibrary,
    instance: &Instance,
    device: &Device,
    queue: &Queue,
) -> Result<DirectContext, String> {
    let api = device.api_version();
    let get_proc = |of: vk::GetProcOf| unsafe {
        match of {
            vk::GetProcOf::Instance(instance, name) => {
                library.get_instance_proc_addr(ash::vk::Instance::from_raw(instance as _), name)
            }
            vk::GetProcOf::Device(device, name) => (instance.fns().v1_0.get_device_proc_addr)(
                ash::vk::Device::from_raw(device as _),
                name,
            ),
        }
        .map(|f| f as _)
        .unwrap_or(ptr::null())
    };
    let backend = unsafe {
        vk::BackendContext::new_builder(
            instance.handle().as_raw() as _,
            device.physical_device().handle().as_raw() as _,
            device.handle().as_raw() as _,
            (
                queue.handle().as_raw() as _,
                queue.queue_family_index() as usize,
            ),
            &get_proc,
            Some((api.major as usize, api.minor as usize, api.patch as usize).into()),
        )
        .build()
    };
    direct_contexts::make_vulkan(&backend, None)
        .ok_or_else(|| "Skia no pudo usar el dispositivo Vulkan".into())
}

/// Superficie de Skia que pinta en una imagen de la swapchain.
fn wrap_image(
    context: &mut DirectContext,
    image: &Image,
    size: (i32, i32),
) -> Result<skia_safe::Surface, String> {
    let (format, color_type) =
        skia_format(image.format()).ok_or("formato de swapchain inesperado")?;
    let info = unsafe {
        vk::ImageInfo::new(
            image.handle().as_raw() as _,
            vk::Alloc::default(),
            vk::ImageTiling::OPTIMAL,
            vk::ImageLayout::UNDEFINED,
            format,
            1,
            None,
            None,
            None,
            None,
        )
    };
    let target = backend_render_targets::make_vk(size, &info);
    gpu::surfaces::wrap_backend_render_target(
        context,
        &target,
        gpu::SurfaceOrigin::TopLeft,
        color_type,
        None,
        None,
    )
    .ok_or_else(|| "Skia no pudo pintar en la imagen de la swapchain".into())
}
