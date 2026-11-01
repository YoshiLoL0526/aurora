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
//! opciones) o la caja (ver `cache`).
//!
//! El código se reparte por fases: `parse` lee los datos de Python, `view`
//! calcula la ventana y reduce las series, `scale` la escala de los ejes,
//! `paint` dibuja el gráfico y `cache` decide cuándo volver a grabarlo.

use std::collections::{HashMap, HashSet};
use std::sync::{Arc, OnceLock};

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

mod cache;
mod paint;
mod parse;
mod scale;
mod view;

pub use self::cache::Charts;
pub use self::paint::record;
pub use self::parse::{Column, parse};
pub use self::view::{RecordedView, Recording, Window};

use self::scale::*;
use self::view::*;

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

    /// La serie leída directamente como slices de `f64`, si sus búferes lo son.
    fn dense(&self) -> Option<Dense<'_>> {
        let y = self.y.as_f64()?;
        let x = match &self.x {
            Some(x) => Some(x.as_f64()?),
            None => None,
        };
        Some(Dense { x, y })
    }
}

/// Acceso a los puntos de una serie. Los recorridos que tocan cada punto
/// visible en cada frame (LTTB, el rango de y) son genéricos sobre él: con una
/// `Dense` el compilador lee los slices sin decidir el tipo del búfer por punto.
trait Points {
    fn len(&self) -> usize;
    fn x_at(&self, i: usize) -> f64;
    fn y_at(&self, i: usize) -> f64;
}

impl Points for Series {
    #[inline]
    fn len(&self) -> usize {
        Series::len(self)
    }

    #[inline]
    fn x_at(&self, i: usize) -> f64 {
        Series::x_at(self, i)
    }

    #[inline]
    fn y_at(&self, i: usize) -> f64 {
        Series::y_at(self, i)
    }
}

/// Una serie cuyos búferes son `f64` contiguos (ver `Series::dense`).
struct Dense<'a> {
    x: Option<&'a [f64]>,
    y: &'a [f64],
}

impl Points for Dense<'_> {
    #[inline]
    fn len(&self) -> usize {
        self.y.len()
    }

    #[inline]
    fn x_at(&self, i: usize) -> f64 {
        match self.x {
            Some(x) => x[i],
            None => i as f64,
        }
    }

    #[inline]
    fn y_at(&self, i: usize) -> f64 {
        self.y[i]
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
    /// Dominio de los datos, calculado la primera vez que se graba.
    domain: OnceLock<Domain>,
}

/// Lo que se sabe de los datos sin mirar la ventana: el tamaño de la serie más
/// larga, el rango de x y de y de los puntos finitos y el orden de cada serie.
#[derive(Debug)]
struct Domain {
    max_len: usize,
    y: (f64, f64),
    x: (f64, f64),
    orders: Vec<Order>,
}
