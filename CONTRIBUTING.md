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

Necesitas Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) y Rust estable
([rustup](https://rustup.rs)). En Linux, además, `libfontconfig-dev` y `libfreetype-dev`.

```bash
git clone https://github.com/YoshiLoL0526/aurora.git
cd aurora
uv sync                     # compila el núcleo e instala todo (incluye pytest, ruff y ty)
uv run pytest               # tests
uv run examples/studio.py   # demo completa
```

- Los cambios en `python/aurora/` se aplican al instante (instalación editable).
- Los cambios en `src/*.rs` disparan la recompilación en el siguiente `uv run`.

## Antes de enviar un PR

Ejecuta lo mismo que la CI:

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
cargo fmt --check && cargo clippy --release -- -D warnings
uv run pytest
```

Y verifica a mano:

- [ ] Si el cambio es **visual**, hay un test en `tests/test_render.py` que lo renderiza, y
      `uv run examples/studio.py` sigue viéndose bien.
- [ ] Si cambia la **API pública**, están actualizados `docs/reference.md`, la guía si aplica,
      los stubs (`_core.pyi`) y el `CHANGELOG.md` (sección *Sin publicar*), y `tests/api.txt`
      está regenerado (`AURORA_UPDATE_API=1 uv run pytest tests/test_api.py`). Para quitar o
      renombrar algo público, márcalo antes como obsoleto según la
      [política de estabilidad](docs/stability.md).
- [ ] Si el cambio toca el **camino de un frame** (layout, pintura, reconstrucción), compara la
      [suite de benchmarks](benchmarks/README.md) antes y después (`--json` / `--compare`).
- [ ] Si añades una **propiedad de estilo**, sigue los pasos de
      [Extender Aurora](docs/architecture.md#extender-aurora).
- [ ] Si tocas la **documentación**, `uv run mkdocs serve` la muestra en local tal como se
      publicará (ver abajo).

## Documentación

La documentación se publica en <https://yoshilol0526.github.io/aurora/> con
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/) cada vez que cambia `main`
(`.github/workflows/docs.yml`).

```bash
uv run mkdocs serve           # en http://127.0.0.1:8000, se recarga al guardar
uv run mkdocs build --strict  # lo mismo que la CI: falla con enlaces rotos o ejemplos que fallan
```

Los ejemplos de código marcados como ```` ```python live ```` son **ejemplos vivos**: se ejecutan
al construir la documentación y debajo se publica la captura de lo que dibujan, en tema claro y
oscuro. Úsalos para todo ejemplo que se pueda ejecutar: así nunca se quedan desfasados.

````markdown
```python live size=900x300
from aurora import App, text

App(lambda: text("Hola"), size=(900, 600)).run()
```
````

Puede ser un programa completo (se renderiza la `App` que ejecuta) o un fragmento que termine en
un elemento (`button("Guardar")`). Las líneas que terminan en `# oculto` (o entre
`# oculto: inicio` y `# oculto: fin`) se ejecutan pero no se muestran, para preparar datos o un
estado. El resto de opciones (`continue`, `size`, `align`, `file`, `theme`, `alt`) están
documentadas en `docs/hooks/livedocs.py`, y `tests/test_docs.py` comprueba que todos los
ejemplos vivos funcionan.

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

- **Python:** formateado con `ruff format`, con type hints en la API pública y sin errores de
  `ty check` (comprobación de tipos).
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
docs/            Guía, referencia, arquitectura y recursos gráficos (sitio en mkdocs.yml)
```

El recorrido completo por el núcleo está en [docs/architecture.md](docs/architecture.md).

## Licencia

Al contribuir aceptas que tu aportación se publique bajo la [licencia MIT](LICENSE) del proyecto.
