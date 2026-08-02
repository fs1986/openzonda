# S026 · OZ-25 · Smoke test usable por una persona

Fecha: 2026-08-02 · Duración: ~20 min · Fase: F0 · Rama: `feature/oz-25-smoke-usable`

## Objetivo (copiado de la tarjeta)

Modificador `-Visible` en `smoke_local.ps1`, lanzador `.cmd` de doble clic, y documentar
ambas formas de uso en `BUILD.md`. Sin cambiar el comportamiento por defecto.

## Cómo se detectó

El fundador intentó ejecutar `smoke_local.ps1` para su validación `[HW]` de OZ-3 y solo vio
*"una ventana en negro que se cierra instantáneamente"*.

Diagnóstico: era la consola de PowerShell, no la aplicación. Windows bloquea los `.ps1` por
política de ejecución; el script fallaba antes de arrancar nada y la ventana se cerraba
antes de que el error fuera legible. Se confirmó mirando el log del bundle: no había
entrada nueva, así que la aplicación nunca llegó a ejecutarse.

Y aunque hubiera funcionado, tampoco habría servido: el script lanzaba la ventana
**minimizada** y la cerraba a 1,5 s.

## La causa real: se escribió para el consumidor equivocado

El DoD de OZ-3 dice literalmente *"[HW] **Tú** ejecutas `smoke_local.ps1`"*. El script se
escribió pensando solo en el runner de CI: silencioso, rápido, no interactivo, ventana
minimizada. Todas esas propiedades son correctas para CI y hostiles para una persona.

No es un fallo del producto: es un fallo de la herramienta de verificación, que es peor de
detectar precisamente porque el producto funcionaba.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requiere ADR.

1. **El modo persona es un añadido, no el nuevo defecto.** CI depende de que el script sea
   rápido y silencioso; cambiar el comportamiento por defecto habría alargado cada build
   por comodidad local. `-Visible` es explícito.
2. **El lanzador es un `.cmd` y no un acceso directo.** Un `.cmd` es texto plano,
   versionable y revisable en un diff; un `.lnk` es binario y opaco.
3. **El `.cmd` propaga el código de salida.** Con `pause` de por medio hay que capturar
   `%ERRORLEVEL%` antes, o se pierde. Sin esto el lanzador serviría para doble clic pero
   sería inútil dentro de otro script, y acabaríamos con dos formas divergentes de invocar
   lo mismo.
4. **El `.cmd` va sin acentos.** Los `.cmd` se interpretan con la codepage de la consola,
   que en un Windows en español suele ser 850, y los mostraría rotos. Es el mismo problema
   que ya obligó a guardar el `.ps1` con BOM, resuelto de otra forma porque el mecanismo es
   distinto.
5. **La salida ahora separa arranque real de cierre programado.** Antes decía "2,1 s
   (incluye el cierre programado de 1,5 s)" y obligaba a restar mentalmente. Ahora imprime
   `Arranque real: ~0,4 s`, que es el número que el DoD compara contra los 4 s.

## Artefactos

- `scripts/smoke_local.cmd` — lanzador de doble clic.
- `scripts/smoke_local.ps1` — modificador `-Visible`, tiempo de cierre y estilo de ventana
  parametrizados, salida que separa arranque real de cierre programado.
- `BUILD.md` — sección de verificación reescrita.

## DoD: checklist con estado real (no aspiracional)

Los cuatro caminos se ejecutaron de verdad, no se razonaron:

- [x] **`.cmd` con doble clic, camino de éxito** — `exit del .cmd: 0`, mensaje "El smoke
      test ha pasado" y pausa.
- [x] **`.cmd`, camino de fallo** — con un `-BundleDir` inexistente: `exit del .cmd: 1`,
      mensaje de fallo legible y pausa. Es el caso que importa: si al fallar no pausara,
      seguiríamos sin poder leer el error.
- [x] **`-Visible`** — ventana normal durante 8 s; `exit: 0`. Salida: *"Arrancó y cerró
      limpio en 8,4 s, de los cuales 8 s son el cierre programado"* y *"Arranque real:
      ~0,4 s"*.
- [x] **El comportamiento por defecto no cambia** — sigue lanzando minimizado con cierre a
      1,5 s; `exit: 0`. El workflow de CI no se ha tocado.
- [x] **`BUILD.md`** documenta las tres formas de invocarlo.

## Corrección adicional en `BUILD.md`

Los ejemplos usaban `pwsh`, que es PowerShell 7 y **no viene con Windows**. Un lector que
siguiera la guía al pie de la letra se habría encontrado con "comando no reconocido" en el
primer intento. Cambiados a `powershell -ExecutionPolicy Bypass -File`, que funciona de
fábrica, con una nota explicando la diferencia. Es el mismo tipo de fallo que motiva esta
tarjeta: documentación escrita desde el entorno de quien la escribe, no desde el de quien
la lee.

## Validaciones [HW] pendientes del fundador

Ninguna bloqueante. Si quieres confirmarlo: doble clic en `scripts\smoke_local.cmd` debe
dejar la ventana abierta hasta que pulses una tecla.

## Desvíos / deuda registrada

Ninguna nueva. Los siete elementos de la retro de F0 siguen sin tarjeta.

## Próxima sesión sugerida

**OZ-5 · S005 · Dominio: entidades y value objects**, primera de F1. Antes conviene dar
destino a la deuda de la retro de F0 y validar el MSI de OZ-4 en VM limpia.
