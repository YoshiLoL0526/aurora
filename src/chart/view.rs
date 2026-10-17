//! Ventana visible (zoom y pan) y reducción de series (tramos y LTTB).

use super::*;

/// Ventana visible del eje x, en unidades de datos.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Window {
    pub x0: f64,
    pub x1: f64,
}

/// Lo que guarda `Charts` de la última grabación de un `chart` para hacer zoom
/// y pan sin volver a leer los datos.
#[derive(Clone, Copy, Debug)]
pub struct RecordedView {
    /// Área de dibujo (dentro de los márgenes de los ejes), en coordenadas
    /// locales de la caja de contenido: es la que recibe el puntero.
    pub plot: Rect,
    /// Dominio completo de los datos.
    pub domain: (f64, f64),
    /// Ventana visible (ya recortada al dominio) con la que se grabó.
    pub window: (f64, f64),
}

/// Una grabación de `chart`: el `Picture` y, si se pudo grabar, con qué eje x,
/// dominio y ventana se hizo (lo usan el zoom, el pan y las pruebas).
pub struct Recording {
    pub picture: Option<Picture>,
    pub view: Option<RecordedView>,
}

/// Recorta una ventana al dominio sin cambiar su ancho (una ventana más ancha
/// que el dominio pasa a ser el dominio).
pub(super) fn clamp_window(w: Window, (d0, d1): (f64, f64)) -> Window {
    if at_most(d1, d0) || at_most(w.x1, w.x0) {
        return Window {
            x0: d0,
            x1: d1.max(d0),
        };
    }
    let span = (w.x1 - w.x0).min(d1 - d0);
    let x0 = w.x0.clamp(d0, d1 - span);
    Window { x0, x1: x0 + span }
}

/// Orden de las x de una serie (calculado al vuelo en la pasada del dominio):
/// con x ordenada, la ventana se acota con búsqueda binaria; si no, filtrando.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub(super) enum Order {
    Asc,
    Desc,
    Mixed,
}

/// Cómo recorrer los puntos de una serie en esta grabación.
#[derive(Clone, Copy, Debug)]
pub(super) enum Span {
    /// Toda la serie (vista completa).
    All,
    /// Índices `[start, end)` visibles (x ordenada). Las barras caen en la
    /// mitad de un hueco, por eso pueden entrar las de los bordes.
    Indices(usize, usize),
    /// Toda la serie, con los puntos visibles filtrados por su x (x desordenada).
    Filtered(f64, f64),
}

impl Span {
    /// Índices del núcleo visible (sin márgenes), para barras, dispersión y
    /// etiquetas.
    pub(super) fn bounds(self, len: usize) -> (usize, usize) {
        match self {
            Span::All => (0, len),
            Span::Indices(a, b) => (a.min(len), b.min(len)),
            Span::Filtered(..) => (0, len),
        }
    }

    /// Si un punto con x `x` cae dentro del tramo (solo filtra `Filtered`).
    pub(super) fn visible(self, x: f64) -> bool {
        match self {
            Span::Filtered(a, b) => x >= a && x <= b,
            _ => true,
        }
    }
}

/// Los índices de `span`, en orden. Con `margins` se añade un punto a cada lado
/// (solo con `Indices`): el segmento que cruza el borde de la ventana se sigue
/// dibujando.
pub(super) fn each(span: Span, len: usize, margins: bool) -> std::ops::Range<usize> {
    match span {
        Span::All => 0..len,
        Span::Indices(a, b) => {
            if margins {
                a.saturating_sub(1)..(b + 1).min(len)
            } else {
                a..b
            }
        }
        Span::Filtered(..) => 0..len,
    }
}

