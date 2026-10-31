# Benchmarks

Cuánto cuesta un frame de Aurora, fase a fase. Es la vara de medir de la v0.3 (rendimiento): cada
optimización se justifica comparando esta suite antes y después.

```bash
uv run benchmarks/run.py                        # todos los escenarios (~1 min)
uv run benchmarks/run.py lista_10k --reps 50    # uno solo, más muestras
uv run benchmarks/run.py --json antes.json      # guarda los resultados
uv run benchmarks/run.py --compare antes.json   # compara con una medición anterior
uv run benchmarks/run.py --scale 0.1            # escenarios reducidos, para iterar rápido
```

## Qué se mide

Cada escenario crea una app y la conduce con el piloto headless (`app.pilot()`), que usa el mismo
runtime que la ventana pero sin presentar en pantalla. Cada **operación** avanza exactamente un
frame. Tras unos frames de calentamiento se toman muestras (hasta `--reps`, o hasta agotar
`--budget` segundos, con un mínimo de 5) y se publican la **mediana** y el **p95** del frame
completo, más la mediana de cada fase:

| Fase | Qué es |
|---|---|
| `view` | Tu función de vista (Python). |
| `to_spec` | Serializar el árbol de `Element` a dicts (Python). |
| `parse` | Dicts → `Node` tipados en Rust (`spec::parse`). |
| `style` | Comparar el árbol nuevo con el anterior: decide si hay que rehacer el layout o solo repintar. |
| `layout` | Árbol de Taffy, shaping de los párrafos, cálculo del layout y regiones de hit-testing. |
| `paint` | Composición (colocar las capas de los `scroll`) y pintura con Skia de la zona dañada. |

`view`, `to_spec`, `parse` y `style` valen 0 en los frames que no reconstruyen la vista, y `layout`
en los que no cambian nada que lo afecte ([invalidación por
fases](../docs/architecture.md#invalidación-por-fases)). Las fases salen
de [`Pilot.stats`](../docs/reference.md#pilot-tests-de-interacción).

## Escenarios

| Escenario | Qué es | Operaciones |
|---|---|---|
| `lista_10k` | 10 000 filas seleccionables en un `scroll` (~50 000 nodos). | `cold`, `rebuild` (cambia la selección), `hover`, `scroll`, `idle` |
| `lista_10k_memo` | La misma lista con cada fila como `@component`: al cambiar la selección solo se reconstruyen 2 filas. | las mismas que `lista_10k` |
| `vista_grande` | 10 000 filas fijas (~50 000 nodos) bajo una cabecera cuyo color y contador leen un `Signal` desde lambdas: la [reconstrucción parcial](../docs/architecture.md#reconstrucción-parcial) no vuelve a llamar a la vista. | `color` (cambia un `bg=lambda`), `texto` (cambia un `text(lambda)`: mueve la geometría), `hover`, `idle` |
| `lista_virtual_100k` | 100 000 filas en una `virtual_list` con filas `@component`: solo existen las visibles. | `cold`, `rebuild`, `hover`, `scroll` (cada paso cambia el rango visible), `idle` |
| `dashboard_50` | 50 paneles con 24 barras cada uno y datos que cambian. | `cold`, `rebuild` (avanzan los datos), `hover`, `idle` |
| `charts_points` | Cuatro gráficos (línea, área, dispersión y dos series) de 20 000 puntos cada uno. | `cold`, `rebuild` (datos nuevos: se vuelven a grabar), `hover`, `idle` |
| `chart_millon` | Un gráfico de 1 000 000 de puntos con `zoom=True`: LTTB al grabar. | `cold`, `rebuild` (datos nuevos), `zoom` (un paso de rueda), `pan` (un paso horizontal), `idle` |
| `typing` | Escribir en un campo que filtra un formulario de 500 filas. | `cold`, `type` (una tecla), `idle` |

- `cold`: crear la app y pintar el primer frame (sin estado previo).
- `rebuild`: un `Signal` cambia y la vista se reconstruye.
- `color` / `texto`: un `Signal` que solo leen regiones cambia; se reevalúan esas regiones y no `view()`.
- `hover` / `scroll`: el puntero se mueve o la rueda desplaza; no se toca Python.
- `idle`: un frame sin cambios. Mide lo que se paga por frame aunque no pase nada.

## Arranque

`arranque` mide lo que tarda una app típica (una barra lateral, un formulario, una lista de 100
filas con badges y unas pestañas: ~550 nodos) desde `import aurora` hasta su primer frame, con el
piloto headless. Cada muestra es un proceso nuevo ([`startup.py`](startup.py)), porque un `import`
repetido en el mismo proceso no cuesta nada; el arranque del intérprete no cuenta. Publica tres
operaciones: `import`, `primer_frame` y `total`.

**Objetivo: `total` por debajo de 250 ms** en un equipo de escritorio con la compilación release.
Es el margen para que una ventana aparezca sin un parpadeo de espera perceptible (a lo que se
suma lo que tarda el sistema en crear la ventana). Tras la tabla, `run.py` dice si se cumple. Se
ejecuta con la suite completa o con `run.py arranque`; para verlo una vez,
`uv run benchmarks/startup.py`. Para no pagar en el `import` lo que la app quizá no use, los
módulos de la biblioteca estándar que pesan (`asyncio`, `json`, `webbrowser`…) se importan donde
se usan.

Los datos son deterministas, sin azar ni reloj. Los escenarios están en
[`scenarios.py`](scenarios.py): para añadir uno, define una función que devuelva un `Bench` y
regístrala en `SCENARIOS`. `tests/test_benchmarks.py` ejecuta todos a escala mínima para que no
se rompan sin que nadie lo note.

## Reproducibilidad

- Compara solo resultados **de la misma máquina**. Cierra lo que consuma CPU y usa la compilación
  release (la de `uv sync`).
- `--compare` marca con ▲/▼ los cambios de mediana de más del 10 %; por debajo (≈) suele ser ruido.
- El JSON incluye versión, commit, plataforma, Python y número de CPU.
- [`baseline-0.2.0.json`](baseline-0.2.0.json) es el punto de partida de la v0.3, medido con la
  0.2.0 en la máquina que indica su `meta` (Windows). Sirve de referencia de orden de magnitud;
  para comparar en tu máquina, mide primero la rama principal con `--json`.
- En CI el job **Benchmarks** ejecuta la suite en cada push, publica la tabla en el resumen del
  build y sube `bench.json` como artefacto. No falla por tiempos: los runners compartidos tienen
  demasiado ruido para usarlos como umbral.
