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
    write_png(&mut surface, path).map_err(PyRuntimeError::new_err)
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

pub fn write_png(surface: &mut Surface, path: &str) -> Result<(), String> {
    let image = surface.image_snapshot();
    let data = image
        .encode(None, EncodedImageFormat::PNG, None)
        .ok_or("no se pudo codificar el PNG")?;
    std::fs::write(path, data.as_bytes()).map_err(|e| e.to_string())
}
