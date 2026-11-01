# Evaluación con agentes de IA

Mide si un agente de programación escribe apps de Aurora que funcionan, y si le ayudan las
herramientas pensadas para agentes (`aurora agents`, `aurora docs`, `aurora check/shot/tree/pilot`).

- `tareas/`: el enunciado de cada tarea, con las keys que debe usar la app (las necesitan las
  comprobaciones).
- `inicio/`: los archivos con los que empieza una tarea (la 04 arregla una app rota).
- `comprobaciones/`: un guion de `aurora pilot` por tarea que comprueba el comportamiento.
- `referencia/`: una solución de cada tarea; demuestra que los guiones se pueden cumplir.
- `corregir.py`: corrige una tanda.

## Cómo se ejecuta

1. Por cada tarea y condición, una carpeta vacía (más lo de `inicio/`). En la condición **con
   guía**, ejecuta `aurora agents` dentro para crear su `AGENTS.md`; en la **sin guía**, nada.
2. Un agente sin contexto previo resuelve la tarea en su carpeta con el Python donde está
   instalada Aurora, sin leer el código ni la documentación del repositorio (solo lo que la
   librería instalada ofrece al ejecutarla). Al acabar informa de cómo aprendió la API, los errores
   que vio y las fricciones.
3. Corrige la tanda:

   ```bash
   uv run evals/agentes/corregir.py CARPETA_SIN_GUIA CARPETA_CON_GUIA
   ```

   Una app **pasa** si arranca (`aurora check`), no tiene avisos de layout y cumple su guion de
   `comprobaciones/`. Sin argumentos corrige `referencia/`, que debe pasar entera.

Las dos condiciones usan la misma versión instalada: la diferencia es solo la guía. La validación
de props (fase 1) actúa en ambas.
