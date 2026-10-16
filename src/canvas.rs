//! Lienzo de dibujo inmediato (`canvas`): Python graba una lista de comandos
//! (`aurora/canvas.py`) y aquí se convierte, en un solo recorrido, en un
//! `Picture` de Skia. El `Picture` se repinta en cada frame sin volver a Python:
//! solo se graba otra vez si la vista se reconstruye o el lienzo cambia de tamaño.
//!
//! Formato del lote: `(pinceles, comandos)`.
//!
//! - Pincel: `(relleno | None, trazo | None, grosor, cap, join, guiones | None)`,
//!   con los colores ya resueltos (sin tokens `$`). Los comandos lo referencian
//!   por índice: un gráfico con miles de figuras usa unos pocos pinceles.
//! - Comando: tupla cuyo primer elemento es su nombre (`"rect"`, `"line"`…).
//!   Las listas de puntos y los trazados llegan como `bytes` de `f32` nativos
//!   (`array("f")`): se leen sin crear un objeto de Python por coordenada.

use std::collections::{HashMap, HashSet};

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyTuple};
use skia_safe::{
    Canvas, Color, FontStyle, Paint, PaintStyle, PathBuilder, PathEffect, Picture, PictureRecorder,
    Point, RRect, Rect,
    font_style::{Slant, Weight, Width},
    paint::{Cap, Join},
    textlayout::{FontCollection, ParagraphBuilder, ParagraphStyle, TextStyle},
};

use crate::color::parse_color;
use crate::render::Engine;
use crate::spec::{Kind, Node};

/// Relleno y trazo de un pincel: una figura puede tener los dos.
struct Brush {
    fill: Option<Paint>,
    stroke: Option<Paint>,
}

impl Brush {
    fn draw(&self, mut f: impl FnMut(&Paint)) {
        for paint in [&self.fill, &self.stroke].into_iter().flatten() {
            f(paint);
        }
    }
}

fn err(msg: impl Into<String>) -> PyErr {
    PyValueError::new_err(format!("canvas: {}", msg.into()))
}

fn parse_brush(obj: &Bound<'_, PyAny>) -> PyResult<Brush> {
    type Spec = (
        Option<String>,
        Option<String>,
        f32,
        String,
        String,
        Option<Vec<f32>>,
    );
    let (fill, stroke, width, cap, join, dash): Spec = obj.extract()?;
    let fill = fill
        .map(|c| -> PyResult<Paint> {
            let mut p = Paint::default();
            p.set_anti_alias(true).set_color(parse_color(&c)?);
            Ok(p)
        })
        .transpose()?;
    let stroke = stroke
        .map(|c| -> PyResult<Paint> {
            let mut p = Paint::default();
            p.set_anti_alias(true)
                .set_style(PaintStyle::Stroke)
                .set_stroke_width(width.max(0.0))
                .set_color(parse_color(&c)?)
                .set_stroke_cap(match cap.as_str() {
                    "butt" => Cap::Butt,
                    "round" => Cap::Round,
                    "square" => Cap::Square,
                    _ => return Err(err(format!("cap inválido: {cap:?}"))),
                })
                .set_stroke_join(match join.as_str() {
                    "miter" => Join::Miter,
                    "round" => Join::Round,
                    "bevel" => Join::Bevel,
                    _ => return Err(err(format!("join inválido: {join:?}"))),
                });
            if let Some(intervals) = dash {
                if intervals.len() < 2
                    || !intervals.len().is_multiple_of(2)
                    || intervals.iter().any(|v| *v < 0.0)
                {
                    return Err(err(
                        "dash debe tener un número par (≥ 2) de longitudes no negativas",
                    ));
                }
                p.set_path_effect(PathEffect::dash(&intervals, 0.0));
            }
            Ok(p)
        })
        .transpose()?;
    Ok(Brush { fill, stroke })
}

