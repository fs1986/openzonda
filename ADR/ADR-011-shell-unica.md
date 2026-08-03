# ADR-011 — Shell única con vista central reemplazable

- **Estado:** Propuesto (pendiente de aceptación del fundador en el PR de OZ-8)
- **Fecha:** 2026-08-03
- **Decisores:** architect
- **Relacionado:** OZ-8 (F1.4). Complementa el patrón de UI de ADR-008 (composition root).

## Contexto

El brief de UI/UX no resuelve la forma de la pantalla de Inicio/Proyectos: solo enumera tres
verbos (crear, abrir, recientes) y manda «patrones de aplicación de escritorio: barra de
menú, barra de herramientas, paneles acoplables, barra de estado» (brief §4). Hay que decidir
cómo se ensambla la shell y cómo se navega entre inicio y un proyecto abierto. Dos opciones:

1. **Shell única** con una vista central reemplazable (`QStackedWidget`: Inicio ↔ Proyecto).
2. **Diálogo de bienvenida separado** que precede a la ventana principal y se cierra al abrir.

## Decisión

**Shell única.** Una sola `QMainWindow` con menú, toolbar y barra de estado; el área central
es un `QStackedWidget` que alterna entre la vista de Inicio (crear/abrir/recientes, con estado
vacío) y la vista de Proyecto. La navegación es por **reemplazo de la vista central**, no por
ventanas separadas.

El estado de UI vive en **ViewModels** (`ShellViewModel`) testeables sin `QApplication`; los
widgets solo conectan comandos y pintan el estado emitido (CLAUDE.md: «el estado de UI vive en
ViewModels», sin estado global oculto).

## Consecuencias

- **Positivas:** realiza el patrón desktop del brief sobre una única superficie; los docks del
  survey (árbol de sitios/plantas, redes en vivo — brief §5.1) se acoplan más adelante sin
  reestructurar la ventana; una sola ventana restaura y persiste su geometría.
- **Aceptadas:** en OZ-8 la vista de Proyecto es mínima (identidad + nombre editable); el árbol
  del proyecto y el plano llegan en tarjetas posteriores (F1.5+).
- **Alternativas descartadas:** *diálogo de bienvenida separado* — dos superficies distintas y
  un «launcher» que se cierra; peor encaje con el modelo de ventana única con docks y con la
  persistencia de estado de la ventana.

## Verificación

- `tests/unit/test_shell_viewmodel.py`: la lógica de la shell (dirty, recientes, guardar-como,
  errores) se verifica **headless**, sin Qt.
- `tests/integration/test_main_window.py`: la vista central cambia de Inicio a Proyecto según
  el estado, con la plataforma Qt `offscreen`.
