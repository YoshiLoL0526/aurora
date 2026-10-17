//! Pintura del gráfico: ejes, rejilla, etiquetas, leyenda y series.

use super::*;

/// Divisiones a las que se apunta en el eje y (el algoritmo las ajusta a un paso
/// de 1, 2 o 5 por una potencia de 10, así que salen entre 4 y 6).
const Y_TICKS: f64 = 5.0;
/// Separación mínima entre etiquetas del eje x, en píxeles lógicos.
const X_LABEL_GAP: f32 = 70.0;

/// Puntos por píxel que se conservan al reducir una serie: dos bastan para que
/// el trazo no pierda picos ni escalones.
const POINTS_PER_PX: f64 = 2.0;

/// Píxeles que puede salirse un punto de la línea por arriba o por abajo antes
/// de topar (lo de fuera lo recorta el `clip_rect`; el tope solo evita
/// coordenadas desorbitadas, que Skia no maneja bien en `f32`).
const FAR: f32 = 100_000.0;

/// Graba el gráfico con el tamaño de su caja, en la ventana visible `window`
/// (`None`: el dominio completo). Una caja demasiado pequeña no se graba (el
/// nodo se queda con su fondo y su borde).
pub fn record(
    chart: &Chart,
    window: Option<Window>,
    width: f32,
    height: f32,
    fonts: &FontCollection,
) -> Recording {
    if width < 2.0 || height < 2.0 {
        return Recording {
            picture: None,
            view: None,
        };
    }
    let bounds = Rect::from_wh(width, height);
    let mut recorder = PictureRecorder::new();
    let canvas = recorder.begin_recording(bounds, false);
    let view = paint(canvas, chart, window, width, height, fonts);
    Recording {
        picture: recorder.finish_recording_as_picture(Some(&bounds)),
        view: Some(view),
    }
}