/// Lee `bytes` de `f32` nativos.
fn floats(obj: &Bound<'_, PyAny>) -> PyResult<Vec<f32>> {
    let raw: &[u8] = obj.extract()?;
    if !raw.len().is_multiple_of(4) {
        return Err(err("datos de coordenadas truncados"));
    }
    Ok(raw
        .as_chunks::<4>()
        .0
        .iter()
        .map(|c| f32::from_ne_bytes([c[0], c[1], c[2], c[3]]))
        .collect())
}

fn points(obj: &Bound<'_, PyAny>) -> PyResult<Vec<Point>> {
    let v = floats(obj)?;
    if !v.len().is_multiple_of(2) {
        return Err(err("los puntos deben ser pares (x, y)"));
    }
    Ok(v.as_chunks::<2>()
        .0
        .iter()
        .map(|p| Point::new(p[0], p[1]))
        .collect())
}

/// Verbos de un trazado (`Path` en Python): cuántos números consume cada uno.
const MOVE: u8 = 0;
const LINE: u8 = 1;
const QUAD: u8 = 2;
const CUBIC: u8 = 3;
const CLOSE: u8 = 4;
const ARC: u8 = 5;

fn build_path(verbs: &[u8], data: &[f32]) -> PyResult<skia_safe::Path> {
    let mut b = PathBuilder::new();
    let mut i = 0;
    let mut take = |n: usize| -> PyResult<&[f32]> {
        let s = data
            .get(i..i + n)
            .ok_or_else(|| err("trazado con menos coordenadas que verbos"))?;
        i += n;
        Ok(s)
    };
    for &verb in verbs {
        match verb {
            MOVE => {
                let p = take(2)?;
                b.move_to((p[0], p[1]));
            }
            LINE => {
                let p = take(2)?;
                b.line_to((p[0], p[1]));
            }
            QUAD => {
                let p = take(4)?;
                b.quad_to((p[0], p[1]), (p[2], p[3]));
            }
            CUBIC => {
                let p = take(6)?;
                b.cubic_to((p[0], p[1]), (p[2], p[3]), (p[4], p[5]));
            }
            CLOSE => {
                b.close();
            }
            ARC => {
                let p = take(5)?;
                let (cx, cy, r) = (p[0], p[1], p[2]);
                let oval = Rect::new(cx - r, cy - r, cx + r, cy + r);
                b.arc_to(oval, p[3], p[4], false);
            }
            other => return Err(err(format!("verbo de trazado desconocido: {other}"))),
        }
    }
    Ok(b.detach())
}

/// Lector de los argumentos de un comando, con mensajes que dicen cuál falla.
struct Args<'a, 'py> {
    t: &'a Bound<'py, PyTuple>,
    op: &'a str,
}

impl<'py> Args<'_, 'py> {
    fn item(&self, i: usize) -> PyResult<Bound<'py, PyAny>> {
        self.t
            .get_item(i)
            .map_err(|_| err(format!("faltan argumentos en {:?}", self.op)))
    }

    fn f(&self, i: usize) -> PyResult<f32> {
        self.item(i)?
            .extract()
            .map_err(|_| err(format!("argumento {i} de {:?} no es un número", self.op)))
    }

    fn brush<'b>(&self, i: usize, brushes: &'b [Brush]) -> PyResult<&'b Brush> {
        let idx: usize = self.item(i)?.extract()?;
        brushes
            .get(idx)
            .ok_or_else(|| err(format!("pincel {idx} inexistente")))
    }
}

