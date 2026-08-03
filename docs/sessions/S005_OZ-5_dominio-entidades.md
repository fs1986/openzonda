# S005 · OZ-5 · Dominio: entidades y value objects

Fecha: 2026-08-02 · Duración: ~1 h · Fase: F1 · Rama: `feature/oz-5-dominio-entidades`

## Objetivo (copiado de la tarjeta)

Implementa el dominio de F1.1 del plan. qa primero: property tests de invariantes.
`Project`/`Site`/`Floor`/`FloorPlan`/`Calibration` frozen; value objects de unidades
(`Dbm`, `Meters`, `Pixels`).

El PO amplió el alcance en la instrucción de arranque: añadir `SurveySession`, punto de
medición con procedencia por atributo, y lecturas RSSI/SNR con «no disponible» de primera
clase.

## ⚠️ Solape de alcance con OZ-18, declarado

El catálogo §5.4 asigna **`SurveySession` + `Measurement` + flags de calidad a
OZ-18 (F3.1 · S018)**, no a esta tarjeta. La instrucción del PO los pide aquí.

Se implementan según lo pedido —el PO decide el alcance— pero queda anotado para que OZ-18
no vuelva a construir lo mismo desde cero. Lo que esta sesión deja hecho de OZ-18:

- `SurveySession` con modo, perfil de adaptador y muestras inmutables.
- `MeasurementPoint` con procedencia por atributo.
- `QualityFlag` con los cuatro casos del diseño §10.2 y detección del RSSI fuera de rango.

Lo que **no** cubre y OZ-18 seguirá necesitando: el flujo de captura en sí, la detección de
duplicados exactos, el rechazo por reloj no monotónico entre muestras consecutivas —que
necesita comparar muestras, no una sola— y la persistencia.

Es el acuerdo nº 3 de la retro de F0 en acción: contrastar contra el catálogo antes de
ejecutar. El solape existe y ahora es visible en lugar de aparecer como sorpresa en F3.

## Decisiones tomadas (y si requirieron ADR)

Ninguna requiere ADR: todas instrumentan ADR-006 y ADR-003, ya aceptados.

### 1. El álgebra de unidades separa dBm de dB

Es la decisión con más consecuencias del módulo. En RF se confunden constantemente:

- **dBm** es una potencia absoluta referida a 1 mW. Un RSSI de -65 dBm.
- **dB** es una *relación*, sin referencia. Un SNR de 30 dB, la atenuación de un tabique.

De ahí el álgebra que implementan los tipos:

| Operación | Resultado | Por qué |
| --- | --- | --- |
| `dBm - dBm` | `dB` | La relación entre dos niveles. **Eso es exactamente el SNR** |
| `dBm ± dB` | `dBm` | Atenuar o amplificar un nivel sigue dando un nivel |
| `dB + dB` | `dB` | Atenuaciones acumuladas: dos paredes |
| `dBm + dBm` | `TypeError` | No significa nada físicamente |

`Dbm.__sub__` lleva `@overload` para que el tipo estático de `rssi - noise` sea `Db` y no
`Dbm | Db`. Sin las sobrecargas, todo consumidor tendría que estrechar el tipo a mano, y el
día que alguien se equivoque de rama el error sería silencioso.

### 2. «No disponible» es un tipo, no un valor centinela

`Unavailable` **no tiene atributo `value`**. Es deliberado: cualquier código que intente
leerlo falla en vez de obtener un número inventado. Y lleva siempre su motivo, porque «no
hay dato» y «no hay dato porque el driver no lo reporta» son informaciones distintas para
quien lee un reporte.

`Reading[T] = Measured[T] | Unavailable` obliga al sistema de tipos a exigir que se
distingan ambos casos antes de usar el valor. No hay forma de olvidarse del caso ausente.

### 3. La derivación nunca mejora la confianza

`weakest()` gobierna todo cálculo: **un valor derivado no puede ser más fiable que su
entrada menos fiable**. Derivar de una estimación produce una estimación.

Aplicado al SNR, esto da tres reglas verificadas por tests:

- Con ambas entradas observadas → `DERIVED`. **Nunca `OBSERVED`**: el SNR se calcula, no se
  mide.
- Con una entrada estimada → `ESTIMATED`.
- Sin noise floor → `Unavailable(NOISE_FLOOR_NOT_REPORTED)`. Nunca `0`.

Este último es el caso **normal** en Windows, no la excepción (diseño §5). Hay un test
dedicado —`test_el_snr_nunca_es_cero_por_falta_de_datos`— cuya única función es proteger
contra la regresión más probable de todo el proyecto: que alguien, en algún momento,
devuelva `0 dB` porque «así el heatmap no queda vacío».

### 4. La calibración almacena su incertidumbre

La escala píxel↔metro se deriva de **dos clics humanos sobre una imagen**. Todo lo que el
producto afirma sobre distancias depende de ese número, así que declarar el error no es
adorno: un factor de escala sin incertidumbre aparenta más exactitud de la que tiene.

