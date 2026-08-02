# Retro de fase F0 — Fundaciones

Fecha: 2026-08-02 · Sesiones cubiertas: S001–S004, S023, S025 · Tarjetas: OZ-1..OZ-4, OZ-23, OZ-24

## Métricas

| Métrica | Valor |
| --- | --- |
| Sesiones planificadas / ejecutadas | 4 / 6 |
| Duración media por sesión | No recuperable en S001–S002; ~1 h en las demás |
| Tarjetas cerradas con DoD completo a la primera | **0 de 4** de las planificadas |
| Tarjetas que necesitaron una sesión posterior para cerrar su DoD | 2 (OZ-1, OZ-2) |
| `VERDICT: FAIL` emitidos | 0 |
| Sesiones sin session log en su momento | 2 (S001, S002), reconstruidas después |
| Tarjetas duplicadas creadas y cerradas sin trabajo | 1 (OZ-24) |
| Tests | 4 → 44 |
| Contratos de capas verificados | 0 → 4 |

La métrica que importa es la tercera: **ninguna de las cuatro tarjetas planificadas de F0
cerró su DoD a la primera**. Las dos primeras se dieron por terminadas sin cumplirlo, y
las dos últimas quedaron en *Review* a la espera de validación física, que es lo correcto.

## Qué funcionó

- **El DoD del catálogo, cuando se lee.** Los tres gaps de OZ-2 —lockfile, CI en Windows,
  test de capas— estaban escritos literalmente en `plan-operativo-sesiones.md` §5.1 desde
  el principio. No hizo falta descubrirlos: hizo falta leerlos.
- **Validar por mutación.** El test que demuestra que un import ilegal rompe CI solo vale
  porque se comprobó que falla al debilitar el contrato. Un test que no se ha visto fallar
  no prueba nada. Este método debería aplicarse a toda barrera nueva.
- **Ejecutar en lugar de leer.** Los dos bugs de `smoke_local.ps1` (sintaxis de PowerShell
  7 en un shell 5.1, y acentos rotos por falta de BOM) y el MSI que empaquetaba
  `logs/` y `settings.json` solo aparecieron al ejecutar de verdad. Ninguno se habría
  detectado revisando el código.
- **Los ADR como sitio donde se justifica lo caro.** ADR-007 y ADR-008 salieron de
  tensiones reales encontradas al implementar, no de un ejercicio de documentación.

## Qué no funcionó

- **OZ-1 y OZ-2 se cerraron sin contrastar su DoD**, y quedaron en *In Progress* durante
  toda la fase, con el tablero desalineado del repositorio.
- **OZ-1 se cerró como *Done* por segunda vez de forma incorrecta**, inmediatamente después
  de haber documentado ese mismo patrón de fallo en OZ-2. Se detectó al revisar el DoD
  punto por punto y se revirtió.
- **OZ-24 se creó sin contrastar el catálogo** y duplicaba F0.7, que ya estaba dentro de
  OZ-4. Se cerró sin trabajo.
- **La regla de oro estuvo incumplida desde el minuto uno.** De las cuatro sesiones
  iniciales, ninguna dejó bitácora. Los logs de S001 y S002 son reconstrucciones marcadas
  como tales, y su "por qué" se ha perdido para siempre.
- **La documentación describía cosas que no existían**: un repo documental separado,
  rutas con el nombre anterior del producto, WiX v4 como toolchain, y un `SECURITY.md`
  que prometía "artefactos firmados" inexistentes.

## DoD fallidos: análisis de causa

| DoD incumplido | Causa raíz |
| --- | --- |
| OZ-2: lockfile con hashes | **No había toolchain en la máquina de desarrollo.** Ni Python ni `uv` estaban instalados: era materialmente imposible generar un `uv.lock`. Nada se ejecutó en local durante F0.1–F0.3; todo el feedback venía de CI |
| OZ-2: CI en ubuntu+windows | Se implementó la mitad del requisito y nadie contrastó la otra |
| OZ-2: violación de capas rechazada | Se confundió "el comando corre en CI" con "la barrera funciona". Nada demostraba lo segundo |
| OZ-1: ADR-007, templates, retros/, session log | Se dio por hecho que "el trabajo está mergeado" equivale a "el DoD está cumplido" |

Las cuatro comparten el mismo patrón: **se verificó la existencia del mecanismo, no su
efecto.** Un workflow que corre, un comando que sale en verde, un archivo que está en
`main`. Ninguna de esas cosas es la propiedad que el DoD pedía.

## Scope creep detectado

Poco, y en su mayoría justificado:

- OZ-3 corrigió la nomenclatura del producto en el diseño (§18, §19). No estaba en su
  alcance, pero era la primera tarjeta que materializaba esas rutas en código y dejarlo
  habría metido el nombre anterior dentro del binario.
