# Visión de Aurora

> **Que construir una interfaz de escritorio bonita, rápida y mantenible en Python
> sea tan directo como escribir un script.**

## El problema

Python es el lenguaje con el que millones de personas automatizan, analizan datos y construyen
sistemas de IA. Pero cuando quieren ponerle una **interfaz de escritorio** a ese trabajo, se
encuentran con un dilema incómodo:

1. **Toolkits tradicionales** (Tkinter, wx, incluso Qt sin mucho trabajo de estilo): estables y
   completos, pero con una estética y un modelo de programación imperativo que se sienten de otra
   época. Conseguir algo que parezca un producto de 2026 exige muchísimo esfuerzo.
2. **Stacks web empaquetados** (React + WebView + FastAPI, Electron, etc.): se ven muy bien, pero
   obligan a dominar dos o tres ecosistemas, a mantener un protocolo entre frontend y backend, y a
   cargar un motor de navegador entero para mostrar un formulario.
3. **Frameworks Python de UI web** (que sirven la interfaz al navegador): productivos, pero la app
   vive en una pestaña, no en una ventana nativa, y el rendimiento depende del puente con el navegador.

El resultado es que la mayoría de herramientas internas, dashboards personales y paneles de control
escritos en Python **nunca llegan a tener una buena interfaz**, o la tienen a un coste
desproporcionado.

## La apuesta

Aurora separa el problema en dos mitades y le da a cada una la herramienta adecuada:

- **Python describe.** La interfaz es una función pura de tu estado, escrita con primitivas
  declarativas y componentes que son simples funciones. Es la parte que tú lees, escribes y
  mantienes, y tiene que ser tan legible como un buen script.
- **Rust ejecuta.** Todo lo que ocurre en cada frame —layout, tipografía, render, animaciones,
  hit-testing— vive en un núcleo nativo construido sobre librerías probadas en producción
  (Skia, el motor gráfico de Chrome y Android; Taffy, el motor de layout que usan Zed y Bevy).

La frontera entre ambos mundos se cruza **pocas veces y con mucha información**: un árbol completo
por actualización, nunca miles de llamadas pequeñas. Así Python conserva su ergonomía sin pagar
el coste del intérprete en cada píxel.

## Principios de diseño

Cuando haya que decidir, estos principios desempatan, en este orden:

1. **Bonito por defecto.** Un componente sin configurar debe verse profesional. La calidad visual
   no es un plugin ni un tema premium: es el punto de partida. Si para que algo se vea bien hay que
   pelear con la librería, es un bug de la librería.
2. **Python idiomático.** Funciones, keyword arguments, type hints, `lambda` para lo dinámico.
   Nada de DSLs de plantillas, archivos de marcado aparte ni clases que heredar para pintar un botón.
3. **El camino rápido es el camino fácil.** La API se diseña para que lo más natural de escribir
   sea también lo más eficiente. El usuario no debería necesitar saber qué es un dirty flag.
4. **Nativo, no embebido.** Una ventana real del sistema operativo, sin navegador escondido.
   Arranque rápido, memoria contenida, integración con el escritorio.
5. **Honestidad sobre el estado.** Documentamos lo que no funciona con la misma claridad que lo que
   sí. Cada limitación conocida aparece en el README y en el roadmap.
6. **Verificable sin pantalla.** Todo lo que se pinta se puede renderizar a PNG en un test.
   La calidad visual se protege con tests, igual que la lógica.

## Para quién es

- **Ingenieros y científicos de datos** que quieren un dashboard o una herramienta de escritorio
  para su trabajo sin aprender desarrollo frontend.
- **Equipos que construyen herramientas internas** y necesitan algo que se vea serio delante de
  usuarios no técnicos.
- **Desarrolladores de IA y automatización** que quieren darle una cara a sus agentes, pipelines
  y modelos locales.
- **Cualquiera que escriba utilidades personales** y quiera que sea un placer usarlas a diario.

## Qué NO es Aurora (no-objetivos)

Decir que no protege el foco. Al menos hasta la 1.0:

- **No es un framework web.** No renderiza a HTML ni corre en el navegador.
- **No es un reemplazo de Qt.** No pretende igualar décadas de widgets, integración con sistemas
  operativos y casos límite. Si necesitas eso hoy, usa Qt.
- **No es un motor de juegos.** Hay animaciones y gráficos personalizados, pero el foco son
  interfaces de aplicación, no escenas 3D ni bucles de juego.
- **No promete móvil (todavía).** El foco es Windows, macOS y Linux de escritorio. La arquitectura
  no lo impide, pero no es una prioridad.
- **No es un constructor visual.** La interfaz se escribe en código; un editor visual podría venir
  después, construido sobre la misma API.

## Cómo sabremos que funciona

- Una persona que nunca usó Aurora construye un dashboard con buen aspecto **en menos de una hora**,
  leyendo solo la guía.
- Las apps de ejemplo se mantienen a **60 fps** en hardware modesto con miles de elementos
  (cuando lleguen scroll virtualizado y reactividad de grano fino).
- El tamaño del ejecutable y el consumo de memoria quedan **muy por debajo** de una app equivalente
  empaquetada con un navegador.
- Las capturas de la documentación se generan con la propia librería y sirven como tests de regresión.

## Horizonte

A largo plazo, Aurora aspira a ser **la forma por defecto de ponerle una interfaz de escritorio a
código Python**: con una biblioteca de componentes rica y accesible, gráficos de datos nativos
capaces de mostrar millones de puntos, hot reload que conserve el estado, y un empaquetado que
convierta una app en un ejecutable distribuible con un solo comando.

El camino concreto está en el [Roadmap](ROADMAP.md).
