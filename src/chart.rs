//! Gráficos nativos (`chart`): línea, área, barras y dispersión.
//!
//! Los datos llegan **sin copiarse**: Python pasa objetos que exponen el
//! protocolo de búfer (arrays de numpy, `array.array`, `memoryview`; las Series
//! y DataFrames de polars o pandas se convierten con `to_numpy`, que comparte
//! memoria) y aquí se toma una vista que lee sus valores directamente de la
//! memoria, con sus *strides* (columnas de una matriz, vistas invertidas…).
//! La vista mantiene con vida al objeto de Python, así que su memoria no se
//! libera mientras el gráfico exista.
//!
//! El dibujo se graba en un `Picture` de Skia con el tamaño de la caja del nodo:
//! a partir de ahí se repinta sin volver a Python ni releer los datos. Se vuelve
//! a grabar solo si cambia el `Chart` (la vista se reconstruyó con otros datos u
//! opciones) o la caja (ver `Charts`).

use std::collections::{HashMap, HashSet};
use std::sync::Arc;

use pyo3::buffer::{ElementType, PyUntypedBuffer};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use skia_safe::{
    Canvas as SkCanvas, Color, Paint, PaintStyle, PathBuilder, PathEffect, Picture,
    PictureRecorder, Point, RRect, Rect, textlayout::FontCollection,
};

use crate::canvas::{Align, Baseline, measure_text, text_at};
use crate::color::parse_color;
use crate::render::Engine;
use crate::spec::Node;

fn err(msg: impl Into<String>) -> PyErr {
    PyValueError::new_err(format!("chart: {}", msg.into()))
}

/// Divisiones a las que se apunta en el eje y (el algoritmo las ajusta a un paso
/// de 1, 2 o 5 por una potencia de 10, así que salen entre 4 y 6).
const Y_TICKS: f64 = 5.0;
/// Separación mínima entre etiquetas del eje x, en píxeles lógicos.
const X_LABEL_GAP: f32 = 70.0;
/// Tope de ticks por eje (con límites fijos y un paso muy fino).
const MAX_TICKS: usize = 200;

// ---------------------------------------------------------------------------
// Datos: vista sin copia sobre un búfer numérico de Python
// ---------------------------------------------------------------------------

/// Tipos de elemento que se leen directamente de memoria.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Num {
    F64,
    F32,
    I64,
    I32,
    I16,
    I8,
    U64,
    U32,
    U16,
    U8,
}

/// Vista de solo lectura sobre un búfer numérico de Python.
///
/// `PyUntypedBuffer` mantiene con vida al exportador (el ndarray, el
/// `array.array`…) y da la dirección, la longitud y los *strides*; los valores se
/// leen de esa misma memoria: no se copia el array ni se itera desde Python.
#[derive(Debug)]
pub struct Column {
    /// El búfer: mantiene viva la memoria y la libera al soltarse la vista.
    _buf: PyUntypedBuffer,
    num: Num,
    /// Primer elemento de la vista (PEP 3118) y salto entre elementos, en bytes.
    base: *const u8,
    stride: isize,
    len: usize,
}

// La vista solo se lee (siempre con el GIL tomado, ver `Charts::draw`) y la
// memoria pertenece al objeto de Python que la exporta, que sigue vivo.
unsafe impl Send for Column {}
unsafe impl Sync for Column {}

