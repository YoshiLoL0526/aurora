# Contribuir a Aurora

¡Gracias por tu interés! Toda contribución suma: reportar un bug, mejorar la documentación,
proponer una idea o implementar una funcionalidad.

## Antes de empezar

- **Bugs:** abre un issue con la plantilla de bug. Un ejemplo mínimo reproducible (y una captura
  si es visual) ahorra mucho tiempo.
- **Funcionalidades:** abre primero un issue para discutirla. Revisa [VISION.md](VISION.md) y el
  [ROADMAP.md](ROADMAP.md): las propuestas alineadas con ellos tienen más recorrido.
- **Cambios pequeños** (erratas, docs, tests): envía el PR directamente.

## Entorno de desarrollo

Necesitas Python ≥ 3.10, [uv](https://docs.astral.sh/uv/) y Rust estable
([rustup](https://rustup.rs)). En Linux, además, `libfontconfig-dev` y `libfreetype-dev`.

```bash
git clone https://github.com/<usuario>/aurora.git
cd aurora
uv sync                     # compila el núcleo e instala todo (incluye pytest y ruff)
uv run pytest               # tests
uv run examples/studio.py   # demo completa
```

- Los cambios en `python/aurora/` se aplican al instante (instalación editable).
- Los cambios en `src/*.rs` disparan la recompilación en el siguiente `uv run`.

## Antes de enviar un PR

Ejecuta lo mismo que la CI:

```bash
uv run ruff check . && uv run ruff format --check .
cargo fmt --check && cargo clippy --release -- -D warnings
uv run pytest
```

Y verifica a mano:

- [ ] Si el cambio es **visual**, hay un test en `tests/test_render.py` que lo renderiza, y
      `uv run examples/studio.py` sigue viéndose bien.
- [ ] Si cambia la **API pública**, están actualizados `docs/reference.md`, la guía si aplica,
      los stubs (`_core.pyi`) y el `CHANGELOG.md` (sección *Sin publicar*).
- [ ] Si el cambio toca el **camino de un frame** (layout, pintura, reconstrucción), compara la
      [suite de benchmarks](benchmarks/README.md) antes y después (`--json` / `--compare`).
- [ ] Si añades una **propiedad de estilo**, sigue los pasos de
      [Extender Aurora](docs/architecture.md#extender-aurora).

## Convenciones

### Diseño de la API

- **Bonito por defecto:** los valores por defecto de un componente nuevo deben verse bien sin
  configurar nada.
- **Componentes en Python** siempre que se puedan componer con primitivas. Al núcleo Rust solo
  bajan capacidades que no se puedan expresar de otra forma (nuevos tipos de nodo, efectos de
  render, layout).
- **Nombres en inglés en el código** (`bg`, `radius`, `on_click`), siguiendo las convenciones
  habituales de CSS y de otros frameworks de UI. Documentación y comentarios, en español.
- **Keyword arguments** para todo lo opcional; los posicionales, solo para lo esencial
  (`text(contenido)`, `button(label, on_click)`).

### Código

- **Python:** formateado con `ruff format` y con type hints en la API pública.
- **Rust:** `cargo fmt` y `clippy` sin warnings. Nada de `unwrap()` en rutas que dependan de datos
  del usuario: los errores de entrada deben llegar a Python como excepciones claras.
- **Commits:** mensajes en imperativo y descriptivos (`Añade contenedor scroll con clipping`).
  Un commit por cambio lógico.

## Estructura del proyecto

```
python/aurora/   API pública en Python
src/             Núcleo nativo en Rust (módulo aurora._core)
tests/           Tests (pytest), incluidos tests de render headless
benchmarks/      Suite de rendimiento: coste por frame y por fase
examples/        Apps de ejemplo; brand.py genera las imágenes del README
docs/            Guía, referencia, arquitectura y recursos gráficos
```

El recorrido completo por el núcleo está en [docs/architecture.md](docs/architecture.md).

## Licencia

Al contribuir aceptas que tu aportación se publique bajo la [licencia MIT](LICENSE) del proyecto.