/// Graba el lote en un `Picture` de `width × height` (coordenadas locales del
/// lienzo, con el origen en la esquina de su caja de contenido).
pub fn record(
    batch: &Bound<'_, PyAny>,
    width: f32,
    height: f32,
    fonts: &FontCollection,
) -> PyResult<Option<Picture>> {
    let (brushes, ops): (Bound<'_, PyList>, Bound<'_, PyList>) = batch
        .extract()
        .map_err(|_| err("el lote debe ser (pinceles, comandos)"))?;
    let brushes = brushes
        .iter()
        .map(|b| parse_brush(&b))
        .collect::<PyResult<Vec<_>>>()?;
    let bounds = Rect::from_wh(width.max(0.0), height.max(0.0));
    let mut recorder = PictureRecorder::new();
    let canvas = recorder.begin_recording(bounds, false);
    let base = canvas.save();
    for op in ops.iter() {
        let t = op
            .cast::<PyTuple>()
            .map_err(|_| err("cada comando debe ser una tupla"))?;
        let name: String = t.get_item(0)?.extract()?;
        let a = Args { t, op: &name };
        draw_op(canvas, &a, &brushes, bounds, fonts)?;
    }
    // Un `save` sin su `restore` no se escapa del lienzo.
    canvas.restore_to_count(base);
    Ok(recorder.finish_recording_as_picture(Some(&bounds)))
}

fn draw_op(
    canvas: &Canvas,
    a: &Args<'_, '_>,
    brushes: &[Brush],
    bounds: Rect,
    fonts: &FontCollection,
) -> PyResult<()> {
    match a.op {
        "rect" => {
            let r = Rect::from_xywh(a.f(1)?, a.f(2)?, a.f(3)?, a.f(4)?);
            let radius = a.f(5)?;
            let rr = RRect::new_rect_xy(r, radius, radius);
            a.brush(6, brushes)?.draw(|p| {
                canvas.draw_rrect(rr, p);
            });
        }
        "oval" => {
            let r = Rect::from_xywh(a.f(1)?, a.f(2)?, a.f(3)?, a.f(4)?);
            a.brush(5, brushes)?.draw(|p| {
                canvas.draw_oval(r, p);
            });
        }
        "circle" => {
            let (c, r) = (Point::new(a.f(1)?, a.f(2)?), a.f(3)?);
            a.brush(4, brushes)?.draw(|p| {
                canvas.draw_circle(c, r, p);
            });
        }
        "line" => {
            let (p1, p2) = (Point::new(a.f(1)?, a.f(2)?), Point::new(a.f(3)?, a.f(4)?));
            a.brush(5, brushes)?.draw(|p| {
                canvas.draw_line(p1, p2, p);
            });
        }
        "arc" => {
            let (cx, cy, r) = (a.f(1)?, a.f(2)?, a.f(3)?);
            let (start, sweep) = (a.f(4)?, a.f(5)?);
            let pie = a.item(6)?.is_truthy()?;
            let oval = Rect::new(cx - r, cy - r, cx + r, cy + r);
            a.brush(7, brushes)?.draw(|p| {
                canvas.draw_arc(oval, start, sweep, pie, p);
            });
        }
        "poly" => {
            let pts = points(&a.item(1)?)?;
            let closed = a.item(2)?.is_truthy()?;
            let brush = a.brush(3, brushes)?;
            if let Some((first, rest)) = pts.split_first() {
                let mut b = PathBuilder::new();
                b.move_to(*first);
                for p in rest {
                    b.line_to(*p);
                }
                if closed {
                    b.close();
                }
                let path = b.detach();
                brush.draw(|p| {
                    canvas.draw_path(&path, p);
                });
            }
        }
        "path" => {
            let verbs: Vec<u8> = a.item(1)?.extract()?;
            let data = floats(&a.item(2)?)?;
            let path = build_path(&verbs, &data)?;
            a.brush(3, brushes)?.draw(|p| {
                canvas.draw_path(&path, p);
            });
        }
        "text" => draw_text(canvas, a, fonts)?,
        "clear" => {
            let color: String = a.item(1)?.extract()?;
            let mut p = Paint::default();
            p.set_color(parse_color(&color)?);
            canvas.draw_rect(bounds, &p);
        }
        "save" => {
            canvas.save();
        }
        "restore" => {
            // Un `restore` de más se ignora (no puede deshacer el estado inicial).
            if canvas.save_count() > 2 {
                canvas.restore();
            }
        }
        "translate" => {
            canvas.translate((a.f(1)?, a.f(2)?));
        }
        "scale" => {
            canvas.scale((a.f(1)?, a.f(2)?));
        }
        "rotate" => {
            canvas.rotate(a.f(1)?, None);
        }
        "clip" => {
            let r = Rect::from_xywh(a.f(1)?, a.f(2)?, a.f(3)?, a.f(4)?);
            canvas.clip_rect(r, None, true);
        }
        other => return Err(err(format!("comando desconocido: {other:?}"))),
    }
    Ok(())
}