impl Column {
    /// Toma una vista del búfer de `obj`, sin copiarlo ni convertirlo.
    /// `column`: columna de un búfer 2-D `(n, m)` (una serie por columna).
    fn acquire(obj: &Bound<'_, PyAny>, column: usize) -> PyResult<Column> {
        let buf = PyUntypedBuffer::get(obj).map_err(|_| {
            err(
                "los datos deben exponer el protocolo de búfer (numpy, array.array, memoryview…); \
                 con polars o pandas, `.to_numpy()`",
            )
        })?;
        if buf.suboffsets().is_some_and(|s| !s.is_empty()) {
            return Err(err("no se admiten búferes indirectos (con suboffsets)"));
        }
        let num = match ElementType::from_format(buf.format()) {
            ElementType::Float { bytes: 8 } => Num::F64,
            ElementType::Float { bytes: 4 } => Num::F32,
            ElementType::SignedInteger { bytes: 8 } => Num::I64,
            ElementType::SignedInteger { bytes: 4 } => Num::I32,
            ElementType::SignedInteger { bytes: 2 } => Num::I16,
            ElementType::SignedInteger { bytes: 1 } => Num::I8,
            ElementType::UnsignedInteger { bytes: 8 } => Num::U64,
            ElementType::UnsignedInteger { bytes: 4 } => Num::U32,
            ElementType::UnsignedInteger { bytes: 2 } => Num::U16,
            ElementType::UnsignedInteger { bytes: 1 } => Num::U8,
            _ => {
                return Err(err(
                    "tipo de dato no soportado (usa números: float o entero)",
                ));
            }
        };
        let base = buf.buf_ptr() as *const u8;
        let (len, stride, base) = match buf.dimensions() {
            1 if column == 0 => (buf.shape()[0], buf.strides()[0], base),
            2 => {
                let (rows, cols) = (buf.shape()[0], buf.shape()[1]);
                if column >= cols {
                    return Err(err(format!(
                        "no existe la columna {column} (el búfer tiene {cols})"
                    )));
                }
                // La columna `column` arranca `strides[1]` bytes más allá y sus
                // valores se leen con el stride de las filas (C u Fortran, da igual).
                let offset = buf.strides()[1].wrapping_mul(column as isize);
                (rows, buf.strides()[0], base.wrapping_offset(offset))
            }
            n => {
                return Err(err(format!(
                    "los datos deben ser 1-D o 2-D (tienen {n} dimensiones)"
                )));
            }
        };
        Ok(Column {
            num,
            base,
            stride,
            len,
            _buf: buf,
        })
    }

    fn len(&self) -> usize {
        self.len
    }

