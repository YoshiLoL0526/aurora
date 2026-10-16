## Qué cambia

<!-- Describe el cambio y por qué es necesario. Enlaza el issue si existe: "Cierra #123". -->

## Cómo se probó

<!-- Tests añadidos, ejemplos ejecutados, capturas antes/después si es visual. -->

## Checklist

- [ ] `uv run pytest` pasa
- [ ] `uv run ruff check .`, `uv run ty check` y `cargo clippy --release -- -D warnings` sin avisos
- [ ] Si es visual: hay un test de render y adjunto capturas
- [ ] Si cambia la API pública: actualicé `docs/reference.md`, los stubs y el `CHANGELOG.md`