/// Alineación horizontal de una línea de texto respecto a su `x`.
#[derive(Clone, Copy)]
pub enum Align {
    Left,
    Center,
    Right,
}

/// Línea base de una línea de texto respecto a su `y`.
#[derive(Clone, Copy)]
pub enum Baseline {
    Top,
    Middle,
    Alphabetic,
    Bottom,
}

fn parse_align(s: &str) -> PyResult<Align> {
    match s {
        "left" => Ok(Align::Left),
        "center" => Ok(Align::Center),
        "right" => Ok(Align::Right),
        other => Err(err(format!("align inválido: {other:?}"))),
    }
}

fn parse_baseline(s: &str) -> PyResult<Baseline> {
    match s {
        "top" => Ok(Baseline::Top),
        "middle" => Ok(Baseline::Middle),
        "alphabetic" => Ok(Baseline::Alphabetic),
        "bottom" => Ok(Baseline::Bottom),
        other => Err(err(format!("baseline inválida: {other:?}"))),
    }
}

/// Párrafo de una línea con esos rasgos (el que dibuja `text_at` y mide `measure_text`).
fn paragraph(
    content: &str,
    color: Color,
    size: f32,
    weight: i32,
    family: &str,
    fonts: &FontCollection,
) -> skia_safe::textlayout::Paragraph {
    let mut ts = TextStyle::new();
    ts.set_color(color)
        .set_font_size(size)
        .set_font_style(FontStyle::new(
            Weight::from(weight),
            Width::NORMAL,
            Slant::Upright,
        ));
    ts.set_font_families(&[family]);
    let mut ps = ParagraphStyle::new();
    ps.set_text_style(&ts);
    let mut builder = ParagraphBuilder::new(&ps, fonts.clone());
    builder.push_style(&ts);
    builder.add_text(content);
    let mut paragraph = builder.build();
    // Una sola línea: sin ancho límite (prácticamente infinito).
    paragraph.layout(1.0e6);
    paragraph
}

/// Ancho de una línea de texto, para colocar etiquetas (ejes de un `chart`, leyenda).
pub fn measure_text(
    content: &str,
    size: f32,
    weight: i32,
    family: &str,
    fonts: &FontCollection,
) -> f32 {
    paragraph(content, Color::BLACK, size, weight, family, fonts).longest_line()
}

/// Dibuja una línea de texto: `align` la coloca respecto a `x` y `baseline`
/// respecto a `y` (`Top`: `y` es su borde superior; `Middle`, su centro;
/// `Alphabetic`, la línea base). Lo usan `canvas` y `chart`.
#[allow(clippy::too_many_arguments)]
pub fn text_at(
    canvas: &Canvas,
    x: f32,
    y: f32,
    content: &str,
    color: Color,
    size: f32,
    weight: i32,
    family: &str,
    align: Align,
    baseline: Baseline,
    fonts: &FontCollection,
) {
    let paragraph = paragraph(content, color, size, weight, family, fonts);
    let dx = match align {
        Align::Left => 0.0,
        Align::Center => -paragraph.longest_line() / 2.0,
        Align::Right => -paragraph.longest_line(),
    };
    let dy = match baseline {
        Baseline::Top => 0.0,
        Baseline::Middle => -paragraph.height() / 2.0,
        Baseline::Alphabetic => -paragraph.alphabetic_baseline(),
        Baseline::Bottom => -paragraph.height(),
    };
    paragraph.paint(canvas, (x + dx, y + dy));
}