- OZ-4 cambió el toolchain de WiX v4 a v5. Forzado: v4 no puede harvestear un árbol de
  archivos sin reinventar `heat`.
- OZ-4 corrigió una afirmación falsa en `SECURITY.md`. Fuera de alcance, pero una política
  de seguridad que promete firma de código inexistente es peor que no tenerla.

En sentido contrario, OZ-23 **rechazó** ampliar alcance al SBOM por decisión explícita del
fundador, y OZ-4 dejó fuera el ZIP portable pese a estar en los canales de distribución
del diseño, porque F0.7 no lo pide.

## Deuda acumulada al cierre de la fase

| Deuda | Origen | Tarjeta que la recoge |
| --- | --- | --- |
| Instalador sin firmar; SmartScreen advertirá | S004 | **OZ-26** — bloqueada: requiere comprar certificado |
| ZIP portable como canal de distribución (diseño §Distribución) no producido por el release | S004 | **OZ-27** |
| Diálogo de desinstalación con opción "eliminar todo" (diseño §18) no implementado | S004 | **OZ-28** |
| Sin icono ni `VERSIONINFO` en el ejecutable | S003 | **OZ-29** — el icono queda bloqueado: es decisión de identidad visual |
| `pre-commit` nunca configurado, pese a pedirlo la instrucción de S002 | S002 | **OZ-30** |
| El plan operativo §2 describe un repo documental separado que no existe | S001 | **OZ-31** |
| El diseño §7.3 no contempla `apps/openzonda` | S003 | **OZ-31** |

> **Actualización del 2026-08-02.** Cuando se redactó esta retro, los siete elementos no
> tenían tarjeta, y eso era el mismo mecanismo que produjo los DoD fallidos: quedaban
> registrados en un log que nadie está obligado a releer. El fundador autorizó el triaje y
> se abrieron seis tarjetas (dos elementos comparten la OZ-31 por ser el mismo trabajo).
>
> Dos quedan **bloqueadas por decisiones que no son técnicas**: OZ-26 necesita adquirir un
> certificado de firma de código, y el icono de OZ-29 es una decisión de identidad visual
> del fundador. Estar bloqueada y estar olvidada no es lo mismo: ahora son visibles en el
> tablero y su bloqueo está escrito.
>
> Con esto queda cumplido el acuerdo nº 4 y levantada la condición de que F1 no arranque
> hasta que la deuda tuviera destino.

## Validaciones [HW] pendientes acumuladas

1. **OZ-3**: ejecutar `scripts/smoke_local.ps1` y confirmar arranque < 4 s; comprobar que
   la ventana se dibuja. CI corre en modo `offscreen`, así que nadie ha visto todavía la
   interfaz renderizada.
2. **OZ-4**: install → upgrade → uninstall en una VM Windows 11 limpia.

Ninguna es opcional para empezar F1: la tarjeta OZ-8 construye la shell de proyectos sobre
esa ventana, y OZ-10 produce el primer pre-release instalable. Arrancar F1 sin haber visto
la ventana funcionar significa construir sobre algo no verificado.

## Acuerdos para la fase siguiente

1. **El DoD se contrasta punto por punto contra el repositorio antes de mover una tarjeta
   fuera de *In Progress*.** No basta con enunciarlo: el template de session log
   (`docs/templates/session-log.md`) ahora exige una casilla por punto con su evidencia
   concreta. *Verificación*: una tarjeta cuyo comentario de cierre no incluya esa tabla no
   se mueve a *Review*.
2. **Toda barrera nueva se valida por mutación.** Si un test protege un invariante, hay
   que verlo fallar al romper el invariante a propósito. *Verificación*: el session log
   documenta qué se rompió y qué test se cayó.
3. **Antes de crear una tarjeta, contrastarla contra el catálogo §5.** OZ-24 no debería
   haber existido. *Verificación*: la descripción de toda tarjeta nueva cita la entrada del
   catálogo que cubre, o dice explícitamente que no hay ninguna.
4. **La deuda sin tarjeta no es deuda: es olvido.** Al cierre de cada fase, cada elemento
   de la tabla de deuda o se convierte en tarjeta o se declara aceptado por escrito.
   *Verificación*: esta retro es el primer caso de prueba — F1 no arranca hasta que los
   siete elementos de arriba tengan destino.
5. **Verificar el efecto, no el mecanismo.** Es la causa raíz común de los cuatro DoD
   fallidos y merece formularse como pregunta explícita en cada revisión: *¿qué observaría
   si esto NO funcionara?* Si la respuesta es "lo mismo que ahora", no está verificado.
