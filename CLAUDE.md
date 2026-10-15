# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Aurora (`aurora-ui`, pre-alpha v0.1) is a declarative, reactive desktop UI library: the public API is
Python (`python/aurora/`), and layout/render/animation/events run in a native Rust core
(`src/`, built as the extension module `aurora._core` via PyO3 + maturin). Stack: Skia (`skia-safe`)
for painting and text, Taffy for flexbox layout, winit + softbuffer for the window (CPU raster).

## Commands

```bash
uv sync                                   # builds the Rust core (release) and installs editable + dev deps
uv run pytest                             # all tests
uv run pytest tests/test_render.py::test_name   # single test
uv run examples/studio.py                 # full demo app (opens a window)
uv run examples/studio.py --png studio-shots     # headless render of the demo (CI smoke test)
uv run examples/hello.py --png hello.png
```

Full lint, same as CI:

```bash
uv run ruff check . && uv run ruff format --check .
cargo fmt --check && cargo clippy --release -- -D warnings
```

- Python edits in `python/aurora/` apply immediately (editable install). Rust edits in `src/**/*.rs`
  trigger an automatic rebuild on the next `uv run` (configured via `tool.uv.cache-keys`).
- Rust unit tests (`uv run cargo test --release`) only link on Windows: with `extension-module`,
  the test binary doesn't link libpython on Linux/macOS.
- First build downloads prebuilt Skia binaries and takes minutes. Linux needs
  `libfontconfig-dev` and `libfreetype-dev`.

## Architecture

Core principle: **Python describes, Rust executes; the boundary is crossed once per update with a
complete tree.** Never expose low-level operations (draw rect, measure text) to Python.

Frame lifecycle:

1. `App._build()` (`python/aurora/__init__.py`) calls the user's `view()`, applies root defaults,
   and serializes the `Element` tree to nested dicts via `Element.to_spec(theme)` — this is where
   `"$token"` theme values and text lambdas are resolved.
2. `spec::parse` (`src/spec.rs`) is the **only** place in Rust that knows the shape of the Python
   data: dicts → typed `Node`. Text style inheritance (`color`, `font_size`, `font_weight`,
   `font_family`, `line_height`, `letter_spacing`) is resolved here once, CSS-style.
3. `render.rs` `Engine`: builds a parallel Taffy tree (text nodes carry a shaped Skia `Paragraph`,
   reused for both measuring and painting), ticks hover/pressed transitions (exponential smoothing,
   τ = 70 ms, real `dt`), and `Painter` paints shadow → bg → border → text → children while
   recording `HitRegion`s in paint order.
4. `runtime.rs` `Runtime`: window-independent app state (tree, hit regions, pointer, event
   dispatch by handler name via `dispatch(key, event, arg)`). Two drivers share it: `window.rs`
   (winit loop, runs with the GIL released via `py.detach`; the GIL is taken only to run a handler or
   rebuild the view; hover never touches Python) and `pilot.rs` (`Pilot`, headless, for interaction
   tests via `app.pilot()`).

`Signal.set` calls `_core.wake()` (any thread): an atomic flag that `Runtime::sync` consumes, plus an
`EventLoopProxy` user event to request a frame. Nodes with `layer="overlay"` are deferred by `Painter`
and painted (and hit-tested) after the whole tree.

Hit-testing: take the last-painted region containing the point, bubble up through parents to the
first node with a `click` handler; a node with `capture=True` stops the bubbling (e.g. modals).

Node identity is stable (explicit `key` or tree path) and is used to keep animation state across
full rebuilds — every event currently rebuilds the whole view.

`App.render_png()` → `_core.render_png` renders without a window; this powers `tests/test_render.py`
(which decodes PNG pixels without Pillow), CI smoke tests, and the README images (`examples/brand.py`).

## Extending

- **New component:** compose primitives in `components.py` in pure Python whenever possible. Only
  push to Rust what can't be expressed otherwise (new node kinds, render effects, layout).
- **New style property:** add the field to `spec::Style` and its parsing, its effect in
  `taffy_style` (layout) or `Painter::paint` (paint), and document it in `docs/reference.md`.
- **New node type:** new `spec::Kind` variant + its layout measurement + its painting.
- Visual changes need a render test in `tests/test_render.py`; interaction changes need a `Pilot`
  test in `tests/test_pilot.py`. Public API changes must update
  `docs/reference.md`, `python/aurora/_core.pyi` stubs (if the native API changes), and the
  "Sin publicar" section of `CHANGELOG.md`.

## Conventions

- Code identifiers in English (`bg`, `radius`, `on_click`, CSS-like); docs, comments and commit
  messages in **Spanish**. Commits in imperative mood (`Añade contenedor scroll con clipping`).
- Components must look good with default values. Optional parameters are keyword-only; positional
  args only for essentials (`text(content)`, `button(label, on_click)`).
- Children are attached with `[...]` (`column(gap=8)[a, b]`); theme colors use `"$token"` strings.
- Rust: no `unwrap()` on paths that depend on user data — input errors must surface in Python as
  clear exceptions.
- Ruff line length is 110; Spanish typography rules (RUF001–003) and lambda assignment (E731) are
  ignored on purpose.