/// `("text", x, y, contenido, color, tamaño, peso, familia | None, align, baseline)`.
fn draw_text(canvas: &Canvas, a: &Args<'_, '_>, fonts: &FontCollection) -> PyResult<()> {
    let (x, y) = (a.f(1)?, a.f(2)?);
    let content: String = a.item(3)?.extract()?;
    let color: Color = parse_color(&a.item(4)?.extract::<String>()?)?;
    let size = a.f(5)?;
    let weight = a.f(6)? as i32;
    let family = a
        .item(7)?
        .extract::<Option<String>>()?
        .unwrap_or_else(|| "Inter".to_owned());
    let align = parse_align(&a.item(8)?.extract::<String>()?)?;
    let baseline = parse_baseline(&a.item(9)?.extract::<String>()?)?;
    text_at(
        canvas, x, y, &content, color, size, weight, &family, align, baseline, fonts,
    );
    Ok(())
}

/// Lo último que se grabó de un `canvas`.
struct Drawn {
    /// Función con la que se grabó (se compara por identidad).
    draw: Py<PyAny>,
    size: (f32, f32),
}

/// Decide cuándo volver a llamar a la función `draw` de cada `canvas`. Vive en
/// el `Runtime` (y uno de usar y tirar en `render_png`).
///
/// Se llama tras el layout, cuando ya se conoce el tamaño de cada lienzo:
/// `draw(width, height, force)` se llama si la vista se reconstruyó o si cambió
/// el tamaño. Con `force=False` (misma función, mismo tamaño y ya hay dibujo),
/// Python puede devolver `None` si no cambió ningún `Signal` que leyera: un
/// `canvas` dentro de un `@component` memorizado no se vuelve a grabar.
#[derive(Default)]
pub struct Canvases {
    drawn: HashMap<String, Drawn>,
    rebuilt: bool,
}

impl Canvases {
    /// La vista se reconstruyó: hay que preguntar a todas las funciones `draw`.
    pub fn rebuilt(&mut self) {
        self.rebuilt = true;
    }

    /// Graba los lienzos que lo necesiten. `relayout`: el último `update` rehízo
    /// el layout (puede haber cambiado algún tamaño).
    pub fn draw(&mut self, root: &Node, engine: &mut Engine, relayout: bool) -> PyResult<()> {
        let rebuilt = std::mem::take(&mut self.rebuilt);
        if !rebuilt && !relayout {
            return Ok(());
        }
        let mut nodes = Vec::new();
        collect(root, &mut nodes);
        if nodes.is_empty() && self.drawn.is_empty() {
            return Ok(());
        }
        // Tamaño de la caja de contenido de cada lienzo, según el layout actual.
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
        let result = Python::attach(|py| -> PyResult<()> {
            for node in &nodes {
                let (Some(draw), Some(&size)) = (&node.draw, sizes.get(node.key.as_str())) else {
                    continue;
                };
                let previous = self.drawn.get(&node.key);
                let same = previous.is_some_and(|d| d.draw.is(draw));
                let force = !same || previous.is_some_and(|d| d.size != size);
                if !rebuilt && !force {
                    continue;
                }
                // Se anota antes de llamar: si `draw` falla, no se reintenta en
                // cada frame, sino en la próxima reconstrucción o cambio de tamaño.
                self.drawn.insert(
                    node.key.clone(),
                    Drawn {
                        draw: draw.clone_ref(py),
                        size,
                    },
                );
                let batch = draw.call1(py, (size.0, size.1, force))?;
                if !batch.is_none(py) {
                    engine.record_canvas(&node.key, batch.bind(py), size)?;
                }
            }
            Ok(())
        });
        let alive: HashSet<&str> = nodes.iter().map(|n| n.key.as_str()).collect();
        self.drawn.retain(|k, _| alive.contains(k.as_str()));
        engine.retain_canvases(|k| alive.contains(k));
        result
    }
}

fn collect<'a>(node: &'a Node, out: &mut Vec<&'a Node>) {
    if node.kind == Kind::Canvas {
        out.push(node);
    }
    for child in &node.children {
        collect(child, out);
    }
}
