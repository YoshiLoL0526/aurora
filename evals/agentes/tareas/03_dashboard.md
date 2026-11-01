# Panel de ventas

Escribe en `app.py` una app de Aurora con un panel de ventas a partir de estos datos:

```python
VENTAS = [
    ("Enero", 820),
    ("Febrero", 640),
    ("Marzo", 910),
    ("Abril", 700),
    ("Mayo", 1080),
    ("Junio", 1250),
]
```

- Arriba, tres métricas: el total (con `key="total"`, mostrando `5400`), la media mensual (con
  `key="average"`, mostrando `900`) y el mejor mes (con `key="best"`, mostrando `Junio`).
- Un gráfico de las ventas por mes con `key="chart"`.
- Una tabla con `key="sales"` con las columnas Mes y Ventas.
- Un interruptor o botón con `key="theme"` que cambia entre tema claro y oscuro.
- Tiene que verse bien en una ventana de 960×720: sin textos cortados ni controles fuera de la
  ventana.