/// Pinta el gráfico entero (ejes, rejilla, etiquetas, leyenda y series) y
/// devuelve su eje x, su dominio y su ventana para el zoom y el pan.
fn paint(
    canvas: &SkCanvas,
    chart: &Chart,
    window: Option<Window>,
    width: f32,
    height: f32,
    fonts: &FontCollection,
) -> RecordedView {
    let (size, family) = (chart.label_size, chart.family.as_str());

    // --- dominio de los datos (y orden de las x de cada serie) --------------
    let mut max_len = 0usize;
    let (mut y_lo, mut y_hi) = (f64::INFINITY, f64::NEG_INFINITY);
    let (mut x_lo, mut x_hi) = (f64::INFINITY, f64::NEG_INFINITY);
    let mut orders: Vec<Order> = Vec::with_capacity(chart.series.len());
    for s in &chart.series {
        max_len = max_len.max(s.len());
        let explicit = s.x.is_some();
        let (mut asc, mut desc, mut prev) = (true, true, None::<f64>);
        for i in 0..s.len() {
            let (x, v) = (s.x_at(i), s.y_at(i));
            if x.is_finite() && v.is_finite() {
                y_lo = y_lo.min(v);
                y_hi = y_hi.max(v);
                x_lo = x_lo.min(x);
                x_hi = x_hi.max(x);
            }
            if explicit && !x.is_finite() {
                // Un hueco en x rompe la búsqueda binaria (un `NaN` no se
                // compara con nada): la serie se recorre filtrando por x.
                (asc, desc) = (false, false);
            } else if explicit {
                match prev {
                    Some(p) if x < p => asc = false,
                    Some(p) if x > p => desc = false,
                    _ => {}
                }
                prev = Some(x);
            }
        }
        orders.push(match (explicit, asc, desc) {
            (false, ..) | (true, true, _) => Order::Asc,
            (true, false, true) => Order::Desc,
            _ => Order::Mixed,
        });
    }
    let implicit_x = chart.series.iter().all(|s| s.x.is_none());
    if implicit_x {
        // Posiciones 0, 1, 2…: las barras de los extremos quedan enteras.
        let n = max_len as f64;
        (x_lo, x_hi) = match chart.kind {
            ChartKind::Bar => (-0.5, n - 0.5),
            _ => (0.0, (n - 1.0).max(0.0)),
        };
    }
    if at_most(x_hi, x_lo) {
        (x_lo, x_hi) = (x_lo - 0.5, x_hi + 0.5);
    }

    // --- ventana visible (zoom y pan) --------------------------------------
    let domain = (x_lo, x_hi);
    // Una ventana que abarca todo el dominio no es un zoom: se graba igual.
    let window = window
        .map(|w| clamp_window(w, domain))
        .filter(|w| w.x1 > w.x0 && (w.x0 > domain.0 || w.x1 < domain.1));
    let (x_lo, x_hi) = window.map_or(domain, |w| (w.x0, w.x1));
    let spans: Vec<Span> = chart
        .series
        .iter()
        .zip(&orders)
        .map(|(s, o)| span_of(s, window, *o))
        .collect();

    // --- escala de y: límites fijos, el dominio o lo visible ----------------
    if window.is_some() && chart.y_min.is_none() && chart.y_max.is_none() {
        // Con zoom, el eje y se ajusta a lo que se ve (si hay algo visible).
        let (lo, hi) = visible_y(chart, &spans, x_lo, x_hi);
        if lo.is_finite() {
            (y_lo, y_hi) = (lo, hi);
        }
    }
    if !y_lo.is_finite() {
        (y_lo, y_hi) = (0.0, 1.0);
    }
    // Las barras nacen del cero (salvo que sus límites se fijen a mano).
    let bar = chart.kind == ChartKind::Bar;
    let mut lo = chart
        .y_min
        .unwrap_or(if bar { y_lo.min(0.0) } else { y_lo });
    let mut hi = chart
        .y_max
        .unwrap_or(if bar { y_hi.max(0.0) } else { y_hi });
    if at_most(hi, lo) {
        // Todos los valores iguales (o un solo punto): una franja alrededor.
        let pad = 0.5f64.max(lo.abs() * 0.05);
        (lo, hi) = (lo - pad, lo + pad);
    }
    // Sin límites fijos, el dominio se ajusta a los ticks (la rejilla cierra).
    let step = nice_step(hi - lo, Y_TICKS);
    let fixed = chart.y_min.is_some() || chart.y_max.is_some();
    let (lo, hi) = if fixed {
        (lo, hi)
    } else {
        (snap(lo, step, false), snap(hi, step, true))
    };
    let ticks = ticks_between(lo, hi, step);
    let unit = tick_unit(lo, hi);
    let labels: Vec<String> = ticks.iter().map(|v| format_tick(*v, step, unit)).collect();

    // --- márgenes y caja de dibujo -----------------------------------------
    let mut left = 10.0f32;
    for l in &labels {
        left = left.max(measure_text(l, size, 400, family, fonts) + 8.0);
    }
    let top = if chart.names.is_empty() {
        8.0
    } else {
        size * 1.5 + 8.0
    };
    let bottom = size * 1.5 + 6.0;
    let plot = Rect::new(
        left,
        top,
        (width - 8.0).max(left + 1.0),
        (height - bottom).max(top + 1.0),
    );
    let xpix = |v: f64| plot.left + ((v - x_lo) / (x_hi - x_lo)) as f32 * plot.width();
    let ypix = |v: f64| plot.bottom - ((v - lo) / (hi - lo)) as f32 * plot.height();

    // --- rejilla y etiquetas de los ejes ------------------------------------
    if chart.grid && plot.width() > 4.0 && plot.height() > 4.0 {
        let mut p = Paint::default();
        p.set_anti_alias(true)
            .set_style(PaintStyle::Stroke)
            .set_stroke_width(1.0)
            .set_color(chart.grid_color)
            .set_path_effect(PathEffect::dash(&[3.0, 5.0], 0.0));
        for t in &ticks {
            let y = ypix(*t);
            canvas.draw_line((plot.left, y), (plot.right, y), &p);
        }
    }
    for (t, l) in ticks.iter().zip(&labels) {
        text_at(
            canvas,
            plot.left - 6.0,
            ypix(*t),
            l,
            chart.label_color,
            size,
            400,
            family,
            Align::Right,
            Baseline::Middle,
            fonts,
        );
    }
    draw_x_labels(canvas, chart, fonts, plot, x_lo, x_hi, &spans, &xpix);

    // --- series --------------------------------------------------------------
    canvas.save();
    canvas.clip_rect(plot, None, true);
    // Puntos visibles (el mayor de las series): el paso de las barras.
    let points = chart
        .series
        .iter()
        .zip(&spans)
        .map(|(s, span)| {
            let (a, b) = span.bounds(s.len());
            b.saturating_sub(a)
        })
        .max()
        .unwrap_or(0);
    let slot = bar_slot(chart, plot, x_lo, x_hi, points, implicit_x);
    let total = chart.series.len();
    for (index, ((s, span), order)) in chart.series.iter().zip(&spans).zip(&orders).enumerate() {
        draw_series(
            canvas,
            chart,
            s,
            *span,
            *order,
            (x_lo, x_hi),
            plot,
            &xpix,
            &ypix,
            slot,
            index,
            total,
        );
    }
    canvas.restore();

    // --- leyenda -------------------------------------------------------------
    if !chart.names.is_empty() {
        draw_legend(canvas, chart, fonts);
    }

    RecordedView {
        plot,
        domain,
        window: (x_lo, x_hi),
    }
}

