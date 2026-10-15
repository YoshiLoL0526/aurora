# Ejemplos

Todos se ejecutan desde la raíz del repositorio con `uv run`. Los que aceptan `--png` renderizan
sin abrir ventana, útil para ver el resultado en un servidor o en CI.

| Ejemplo | Qué muestra | Comando |
|---|---|---|
| [`hello.py`](hello.py) | Lo esencial: layout, tarjetas de métricas, botones y un contador reactivo. | `uv run examples/hello.py` |
| [`studio.py`](studio.py) | Una app completa: navegación entre vistas, kanban, gráfico interactivo, modal con confirmación, toasts y tema claro/oscuro. | `uv run examples/studio.py` |
| [`brand.py`](brand.py) | Genera el banner y el logo del README con la propia librería. | `uv run examples/brand.py` |

```bash
uv run examples/hello.py --png hola.png
uv run examples/studio.py --png capturas/
```

<p align="center">
  <img src="../docs/studio/2-tablero.png" width="49%"> <img src="../docs/studio/4-equipo-claro.png" width="49%">
</p>
