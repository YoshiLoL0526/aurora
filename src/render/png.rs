//! Render a PNG sin ventana (tests de snapshot y CI).

use super::*;

/// Renderiza sin ventana a un PNG: útil para tests de snapshot y CI.
pub fn render_png(
    root: &Node,
    width: f32,
    height: f32,
    scale: f32,
    path: &str,
) -> pyo3::PyResult<()> {
    use pyo3::exceptions::PyRuntimeError;
    let mut engine = Engine::new();
    engine.load_images(root)?;
    let mut surface = raster_surface(width, height, scale).map_err(PyRuntimeError::new_err)?;
    engine.update(root, width, height, scale);
    let mut canvases = crate::canvas::Canvases::default();
    canvases.rebuilt();
    canvases.draw(root, &mut engine, true)?;
    let mut charts = crate::chart::Charts::default();
    charts.rebuilt();
    charts.draw(root, &mut engine, true)?;
    engine.paint(surface.canvas(), root, width, height, None);
    write_png(&mut surface, path, None).map_err(PyRuntimeError::new_err)
}

/// Superficie en memoria de `width × height` píxeles lógicos a la escala dada.
pub fn raster_surface(width: f32, height: f32, scale: f32) -> Result<Surface, String> {
    let (pw, ph) = (
        (width * scale).round() as i32,
        (height * scale).round() as i32,
    );
    surfaces::raster_n32_premul((pw.max(1), ph.max(1)))
        .ok_or_else(|| "no se pudo crear la superficie".into())
}

/// Guarda la superficie como PNG; con `crop`, solo esa zona (en píxeles físicos,
/// recortada a la superficie).
pub fn write_png(surface: &mut Surface, path: &str, crop: Option<IRect>) -> Result<(), String> {
    let image = match crop {
        None => surface.image_snapshot(),
        Some(area) => {
            let frame = IRect::from_wh(surface.width(), surface.height());
            let area = IRect::intersect(&area, &frame)
                .ok_or("la zona que se quiere guardar no está dentro del frame")?;
            surface
                .image_snapshot_with_bounds(area)
                .ok_or("no se pudo recortar el frame")?
        }
    };
    let data = image
        .encode(None, EncodedImageFormat::PNG, None)
        .ok_or("no se pudo codificar el PNG")?;
    std::fs::write(path, data.as_bytes()).map_err(|e| e.to_string())
}