/// Etiquetas del eje x: las de `labels` (las que caen en la ventana), o ticks
/// numéricos del dominio visible. Se saltan las que no caben (con al menos
/// `X_LABEL_GAP` px entre ellas) y las de los extremos se separan del borde lo
/// justo para verse enteras.
#[allow(clippy::too_many_arguments)]
fn draw_x_labels(
    canvas: &SkCanvas,
    chart: &Chart,
    fonts: &FontCollection,
    plot: Rect,
    x_lo: f64,
    x_hi: f64,
    spans: &[Span],
    xpix: &impl Fn(f64) -> f32,
) {
    let (size, family) = (chart.label_size, chart.family.as_str());
    let y = plot.bottom + 5.0;
    let mut last_right = f32::NEG_INFINITY;
    let mut place = |x: f32, text: &str| {
        let w = measure_text(text, size, 400, family, fonts);
        let x = x.clamp(plot.left + w / 2.0, plot.right - w / 2.0);
        if x - w / 2.0 >= last_right + 6.0 {
            text_at(
                canvas,
                x,
                y,
                text,
                chart.label_color,
                size,
                400,
                family,
                Align::Center,
                Baseline::Top,
                fonts,
            );
            last_right = x + w / 2.0;
        }
    };
    if !chart.labels.is_empty() {
        let (a, b) = spans
            .first()
            .map_or((0, chart.labels.len()), |s| s.bounds(chart.labels.len()));
        for i in a..b.min(chart.labels.len()) {
            place(xpix(i as f64), &chart.labels[i]);
        }
    } else {
        // Un tick cada ~70 px: el algoritmo encaja el paso con el ancho.
        let target = f64::from((plot.width() / X_LABEL_GAP).clamp(2.0, 8.0));
        let step = nice_step(x_hi - x_lo, target);
        let unit = tick_unit(x_lo, x_hi);
        for t in ticks_between(x_lo, x_hi, step) {
            place(xpix(t), &format_tick(t, step, unit));
        }
    }
}