/// Primer índice cuyo x ya no queda "antes" de `v` (menor, o mayor si la serie
/// desciende), por búsqueda binaria: la cota inferior de un tramo ordenado.
fn first_at(series: &Series, v: f64, desc: bool, strict: bool) -> usize {
    let (mut lo, mut hi) = (0, series.len());
    while lo < hi {
        let mid = (lo + hi) / 2;
        let x = series.x_at(mid);
        let before = match (desc, strict) {
            (false, true) => x < v,
            (false, false) => x <= v,
            (true, true) => x > v,
            (true, false) => x >= v,
        };
        if before {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo
}

/// El tramo de una serie que se ve en la ventana.
pub(super) fn span_of(series: &Series, window: Option<Window>, order: Order) -> Span {
    let Some(w) = window else {
        return Span::All;
    };
    match &series.x {
        None => {
            // Posiciones 0, 1, 2…: la ventana son índices (± 0.5 para que las
            // barras de los bordes entren partidas).
            let n = series.len() as f64;
            let a = (w.x0 - 0.5).ceil().clamp(0.0, n) as usize;
            let b = ((w.x1 + 0.5).floor() + 1.0).clamp(0.0, n) as usize;
            Span::Indices(a, b.max(a))
        }
        Some(_) => match order {
            Order::Asc => Span::Indices(
                first_at(series, w.x0, false, true),
                first_at(series, w.x1, false, false),
            ),
            Order::Desc => Span::Indices(
                first_at(series, w.x1, true, true),
                first_at(series, w.x0, true, false),
            ),
            Order::Mixed => Span::Filtered(w.x0, w.x1),
        },
    }
}

/// Rango de y de los puntos que caen en la ventana visible (todas las series).
pub(super) fn visible_y(chart: &Chart, spans: &[Span], x0: f64, x1: f64) -> (f64, f64) {
    let (mut lo, mut hi) = (f64::INFINITY, f64::NEG_INFINITY);
    for (s, span) in chart.series.iter().zip(spans) {
        for i in each(*span, s.len(), false) {
            let (x, y) = (s.x_at(i), s.y_at(i));
            if x.is_finite() && y.is_finite() && x >= x0 && x <= x1 {
                lo = lo.min(y);
                hi = hi.max(y);
            }
        }
    }
    (lo, hi)
}

/// Los puntos de una serie listos para dibujar, en coordenadas de datos: `pts`
/// y, en `ends`, el final (exclusivo) de cada tramo continuo.
pub(super) struct Curves {
    pub(super) pts: Vec<(f64, f64)>,
    pub(super) ends: Vec<usize>,
}

/// Reduce una serie a lo que hay que dibujar: recorta a la ventana, corta la
/// línea en los valores que faltan (los `NaN`) y, cuando un tramo tiene más
/// puntos que `budget` (su ancho en pantalla), lo reduce con LTTB.
pub(super) fn curves(series: &Series, span: Span, budget: impl Fn(f64, f64) -> usize) -> Curves {
    let len = series.len();
    let finite = |i: usize| series.x_at(i).is_finite() && series.y_at(i).is_finite();
    // Con x desordenada entra cada punto visible y sus vecinos: así se siguen
    // dibujando los segmentos que cruzan el borde (luego se recortan en él).
    let visible = |i: usize| {
        finite(i)
            && match span {
                Span::Filtered(..) => {
                    let inside = |j: usize| span.visible(series.x_at(j)) && finite(j);
                    inside(i) || (i > 0 && inside(i - 1)) || (i + 1 < len && inside(i + 1))
                }
                _ => true,
            }
    };
    // Tramos continuos: un `NaN` en x o en y corta la línea.
    let mut runs: Vec<(usize, usize)> = Vec::new();
    let mut start: Option<usize> = None;
    let indices = each(span, len, true);
    let end = indices.end;
    for i in indices {
        match (visible(i), start) {
            (true, None) => start = Some(i),
            (false, Some(s)) => {
                runs.push((s, i));
                start = None;
            }
            _ => {}
        }
    }
    if let Some(s) = start {
        runs.push((s, end));
    }
    let mut pts = Vec::new();
    let mut ends = Vec::with_capacity(runs.len());
    for (a, b) in runs {
        let n = b - a;
        let target = budget(series.x_at(a), series.x_at(b - 1)).max(3);
        if n > target {
            lttb(
                n,
                target,
                |i| (series.x_at(a + i), series.y_at(a + i)),
                &mut pts,
            );
        } else {
            for i in a..b {
                pts.push((series.x_at(i), series.y_at(i)));
            }
        }
        ends.push(pts.len());
    }
    Curves { pts, ends }
}

/// Reduce `n` puntos a `target` con LTTB (*Largest-Triangle-Three-Buckets*):
/// conserva el primero, el último y, de cada bucket, el punto que forma el
/// triángulo de área mayor con el punto anterior y la media del siguiente. Es
/// el estándar para dibujar millones de muestras sin perder el perfil.
fn lttb(n: usize, target: usize, point: impl Fn(usize) -> (f64, f64), out: &mut Vec<(f64, f64)>) {
    if target >= n || target < 3 {
        for i in 0..n {
            out.push(point(i));
        }
        return;
    }
    out.push(point(0));
    let every = (n - 2) as f64 / (target - 2) as f64;
    let mut a = 0usize;
    for i in 0..target - 2 {
        // Media del bucket siguiente (para el último, el punto final).
        let from = (((i + 1) as f64 * every).floor() as usize + 1).min(n - 1);
        let to = (((i + 2) as f64 * every).floor() as usize + 1).clamp(from + 1, n);
        let count = (to - from) as f64;
        let (mut ax, mut ay) = (0.0, 0.0);
        for j in from..to {
            let (x, y) = point(j);
            ax += x;
            ay += y;
        }
        let (ax, ay) = (ax / count, ay / count);
        // El punto del bucket actual con el triángulo de área mayor.
        let first = ((i as f64 * every).floor() as usize + 1).min(n - 2);
        let (px, py) = point(a);
        let (mut best, mut area) = (first, -1.0f64);
        for j in first..from {
            let (x, y) = point(j);
            let a = ((px - ax) * (y - py) - (px - x) * (ay - py)).abs();
            if a > area {
                area = a;
                best = j;
            }
        }
        out.push(point(best));
        a = best;
    }
    out.push(point(n - 1));
}

/// Recorta una polilínea (en unidades de datos) a la franja `x ∈ [x0, x1]`:
/// el segmento que cruza un borde se corta justo en él, interpolando su y, así
/// que en el borde se ve la pendiente de verdad. Puede partirla en varios
/// tramos (con x desordenada la línea sale y vuelve a entrar).
pub(super) fn clip_x(run: &[(f64, f64)], x0: f64, x1: f64, out: &mut Vec<Vec<(f64, f64)>>) {
    fn flush(cur: &mut Vec<(f64, f64)>, out: &mut Vec<Vec<(f64, f64)>>) {
        if !cur.is_empty() {
            out.push(std::mem::take(cur));
        }
    }
    let inside = |x: f64| x >= x0 && x <= x1;
    if let [p] = run {
        if inside(p.0) {
            out.push(vec![*p]);
        }
        return;
    }
    let mut cur = Vec::new();
    for w in run.windows(2) {
        let ((ax, ay), (bx, by)) = (w[0], w[1]);
        // Parámetros (0..1) del segmento donde entra y sale de la franja.
        let (mut t0, mut t1) = (0.0f64, 1.0f64);
        let dx = bx - ax;
        if dx == 0.0 {
            if !inside(ax) {
                flush(&mut cur, out);
                continue;
            }
        } else {
            let (ta, tb) = ((x0 - ax) / dx, (x1 - ax) / dx);
            t0 = t0.max(ta.min(tb));
            t1 = t1.min(ta.max(tb));
            if t0 > t1 {
                flush(&mut cur, out);
                continue;
            }
        }
        let at = |t: f64| (ax + dx * t, ay + (by - ay) * t);
        let p0 = if t0 > 0.0 { at(t0) } else { (ax, ay) };
        let p1 = if t1 < 1.0 { at(t1) } else { (bx, by) };
        if cur.last() != Some(&p0) {
            flush(&mut cur, out);
            cur.push(p0);
        }
        cur.push(p1);
        if t1 < 1.0 {
            flush(&mut cur, out);
        }
    }
    flush(&mut cur, out);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lttb_is_the_identity_without_reduction() {
        let mut out = Vec::new();
        lttb(5, 5, |i| (i as f64, i as f64 * 2.0), &mut out);
        assert_eq!(
            out,
            vec![(0.0, 0.0), (1.0, 2.0), (2.0, 4.0), (3.0, 6.0), (4.0, 8.0)]
        );
        let mut more = Vec::new();
        lttb(3, 100, |i| (i as f64, i as f64), &mut more);
        assert_eq!(more, vec![(0.0, 0.0), (1.0, 1.0), (2.0, 2.0)]);
    }

    #[test]
    fn lttb_keeps_the_ends_the_spikes_and_the_order() {
        let n = 10_000;
        let spikes = [1_234usize, 5_555, 9_000];
        let y = |i: usize| if spikes.contains(&i) { 10.0 } else { 0.5 };
        let mut out = Vec::new();
        lttb(n, 64, |i| (i as f64, y(i)), &mut out);
        assert_eq!(out.len(), 64);
        assert_eq!(out.first(), Some(&(0.0, 0.5)));
        assert_eq!(out.last(), Some(&((n - 1) as f64, 0.5)));
        for s in spikes {
            assert!(
                out.iter().any(|&(x, _)| x == s as f64),
                "el pico {s} no sobrevivió"
            );
        }
        assert!(out.windows(2).all(|w| w[0].0 < w[1].0), "fuera de orden");
    }

    #[test]
    fn lttb_covers_the_whole_series_with_its_buckets() {
        // Con objetivo 4, los 4 tramos cubren la serie entera (no se deja cola).
        let mut out = Vec::new();
        lttb(10, 4, |i| (i as f64, i as f64), &mut out);
        assert_eq!(out.len(), 4);
        assert_eq!(out.first().unwrap().0, 0.0);
        assert_eq!(out.last().unwrap().0, 9.0);
        assert!(out.windows(2).all(|w| w[0].0 < w[1].0), "fuera de orden");
    }

    #[test]
    fn clipping_cuts_the_segments_at_the_edges() {
        let mut out = Vec::new();
        // Un punto de margen a cada lado: se cortan en el borde, interpolando y.
        clip_x(&[(0.0, 0.0), (2.0, 4.0), (4.0, 0.0)], 1.0, 3.0, &mut out);
        assert_eq!(out, vec![vec![(1.0, 2.0), (2.0, 4.0), (3.0, 2.0)]]);
        // La línea sale y vuelve a entrar (x desordenada): dos tramos.
        out.clear();
        clip_x(&[(1.0, 0.0), (5.0, 0.0), (2.0, 1.0)], 0.0, 3.0, &mut out);
        assert_eq!(
            out,
            vec![
                vec![(1.0, 0.0), (3.0, 0.0)],
                vec![(3.0, 2.0 / 3.0), (2.0, 1.0)]
            ]
        );
        // Del todo fuera: nada.
        out.clear();
        clip_x(&[(5.0, 0.0), (6.0, 1.0)], 0.0, 3.0, &mut out);
        assert!(out.is_empty());
    }

    #[test]
    fn the_window_keeps_its_width_inside_the_domain() {
        let domain = (0.0, 100.0);
        let same = |a: (f64, f64)| Window { x0: a.0, x1: a.1 };
        assert_eq!(clamp_window(same((10.0, 30.0)), domain), same((10.0, 30.0)));
        // Pegada al borde derecho: mantiene el ancho.
        assert_eq!(
            clamp_window(same((90.0, 110.0)), domain),
            same((80.0, 100.0))
        );
        assert_eq!(clamp_window(same((-20.0, 5.0)), domain), same((0.0, 25.0)));
        // Más ancha que el dominio: todo el dominio.
        assert_eq!(
            clamp_window(same((-50.0, 500.0)), domain),
            same((0.0, 100.0))
        );
        // Un dominio degenerado no rompe nada.
        assert_eq!(clamp_window(same((1.0, 2.0)), (3.0, 3.0)), same((3.0, 3.0)));
    }
}
