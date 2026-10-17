//! Animaciones declarativas: curvas de tiempo (muelle físico o interpolación
//! con easing) y pistas que llevan un valor de cuatro componentes de un origen
//! a un destino. El estado de cada nodo animado vive en el `Engine` (ver
//! `render.rs`); aquí solo está la matemática y el parseo de lo que declara Python.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBool;

/// Valor animado: un color (`a, r, g, b`), un rectángulo (`l, t, r, b`), un
/// efecto (`opacidad, x, y, escala`) o un escalar en la primera componente.
pub type Vec4 = [f32; 4];

/// Efecto neutro: opacidad 1, sin desplazamiento, escala 1.
pub const IDENTITY: Vec4 = [1.0, 0.0, 0.0, 1.0];

/// Curva de easing de una interpolación (las de CSS).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Easing {
    Linear,
    Ease,
    EaseIn,
    EaseOut,
    EaseInOut,
}

impl Easing {
    fn parse(name: &str) -> Option<Self> {
        Some(match name {
            "linear" => Easing::Linear,
            "ease" => Easing::Ease,
            "ease_in" => Easing::EaseIn,
            "ease_out" => Easing::EaseOut,
            "ease_in_out" => Easing::EaseInOut,
            _ => return None,
        })
    }

    /// Fracción de la curva para un avance lineal `p` (0 → 1).
    fn apply(self, p: f32) -> f32 {
        let (x1, y1, x2, y2) = match self {
            Easing::Linear => return p,
            Easing::Ease => (0.25, 0.1, 0.25, 1.0),
            Easing::EaseIn => (0.42, 0.0, 1.0, 1.0),
            Easing::EaseOut => (0.0, 0.0, 0.58, 1.0),
            Easing::EaseInOut => (0.42, 0.0, 0.58, 1.0),
        };
        cubic_bezier(x1, y1, x2, y2, p)
    }
}

/// `cubic-bezier(x1, y1, x2, y2)` de CSS: busca el parámetro cuya x es `p`
/// (bisección, la curva es monótona en x) y devuelve su y.
fn cubic_bezier(x1: f32, y1: f32, x2: f32, y2: f32, p: f32) -> f32 {
    let bez = |a: f32, b: f32, s: f32| {
        let r = 1.0 - s;
        3.0 * r * r * s * a + 3.0 * r * s * s * b + s * s * s
    };
    let (mut lo, mut hi) = (0.0f32, 1.0f32);
    for _ in 0..24 {
        let mid = (lo + hi) / 2.0;
        if bez(x1, x2, mid) < p {
            lo = mid;
        } else {
            hi = mid;
        }
    }
    bez(y1, y2, (lo + hi) / 2.0)
}

/// Cómo avanza una animación en el tiempo.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Timing {
    /// Muelle amortiguado (puede pasarse un poco del destino). Su duración
    /// sale de la física: termina cuando la oscilación ya no se ve.
    Spring {
        stiffness: f32,
        damping: f32,
        mass: f32,
        delay: f32,
    },
    /// Interpolación de duración fija con una curva de easing.
    Tween {
        duration: f32,
        easing: Easing,
        delay: f32,
    },
    /// Vaivén perpetuo de ida y vuelta en `duration` segundos: nunca termina.
    /// Lo usan `pulse` (opacidad de spinners y esqueletos): la opacidad baja
    /// hasta `floor` y vuelve.
    Pulse {
        duration: f32,
        delay: f32,
        floor: f32,
    },
}

impl Default for Timing {
    /// El muelle de `animate.spring()`: rápido, con un rebote apenas visible.
    fn default() -> Self {
        Timing::Spring {
            stiffness: 380.0,
            damping: 30.0,
            mass: 1.0,
            delay: 0.0,
        }
    }
}

/// Desviación del destino por debajo de la cual un muelle se da por parado.
const SPRING_REST: f32 = 1.0e-3;
/// Tope de duración de cualquier animación (segundos).
const MAX_DURATION: f32 = 10.0;

impl Timing {
    /// Avance a los `t` segundos de empezar (0 → 1; un muelle puede pasarse
    /// de 1) y si ya terminó.
    pub fn progress(&self, t: f32) -> (f32, bool) {
        match *self {
            Timing::Tween {
                duration,
                easing,
                delay,
            } => {
                let t = t - delay;
                if t <= 0.0 {
                    return (0.0, false);
                }
                if duration <= 0.0 || t >= duration {
                    return (1.0, true);
                }
                (easing.apply(t / duration), false)
            }
            Timing::Spring {
                stiffness,
                damping,
                mass,
                delay,
            } => {
                let t = t - delay;
                if t <= 0.0 {
                    return (0.0, false);
                }
                let (x, envelope) = spring_step(stiffness, damping, mass, t);
                if envelope < SPRING_REST || t >= MAX_DURATION {
                    (1.0, true)
                } else {
                    (x, false)
                }
            }
            Timing::Pulse {
                duration, delay, ..
            } => {
                let t = t - delay;
                if t <= 0.0 {
                    return (0.0, false);
                }
                // Coseno de ida y vuelta: 0 → 1 → 0 sin parar (nunca termina).
                let phase = (t % duration) / duration;
                (0.5 - 0.5 * (std::f32::consts::TAU * phase).cos(), false)
            }
        }
    }
}

