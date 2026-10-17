//! Grabado perezoso entre frames: cuándo volver a grabar cada `chart`.

use super::*;

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
