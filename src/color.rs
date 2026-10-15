use pyo3::PyResult;
use pyo3::exceptions::PyValueError;
use skia_safe::Color;

/// Acepta `#rgb`, `#rrggbb` y `#rrggbbaa`.
pub fn parse_color(s: &str) -> PyResult<Color> {
    let hex = s.trim().trim_start_matches('#');
    let err = || PyValueError::new_err(format!("color inválido: {s:?}"));
    let byte =
        |i: usize| u8::from_str_radix(hex.get(i..i + 2).ok_or_else(err)?, 16).map_err(|_| err());
    match hex.len() {
        3 => {
            let n = |i: usize| {
                u8::from_str_radix(&hex[i..i + 1], 16)
                    .map(|v| v * 17)
                    .map_err(|_| err())
            };
            Ok(Color::from_rgb(n(0)?, n(1)?, n(2)?))
        }
        6 => Ok(Color::from_rgb(byte(0)?, byte(2)?, byte(4)?)),
        8 => Ok(Color::from_argb(byte(6)?, byte(0)?, byte(2)?, byte(4)?)),
        _ => Err(err()),
    }
}

/// Interpolación lineal de colores en sRGB (suficiente para transiciones cortas de UI).
pub fn lerp(a: Color, b: Color, t: f32) -> Color {
    let t = t.clamp(0.0, 1.0);
    let mix = |x: u8, y: u8| (x as f32 + (y as f32 - x as f32) * t).round() as u8;
    Color::from_argb(
        mix(a.a(), b.a()),
        mix(a.r(), b.r()),
        mix(a.g(), b.g()),
        mix(a.b(), b.b()),
    )
}
