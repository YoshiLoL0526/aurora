//! Texto: párrafos «shapeados» de Skia y su medición para el layout.

use super::*;

/// Contexto de las hojas del árbol de layout.
pub enum Leaf {
    Text(TextCtx),
    /// Imagen: su tamaño natural, para medirla manteniendo la proporción.
    Image(skia_safe::Size),
}

/// Contexto de los nodos hoja de texto: el párrafo ya "shapeado" se reutiliza
/// para medir (durante el layout) y para pintar.
pub struct TextCtx {
    pub(super) paragraph: Paragraph,
    /// Lo que determina el párrafo: permite reutilizarlo en el siguiente layout.
    pub(super) key: ParagraphKey,
    /// Solo en campos de texto: cómo se mide y se maqueta el párrafo.
    pub(super) input: Option<InputLeaf>,
    /// Mediciones ya hechas. Taffy mide cada hoja varias veces por layout (mín.,
    /// máx., definitivo…) y cada medición rehace el layout del párrafo en Skia:
    /// memorizarlas, y conservarlas con el párrafo entre frames, lo evita.
    pub(super) measures: Vec<Measured>,
    /// Ancho con el que está maquetado el párrafo ahora mismo, si se conoce:
    /// `finalize_text` no lo repite si ya coincide.
    pub(super) laid_out: Option<f32>,
}

/// Una medición memorizada: restricciones de Taffy → tamaño y baseline.
#[derive(Clone, Copy)]
pub(super) struct Measured {
    pub(super) key: MeasureKey,
    pub(super) size: Size<f32>,
    pub(super) baseline: f32,
}

/// Restricciones de una medición. El alto disponible no influye en el texto.
#[derive(Clone, Copy, PartialEq)]
pub(super) struct MeasureKey {
    pub(super) known: Size<Option<f32>>,
    pub(super) avail_width: AvailableSpace,
    /// El mismo párrafo se mide distinto en un campo de texto.
    pub(super) input: Option<InputLeaf>,
}

/// Mediciones que se memorizan por párrafo (los textos rara vez pasan de 3 o 4).
pub(super) const MAX_MEASURES: usize = 8;

/// Todo lo que determina el shaping de un párrafo. Dos párrafos con la misma
/// clave son intercambiables, así que al rehacer el layout se reutilizan por
/// contenido (no por key): sobreviven a reordenaciones y a keys de ruta.
#[derive(Clone, PartialEq, Eq, Hash)]
pub(super) struct ParagraphKey {
    text: String,
    family: String,
    color: u32,
    size: u32,
    weight: i32,
    line_height: Option<u32>,
    letter_spacing: u32,
    max_lines: Option<usize>,
    align: Option<String>,
}