/// Dibuja una serie: la línea (o el área), las barras o los puntos. Las series
/// largas se reducen con LTTB a lo que cabe en el ancho del dibujo.
/// `slot`: ancho del hueco de cada punto en las barras; `index`/`total`: qué
/// serie es y cuántas hay (las barras de varias series van agrupadas).
#[allow(clippy::too_many_arguments)]
fn draw_series(
    canvas: &SkCanvas,
    chart: &Chart,
    series: &Series,
    span: Span,
    order: Order,
    x_range: (f64, f64),
    plot: Rect,
    xpix: &impl Fn(f64) -> f32,
    ypix: &impl Fn(f64) -> f32,
    slot: f32,
    index: usize,
    total: usize,
) {
    let len = series.len();
    // Un punto se dibuja si es finito y cae en el tramo visible (con x
    // desordenada, `span` filtra por x).
    let visible = |i: usize| {
        let (x, y) = (series.x_at(i), series.y_at(i));
        x.is_finite() && y.is_finite() && span.visible(x)
    };

    match chart.kind {
        ChartKind::Scatter => {
            let mut path = PathBuilder::new();
            for i in each(span, len, true) {
                if !visible(i) {
                    continue;
                }
                let (x, y) = (xpix(series.x_at(i)), ypix(series.y_at(i)));
                // Un punto fuera del rango fijo se omite (no se pega al borde).
                if x < plot.left - 1.0
                    || x > plot.right + 1.0
                    || y < plot.top - 1.0
                    || y > plot.bottom + 1.0
                {
                    continue;
                }
                path.add_circle((x, y), chart.point_size, None);
            }
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(series.color);
            canvas.draw_path(&path.detach(), &p);
        }
        ChartKind::Bar => {
            let base = ypix(0.0).clamp(plot.top, plot.bottom);
            // Cada serie ocupa una franja del hueco: `n` barras por punto, juntas.
            let width = slot / total as f32;
            let half = (width / 2.0).max(0.5);
            let offset = (index as f32 - (total - 1) as f32 / 2.0) * width;
            let mut path = PathBuilder::new();
            let radius = (half * 0.4).min(3.0);
            for i in each(span, len, true) {
                if !visible(i) {
                    continue;
                }
                let x = (xpix(series.x_at(i)) + offset).clamp(plot.left, plot.right);
                let y = ypix(series.y_at(i)).clamp(plot.top, plot.bottom);
                let (t, h) = (base.min(y), (base - y).abs().max(1.0));
                let r = Rect::from_xywh(x - half, t, half * 2.0, h);
                path.add_rrect(RRect::new_rect_xy(r, radius, radius), None, None);
            }
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(series.color);
            canvas.draw_path(&path.detach(), &p);
        }
        ChartKind::Line | ChartKind::Area => {
            let area = chart.kind == ChartKind::Area;
            let base = ypix(0.0).clamp(plot.top, plot.bottom);
            // Puntos objetivo de cada tramo: los que caben en su ancho en
            // pantalla, para que un pico vertical no se lleve el presupuesto.
            // Con x desordenada (una curva cerrada, una espiral…) el ancho entre
            // el primer y el último punto no dice nada: se da el de todo el dibujo.
            let width = f64::from(plot.width().max(1.0));
            let budget = |first: f64, last: f64| {
                let frac = if order == Order::Mixed {
                    1.0
                } else {
                    (f64::from((xpix(last) - xpix(first)).abs()) / width).clamp(0.0, 1.0)
                };
                (width * POINTS_PER_PX * frac).round() as usize + 3
            };
            let reduced = curves(series, span, budget);
            // Cada tramo se recorta a la ventana en unidades de datos (los
            // puntos de margen quedan fuera): sin eso, el segmento que cruza el
            // borde se dibujaría con otra pendiente.
            let mut runs = Vec::new();
            let mut from = 0usize;
            for &end in &reduced.ends {
                let run = &reduced.pts[from..end];
                from = end;
                if run.len() == 1 {
                    // Un tramo de un solo punto se ve como un punto.
                    if run[0].0 >= x_range.0 && run[0].0 <= x_range.1 {
                        runs.push((run.to_vec(), true));
                    }
                    continue;
                }
                let mut clipped = Vec::new();
                clip_x(run, x_range.0, x_range.1, &mut clipped);
                runs.extend(clipped.into_iter().map(|r| (r, false)));
            }
            let mut stroke = PathBuilder::new();
            let mut fill = PathBuilder::new();
            let mut dots: Vec<Point> = Vec::new();
            for (run, dot) in &runs {
                let mut last = Point::default();
                for (k, &(x, y)) in run.iter().enumerate() {
                    // La y fuera del rango la recorta el `clip_rect`; el tope
                    // solo evita coordenadas desorbitadas para Skia.
                    let p = Point::new(xpix(x), ypix(y).clamp(plot.top - FAR, plot.bottom + FAR));
                    if k == 0 {
                        stroke.move_to(p);
                        if area {
                            fill.move_to((p.x, base));
                            fill.line_to(p);
                        }
                    } else {
                        stroke.line_to(p);
                        if area {
                            fill.line_to(p);
                        }
                    }
                    last = p;
                }
                if area {
                    fill.line_to((last.x, base));
                    fill.close();
                }
                if *dot {
                    dots.push(last);
                }
            }
            if area {
                let mut p = Paint::default();
                p.set_anti_alias(true).set_color(alpha(series.color, 0.28));
                canvas.draw_path(&fill.detach(), &p);
            }
            if !stroke.is_empty() {
                let mut p = Paint::default();
                p.set_anti_alias(true)
                    .set_style(PaintStyle::Stroke)
                    .set_stroke_width(chart.stroke_width)
                    .set_stroke_cap(skia_safe::paint::Cap::Round)
                    .set_stroke_join(skia_safe::paint::Join::Round)
                    .set_color(series.color);
                canvas.draw_path(&stroke.detach(), &p);
            }
            if !dots.is_empty() {
                let mut p = Paint::default();
                p.set_anti_alias(true).set_color(series.color);
                for d in dots {
                    canvas.draw_circle(d, (chart.stroke_width / 2.0).max(1.5), &p);
                }
            }
        }
    }
}

