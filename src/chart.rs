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
    /// El búfer está en el orden de bytes contrario al de la máquina (p. ej.
    /// un array de numpy `>f8` en x86): cada valor se lee dándole la vuelta.
    swap: bool,
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
        // `ElementType` ignora el orden de bytes del formato (`<`, `>`, `!`):
        // se mira aquí para no leer como basura los arrays de otro endianness.
        let big = match buf.format().to_bytes().first() {
            Some(b'>' | b'!') => Some(true),
            Some(b'<') => Some(false),
            _ => None,
        };
        let swap = big.is_some_and(|big| big != cfg!(target_endian = "big"));
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
            swap,
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
        // Lee un entero del ancho de `$t`, dándole la vuelta si hace falta.
        macro_rules! read {
            ($t:ty) => {{
                let v = unsafe { p.cast::<$t>().read_unaligned() };
                if self.swap { v.swap_bytes() } else { v }
            }};
        }
        match self.num {
            Num::F64 => f64::from_bits(read!(u64)),
            Num::F32 => f32::from_bits(read!(u32)) as f64,
            Num::I64 => read!(i64) as f64,
            Num::I32 => read!(i32) as f64,
            Num::I16 => read!(i16) as f64,
            Num::I8 => read!(i8) as f64,
            Num::U64 => read!(u64) as f64,
            Num::U32 => read!(u32) as f64,
            Num::U16 => read!(u16) as f64,
            Num::U8 => read!(u8) as f64,
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
    /// Zoom (rueda) y pan (arrastre) sobre el eje x; el doble clic vuelve a la
    /// vista completa. Ver `Charts`.
    pub zoom: bool,
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
        zoom: get(d, "zoom")?
            .map(|v| v.is_truthy())
            .transpose()?
            .unwrap_or(false),
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
// Reducción (downsampling) y ventana visible (zoom y pan)
// ---------------------------------------------------------------------------

/// Puntos por píxel que se conservan al reducir una serie: dos bastan para que
/// el trazo no pierda picos ni escalones.
const POINTS_PER_PX: f64 = 2.0;

/// Píxeles que puede salirse un punto de la línea por arriba o por abajo antes
/// de topar (lo de fuera lo recorta el `clip_rect`; el tope solo evita
/// coordenadas desorbitadas, que Skia no maneja bien en `f32`).
const FAR: f32 = 100_000.0;

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
fn clamp_window(w: Window, (d0, d1): (f64, f64)) -> Window {
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
enum Order {
    Asc,
    Desc,
    Mixed,
}

/// Cómo recorrer los puntos de una serie en esta grabación.
#[derive(Clone, Copy, Debug)]
enum Span {
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
    fn bounds(self, len: usize) -> (usize, usize) {
        match self {
            Span::All => (0, len),
            Span::Indices(a, b) => (a.min(len), b.min(len)),
            Span::Filtered(..) => (0, len),
        }
    }

    /// Si un punto con x `x` cae dentro del tramo (solo filtra `Filtered`).
    fn visible(self, x: f64) -> bool {
        match self {
            Span::Filtered(a, b) => x >= a && x <= b,
            _ => true,
        }
    }
}

/// Los índices de `span`, en orden. Con `margins` se añade un punto a cada lado
/// (solo con `Indices`): el segmento que cruza el borde de la ventana se sigue
/// dibujando.
fn each(span: Span, len: usize, margins: bool) -> std::ops::Range<usize> {
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
fn span_of(series: &Series, window: Option<Window>, order: Order) -> Span {
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
fn visible_y(chart: &Chart, spans: &[Span], x0: f64, x1: f64) -> (f64, f64) {
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
struct Curves {
    pts: Vec<(f64, f64)>,
    ends: Vec<usize>,
}

/// Reduce una serie a lo que hay que dibujar: recorta a la ventana, corta la
/// línea en los valores que faltan (los `NaN`) y, cuando un tramo tiene más
/// puntos que `budget` (su ancho en pantalla), lo reduce con LTTB.
fn curves(series: &Series, span: Span, budget: impl Fn(f64, f64) -> usize) -> Curves {
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
fn clip_x(run: &[(f64, f64)], x0: f64, x1: f64, out: &mut Vec<Vec<(f64, f64)>>) {
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

// ---------------------------------------------------------------------------
// Grabado: de los datos a un `Picture` de Skia
// ---------------------------------------------------------------------------

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
    /// El eje x, el dominio y la ventana de esa grabación. `None`: la caja aún
    /// era demasiado pequeña para grabar.
    view: Option<RecordedView>,
}

/// Decide cuándo volver a grabar cada `chart` y guarda su ventana visible
/// (zoom y pan). Vive en el `Runtime` (y uno de usar y tirar en `render_png`).
///
/// Se llama tras el layout, cuando ya se conoce el tamaño de cada gráfico. Solo
/// se graba si el `Chart` es otro (la vista se reconstruyó con otros datos u
/// opciones), si cambió la caja o si su ventana cambió (zoom o pan): en hover,
/// scroll y animaciones de otros nodos no se hace nada.
#[derive(Default)]
pub struct Charts {
    drawn: HashMap<String, Drawn>,
    /// Ventana visible de cada `chart` con zoom, por key. Es lo último que
    /// pidió el usuario; se recorta al dominio al grabar.
    windows: HashMap<String, Window>,
    /// `chart`s cuya ventana cambió: hay que volver a grabarlos aunque los
    /// datos y la caja sean los mismos.
    dirty: HashSet<String>,
    rebuilt: bool,
}

impl Charts {
    /// La vista se reconstruyó: puede haber gráficos con datos nuevos.
    pub fn rebuilt(&mut self) {
        self.rebuilt = true;
    }

    /// Ventana visible del eje x de `key` (en unidades de datos), o `None` si
    /// no hay un gráfico grabado con esa key.
    pub fn view(&self, key: &str) -> Option<(f64, f64)> {
        let view = self.drawn.get(key)?.view?;
        let w = self.windows.get(key).map_or(
            Window {
                x0: view.window.0,
                x1: view.window.1,
            },
            |w| clamp_window(*w, view.domain),
        );
        (w.x1 > w.x0).then_some((w.x0, w.x1))
    }

    /// Área de dibujo del eje x de `key`, en coordenadas locales de la caja de
    /// contenido (la que recibe el puntero).
    pub fn plot(&self, key: &str) -> Option<Rect> {
        self.drawn.get(key)?.view.map(|v| v.plot)
    }

    /// Acerca (`factor` < 1) alrededor de la fracción `t` (0..1) del ancho del
    /// eje x: el dato que hay bajo el puntero se queda donde está. Devuelve si
    /// algo cambió (`false`: ya está en el tope, el scroll puede seguir).
    pub fn zoom(&mut self, key: &str, t: f32, factor: f64) -> bool {
        let Some((x0, x1)) = self.view(key) else {
            return false;
        };
        let anchor = x0 + f64::from(t.clamp(0.0, 1.0)) * (x1 - x0);
        let (a, b) = (
            anchor + (x0 - anchor) * factor,
            anchor + (x1 - anchor) * factor,
        );
        self.set_window(key, a, b)
    }

    /// Desplaza la ventana `dx` píxeles: el contenido sigue al puntero.
    pub fn pan(&mut self, key: &str, dx: f32) -> bool {
        let Some(view) = self.drawn.get(key).and_then(|d| d.view) else {
            return false;
        };
        let Some((x0, x1)) = self.view(key) else {
            return false;
        };
        let shift = -f64::from(dx) * (x1 - x0) / f64::from(view.plot.width().max(1.0));
        self.set_window(key, x0 + shift, x1 + shift)
    }

    /// Vuelve a la vista completa (dominio entero).
    pub fn reset(&mut self, key: &str) -> bool {
        let changed = self.windows.remove(key).is_some();
        if changed {
            self.dirty.insert(key.to_owned());
        }
        changed
    }

    /// Guarda una ventana nueva, recortada al dominio de la última grabación.
    fn set_window(&mut self, key: &str, a: f64, b: f64) -> bool {
        if !(a.is_finite() && b.is_finite()) {
            return false;
        }
        let Some(view) = self.drawn.get(key).and_then(|d| d.view) else {
            return false;
        };
        let window = clamp_window(Window { x0: a, x1: b }, view.domain);
        if at_most(window.x1, window.x0) {
            return false;
        }
        let current = self.view(key).unwrap_or(view.window);
        if window.x0 == current.0 && window.x1 == current.1 {
            return false;
        }
        self.windows.insert(key.to_owned(), window);
        self.dirty.insert(key.to_owned());
        true
    }

    /// Graba los gráficos que lo necesiten, con su ventana visible (si la
    /// tienen) y devuelve el `Picture` al `Engine`.
    pub fn draw(&mut self, root: &Node, engine: &mut Engine, relayout: bool) -> PyResult<()> {
        if !std::mem::take(&mut self.rebuilt) && !relayout && self.dirty.is_empty() {
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
                let dirty = self.dirty.remove(&node.key);
                let previous = self.drawn.get(&node.key);
                let same = previous.is_some_and(|d| Arc::ptr_eq(&d.data, data) && d.size == size);
                if same && !dirty {
                    continue;
                }
                let recording = record(
                    data,
                    self.windows.get(&node.key).copied(),
                    size.0,
                    size.1,
                    engine.fonts(),
                );
                engine.record_chart(&node.key, recording.picture);
                let view = recording.view.or_else(|| previous.and_then(|d| d.view));
                self.drawn.insert(
                    node.key.clone(),
                    Drawn {
                        data: data.clone(),
                        size,
                        view,
                    },
                );
            }
            Ok(())
        });
        let alive: HashSet<&str> = nodes.iter().map(|n| n.key.as_str()).collect();
        self.drawn.retain(|k, _| alive.contains(k.as_str()));
        self.windows.retain(|k, _| alive.contains(k.as_str()));
        self.dirty.retain(|k| alive.contains(k.as_str()));
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
