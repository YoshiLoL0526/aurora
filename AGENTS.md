# AGENTS.md

Aurora (`aurora-ui`, pre-alpha v0.4) is a declarative, reactive desktop UI library: the public API is
pure Python (`python/aurora/`), while layout, render, animation and events run in a native Rust core
(`src/`, built as the extension module `aurora._core` via PyO3 + maturin). Stack: Skia for painting
and text shaping, Taffy for flexbox, winit for the window, GPU via Vulkan/Metal with a CPU
(softbuffer) fallback.

Layout: `python/aurora/` public API · `src/` Rust core · `tests/` pytest (mostly headless renders) ·
`benchmarks/` frame-cost suite · `examples/` runnable apps · `docs/` MkDocs site.

## Commands

```bash
uv sync                                             # build Rust core (release) + editable install + dev deps
uv run pytest                                       # full suite
uv run pytest tests/test_render.py::test_name       # single test
uv run examples/hello.py                            # open a window
uv run examples/studio.py --png studio-shots        # headless render (also the CI visual smoke test)
uv run mkdocs serve                                 # docs at http://127.0.0.1:8000
uv run mkdocs build --strict                        # same as docs CI: runs every live example in docs/
uv run benchmarks/run.py                            # frame-cost suite (~1 min; --json / --compare / --scale 0.1)
```

Full lint, same as CI:

```bash
uv run ruff check . && uv run ruff format --check . && uv run ty check
cargo fmt --check && cargo clippy --release -- -D warnings
```

- Python edits apply immediately (editable install). Rust edits under `src/**` recompile on the next
  `uv run` (`tool.uv.cache-keys` in `pyproject.toml`).
- First build downloads prebuilt Skia and takes minutes. The per-OS `skia-safe` features in
  `Cargo.toml` must match a combination published by rust-skia/skia-binaries; anything else silently
  builds Skia from source (needs LLVM, very slow). Linux also needs `libfontconfig-dev` + `libfreetype-dev`.
- `uv run cargo test --release` (Rust unit tests) only links on Windows; with `extension-module` the
  test binary can't link libpython on Linux/macOS. CI runs it on Windows only.
- `tests/test_build.py` real-packaging test is skipped unless `AURORA_BUILD_TEST=1` (needs
  PyInstaller, ~30 s).
- `python/aurora/_core.pyd` (`.so` on Linux/macOS) is a gitignored build artifact — never edit or
  delete it.
  `python/aurora/_core.pyi` is the hand-written stub `ty` uses to typecheck without compiling the
  core; update it when the native API changes.

## Architecture (only what changes how you edit)

- Core principle: **Python describes, Rust executes**; the boundary is crossed once per update with a
  complete tree. Never expose low-level operations (draw rect, measure text) to Python.
- Frame path: `App._build()` (`python/aurora/__init__.py`) → `Element.to_spec(theme)`
  (`elements.py`; resolves `"$token"` themes and text lambdas) → `spec::parse` (`src/spec.rs`, the
  only Rust code that knows the dict shape; resolves CSS-style text-style inheritance here) →
  `render::Engine` phased invalidation (`restyle` diffs and skips relayout → `update` runs
  Taffy/layout/composite → `paint` repaints only the damaged rect; `tick` advances transitions).
- `src/runtime/` `Runtime` is window-independent app state, shared by the winit loop (`window.rs`,
  GIL released via `py.detach`) and the headless `Pilot` (`pilot.rs`, `app.pilot()`). `Signal.set`
  from any thread calls `_core.wake()`. Every event rebuilds the whole `view()`; node identity
  (explicit `key` or tree path) preserves animation state across rebuilds.
- Hit-testing: take the last-painted region containing the point and bubble up to the first node with
  a `click` handler; `capture=True` stops bubbling (e.g. modals).

## Extending

- New component: pure Python in `python/aurora/components/` (one module per family). Only push to
  Rust what can't be expressed otherwise (new node kinds, render effects, layout).
- New style property: field + parsing in `src/spec.rs`; effect in `taffy_style` (layout) or
  `Painter::paint`; if it paints outside the box or changes hit regions, also update `compute_ink`
  and `same_geometry` in `render/geom.rs` (otherwise partial repaints miss it); document it in
  `docs/reference.md`.
- Docs examples: `python live` fenced blocks in `docs/*.md` are executed at `mkdocs build` time and
  their PNG (light + dark) is inserted below (`docs/hooks/livedocs.py`; `tests/test_docs.py` runs
  them all). Lines ending in `# oculto` (or between `# oculto: inicio` / `# oculto: fin`) run but
  aren't shown. Ruff also formats the Python inside the Markdown files.
- Required per change: visual → render test in `tests/test_render.py`; interaction → `Pilot` test in
  `tests/test_pilot.py`; public API → `docs/reference.md` + `_core.pyi` (if native) + the
  "Sin publicar" section of `CHANGELOG.md`; frame-path (layout/paint/rebuild) → compare
  `benchmarks/run.py --json` / `--compare` before and after.

## Conventions

- Identifiers in English, CSS-like (`bg`, `radius`, `on_click`); docs, comments and commit messages
  in **Spanish**, imperative mood (`Añade contenedor scroll con clipping`). Releases publish to PyPI
  on `vX.Y.Z` tags.
- Components must look good with default values. Optional parameters are keyword-only; positional
  args only for essentials (`text(content)`, `button(label, on_click)`). Children attach with `[...]`
  (`column(gap=8)[a, b]`); theme colors use `"$token"` strings.
- Rust: no `unwrap()` on paths that depend on user data — input errors must surface in Python as
  clear exceptions.
- Ruff line length is 110; RUF001–003 and E731 are ignored on purpose. Type-check with `ty`; fix the
  types rather than silencing them, and use `# ty: ignore[rule]` only where invalid input is
  intentional.
- `AGENTS.md` (this file) is the single source of truth for agent guidance; `CLAUDE.md` is just a
  one-line pointer to it for Claude Code — don't add content there.
  Deeper walkthrough: `docs/architecture.md`. PR checklist: `CONTRIBUTING.md` (Spanish).