/// Leyenda en la franja superior: una muestra de la forma de cada serie y su nombre.
fn draw_legend(canvas: &SkCanvas, chart: &Chart, fonts: &FontCollection) {
    let (size, family) = (chart.label_size, chart.family.as_str());
    let cy = (size * 1.5 + 8.0) / 2.0;
    let mut x = 10.0;
    for (s, name) in chart.series.iter().zip(&chart.names) {
        let mut p = Paint::default();
        p.set_anti_alias(true).set_color(s.color);
        match chart.kind {
            ChartKind::Scatter => {
                canvas.draw_circle((x + chart.point_size, cy), chart.point_size, &p);
                x += chart.point_size * 2.0 + 6.0;
            }
            ChartKind::Bar => {
                let r = Rect::from_xywh(x, cy - 5.0, 10.0, 10.0);
                canvas.draw_rrect(RRect::new_rect_xy(r, 2.0, 2.0), &p);
                x += 16.0;
            }
            ChartKind::Line | ChartKind::Area => {
                if chart.kind == ChartKind::Area {
                    p.set_color(alpha(s.color, 0.28));
                    let r = Rect::from_xywh(x, cy - 5.0, 16.0, 10.0);
                    canvas.draw_rrect(RRect::new_rect_xy(r, 2.0, 2.0), &p);
                    p.set_color(s.color);
                }
                let r = Rect::from_xywh(x, cy - 1.25, 16.0, 2.5);
                canvas.draw_rrect(RRect::new_rect_xy(r, 1.25, 1.25), &p);
                x += 22.0;
            }
        }
        text_at(
            canvas,
            x,
            cy,
            name,
            chart.label_color,
            size,
            500,
            family,
            Align::Left,
            Baseline::Middle,
            fonts,
        );
        x += measure_text(name, size, 500, family, fonts) + 18.0;
    }
}

/// Ancho del hueco de cada punto de una serie de barras, en píxeles. En una
/// barra, `bar_width` es la fracción del hueco que ocupan las barras juntas.
/// `points`: puntos visibles, para el paso medio de una serie con x explícita
/// (con x implícita cada punto ocupa una unidad de la ventana).
fn bar_slot(
    chart: &Chart,
    plot: Rect,
    x_lo: f64,
    x_hi: f64,
    points: usize,
    implicit_x: bool,
) -> f32 {
    let span = (x_hi - x_lo).max(f64::MIN_POSITIVE);
    let unit = if implicit_x {
        1.0
    } else {
        span / (points.max(2) - 1) as f64
    };
    ((unit / span) as f32 * plot.width() * chart.bar_width).max(1.5)
}

/// Multiplica el alfa de un color (rellenos translúcidos del área y la leyenda).
fn alpha(color: Color, factor: f32) -> Color {
    color.with_a((color.a() as f32 * factor).round() as u8)
}
