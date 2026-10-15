//! Imágenes: decodificación (PNG, JPEG, WebP, GIF, BMP, ICO y SVG) con caché,
//! y el encaje (`fit`) dentro de la caja del nodo.
//!
//! Se decodifica una vez por archivo (o por contenido, si llegan bytes) y se
//! reutiliza entre reconstrucciones. Un archivo que cambia en disco (fecha o
//! tamaño) se vuelve a leer.

use std::collections::HashMap;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::rc::Rc;
use std::time::SystemTime;

use pyo3::PyErr;
use pyo3::exceptions::{PyFileNotFoundError, PyValueError};
use skia_safe::svg::Dom;
use skia_safe::{Data, FontMgr, Image, Rect, Size};

/// Imágenes sin usar que se conservan en caché (por si vuelven a aparecer).
const KEEP_UNUSED: usize = 32;
/// Tamaño de un SVG sin `width`/`height` ni `viewBox`.
const SVG_DEFAULT: f32 = 150.0;

/// De dónde sale la imagen.
#[derive(Clone, Debug)]
pub enum Source {
    Path(String),
    Bytes(Vec<u8>),
}

/// Cómo encaja la imagen en la caja del nodo (como `object-fit` en CSS).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Fit {
    /// Entera y sin deformar, centrada (puede dejar márgenes).
    #[default]
    Contain,
    /// Cubre toda la caja sin deformar, centrada y recortando lo que sobra.
    Cover,
    /// Estirada a la caja (puede deformarse).
    Fill,
    /// A su tamaño natural, centrada y recortada.
    None,
}

impl Fit {
    pub fn parse(s: &str) -> Option<Self> {
        Some(match s {
            "contain" => Fit::Contain,
            "cover" => Fit::Cover,
            "fill" => Fit::Fill,
            "none" => Fit::None,
            _ => return None,
        })
    }

    /// Rectángulo de destino de una imagen de tamaño `natural` dentro de `bx`.
    pub fn place(self, natural: Size, bx: Rect) -> Rect {
        let (iw, ih) = (natural.width.max(1e-3), natural.height.max(1e-3));
        let (w, h) = match self {
            Fit::Fill => return bx,
            Fit::None => (iw, ih),
            Fit::Contain | Fit::Cover => {
                let (sx, sy) = (bx.width() / iw, bx.height() / ih);
                let k = if self == Fit::Contain {
                    sx.min(sy)
                } else {
                    sx.max(sy)
                };
                (iw * k, ih * k)
            }
        };
        let c = bx.center();
        Rect::from_xywh(c.x - w / 2.0, c.y - h / 2.0, w, h)
    }
}

pub enum Decoded {
    Raster(Image),
    Svg(Dom),
}

pub struct Loaded {
    pub decoded: Decoded,
    /// Tamaño natural en píxeles lógicos (1 píxel de la imagen = 1 píxel lógico).
    pub size: Size,
}

/// Error de carga, que llega a Python como `FileNotFoundError` o `ValueError`.
#[derive(Debug)]
pub struct ImageError {
    message: String,
    missing: bool,
}

impl From<ImageError> for PyErr {
    fn from(e: ImageError) -> Self {
        if e.missing {
            PyFileNotFoundError::new_err(e.message)
        } else {
            PyValueError::new_err(e.message)
        }
    }
}

#[derive(Clone, PartialEq, Eq, Hash)]
enum CacheKey {
    File {
        path: String,
        modified: Option<SystemTime>,
        len: u64,
    },
    Bytes {
        hash: u64,
        len: usize,
    },
}

#[derive(Default)]
pub struct ImageCache {
    entries: HashMap<CacheKey, Rc<Loaded>>,
    /// Orden de último uso (el más reciente al final), para descartar los viejos.
    recent: Vec<CacheKey>,
}