`relative_error = incertidumbre_del_clic / distancia_en_píxeles`. De ahí sale un resultado
con valor práctico: **calibrar sobre una distancia larga reduce el error**, porque el mismo
píxel de duda pesa menos. Es el consejo que la UI debe dar en F1.6, y aquí queda
cuantificado y testeado.

`to_meters_measured()` devuelve la distancia marcada como `DERIVED`, no observada: procede
de una escala que a su vez procede de dos clics.

### 5. Las posiciones se guardan en píxeles, no en metros

Los píxeles son lo que el usuario marcó. Los metros dependen de una calibración que puede
rehacerse después; almacenarlos congelaría una escala que quizá era incorrecta y haría
irrecuperable el dato original.

### 6. La procedencia es por atributo, no por muestra

El diseño §10.1 lo exige para el modo continuo: *"Posición derivada (flag); RSSI
observado"*. En una misma muestra el RSSI se midió de verdad y la posición se interpoló.
Una sola etiqueta por muestra perdería justo la información que hace confiable al producto.

### 7. Los flags de calidad anotan, no invalidan

El diseño §10.2 lista anomalías que hacen un dato sospechoso sin hacerlo inútil.
Descartarlo perdería información sobre un adaptador que se comporta mal; presentarlo sin
marca sería mentir. `is_suspect` expone la distinción sin ocultar el valor.

### 8. Los timestamps exigen zona horaria

Un survey se compara entre equipos y husos. Un `datetime` naive es ambiguo, y la ambigüedad
aparecería meses después al cruzar dos sesiones. Se rechaza en el constructor.

## Artefactos

| Módulo | Contenido |
| --- | --- |
| `domain/units.py` | `Dbm`, `Db`, `Meters`, `Pixels` con su álgebra |
| `domain/measurement.py` | `Measured`, `Provenance` (existentes) + `Unavailable`, `UnavailableReason`, `Reading`, `weakest()` |
| `domain/rf.py` | `snr_from()`, rango físico del RSSI |
| `domain/calibration.py` | `Calibration` con error propagado |
| `domain/project.py` | `Entity`, `Project`, `Site`, `Floor`, `FloorPlan` |
| `domain/survey.py` | `Bssid`, `SurveyMode`, `QualityFlag`, `PlanPosition`, `AdapterProfile`, `MeasurementPoint`, `SurveySession` |

Tests: de 44 a **126**. Cinco archivos nuevos en `tests/unit/`.

## DoD: checklist con estado real (no aspiracional)

- [x] **Entidades frozen** — `Project`, `Site`, `Floor`, `FloorPlan`, `Calibration`,
      `SurveySession`, `MeasurementPoint`. Todas con test de inmutabilidad.
- [x] **Value objects de unidades que impiden mezclar magnitudes** — verificado con tests
      que exigen `TypeError` al sumar dBm+dBm, píxeles+metros y metros+dB.
- [x] **`mypy --strict` verde** — 8 módulos, sin errores. Las sobrecargas de `Dbm.__sub__`
      hacen que el tipo de un SNR sea estáticamente `Db`.
- [x] **Property tests de invariantes** — cuatro con Hypothesis sobre la calibración: ida y
      vuelta conserva el valor, la escala es siempre finita y positiva, y la conversión es
      monótona.
- [x] **Honestidad metrológica ejecutable** — el «no disponible» es un tipo sin `value`, la
      derivación nunca mejora la confianza, y el SNR nunca es `0` por falta de datos.
- [x] **Contratos de capas** — 4 kept. El dominio sigue sin importar nada externo.
- [x] **Test-first** — los cinco archivos de test se escribieron y se vieron fallar con
      `ModuleNotFoundError` antes de existir la implementación.

## Validaciones [HW] pendientes del fundador

Ninguna. Dominio puro, sin dependencia de hardware ni del instalador — que es precisamente
por lo que el PO decidió arrancar F1 en paralelo sin esperar a la validación en VM de OZ-4.

## Desvíos / deuda registrada

- **Solape con OZ-18**, detallado arriba. Es el desvío principal de la sesión.
- `Floor.height` queda declarada pero sin uso: la atenuación entre plantas llega en F5.
- `AccessPoint` (agrupación de BSS por OUI+SSID) del diseño §8.1 **no** se implementa: el
  catálogo no lo pide en F1.1 y agruparlo bien exige heurística editable por el usuario.
  `Bssid.oui` deja el gancho preparado.
- `UnavailableReason.OUT_OF_RANGE` y `rssi_reading()` existen pero todavía no los usa nadie:
  los consumirá el adaptador de captura en F2.

## Próxima sesión sugerida

**OZ-31 · Alinear la documentación de diseño con el repo real**, ya planificada por el PO
para inmediatamente después de esta. Luego **OZ-6 · Migraciones SQLite + repositorio**,
que es la continuación natural: estas entidades necesitan dónde vivir.