impl ParagraphKey {
    pub(super) fn new(text: &str, tp: &TextProps, style: &Style) -> Self {
        Self {
            text: text.to_owned(),
            family: tp.family.clone(),
            color: u32::from_be_bytes([tp.color.a(), tp.color.r(), tp.color.g(), tp.color.b()]),
            size: tp.size.to_bits(),
            weight: tp.weight,
            line_height: tp.line_height.map(f32::to_bits),
            letter_spacing: tp.letter_spacing.to_bits(),
            max_lines: style.max_lines,
            align: style.text_align.clone(),
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
pub(super) struct InputLeaf {
    pub(super) multiline: bool,
    pub(super) rows: usize,
}

/// Ancho por defecto de un campo sin tamaño (como unos 25 caracteres).
pub(super) const INPUT_WIDTH: f32 = 200.0;
pub(super) const INPUT_MIN_WIDTH: f32 = 40.0;
/// Ancho "infinito" para maquetar texto sin saltos de línea.
pub(super) const UNBOUNDED: f32 = 1.0e6;

impl Engine {
    // ------------------------------------------------------------------ texto

    pub(super) fn paragraph(&self, text: &str, tp: &TextProps, style: &Style) -> Paragraph {
        let mut ts = TextStyle::new();
        ts.set_color(tp.color)
            .set_font_size(tp.size)
            .set_font_families(&[tp.family.as_str()])
            .set_letter_spacing(tp.letter_spacing)
            .set_font_style(FontStyle::new(
                Weight::from(tp.weight),
                Width::NORMAL,
                Slant::Upright,
            ));
        if let Some(lh) = tp.line_height {
            ts.set_height(lh).set_height_override(true);
        }
        let mut ps = ParagraphStyle::new();
        ps.set_text_style(&ts);
        if let Some(n) = style.max_lines {
            ps.set_max_lines(n).set_ellipsis("…");
        }
        ps.set_text_align(match style.text_align.as_deref() {
            Some("center") => TextAlign::Center,
            Some("right") => TextAlign::Right,
            _ => TextAlign::Left,
        });
        let mut builder = ParagraphBuilder::new(&ps, self.fonts.clone());
        builder.push_style(&ts);
        builder.add_text(text);
        builder.build()
    }

    /// Contexto de una hoja de texto. Reutiliza el shaping (y las mediciones)
    /// de un párrafo idéntico que haya quedado libre en este layout, si lo hay.
    pub(super) fn text_ctx(
        &self,
        key: ParagraphKey,
        props: &TextProps,
        style: &Style,
        input: Option<InputLeaf>,
    ) -> TextCtx {
        if let Some(mut ctx) = self.recycled.borrow_mut().get_mut(&key).and_then(Vec::pop) {
            ctx.input = input;
            return ctx;
        }
        TextCtx {
            paragraph: self.paragraph(&key.text, props, style),
            key,
            input,
            measures: Vec::new(),
            laid_out: None,
        }
    }

    // ---------------------------------------------------------- campos de texto

    /// Lo que muestra un campo: su valor (con la composición del IME) o, si
    /// está vacío, el placeholder en un color atenuado. Devuelve el texto, sus
    /// propiedades y si es el placeholder.
    pub(super) fn input_display(&self, node: &Node) -> (String, TextProps, bool) {
        let value = match self.inputs.get(&node.key) {
            Some(state) => state.display(),
            None => node.text.clone().unwrap_or_default(),
        };
        let s = &node.style;
        if !value.is_empty() {
            let mut text = value;
            if !s.multiline {
                text = text.replace('\n', " ");
            }
            return (text, node.text_props.clone(), false);
        }
        let tp = &node.text_props;
        let mut props = tp.clone();
        props.color = s
            .placeholder_color
            .unwrap_or_else(|| tp.color.with_a((tp.color.a() as f32 * 0.45) as u8));
        (s.placeholder.clone().unwrap_or_default(), props, true)
    }

    /// Huella del texto que muestran los campos: si cambia (se escribe, se
    /// compone o se deshace sin reconstruir la vista), el layout cacheado no vale.
    pub(super) fn inputs_signature(&self) -> u64 {
        self.inputs.iter().fold(0u64, |acc, (key, state)| {
            let mut h = DefaultHasher::new();
            (key, state.display()).hash(&mut h);
            // Suma: no depende del orden de iteración del mapa.
            acc.wrapping_add(h.finish())
        })
    }
}

/// Un campo ocupa el ancho que le den (o `INPUT_WIDTH`) y el alto de una línea;
/// uno multilínea crece con el texto, con un mínimo de `rows` líneas.
pub(super) fn measure_input(
    p: &mut Paragraph,
    leaf: InputLeaf,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    let width = known.width.unwrap_or(match avail.width {
        AvailableSpace::Definite(w) => INPUT_WIDTH.min(w).max(INPUT_MIN_WIDTH.min(w)),
        AvailableSpace::MinContent => INPUT_MIN_WIDTH,
        AvailableSpace::MaxContent => INPUT_WIDTH,
    });
    p.layout(if leaf.multiline {
        width.max(1.0)
    } else {
        UNBOUNDED
    });
    let line = p.height() / p.line_number().max(1) as f32;
    let height = if leaf.multiline {
        p.height().max(leaf.rows as f32 * line)
    } else {
        line
    };
    Size {
        width,
        height: known.height.unwrap_or(height.ceil()),
    }
}

/// Una imagen mantiene su proporción: con un lado fijado, el otro sale de él;
/// sin ninguno, ocupa su tamaño natural sin pasar del ancho disponible.
pub(super) fn measure_image(
    natural: skia_safe::Size,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    let ratio = if natural.height > 0.0 {
        natural.width / natural.height
    } else {
        1.0
    };
    let (width, height) = match (known.width, known.height) {
        (Some(w), Some(h)) => (w, h),
        (Some(w), None) => (w, w / ratio),
        (None, Some(h)) => (h * ratio, h),
        (None, None) => {
            let max = match avail.width {
                AvailableSpace::Definite(w) => w,
                // Como `max-width: 100%`: en una fila sin sitio, la imagen se encoge.
                AvailableSpace::MinContent => 0.0,
                AvailableSpace::MaxContent => f32::INFINITY,
            };
            let w = natural.width.min(max);
            (w, w / ratio)
        }
    };
    Size { width, height }
}

pub(super) fn measure_text(
    p: &mut Paragraph,
    known: Size<Option<f32>>,
    avail: Size<AvailableSpace>,
) -> Size<f32> {
    let max_w = known.width.unwrap_or(match avail.width {
        AvailableSpace::Definite(w) => w,
        AvailableSpace::MinContent => {
            p.layout(UNBOUNDED);
            p.min_intrinsic_width()
        }
        AvailableSpace::MaxContent => UNBOUNDED,
    });
    p.layout(max_w.max(1.0));
    Size {
        width: known
            .width
            .unwrap_or_else(|| p.max_intrinsic_width().min(max_w).ceil()),
        height: known.height.unwrap_or_else(|| p.height().ceil()),
    }
}

pub(super) fn finalize_text(tree: &mut TaffyTree<Leaf>, lnode: &LayoutNode) {
    let layout = *tree.layout(lnode.id).expect("layout");
    if let Some(Leaf::Text(ctx)) = tree.get_node_context_mut(lnode.id) {
        let w = layout.content_box_width();
        // +0.5 evita cortes de línea espurios por redondeo del layout.
        let w = match ctx.input {
            Some(leaf) if !leaf.multiline => UNBOUNDED,
            _ => w + 0.5,
        };
        if ctx.laid_out != Some(w) {
            ctx.paragraph.layout(w);
            ctx.laid_out = Some(w);
        }
    }
    for child in &lnode.children {
        finalize_text(tree, child);
    }
}