impl ImageCache {
    pub fn load(&mut self, src: &Source) -> Result<Rc<Loaded>, ImageError> {
        let (key, bytes) = match src {
            Source::Path(path) => {
                let meta = std::fs::metadata(path).map_err(|e| ImageError {
                    missing: e.kind() == std::io::ErrorKind::NotFound,
                    message: format!("no se pudo abrir la imagen {path:?}: {e}"),
                })?;
                let key = CacheKey::File {
                    path: path.clone(),
                    modified: meta.modified().ok(),
                    len: meta.len(),
                };
                (key, None)
            }
            Source::Bytes(data) => {
                let mut h = DefaultHasher::new();
                data.hash(&mut h);
                let key = CacheKey::Bytes {
                    hash: h.finish(),
                    len: data.len(),
                };
                (key, Some(data.as_slice()))
            }
        };
        self.touch(&key);
        if let Some(loaded) = self.entries.get(&key) {
            return Ok(loaded.clone());
        }
        let label = match src {
            Source::Path(p) => format!("{p:?}"),
            Source::Bytes(d) => format!("de {} bytes", d.len()),
        };
        let owned;
        let bytes = match (bytes, src) {
            (Some(b), _) => b,
            (None, Source::Path(path)) => {
                owned = std::fs::read(path).map_err(|e| ImageError {
                    missing: e.kind() == std::io::ErrorKind::NotFound,
                    message: format!("no se pudo leer la imagen {path:?}: {e}"),
                })?;
                &owned[..]
            }
            (None, Source::Bytes(_)) => unreachable!("los bytes vienen en la clave"),
        };
        let loaded = Rc::new(decode(bytes).ok_or_else(|| ImageError {
            missing: false,
            message: format!(
                "no se pudo decodificar la imagen {label} (formatos: PNG, JPEG, WebP, GIF, BMP, ICO, SVG)"
            ),
        })?);
        self.entries.insert(key, loaded.clone());
        Ok(loaded)
    }

    fn touch(&mut self, key: &CacheKey) {
        self.recent.retain(|k| k != key);
        self.recent.push(key.clone());
    }

    /// Descarta las imágenes que no se usan en `used` salvo las más recientes.
    pub fn trim(&mut self, used: usize) {
        let keep = used + KEEP_UNUSED;
        if self.recent.len() > keep {
            for old in self.recent.drain(..self.recent.len() - keep) {
                self.entries.remove(&old);
            }
        }
    }
}

fn decode(bytes: &[u8]) -> Option<Loaded> {
    if looks_like_svg(bytes) {
        let mut dom = Dom::from_bytes(bytes, FontMgr::new()).ok()?;
        let root = dom.root();
        let mut size = root.intrinsic_size();
        if size.width <= 0.0 || size.height <= 0.0 {
            size = root
                .view_box()
                .map(|v| v.size())
                .filter(|s| s.width > 0.0 && s.height > 0.0)
                .unwrap_or(Size::new(SVG_DEFAULT, SVG_DEFAULT));
        }
        dom.set_container_size(size);
        return Some(Loaded {
            decoded: Decoded::Svg(dom),
            size,
        });
    }
    let image = Image::from_encoded(Data::new_copy(bytes))?;
    // Decodifica ya (no en el primer frame) y prepara mipmaps para reducir sin aliasing.
    let image = image.make_raster_image(None, None).unwrap_or(image);
    let image = image.with_default_mipmaps().unwrap_or(image);
    let size = Size::new(image.width() as f32, image.height() as f32);
    Some(Loaded {
        decoded: Decoded::Raster(image),
        size,
    })
}

fn looks_like_svg(bytes: &[u8]) -> bool {
    let head = &bytes[..bytes.len().min(512)];
    let text = String::from_utf8_lossy(head);
    let text = text.trim_start_matches('\u{feff}').trim_start();
    text.starts_with("<svg") || (text.starts_with("<?xml") && text.contains("<svg"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fit_contain_and_cover_keep_aspect() {
        let bx = Rect::from_xywh(0.0, 0.0, 100.0, 50.0);
        let natural = Size::new(20.0, 20.0);
        assert_eq!(
            Fit::Contain.place(natural, bx),
            Rect::from_xywh(25.0, 0.0, 50.0, 50.0)
        );
        assert_eq!(
            Fit::Cover.place(natural, bx),
            Rect::from_xywh(0.0, -25.0, 100.0, 100.0)
        );
        assert_eq!(Fit::Fill.place(natural, bx), bx);
        assert_eq!(
            Fit::None.place(natural, bx),
            Rect::from_xywh(40.0, 15.0, 20.0, 20.0)
        );
    }

    #[test]
    fn detects_svg() {
        assert!(looks_like_svg(b"<?xml version=\"1.0\"?>\n<svg></svg>"));
        assert!(looks_like_svg(
            b"  <svg xmlns=\"http://www.w3.org/2000/svg\"/>"
        ));
        assert!(!looks_like_svg(b"\x89PNG\r\n"));
    }
}
