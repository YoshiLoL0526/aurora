//! Caché rasterizada de los `Picture` de `canvas` y `chart`.
//!
//! Reproducir un `Picture` con miles de trazos cuesta milisegundos, y se paga
//! cada vez que se repinta algo que lo toca (el hover de la tarjeta que lo
//! contiene, una transición vecina…) aunque el dibujo no haya cambiado. Si un
//! dibujo se pinta dos veces seguidas con la misma posición subpíxel y la misma
//! escala, se rasteriza una vez en una imagen del tamaño de la caja y desde ahí
//! se copia: el resultado es el mismo que pintar el `Picture`, salvo el redondeo
//! de componer sobre una imagen transparente de 8 bits (unos pocos niveles donde
//! se solapan bordes suavizados, como los puntos de una dispersión).
//!
//! Un dibujo que se mueve en fracciones de píxel (una animación de layout) o
//! que se transforma (escala, `press_scale`) se pinta directamente, sin caché.

use super::*;
use skia_safe::{Image, ImageInfo, Matrix};

/// Precisión con la que se compara la posición subpíxel (1/64 de píxel físico).
const SUBPIXEL: f32 = 64.0;

/// Imagen de un `Picture` ya rasterizado, o la primera vez que se pintó con
/// estos parámetros (aún sin imagen: se crea si el siguiente frame repite).
pub(super) struct Raster {
    params: Params,
    image: Option<Image>,
}

#[derive(Clone, Copy, PartialEq)]
struct Params {
    picture: u32,
    scale: f32,
    /// Parte fraccionaria del origen en píxeles físicos, en 1/64.
    frac: (i32, i32),
    /// Tamaño de la imagen en píxeles físicos.
    size: (i32, i32),
}

impl Engine {
    /// Pinta `picture` (de la caja de contenido de `key`, de `size` píxeles
    /// lógicos) en el origen local actual del lienzo, desde su caché si se puede.
    pub(super) fn draw_recorded(
        &self,
        canvas: &Canvas,
        key: &str,
        picture: &Picture,
        size: (f32, f32),
    ) {
        let Some((params, origin)) = params(canvas, picture, size) else {
            canvas.draw_picture(picture, None, None);
            return;
        };
        let mut rasters = self.rasters.borrow_mut();
        let entry = rasters.get(key).filter(|r| r.params == params);
        let image = match entry {
            Some(Raster {
                image: Some(image), ..
            }) => Some(image.clone()),
            // Segunda vez con los mismos parámetros: se rasteriza.
            Some(_) => rasterize(canvas, picture, params),
            // Primera vez: se pinta directamente y se recuerda.
            None => None,
        };
        rasters.insert(
            key.to_owned(),
            Raster {
                params,
                image: image.clone(),
            },
        );
        drop(rasters);
        match image {
            Some(image) => {
                canvas.save();
                canvas.reset_matrix();
                canvas.draw_image(&image, origin, None);
                canvas.restore();
            }
            None => {
                canvas.draw_picture(picture, None, None);
            }
        }
    }

    /// Olvida las imágenes de los dibujos que ya no existen.
    pub(super) fn retain_rasters(&mut self) {
        let (pictures, charts) = (&self.pictures, &self.charts);
        self.rasters
            .get_mut()
            .retain(|k, _| pictures.contains_key(k) || charts.contains_key(k));
    }
}

/// Parámetros de la caché y origen entero (en píxeles físicos) donde copiar la
/// imagen. `None` si el lienzo tiene una transformación que no es una escala
/// uniforme con traslación: entonces se pinta el `Picture` sin caché.
fn params(canvas: &Canvas, picture: &Picture, size: (f32, f32)) -> Option<(Params, Point)> {
    let m: Matrix = canvas.local_to_device_as_3x3();
    if !m.is_scale_translate() {
        return None;
    }
    let (sx, sy) = (m.scale_x(), m.scale_y());
    if sx <= 0.0 || (sx - sy).abs() > 1e-4 {
        return None;
    }
    let (tx, ty) = (m.translate_x(), m.translate_y());
    if !(tx.is_finite() && ty.is_finite()) {
        return None;
    }
    let (fx, fy) = (tx - tx.floor(), ty - ty.floor());
    let frac = (
        (fx * SUBPIXEL).round() as i32,
        (fy * SUBPIXEL).round() as i32,
    );
    let w = (size.0 * sx + fx).ceil() as i32;
    let h = (size.1 * sy + fy).ceil() as i32;
    // Una caja enorme no se rasteriza (la imagen costaría más que el dibujo).
    if w <= 0 || h <= 0 || i64::from(w) * i64::from(h) > 4096 * 4096 {
        return None;
    }
    let params = Params {
        picture: picture.unique_id(),
        scale: sx,
        frac,
        size: (w, h),
    };
    Some((params, Point::new(tx.floor(), ty.floor())))
}

/// Rasteriza `picture` con la escala y la posición subpíxel de `params` en una
/// superficie compatible con `canvas` (de GPU si el lienzo lo es).
fn rasterize(canvas: &Canvas, picture: &Picture, params: Params) -> Option<Image> {
    let info = ImageInfo::new_n32_premul(params.size, None);
    let mut surface = canvas.new_surface(&info, None)?;
    let target = surface.canvas();
    target.clear(Color::TRANSPARENT);
    target.translate((
        params.frac.0 as f32 / SUBPIXEL,
        params.frac.1 as f32 / SUBPIXEL,
    ));
    target.scale((params.scale, params.scale));
    target.draw_picture(picture, None, None);
    Some(surface.image_snapshot())
}
