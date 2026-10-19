# Estabilidad de la API

Qué puedes dar por estable al escribir una app con Aurora, cómo cambia la API entre versiones y
cómo te enteras antes de que algo desaparezca.

## Qué es API pública

Es pública, y sigue las reglas de esta página:

- Todo lo que se importa **desde `aurora`** (`from aurora import App, button, ...`): los nombres
  de `aurora.__all__`, con sus parámetros, valores por defecto documentados y tipos de retorno.
- Los módulos públicos **`aurora.animate`**, **`aurora.dialogs`** y **`aurora.menus`** (sus
  `__all__`).
- Los métodos y propiedades documentados de `App`, `Window`, `Signal`, `Pilot`, `Canvas`, `Path`,
  `Column`, `Theme` y de los eventos (`KeyEvent`, `DragEvent`, `ScrollEvent`).
- Las **propiedades de estilo y de accesibilidad** de los elementos (`bg`, `radius`, `on_click`,
  `role`…) y los **tokens del tema** (`"$primary"`, `"$surface"`…), tal como los describe la
  [referencia](reference.md).
- La **línea de comandos** (`aurora dev`, `aurora build` y sus opciones), la tabla
  `[tool.aurora.build]` de `pyproject.toml` y las variables de entorno documentadas
  (`AURORA_MOTION`, `AURORA_BACKEND`, `AURORA_INSPECTOR`, `AURORA_RELOAD`).

**No** es pública, y puede cambiar en cualquier versión sin aviso:

- Todo lo que empieza por `_` (`aurora._core`, `_motion`, parámetros como `Window(_id=...)`).
- Los módulos internos aunque se puedan importar (`aurora.elements`, `aurora.reactive`,
  `aurora.signal`, `aurora.components.forms`…): importa siempre desde `aurora`.
- Los atributos de un `Element` (`children`, `style`, `to_spec()`…): un elemento se construye con
  las funciones de Aurora y se compone con `[...]`; lo que lleva dentro es un detalle.
- La forma del dict que viaja a Rust (el *spec*) y del árbol que devuelve el inspector.
- El **aspecto exacto** de los componentes: colores de los temas incluidos, márgenes, duraciones
  de animación. Aurora puede pulir cómo se ve algo sin que sea un cambio incompatible; si tus
  tests comparan píxeles, fija la versión.

## Versiones

Aurora sigue [Versionado Semántico](https://semver.org/lang/es/):

| | Mientras sea `0.x` | Desde la `1.0` |
|---|---|---|
| **Parche** (`0.5.0 → 0.5.1`) | Solo correcciones; nada se rompe ni se marca obsoleto. | Igual. |
| **Menor** (`0.5 → 0.6`) | Puede marcar cosas como obsoletas y **eliminar** lo que ya lo estaba. | Puede marcar cosas como obsoletas; nunca elimina. |
| **Mayor** (`1.x → 2.0`) | — | Elimina lo obsoleto. |

## Cómo se retira algo

Nada público desaparece ni cambia de significado de golpe. Antes de quitarlo o renombrarlo:

1. **Se marca como obsoleto.** Sigue funcionando igual, pero cada uso emite un
   `aurora.AuroraDeprecationWarning` que dice desde qué versión está obsoleto, en cuál se
   eliminará y qué usar en su lugar:

    ```text
    AuroraDeprecationWarning: El parámetro `color` de `badge()` está obsoleto desde la versión
    0.6 y se eliminará en la 0.7: usa `tone` en su lugar.
    ```

2. **Se anuncia** en la sección *Obsoleto* del [CHANGELOG](changelog.md) de esa versión, con la
   alternativa.
3. **Se mantiene un plazo**: al menos **una versión menor** mientras sea `0.x` (lo obsoleto en la
   0.6 se puede eliminar en la 0.7) y, desde la 1.0, hasta la siguiente versión mayor.
4. **Se elimina**, anotándolo en la sección *Eliminado* del CHANGELOG.

Cuando un cambio no se puede hacer así (un fallo de seguridad, un comportamiento que era un bug),
se explica en el CHANGELOG por qué no hubo periodo de obsolescencia.

## Ver los avisos en tu app

`AuroraDeprecationWarning` hereda de `FutureWarning`, así que Python lo muestra por defecto en la
consola. Para que tu suite de tests falle en cuanto uses algo obsoleto (y migrar antes de
actualizar):

```toml
# pyproject.toml
[tool.pytest.ini_options]
filterwarnings = ["error::aurora.AuroraDeprecationWarning"]
```

O para un script suelto: `python -W error::aurora.AuroraDeprecationWarning app.py`.

## Para quien contribuye

- La superficie pública está fijada en `tests/api.txt`: `tests/test_api.py` falla si un cambio
  añade, quita o cambia la firma de algo público. Si es intencionado, regenera el archivo con
  `AURORA_UPDATE_API=1 uv run pytest tests/test_api.py` y revisa el diff en el PR.
- Lo nuevo público entra en el `__all__` de su módulo, en la [referencia](reference.md) y en el
  CHANGELOG.
- Para retirar algo, `aurora._deprecation` tiene los ayudantes: `@deprecated(...)` para una
  función o un método entero, `@renamed_kwargs(viejo="nuevo", ...)` para renombrar parámetros y
  `warn(...)` para cualquier otro caso (un valor o un token). La suite de Aurora convierte el aviso
  en error, así que ni los ejemplos ni la documentación pueden usar lo obsoleto.
