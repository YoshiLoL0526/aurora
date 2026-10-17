//! Datos y parseo: la vista sin copia sobre el búfer de Python y el `Chart`.

use super::*;

fn err(msg: impl Into<String>) -> PyErr {
    PyValueError::new_err(format!("chart: {}", msg.into()))
}

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

    pub(super) fn len(&self) -> usize {
        self.len
    }

    /// Valor `i` como `f64`, leído de la memoria del búfer.
    #[inline]
    pub(super) fn value(&self, i: usize) -> f64 {
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