/// Respuesta de un muelle que parte del reposo en 0 hacia 1: posición a los
/// `t` segundos y cota de lo que aún puede alejarse de 1.
fn spring_step(k: f32, c: f32, m: f32, t: f32) -> (f32, f32) {
    let w0 = (k / m).sqrt();
    let zeta = c / (2.0 * (k * m).sqrt());
    if (zeta - 1.0).abs() < 1.0e-3 {
        // Amortiguamiento crítico.
        let e = (-w0 * t).exp() * (1.0 + w0 * t);
        (1.0 - e, e)
    } else if zeta < 1.0 {
        let wd = w0 * (1.0 - zeta * zeta).sqrt();
        let b = zeta * w0 / wd;
        let e = (-zeta * w0 * t).exp();
        let x = 1.0 - e * ((wd * t).cos() + b * (wd * t).sin());
        (x, e * (1.0 + b * b).sqrt())
    } else {
        // Sobreamortiguado: suma de dos exponenciales sin oscilación.
        let s = (zeta * zeta - 1.0).sqrt();
        let (r1, r2) = (-w0 * (zeta - s), -w0 * (zeta + s));
        let (e1, e2) = ((r1 * t).exp(), (r2 * t).exp());
        let x = 1.0 - (r2 * e1 - r1 * e2) / (r2 - r1);
        (x, (r2.abs() * e1 + r1.abs() * e2) / (r2 - r1).abs())
    }
}

/// Lleva un valor de `from` a `to` siguiendo una curva de tiempo.
#[derive(Clone, Copy, Debug)]
pub struct Track {
    pub from: Vec4,
    pub to: Vec4,
    timing: Timing,
    /// Segundos desde que empezó (o desde que cambió de destino).
    t: f32,
    /// Avance de la curva en `t`.
    x: f32,
    done: bool,
}

impl Track {
    pub fn new(from: Vec4, to: Vec4, timing: Timing) -> Self {
        let done = from == to;
        Self {
            from,
            to,
            timing,
            t: 0.0,
            x: if done { 1.0 } else { 0.0 },
            done,
        }
    }

    /// Valor actual.
    pub fn value(&self) -> Vec4 {
        if self.done {
            return self.to;
        }
        let x = self.x;
        std::array::from_fn(|i| self.from[i] + (self.to[i] - self.from[i]) * x)
    }

    pub fn done(&self) -> bool {
        self.done
    }

    /// Avanza `dt` segundos. Devuelve `true` si el valor cambió.
    pub fn step(&mut self, dt: f32) -> bool {
        if self.done {
            return false;
        }
        self.t += dt;
        let before = self.x;
        let (x, done) = self.timing.progress(self.t);
        self.x = x;
        self.done = done;
        done || x != before
    }

    /// Cambia el destino partiendo del valor actual, sin saltos.
    pub fn retarget(&mut self, to: Vec4, timing: Timing) {
        if to == self.to && timing == self.timing {
            return;
        }
        *self = Track::new(self.value(), to, timing);
    }
}

/// Efecto de entrada o salida: desde qué valores aparece un nodo o hacia
/// cuáles se va (`opacidad, x, y, escala`) y, si se fija, con qué curva.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Effect {
    pub values: Vec4,
    pub timing: Option<Timing>,
}

// ---------------------------------------------------------------------------
// Parseo de los objetos de `aurora.animate`.
// ---------------------------------------------------------------------------

fn attr(obj: &Bound<'_, PyAny>, name: &str) -> PyResult<f32> {
    obj.getattr(name)?.extract::<f32>()
}

/// `animate.spring(...)` o `animate.tween(...)`.
pub fn parse_timing(obj: &Bound<'_, PyAny>) -> PyResult<Timing> {
    let invalid = || {
        PyValueError::new_err(
            "transition debe ser animate.spring(...) o animate.tween(...)".to_owned(),
        )
    };
    let delay = obj
        .getattr("delay")
        .map_err(|_| invalid())?
        .extract::<f32>()?;
    if delay.is_nan() || delay < 0.0 {
        return Err(PyValueError::new_err("delay no puede ser negativo"));
    }
    if obj.hasattr("stiffness")? {
        let (stiffness, damping, mass) = (
            attr(obj, "stiffness")?,
            attr(obj, "damping")?,
            attr(obj, "mass")?,
        );
        if !(stiffness > 0.0 && damping > 0.0 && mass > 0.0) {
            return Err(PyValueError::new_err(
                "stiffness, damping y mass del muelle deben ser positivos",
            ));
        }
        return Ok(Timing::Spring {
            stiffness,
            damping,
            mass,
            delay,
        });
    }
    if obj.hasattr("easing")? {
        let duration = attr(obj, "duration")?;
        if duration.is_nan() || duration < 0.0 {
            return Err(PyValueError::new_err("duration no puede ser negativa"));
        }
        let name: String = obj.getattr("easing")?.extract()?;
        let easing = Easing::parse(&name).ok_or_else(|| {
            PyValueError::new_err(format!(
                "easing inválido: {name:?} (usa \"linear\", \"ease\", \"ease_in\", \"ease_out\" o \"ease_in_out\")"
            ))
        })?;
        return Ok(Timing::Tween {
            duration,
            easing,
            delay,
        });
    }
    if obj.hasattr("duration")? {
        let duration = attr(obj, "duration")?;
        if duration.is_nan() || duration <= 0.0 {
            return Err(PyValueError::new_err(
                "la duración del vaivén debe ser positiva",
            ));
        }
        let floor = attr(obj, "floor")?;
        if !(floor > 0.0 && floor <= 1.0) {
            return Err(PyValueError::new_err(
                "floor del vaivén debe estar entre 0 y 1",
            ));
        }
        return Ok(Timing::Pulse {
            duration,
            delay,
            floor,
        });
    }
    Err(invalid())
}