    /// Valor `i` como `f64`, leído de la memoria del búfer.
    #[inline]
    fn value(&self, i: usize) -> f64 {
        debug_assert!(i < self.len);
        // Seguridad: `len`, `stride` y `base` vienen del búfer, que sigue vivo
        // mientras exista esta vista; `i < len` mantiene la lectura dentro de la
        // memoria del exportador. `read_unaligned` cubre búferes sin alinear.
        let p = self
            .base
            .wrapping_offset(self.stride.wrapping_mul(i as isize));
        unsafe {
            match self.num {
                Num::F64 => p.cast::<f64>().read_unaligned(),
                Num::F32 => p.cast::<f32>().read_unaligned() as f64,
                Num::I64 => p.cast::<i64>().read_unaligned() as f64,
                Num::I32 => p.cast::<i32>().read_unaligned() as f64,
                Num::I16 => p.cast::<i16>().read_unaligned() as f64,
                Num::I8 => p.cast::<i8>().read_unaligned() as f64,
                Num::U64 => p.cast::<u64>().read_unaligned() as f64,
                Num::U32 => p.cast::<u32>().read_unaligned() as f64,
                Num::U16 => p.cast::<u16>().read_unaligned() as f64,
                Num::U8 => p.cast::<u8>().read_unaligned() as f64,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// El gráfico, tal como llega en el dict de la vista
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ChartKind {
    Line,
    Area,
    Bar,
    Scatter,
}

/// Una serie de datos: `y` obligatoria y `x` opcional (por defecto, 0, 1, 2…).
#[derive(Debug)]
pub struct Series {
    x: Option<Column>,
    y: Column,
    color: Color,
}

impl Series {
    fn len(&self) -> usize {
        self.y.len()
    }

    #[inline]
    fn x_at(&self, i: usize) -> f64 {
        match &self.x {
            Some(x) => x.value(i),
            None => i as f64,
        }
    }

    #[inline]
    fn y_at(&self, i: usize) -> f64 {
        self.y.value(i)
    }
}

/// Un gráfico completo: sus series y el aspecto de los ejes.
#[derive(Debug)]
pub struct Chart {
    kind: ChartKind,
    series: Vec<Series>,
    /// Etiquetas del eje x, una por punto (sin ellas, ticks numéricos).
    labels: Vec<String>,
    /// Nombre de cada serie para la leyenda (vacío: sin leyenda).
    names: Vec<String>,
    /// Límites del eje y; `None` los deduce de los datos.
    y_min: Option<f64>,
    y_max: Option<f64>,
    grid: bool,
    stroke_width: f32,
    point_size: f32,
    bar_width: f32,
    label_size: f32,
    label_color: Color,
    grid_color: Color,
    family: String,
}
/// Convierte el dict que envía `aurora/charts.py` en un `Chart`.
pub fn parse(d: &Bound<'_, PyDict>) -> PyResult<Chart> {
    let kind = match str_of(d, "kind")?.as_deref() {
        Some("area") => ChartKind::Area,
        Some("bar") => ChartKind::Bar,
        Some("scatter") => ChartKind::Scatter,
        Some("line") | None => ChartKind::Line,
        Some(other) => return Err(err(format!("kind desconocido: {other:?}"))),
    };

    let Some(series_obj) = get(d, "series")? else {
        return Err(err("faltan las series"));
    };
    let mut series = Vec::new();
    for item in series_obj.cast::<PyList>()?.iter() {
        let t = item.cast::<PyTuple>()?;
        if t.len() != 3 {
            return Err(err(
                "cada serie debe ser (x | None, (búfer, columna), color)",
            ));
        }
        let x = match t.get_item(0)? {
            x if x.is_none() => None,
            x => {
                let (obj, column): (Bound<'_, PyAny>, usize) = x.extract()?;
                Some(Column::acquire(&obj, column)?)
            }
        };
        let (obj, column): (Bound<'_, PyAny>, usize) = t.get_item(1)?.extract()?;
        let y = Column::acquire(&obj, column)?;
        if let Some(x) = &x
            && x.len() != y.len()
        {
            return Err(err(format!(
                "x tiene {} valores y la serie {}; deben coincidir",
                x.len(),
                y.len()
            )));
        }
        let color = parse_color(&t.get_item(2)?.extract::<String>()?)?;
        series.push(Series { x, y, color });
    }
    if series.is_empty() {
        return Err(err("no hay ninguna serie"));
    }

    let strings = |key: &str| -> PyResult<Vec<String>> {
        Ok(match get(d, key)? {
            Some(list) => list.extract::<Vec<String>>()?,
            None => Vec::new(),
        })
    };
    let labels = strings("labels")?;
    if !labels.is_empty()
        && let Some(s) = series.iter().find(|s| s.len() != labels.len())
    {
        return Err(err(format!(
            "hay {} etiquetas y una serie de {} puntos; deben coincidir",
            labels.len(),
            s.len()
        )));
    }
    let names = strings("names")?;
    if !names.is_empty() && names.len() != series.len() {
        return Err(err(format!(
            "hay {} nombres y {} series; deben coincidir",
            names.len(),
            series.len()
        )));
    }

    let (y_min, y_max) = (f_of(d, "y_min")?, f_of(d, "y_max")?);
    for (name, bound) in [("y_min", y_min), ("y_max", y_max)] {
        if let Some(v) = bound
            && !v.is_finite()
        {
            return Err(err(format!("{name} debe ser un número finito")));
        }
    }
    if let (Some(lo), Some(hi)) = (y_min, y_max)
        && at_most(hi, lo)
    {
        return Err(err("y_max debe ser mayor que y_min"));
    }

    Ok(Chart {
        kind,
        series,
        labels,
        names,
        y_min,
        y_max,
        grid: get(d, "grid")?
            .map(|v| v.is_truthy())
            .transpose()?
            .unwrap_or(true),
        stroke_width: f32_of(d, "stroke_width")?.unwrap_or(2.0).max(0.0),
        point_size: f32_of(d, "point_size")?.unwrap_or(3.5).max(0.5),
        bar_width: f32_of(d, "bar_width")?.unwrap_or(0.7).clamp(0.05, 1.0),
        label_size: f32_of(d, "label_size")?.unwrap_or(11.0).max(1.0),
        label_color: parse_color(&str_of(d, "label_color")?.unwrap_or_else(|| "#8A91A8".into()))?,
        grid_color: parse_color(&str_of(d, "grid_color")?.unwrap_or_else(|| "#252B3B".into()))?,
        family: str_of(d, "family")?.unwrap_or_else(|| "Inter".into()),
    })
}

fn get<'py>(d: &Bound<'py, PyDict>, key: &str) -> PyResult<Option<Bound<'py, PyAny>>> {
    Ok(d.get_item(key)?.filter(|v| !v.is_none()))
}

fn str_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<String>> {
    get(d, key)?.map(|v| v.extract::<String>()).transpose()
}

fn f_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<f64>> {
    get(d, key)?.map(|v| v.extract::<f64>()).transpose()
}

fn f32_of(d: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<f32>> {
    get(d, key)?.map(|v| v.extract::<f32>()).transpose()
}

// ---------------------------------------------------------------------------
// Grabado: de los datos a un `Picture` de Skia
// ---------------------------------------------------------------------------

/// Graba el gráfico con el tamaño de su caja. `None` si la caja es demasiado
/// pequeña para dibujar nada (el nodo se queda con su fondo y su borde).
pub fn record(chart: &Chart, width: f32, height: f32, fonts: &FontCollection) -> Option<Picture> {
    if width < 2.0 || height < 2.0 {
        return None;
    }
    let bounds = Rect::from_wh(width, height);
    let mut recorder = PictureRecorder::new();
    let canvas = recorder.begin_recording(bounds, false);
    paint(canvas, chart, width, height, fonts);
    recorder.finish_recording_as_picture(Some(&bounds))
}

fn paint(canvas: &SkCanvas, chart: &Chart, width: f32, height: f32, fonts: &FontCollection) {
    let (size, family) = (chart.label_size, chart.family.as_str());

    // --- dominio de los datos ----------------------------------------------
    let mut max_len = 0usize;
    let (mut y_lo, mut y_hi) = (f64::INFINITY, f64::NEG_INFINITY);
    let (mut x_lo, mut x_hi) = (f64::INFINITY, f64::NEG_INFINITY);
    for s in &chart.series {
        max_len = max_len.max(s.len());
        for i in 0..s.len() {
            let (x, v) = (s.x_at(i), s.y_at(i));
            if x.is_finite() && v.is_finite() {
                y_lo = y_lo.min(v);
                y_hi = y_hi.max(v);
                x_lo = x_lo.min(x);
                x_hi = x_hi.max(x);
            }
        }
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
    draw_x_labels(canvas, chart, fonts, plot, x_lo, x_hi, &xpix);

    // --- series --------------------------------------------------------------
    canvas.save();
    canvas.clip_rect(plot, None, true);
    let slot = bar_slot(chart, plot, x_lo, x_hi, max_len, implicit_x);
    let total = chart.series.len();
    for (index, s) in chart.series.iter().enumerate() {
        draw_series(canvas, chart, s, plot, &xpix, &ypix, slot, index, total);
    }
    canvas.restore();

    // --- leyenda -------------------------------------------------------------
    if !chart.names.is_empty() {
        draw_legend(canvas, chart, fonts);
    }
}

/// Etiquetas del eje x: las de `labels`, o ticks numéricos del dominio. Se
/// saltan las que no caben (con al menos `X_LABEL_GAP` px entre ellas) y las de
/// los extremos se separan del borde lo justo para verse enteras.
fn draw_x_labels(
    canvas: &SkCanvas,
    chart: &Chart,
    fonts: &FontCollection,
    plot: Rect,
    x_lo: f64,
    x_hi: f64,
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
        for (i, l) in chart.labels.iter().enumerate() {
            place(xpix(i as f64), l);
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

/// Dibuja una serie: la línea (o el área), las barras o los puntos.
/// `slot`: ancho del hueco de cada punto en las barras; `index`/`total`: qué
/// serie es y cuántas hay (las barras de varias series van agrupadas).
#[allow(clippy::too_many_arguments)]
fn draw_series(
    canvas: &SkCanvas,
    chart: &Chart,
    series: &Series,
    plot: Rect,
    xpix: &impl Fn(f64) -> f32,
    ypix: &impl Fn(f64) -> f32,
    slot: f32,
    index: usize,
    total: usize,
) {
    let len = series.len();
    // Tramos de valores finitos: un `move_to` cada vez que un valor que falta
    // interrumpe la serie (la línea no une puntos a través de un hueco).
    let mut runs: Vec<(usize, usize)> = Vec::new();
    let mut start: Option<usize> = None;
    for i in 0..len {
        let ok = series.x_at(i).is_finite() && series.y_at(i).is_finite();
        match (ok, start) {
            (true, None) => start = Some(i),
            (false, Some(s)) => {
                runs.push((s, i));
                start = None;
            }
            _ => {}
        }
    }
    if let Some(s) = start {
        runs.push((s, len));
    }
    let px_of = |i: usize| xpix(series.x_at(i));
    let py_of = |i: usize| ypix(series.y_at(i));

    match chart.kind {
        ChartKind::Scatter => {
            let mut path = PathBuilder::new();
            for &(s0, s1) in &runs {
                for i in s0..s1 {
                    let (x, y) = (px_of(i), py_of(i));
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
            for &(s0, s1) in &runs {
                for i in s0..s1 {
                    let x = (px_of(i) + offset).clamp(plot.left, plot.right);
                    let y = py_of(i).clamp(plot.top, plot.bottom);
                    let (t, h) = (base.min(y), (base - y).abs().max(1.0));
                    let r = Rect::from_xywh(x - half, t, half * 2.0, h);
                    path.add_rrect(RRect::new_rect_xy(r, radius, radius), None, None);
                }
            }
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(series.color);
            canvas.draw_path(&path.detach(), &p);
        }
        ChartKind::Line | ChartKind::Area => {
            let area = chart.kind == ChartKind::Area;
            let base = ypix(0.0).clamp(plot.top, plot.bottom);
            let mut stroke = PathBuilder::new();
            let mut fill = PathBuilder::new();
            let mut dots: Vec<Point> = Vec::new();
            for &(s0, s1) in &runs {
                let mut last = Point::default();
                for i in s0..s1 {
                    let p = Point::new(
                        px_of(i).clamp(plot.left, plot.right),
                        py_of(i).clamp(plot.top, plot.bottom),
                    );
                    if i == s0 {
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
                if s1 - s0 == 1 {
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
            // Una serie de un solo valor se ve como un punto.
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

/// Ancho del hueco de cada punto de una serie de barras, en píxeles (en una
/// barra, `bar_width` es la fracción del hueco que ocupan las barras juntas).
fn bar_slot(
    chart: &Chart,
    plot: Rect,
    x_lo: f64,
    x_hi: f64,
    points: usize,
    implicit_x: bool,
) -> f32 {
    let step = if implicit_x {
        // El dominio es justo `points` unidades de ancho.
        plot.width() / points.max(1) as f32
    } else {
        let data_step = (x_hi - x_lo) / (points.max(2) - 1) as f64;
        (data_step / (x_hi - x_lo)) as f32 * plot.width()
    };
    (step * chart.bar_width).max(1.5)
}

/// Multiplica el alfa de un color (rellenos translúcidos del área y la leyenda).
fn alpha(color: Color, factor: f32) -> Color {
    color.with_a((color.a() as f32 * factor).round() as u8)
}

// --- escala de los ejes -----------------------------------------------------

/// `true` si `a <= b`, y también si alguno es NaN (un eje sin datos válidos:
/// el dibujo degenera en una franja en vez de en números imposibles).
fn at_most(a: f64, b: f64) -> bool {
    a.partial_cmp(&b) != Some(std::cmp::Ordering::Greater)
}

/// Paso "bonito" (1, 2 o 5 por una potencia de 10) para cubrir `span` con unas
/// `target` divisiones.
fn nice_step(span: f64, target: f64) -> f64 {
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
fn snap(v: f64, step: f64, up: bool) -> f64 {
    let q = v / step;
    if (q - q.round()).abs() < 1e-9 {
        return v;
    }
    let k = if up { q.ceil() } else { q.floor() };
    k * step
}

/// Múltiplos de `step` dentro de `[lo, hi]`, de `lo` hacia arriba.
fn ticks_between(lo: f64, hi: f64, step: f64) -> Vec<f64> {
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
fn tick_unit(lo: f64, hi: f64) -> f64 {
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
fn format_tick(v: f64, step: f64, unit: f64) -> String {
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

// ---------------------------------------------------------------------------
// Grabado perezoso entre frames
// ---------------------------------------------------------------------------

/// Lo último que se grabó de un `chart`.
struct Drawn {
    /// El `Chart` con el que se grabó (se compara por identidad: un nodo
    /// memorizado por un `@component` reutiliza el mismo).
    data: Arc<Chart>,
    size: (f32, f32),
}

/// Decide cuándo volver a grabar cada `chart`. Vive en el `Runtime` (y uno de
/// usar y tirar en `render_png`).
///
/// Se llama tras el layout, cuando ya se conoce el tamaño de cada gráfico. Solo
/// se graba si el `Chart` es otro (la vista se reconstruyó con otros datos u
/// opciones) o si cambió la caja: en hover, scroll y animaciones de otros nodos
/// no se hace nada.
#[derive(Default)]
pub struct Charts {
    drawn: HashMap<String, Drawn>,
    rebuilt: bool,
}

impl Charts {
    /// La vista se reconstruyó: puede haber gráficos con datos nuevos.
    pub fn rebuilt(&mut self) {
        self.rebuilt = true;
    }

    /// Graba los gráficos que lo necesiten. `relayout`: el último `update`
    /// rehízo el layout (puede haber cambiado algún tamaño).
    pub fn draw(&mut self, root: &Node, engine: &mut Engine, relayout: bool) -> PyResult<()> {
        if !std::mem::take(&mut self.rebuilt) && !relayout {
            return Ok(());
        }
        let mut nodes = Vec::new();
        collect(root, &mut nodes);
        if nodes.is_empty() && self.drawn.is_empty() {
            return Ok(());
        }
        // Tamaño de la caja de contenido de cada gráfico, según el layout actual.
        let sizes: HashMap<&str, (f32, f32)> = {
            let rects = engine.node_rects();
            nodes
                .iter()
                .filter_map(|n| {
                    let rect = rects.get(n.key.as_str())?;
                    Some((n.key.as_str(), crate::render::content_size(n, *rect)))
                })
                .collect()
        };
        // Leer la memoria de los búferes con el GIL tomado: mientras se graba,
        // ningún otro hilo de Python puede estar escribiendo en ellos.
        let result = Python::attach(|_py| -> PyResult<()> {
            for node in &nodes {
                let (Some(data), Some(&size)) = (&node.chart, sizes.get(node.key.as_str())) else {
                    continue;
                };
                let same = self
                    .drawn
                    .get(&node.key)
                    .is_some_and(|d| Arc::ptr_eq(&d.data, data) && d.size == size);
                if same {
                    continue;
                }
                let picture = record(data, size.0, size.1, engine.fonts());
                engine.record_chart(&node.key, picture);
                self.drawn.insert(
                    node.key.clone(),
                    Drawn {
                        data: data.clone(),
                        size,
                    },
                );
            }
            Ok(())
        });
        let alive: HashSet<&str> = nodes.iter().map(|n| n.key.as_str()).collect();
        self.drawn.retain(|k, _| alive.contains(k.as_str()));
        engine.retain_charts(|k| alive.contains(k));
        result
    }
}

fn collect<'a>(node: &'a Node, out: &mut Vec<&'a Node>) {
    if node.chart.is_some() {
        out.push(node);
    }
    for child in &node.children {
        collect(child, out);
    }
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
