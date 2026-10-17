//! Escala de los ejes: pasos «bonitos», ticks y formato de las etiquetas.

/// Tope de ticks por eje (con límites fijos y un paso muy fino).
const MAX_TICKS: usize = 200;

/// `true` si `a <= b`, y también si alguno es NaN (un eje sin datos válidos:
/// el dibujo degenera en una franja en vez de en números imposibles).
pub(super) fn at_most(a: f64, b: f64) -> bool {
    a.partial_cmp(&b) != Some(std::cmp::Ordering::Greater)
}

/// Paso "bonito" (1, 2 o 5 por una potencia de 10) para cubrir `span` con unas
/// `target` divisiones.
pub(super) fn nice_step(span: f64, target: f64) -> f64 {
    let raw = span.max(f64::MIN_POSITIVE) / target.max(1.0);
    let mag = 10f64.powf(raw.log10().floor());
    let n = raw / mag;
    mag * if n <= 1.0 {
        1.0
    } else if n <= 2.0 {
        2.0
    } else if n <= 5.0 {
        5.0
    } else {
        10.0
    }
}

/// Redondea `v` al múltiplo de `step` más cercano hacia abajo (o hacia arriba).
/// Un valor ya en la rejilla se devuelve tal cual, aunque el cociente dé
/// 2.9999… por el error de coma flotante (`3 * 0.1` no es `0.3`).
pub(super) fn snap(v: f64, step: f64, up: bool) -> f64 {
    let q = v / step;
    if (q - q.round()).abs() < 1e-9 {
        return v;
    }
    let k = if up { q.ceil() } else { q.floor() };
    k * step
}

/// Múltiplos de `step` dentro de `[lo, hi]`, de `lo` hacia arriba.
pub(super) fn ticks_between(lo: f64, hi: f64, step: f64) -> Vec<f64> {
    let mut out = Vec::new();
    if at_most(step, 0.0) || !lo.is_finite() || !hi.is_finite() {
        return if lo.is_finite() { vec![lo] } else { out };
    }
    let mut v = snap(lo, step, true);
    while v <= hi + step * 1e-9 && out.len() < MAX_TICKS {
        if v >= lo - step * 1e-9 {
            out.push(v);
        }
        v += step;
    }
    if out.is_empty() {
        out.push(lo);
    }
    out
}

/// Unidad de las etiquetas de un eje: 1, k, M o G según la magnitud que abarca.
/// Es la misma para todos los ticks del eje (las etiquetas son consistentes).
pub(super) fn tick_unit(lo: f64, hi: f64) -> f64 {
    let max = lo.abs().max(hi.abs());
    if max >= 1e9 {
        1e9
    } else if max >= 1e6 {
        1e6
    } else if max >= 1e4 {
        1e3
    } else {
        1.0
    }
}

/// Decimales necesarios para escribir un paso sin perder su valor (hasta 3).
fn decimals_for(step: f64) -> usize {
    let mut decimals = 0;
    let mut s = step.abs();
    while decimals < 3 && (s - s.round()).abs() > 1e-9 {
        s *= 10.0;
        decimals += 1;
    }
    decimals
}

/// Etiqueta de un tick con la unidad del eje (`12.3k`, `1.5M`); sin decimales
/// de más (`3.0k` → `3k`) y con el `-0` que no dice nada escrito como `0`.
pub(super) fn format_tick(v: f64, step: f64, unit: f64) -> String {
    // El cero se escribe `0`, sin sufijo (`0k` no dice nada).
    if v == 0.0 {
        return "0".into();
    }
    let suffix = match unit {
        1e9 => "G",
        1e6 => "M",
        1e3 => "k",
        _ => "",
    };
    let mut s = format!("{:.*}", decimals_for(step / unit), v / unit);
    if s.contains('.') {
        s = s.trim_end_matches('0').trim_end_matches('.').to_owned();
    }
    if s.starts_with('-') && s[1..].chars().all(|c| c == '0' || c == '.') {
        s.remove(0);
    }
    format!("{s}{suffix}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nice_steps_are_one_two_or_five() {
        assert_eq!(nice_step(10.0, 5.0), 2.0);
        assert_eq!(nice_step(1.0, 5.0), 0.2);
        assert_eq!(nice_step(0.03, 5.0), 0.01);
        assert_eq!(nice_step(4830.0, 5.0), 1000.0);
    }

    #[test]
    fn snapping_keeps_values_already_on_the_grid() {
        // 0.1 * 3 no es exactamente 0.3: un valor ya en la rejilla no se mueve.
        assert_eq!(snap(0.3, 0.1, false), 0.3);
        assert_eq!(snap(0.3, 0.1, true), 0.3);
        // Uno entre dos ticks cae en el más cercano de cada lado.
        assert_eq!(snap(0.31, 0.1, false), 3.0 * 0.1);
        assert_eq!(snap(0.31, 0.1, true), 0.4);
    }

    #[test]
    fn ticks_cover_the_domain() {
        assert_eq!(
            ticks_between(0.0, 1.0, 0.25),
            vec![0.0, 0.25, 0.5, 0.75, 1.0]
        );
        assert_eq!(ticks_between(0.3, 0.9, 0.5), vec![0.5]);
    }

    #[test]
    fn labels_shrink_large_numbers_and_drop_noise() {
        assert_eq!(format_tick(0.0, 1.0, 1.0), "0");
        assert_eq!(format_tick(2.0, 2.0, 1.0), "2");
        assert_eq!(format_tick(0.25, 0.25, 1.0), "0.25");
        assert_eq!(format_tick(-0.0, 1.0, 1.0), "0");
        assert_eq!(format_tick(2500.0, 2500.0, 1e3), "2.5k");
        assert_eq!(format_tick(3000.0, 1000.0, 1e3), "3k");
        assert_eq!(format_tick(0.0, 5000.0, 1e3), "0");
        assert_eq!(format_tick(1.5e6, 500_000.0, 1e6), "1.5M");
    }

    #[test]
    fn units_come_from_the_magnitude() {
        assert_eq!(tick_unit(0.0, 999.0), 1.0);
        assert_eq!(tick_unit(0.0, 12_000.0), 1e3);
        assert_eq!(tick_unit(-3e6, 2e6), 1e6);
        assert_eq!(tick_unit(-4e9, 1.0), 1e9);
    }
}