/// `animate_layout`: `True` (con la curva de `transition` o la por defecto) o una curva.
pub fn parse_layout(
    obj: &Bound<'_, PyAny>,
    transition: Option<Timing>,
) -> PyResult<Option<Timing>> {
    if obj.is_instance_of::<PyBool>() {
        return Ok(obj.is_truthy()?.then(|| transition.unwrap_or_default()));
    }
    parse_timing(obj).map(Some)
}

/// `animate.fade(...)`, `animate.slide(...)`, `animate.zoom(...)` o `animate.effect(...)`.
pub fn parse_effect(obj: &Bound<'_, PyAny>, prop: &str) -> PyResult<Effect> {
    let read = || -> PyResult<Vec4> {
        Ok([
            attr(obj, "opacity")?,
            attr(obj, "x")?,
            attr(obj, "y")?,
            attr(obj, "scale")?,
        ])
    };
    let values = read().map_err(|_| {
        PyValueError::new_err(format!(
            "{prop} debe ser un efecto de animate (fade, slide, zoom o effect)"
        ))
    })?;
    if !values.iter().all(|v| v.is_finite()) || values[3] < 0.0 {
        return Err(PyValueError::new_err(format!(
            "{prop}: los valores deben ser finitos y la escala no negativa"
        )));
    }
    let timing = match obj.getattr("transition")? {
        t if t.is_none() => None,
        t => Some(parse_timing(&t)?),
    };
    Ok(Effect { values, timing })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tween_ends_at_its_duration() {
        let t = Timing::Tween {
            duration: 0.2,
            easing: Easing::Linear,
            delay: 0.1,
        };
        assert_eq!(t.progress(0.05), (0.0, false));
        let (x, done) = t.progress(0.2);
        assert!((x - 0.5).abs() < 1e-5 && !done);
        assert_eq!(t.progress(0.3), (1.0, true));
    }

    #[test]
    fn easing_curves_keep_their_ends() {
        for e in [
            Easing::Ease,
            Easing::EaseIn,
            Easing::EaseOut,
            Easing::EaseInOut,
        ] {
            assert!(e.apply(0.0).abs() < 1e-4);
            assert!((e.apply(1.0) - 1.0).abs() < 1e-4);
        }
        assert!(Easing::EaseOut.apply(0.5) > 0.5);
        assert!(Easing::EaseIn.apply(0.5) < 0.5);
    }

    #[test]
    fn springs_settle_at_one() {
        for (k, c) in [(380.0, 30.0), (100.0, 20.0), (100.0, 60.0)] {
            let t = Timing::Spring {
                stiffness: k,
                damping: c,
                mass: 1.0,
                delay: 0.0,
            };
            let (x, done) = t.progress(0.05);
            assert!(x > 0.0 && x < 1.0 && !done);
            assert_eq!(t.progress(MAX_DURATION), (1.0, true));
        }
    }

    #[test]
    fn pulses_oscillate_and_never_finish() {
        let t = Timing::Pulse {
            duration: 1.0,
            delay: 0.25,
            floor: 0.35,
        };
        // Durante el retardo está arriba (valor 0) y no ha terminado.
        assert_eq!(t.progress(0.25), (0.0, false));
        let (mid, done) = t.progress(0.5);
        assert!((mid - 0.5).abs() < 1e-4 && !done);
        let (top, _) = t.progress(0.75);
        assert!((top - 1.0).abs() < 1e-4);
        // Una vuelta después vuelve a empezar: el vaivén no termina nunca.
        let (again, done) = t.progress(2.25);
        assert!(again < 1e-4 && !done);
    }

    #[test]
    fn retarget_starts_from_the_current_value() {
        let timing = Timing::Tween {
            duration: 1.0,
            easing: Easing::Linear,
            delay: 0.0,
        };
        let mut track = Track::new([0.0; 4], [10.0, 0.0, 0.0, 0.0], timing);
        track.step(0.5);
        track.retarget([0.0; 4], timing);
        assert_eq!(track.value()[0], 5.0);
        track.step(1.0);
        assert!(track.done());
        assert_eq!(track.value(), [0.0; 4]);
    }
}
