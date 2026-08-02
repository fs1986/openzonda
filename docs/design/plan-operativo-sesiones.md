
OpenZonda
Plan Operativo de Sesiones con Claude Code — v1.1
Modelo de equipo virtual con subagentes · Protocolo de sesión · Trazabilidad Jira · Catálogo de sesiones F0–F9
Producto: OpenZonda · Key Jira: OPENZONDA · Repos: openzonda (código) y openzonda-docs (documental).

| Campo | Valor |
| --- | --- |
| Documento | Plan operativo (complementa Diseño v0.2 y Plan de Implementación v1.0) |
| Entorno | Windows 10/11 + Claude Code (terminal) + Git + uv + WiX |
| Modelo de trabajo | 1 sesión = 1 tarjeta Jira = 1 bloque de trabajo con Claude Code (2–4 h) |
| Trazabilidad | Cada sesión genera un session log en el repo documental, enlazado a su tarjeta |
| Interacción con Jira | Solo el fundador y Claude Code operan las tarjetas; Claude (chat) solo cuando se le pida |

# Tabla de contenidos
Actualizar campos en Word (Ctrl+A, F9).

# 1. Modelo operativo: equipo virtual en Claude Code

## 1.1 Concepto
Claude Code actúa como un equipo de desarrollo completo mediante subagentes definidos en el repositorio (.claude/agents/). El agente principal orquesta; los subagentes ejecutan roles especializados con contexto propio, cada uno con permisos de herramientas acotados (principio de least-privilege que ya aplicas en tus arquitecturas multi-agente). El fundador actúa como Product Owner y única autoridad de merge.

## 1.2 Qué se comprime y qué no (expectativa honesta)
- Se comprime: escritura de código, tests, documentación, scaffolding, revisión cruzada, gestión de tarjetas y session logs. Un equipo virtual trabaja en paralelo dentro de la sesión (dev implementa mientras qa escribe tests del contrato y docs redacta).
- No se comprime: (a) validación física — Claude Code no puede escanear radios: las pruebas con NICs reales, VMs de instalación y surveys de campo las ejecutas tú (el plan las marca como [HW]); (b) tu ancho de banda de revisión — cada sesión termina con tu revisión y merge; (c) el feedback de colegas en la alpha, que tiene su ritmo humano.
★ Estimación revisada: ~58 sesiones hasta 1.0. Con 3–4 sesiones/semana: alpha privada (fin F3) en 6–7 semanas y release 1.0 en ~5 meses — contra 16–18 meses del plan manual. El cuello de botella pasa de 'escribir código' a 'revisar, validar en hardware y decidir'.

## 1.3 Estructura de subagentes (.claude/agents/)

| Agente | Rol | Herramientas permitidas | Cuándo se invoca |
| --- | --- | --- | --- |
| architect | Decisiones de diseño, ADRs, revisión de fronteras de capas | Read, Grep, Glob (solo lectura de código) | Inicio de fase; cualquier cambio que toque contratos entre paquetes |
| dev-core | Implementación de dominio, servicios, persistencia | Read, Edit, Write, Bash (uv, pytest) | Cuerpo principal de casi toda sesión |
| dev-ui | PySide6: vistas, viewmodels, UX de terreno | Read, Edit, Write, Bash | Sesiones con componente UI |
| qa | Escribe/ejecuta tests ANTES de aceptar implementación; property tests; cobertura; casos borde | Read, Write (solo tests/), Bash (pytest, mypy, ruff) | Toda sesión; veto sobre el DoD |
| security | Revisión de superficie: parsing hostil, zips, ctypes, dependencias nuevas | Read, Grep, Bash (pip-audit) | Sesiones que tocan IO externo, parsers o deps |
| docs | Docstrings, docs/ de usuario y desarrollador, CHANGELOG, session log | Read, Write (docs/, *.md) | Cierre de toda sesión |
| pm-jira | Lee la tarjeta al inicio, descompone subtareas, actualiza estado/comentarios al cierre vía MCP Atlassian | Atlassian MCP, Read | Apertura y cierre de toda sesión |
| scrum | Retro de fase, métricas de sesiones (duración, DoD fallidos), detección de scope creep | Read (repo documental) | Cierre de cada fase |
| devops | CI, PyInstaller, WiX, pipelines de release, SBOM | Read, Edit, Write, Bash | F0 y sesiones de packaging/release |

## 1.4 Ejemplo de definición de subagente

# .claude/agents/qa.md
---
name: qa
description: QA engineer. Escribe los tests del contrato ANTES de
  aceptar una implementación. Ejecuta pytest/mypy/ruff y reporta.
  Tiene veto sobre el DoD de la sesión.
tools: Read, Write, Bash
---
Eres el QA del proyecto. Reglas:
1. Nunca modificas código de producción; solo tests/ y fixtures.
2. Para cada feature exiges: caso feliz, caso borde, caso hostil.
3. Parsers y contenedores de archivo requieren property tests
   (hypothesis) y al menos un fixture malformado.
4. Si cobertura de domain/ baja de 90%, el DoD falla.
5. Tu salida final es siempre: VERDICT: PASS|FAIL + evidencia.

## 1.5 CLAUDE.md del repositorio (reglas permanentes)
- Contexto: enlaces a Diseño v0.2, Plan v1.0 y este documento dentro del repo documental; resumen de arquitectura de capas y decisiones inmutables (§25 del diseño) que ningún agente puede violar.
- Flujo obligatorio de sesión (protocolo §3 de este documento) incluido literalmente para que Code lo siga sin recordárselo.
- Convenciones: commits convencionales (feat/fix/docs/test/chore + scope de paquete), rama por tarjeta (feature/OPENZONDA-N-slug), PR aunque seas el único humano (la revisión la hace architect+qa+security antes de pedirte merge).
- Prohibiciones explícitas: tocar decisiones §25 sin ADR; mergear sin VERDICT: PASS de qa; instalar dependencias sin pasar por security.

## 1.6 Matriz de modelos IA por agente y tipo de tarea
Cada subagente declara su modelo en el frontmatter (campo model: opus | sonnet | haiku | inherit). El criterio: capacidad máxima donde una mala decisión es cara (arquitectura, seguridad, bindings de bajo nivel) y modelos rápidos/económicos donde la tarea es mecánica (gestión de tarjetas, logs, changelog). Se usan alias, no versiones fijas: el alias resuelve siempre a la versión más reciente de la familia.

| Agente | Modelo | Justificación |
| --- | --- | --- |
| Sesión principal (orquestador) | opusplan | Modo híbrido de Claude Code: Opus planifica (plan mode, solo lectura) y Sonnet ejecuta. La planificación de la sesión es la decisión más cara; la ejecución ya viene acotada por el plan aprobado |
| architect | opus | ADRs, contratos entre capas, revisión de diseño: máximo razonamiento, bajo volumen de invocaciones |
| security | opus | Threat review de parsers, contenedores y deps: un fallo aquí es el más caro del proyecto; se invoca poco |
| dev-core | sonnet | Implementación estándar. Escala a opus solo en las sesiones marcadas ★ (abajo) |
| dev-ui | sonnet | PySide6/ViewModels: patrón conocido, volumen alto |
| qa | sonnet | Diseñar tests y casos borde exige razonar; ejecutar suites es Bash (coste de modelo casi nulo) |
| devops | sonnet | CI/WiX/PyInstaller: técnico pero bien documentado |
| scrum | sonnet | Análisis de retro sobre session logs: síntesis, no mecánica |
| docs | haiku | Session logs, CHANGELOG, docstrings: formato definido por template. Las release notes y docs de usuario finales las revisa la sesión principal |
| pm-jira | haiku | CRUD de tarjetas, comentarios con formato fijo, transiciones de estado: puramente mecánico |

### Regla de escalado ★ (dev-core → opus)
El agente líder de implementación usa opus (vía el parámetro model de la invocación o duplicando el agente como dev-core-opus) en las sesiones donde el coste de un error sutil es máximo:
- S007 (contenedor .wifisurvey: atomicidad y superficie hostil), S011–S012 (structs ctypes y flujo de notificaciones: un offset mal calculado corrompe datos silenciosamente), S014–S015 (parser de IEs: correctitud binaria), F5 S030–S034 (RF engine: matemática de propagación y determinismo), F6 sesiones de import de proyectos de terceros (ingeniería inversa de formato).
- El resto de sesiones no escala: Sonnet con el contrato de tests de qa delante es suficiente y 5× más económico.

### Configuración práctica

# Frontmatter de cada agente (.claude/agents/architect.md):
---
name: architect
model: opus
tools: Read, Grep, Glob
---

# Sesión: arrancar el orquestador en modo híbrido
claude              # y luego /model opusplan

# Nota: no fijar CLAUDE_CODE_SUBAGENT_MODEL globalmente —

# pisa la resolución de modelo de los subagentes y anularía

# esta matriz. La matriz vive en el frontmatter de cada agente.
★ Regla presupuestaria: Opus se gasta en decisiones, no en volumen. Si una sesión Sonnet produce dos VERDICT: FAIL consecutivos de qa sobre el mismo problema, esa es la señal para re-ejecutar el paso con opus en vez de iterar a ciegas.

# 2. Repositorio documental (se crea primero)
Antes que el repo de código existe el repo documental: es la memoria del proyecto y el registro auditable de cada sesión. Recomendación: repo Git separado (openzonda-docs) para que su historia no se mezcle con la del código y pueda compartirse con colegas sin dar acceso al código en fases tempranas si se quisiera.
openzonda-docs/
  README.md                  # índice del repo y estado del proyecto
  design/
    software-design-v0.2.md  # diseño convertido a markdown (fuente de verdad)
    plan-implementacion.md
    plan-operativo-sesiones.md   # este documento
  adr/                       # ADR-001..N (inmutables)
  sessions/                  # UN archivo por sesión
    S001_OPENZONDA-1_bootstrap-docs.md
    S002_OPENZONDA-2_monorepo.md
    ...
  retros/                    # retro de cada fase (agente scrum)
    F0-retro.md
  hardware/HARDWARE.md       # NICs validadas (desde F2)
  templates/
    session-log.md  jira-card.md  retro.md

## 2.1 Template de session log

# S0NN · OPENZONDA-N · <título>
Fecha: · Duración: · Fase: F# · Rama: feature/OPENZONDA-N-slug

## Objetivo (copiado de la tarjeta)

## Agentes utilizados y salidas clave

## Decisiones tomadas (y si requirieron ADR)

## Artefactos: commits/PR, archivos nuevos, tests agregados

## DoD: checklist con estado real (no aspiracional)

## Validaciones [HW] pendientes del fundador

## Desvíos / deuda registrada

## Próxima sesión sugerida
El agente docs genera este archivo al cierre de cada sesión; el agente pm-jira publica un resumen de 5 líneas como comentario en la tarjeta con link al log. La tarjeta guarda el qué; el session log guarda el cómo y el porqué.

# 3. Protocolo de sesión (invariante)

| Etapa | Quién | Acción |
| --- | --- | --- |
| 0. Apertura | Fundador | Abre Claude Code en el repo y da la instrucción de arranque de la sesión (catálogo §5) |
| 1. Contexto | pm-jira | Lee la tarjeta OPENZONDA-N vía MCP, verifica dependencias cerradas, mueve a In Progress, propone descomposición en subtareas |
| 2. Diseño | architect | Valida que el plan de la sesión respeta capas y §25; si detecta decisión nueva → borrador de ADR para aprobación del fundador |
| 3. Contrato de tests | qa | Escribe los tests del contrato (fallando) antes de la implementación |
| 4. Implementación | dev-core / dev-ui / devops | Implementa hasta poner los tests en verde; commits atómicos en la rama de la tarjeta |
| 5. Revisión | qa + security | qa ejecuta suite completa y emite VERDICT; security revisa si aplica (IO/parsers/deps) |
| 6. Documentación | docs | Actualiza docs afectadas, CHANGELOG y genera el session log en openzonda-docs |
| 7. Cierre | pm-jira | Comenta la tarjeta (resumen + link al log + VERDICT), la mueve a Review; lista validaciones [HW] pendientes |
| 8. Merge | Fundador | Revisa PR, ejecuta validaciones [HW] si las hay, mergea y mueve la tarjeta a Done |

★ Regla de oro: una sesión que no cierra su session log y su tarjeta no existió. La trazabilidad tarjeta→log→commits es lo que convierte esto en un proyecto profesional auditable y no en una racha de vibe coding.

# 4. Convención Jira
- Proyecto Jira con key = prefijo del producto (ver propuestas de nombre); tablero Kanban simple: Backlog → Selected → In Progress → Review → Done.
- Título de tarjeta: 'OPENZONDA-N · F#.# · <verbo + entregable>' (ej.: 'F2.3 · Implementar parser de IEs con golden tests').
- Labels: fase (F0..F9), tipo (feat/infra/docs/qa/hw), y hw-validation para tarjetas que requieren tu validación física.
- Cada tarjeta contiene: objetivo, DoD (copiado del catálogo §5), dependencias (links a tarjetas), y al cierre el comentario estándar de pm-jira.
- Actores: solo fundador y Claude Code (vía MCP Atlassian configurado en Code). Claude en chat interviene únicamente a pedido — por ejemplo, para crear el primer conjunto de tarjetas desde el catálogo §5 cuando lo solicites.

# 5. Catálogo de sesiones F0–F3 (detallado)
Cada bloque incluye la instrucción de arranque literal para Claude Code. [HW] marca validación física del fundador; ★ marca sesión con escalado del agente líder a opus (§1.6). La numeración de tarjetas asume creación en este orden.

## 5.1 Fase F0 — Fundaciones (4 sesiones)

### S001 · [OPENZONDA-1] Bootstrap del repositorio documental
Objetivo: Crear openzonda-docs con estructura §2, migrar diseño y planes a markdown, ADR-001..007, templates.
Subagentes: docs (líder), pm-jira, architect (valida ADRs migrados)
Instrucción de arranque para Claude Code:
Sesión S001 / OPENZONDA-1. Crea el repo documental según §2 del plan
operativo. Convierte los .docx adjuntos a markdown fiel (pandoc),
genera templates de session log / tarjeta / retro, y produce el
session log de esta misma sesión como primer ejemplo. Inicializa
git con commits convencionales.
DoD de la sesión: Repo navegable; diseño legible en markdown; ADRs numerados; template de session log usado en S001.

### S002 · [OPENZONDA-2] Monorepo + calidad + CI
Objetivo: F0.1–F0.3 del plan: uv workspace, ruff/mypy strict, import-linter con contratos de capas, GitHub Actions.
Subagentes: devops (líder), dev-core, qa, security (revisión de deps iniciales)
Instrucción de arranque para Claude Code:
Sesión S002 / OPENZONDA-2. Crea el monorepo según §7.3 del diseño
con uv workspace y paquetes vacíos pero importables. Configura
ruff, mypy --strict en domain, import-linter con los contratos
de capas, pre-commit y CI en ubuntu+windows. qa debe demostrar
que un import ilegal entre capas rompe CI con un test.
DoD de la sesión: CI verde en ambos OS < 5 min; violación de capas rechazada; lockfile con hashes.

### S003 · [OPENZONDA-3] Walking skeleton Qt + PyInstaller
Objetivo: F0.4–F0.5: ventana PySide6 con logging estructurado y settings; bundle onedir.
Subagentes: dev-ui (líder), devops, qa, docs
Instrucción de arranque para Claude Code:
Sesión S003 / OPENZONDA-3. Implementa MainWindow mínima con
logging JSON y settings.json versionado; modo portable por
marker file. Crea el spec de PyInstaller onedir con exclusiones
y versión desde git tag. Genera el bundle y un script
scripts/smoke_local.ps1 que lo arranca y verifica el log.
DoD de la sesión: Bundle < 180 MB arranca en tu máquina [HW: ejecutar smoke_local.ps1]; log JSON correcto.

### S004 · [OPENZONDA-4] Instalador WiX + pipeline de release
Objetivo: F0.6–F0.8: MSI per-user idempotente, workflow de release por tag con SHA256+SBOM, docs de gobernanza.
Subagentes: devops (líder), security (SBOM), docs (gobernanza), pm-jira, scrum (retro F0)
Instrucción de arranque para Claude Code:
Sesión S004 / OPENZONDA-4. Autoría WiX v4: MSI per-user,
UpgradeCode fijo, MajorUpgrade, uninstaller, preflight.
Workflow release.yml por tag: build → SHA256SUMS → SBOM
CycloneDX → Release draft. Redacta CONTRIBUTING, GOVERNANCE,
SECURITY, BUILD.md. Cierra F0 con retro del agente scrum.
DoD de la sesión: [HW] Tú validas install→upgrade→uninstall en VM Win11 limpia; tag v0.0.1 produce release completa.

## 5.2 Fase F1 — Shell, proyecto y persistencia (6 sesiones)

### S005 · [OPENZONDA-5] Dominio: entidades y value objects
Objetivo: F1.1: Project/Site/Floor/FloorPlan/Calibration frozen; value objects de unidades (Dbm, Meters, Pixels).
Subagentes: architect (contratos), dev-core (líder), qa (property tests de invariantes)
Instrucción de arranque para Claude Code:
Sesión S005 / OPENZONDA-5. Implementa el dominio de F1.1 del
plan. qa primero: property tests de invariantes (una Calibration
con factor <= 0 es inconstruible; Dbm fuera de [-100,-10] en
mediciones marca flag). Luego dev-core implementa hasta verde.
DoD de la sesión: mypy --strict verde; cobertura domain ≥ 90%; imposible mezclar unidades sin error de tipos.

### S006 · [OPENZONDA-6] Migraciones SQLite + repositorio
Objetivo: F1.2: runner de migraciones, 0001_init.sql, SQLiteRepository con WAL.
Subagentes: dev-core (líder), qa (rollback y forward-incompatible), security (PRAGMAs defensivos)
Instrucción de arranque para Claude Code:
Sesión S006 / OPENZONDA-6. Runner de migraciones minimalista y
esquema 0001 según §8.2 del diseño. Tests: migración parcial
hace rollback; DB de user_version futura falla con mensaje
claro; trusted_schema=OFF y foreign_keys=ON verificados.
DoD de la sesión: Suite de persistencia verde; apertura defensiva demostrada con fixture hostil.

### S007 · [OPENZONDA-7] Contenedor .wifisurvey
Objetivo: F1.3: ZIP con manifest, escritura atómica, validación anti path-traversal.
Subagentes: dev-core (líder), security (líder de revisión), qa (kill-test y zip hostil)
Instrucción de arranque para Claude Code:
Sesión S007 / OPENZONDA-7. Implementa el contenedor de proyecto:
guardar = temp+fsync+rename; abrir valida rutas, tamaños y
manifest. qa: test de round-trip por hash y test que mata el
proceso durante el guardado. security: fixtures de zip bomb y
path traversal que deben rechazarse.
DoD de la sesión: Round-trip idéntico por hash; kill-test sin corrupción; 3 fixtures hostiles rechazados.

### S008 · [OPENZONDA-8] Shell UI: proyectos
Objetivo: F1.4: MainWindow con docks, ViewModels, crear/abrir/guardar/recientes/dirty.
Subagentes: dev-ui (líder), dev-core (servicios), qa (tests de ViewModel sin Qt)
Instrucción de arranque para Claude Code:
Sesión S008 / OPENZONDA-8. Shell según F1.4: docks, patrón
ViewModel testeable sin QApplication, flujo completo de
proyecto desde UI con diálogos nativos.
DoD de la sesión: Flujo completo manualmente verificado [HW]; ViewModels con tests headless.

### S009 · [OPENZONDA-9] Visor de plano + calibración
Objetivo: F1.5–F1.6: QGraphicsView con zoom/pan, capas, herramienta de calibración de 2 puntos.
Subagentes: dev-ui (líder), dev-core (Calibration service), qa
Instrucción de arranque para Claude Code:
Sesión S009 / OPENZONDA-9. Visor QGraphicsView (zoom rueda,
pan arrastre, capas) y herramienta de calibración con error
estimado persistido. Benchmark con imagen 8000x6000.
DoD de la sesión: [HW] Navegación fluida con plano real tuyo; calibrar→guardar→reabrir conserva factor.

### S010 · [OPENZONDA-10] i18n + release 0.1.0-alpha.1 + retro F1
Objetivo: F1.7 + primer pre-release instalable de la cadencia quincenal.
Subagentes: dev-ui, docs (líder de release notes), devops, scrum (retro), pm-jira
Instrucción de arranque para Claude Code:
Sesión S010 / OPENZONDA-10. Externaliza strings a tr(), genera
es/en, selector de idioma. Prepara release notes orientadas a
usuario y taggea 0.1.0-alpha.1. scrum ejecuta retro de F1
contra los session logs S005-S010.
DoD de la sesión: [HW] Instalas alpha.1 desde el MSI de release en VM; retro F1 en openzonda-docs/retros/.

## 5.3 Fase F2 — Captura Native WiFi (7 sesiones)

### S011 · [OPENZONDA-11] Bindings ctypes de wlanapi
Objetivo: Structs + funciones del flujo §4.2 del plan con tests de sizeof/offsets.
Subagentes: dev-core (líder), architect (revisión ADR-007), qa (tests de struct)
Instrucción de arranque para Claude Code:
Sesión S011 / OPENZONDA-11. Implementa packages/wifi/win32/:
structs WLAN_* con ctypes y las 8 funciones del flujo
normativo. qa: test de sizeof y offsets por struct contra
valores del SDK documentados en comentarios.
DoD de la sesión: Todos los sizeof-tests verdes; sin llamadas reales aún (unit puro).

### S012 · [OPENZONDA-12] Flujo de scan + notificaciones
Objetivo: WlanRegisterNotification + evento con timeout; adaptador WindowsNativeWifiScanner.
Subagentes: dev-core (líder), qa, security (revisión del callback en hilo externo)
Instrucción de arranque para Claude Code:
Sesión S012 / OPENZONDA-12. Implementa el flujo completo de
scan con espera de scan_complete (timeout 6 s), context
manager del handle y política de degradación por timeouts.
El callback solo señaliza un Event: security lo verifica.
DoD de la sesión: [HW] Tú ejecutas el primer scan real: BSS con dBm en consola en tu equipo.

### S013 · [OPENZONDA-13] CLI oz-capture + primeros fixtures
Objetivo: Herramienta de captura de fixtures (JSON+base64) que usarán los colegas.
Subagentes: dev-core (líder), docs (guía de uso de 1 página), qa
Instrucción de arranque para Claude Code:
Sesión S013 / OPENZONDA-13. CLI oz-capture: ejecuta el flujo,
serializa cada WLAN_BSS_ENTRY cruda + metadatos de NIC/driver
a un JSON portable. docs redacta la guía que enviarás a
colegas. Capturas tu primer fixture y se versiona en tests/.
DoD de la sesión: [HW] Fixture de tu NIC versionado; guía lista para compartir.

### S014 · [OPENZONDA-14] Parser de IEs (núcleo)
Objetivo: TLV parser + elementos EID 0/1/11/45/48/50/61 con golden y property tests.
Subagentes: qa (contrato primero), dev-core (líder), security (bytes hostiles)
Instrucción de arranque para Claude Code:
Sesión S014 / OPENZONDA-14. Parser TLV robusto según §4.4 del
plan: SSID, rates, QBSS, HT, RSN. hypothesis: jamás excepción
con bytes arbitrarios, jamás lectura fuera del blob. Golden
tests contra tu fixture real.
DoD de la sesión: Property tests verdes; QBSS station_count/chan_util extraídos de tu fixture.

### S015 · [OPENZONDA-15] Parser de IEs (VHT/HE/EHT) + derivación canal/ancho
Objetivo: EID 191/192, ext 35/36/106/108; precedencia EHT>HE>VHT>HT; validación contra frecuencia.
Subagentes: dev-core (líder), qa, docs (tabla de capacidades soportadas)
Instrucción de arranque para Claude Code:
Sesión S015 / OPENZONDA-15. Completa el parser para WiFi
5/6/6E/7 y la derivación de canal primario y ancho efectivo
por precedencia, validada contra ulChCenterFrequency.
DoD de la sesión: Golden tests de ancho/PHY correctos en todos los fixtures disponibles.

### S016 · [OPENZONDA-16] health() + netsh fallback
Objetivo: Las 5 causas de la tabla §4.3; verificación cruzada de permiso de ubicación; netsh como estimado.
Subagentes: dev-core (líder), dev-ui (panel de diagnóstico), qa, docs
Instrucción de arranque para Claude Code:
Sesión S016 / OPENZONDA-16. Implementa ScannerHealth con las 5
causas y el deep link a ms-settings:privacy-location. Fallback
netsh marcado source='netsh' y conversión %→dBm etiquetada
estimada. Panel de diagnóstico en UI.
DoD de la sesión: [HW] Matriz manual: radio off / permiso off / servicio off / sin adaptador → causa correcta en UI.

### S017 · [OPENZONDA-17] Panel de scan en vivo + retro F2
Objetivo: Tabla de BSS en vivo (4 s, sin congelar UI) con todas las columnas; cierre de fase.
Subagentes: dev-ui (líder), dev-core (scanner thread + cola), qa, scrum, pm-jira
Instrucción de arranque para Claude Code:
Sesión S017 / OPENZONDA-17. Scanner thread con cola thread-safe
y señal Qt; tabla en vivo: SSID, BSSID, dBm, banda, canal,
ancho, PHY, seguridad, QBSS. Release 0.1.0-alpha.2. Retro F2.
Actualiza HARDWARE.md con tu NIC.
DoD de la sesión: [HW] 10 min de scan continuo sin freeze ni fuga de memoria; alpha.2 publicada.

## 5.4 Fase F3 — Survey + alpha privada (5 sesiones)

| Sesión | Tarjeta | Contenido | DoD clave |
| --- | --- | --- | --- |
| S018 | OPENZONDA-18 | SurveySession + Measurement + flags de calidad + adapter_profile | Sesión persiste y reabre; muestras inmutables |
| S019 | OPENZONDA-19 | Flujo stop-and-go: clic → N scans → punto; atajos espacio/Z | [HW] Survey de 20 puntos en tu casa/oficina |
| S020 | OPENZONDA-20 | Capa de muestras sobre plano coloreada por RSSI del SSID activo | Feedback visual inmediato por punto |
| S021 | OPENZONDA-21 | Export CSV/JSON + perfiles de adaptador en reporte | Schema JSON publicado en docs |
| S022 | OPENZONDA-22 | Kit de alpha: guía 1 página, Discussions, release 0.1.0-alpha.3, retro F3 | [HW] Envías el kit a 3–5 colegas — hito ALPHA |

# 6. Catálogo F4–F9 (nivel título)
Se detallan al abrir cada fase (el agente pm-jira genera las tarjetas desde esta lista + el plan de implementación). Estimación por fase:

| Fase | Sesiones | Títulos |
| --- | --- | --- |
| F4 (7) | S023–S029 | Malla + IDW · Máscara de confianza + overlay distancia · Render cacheado en ProcessPool · Mapas derivados (cobertura/canal/QBSS) · Leyendas y escalas fijas · Plantilla reporte PDF/HTML · Release + retro |
| F5 (7) | S030–S036 | Editor de muros + biblioteca materiales · Ray casting 2D · log_distance v1 + golden sintéticos · multi_wall v1 · APs virtuales + heatmap predictivo · [HW] Validación empírica 2 sites · Publicación de error + retro |
| F6 (8) | S037–S044 | Co-channel/adjacent · Roaming candidates · Capacidad heurística QBSS · Import de proyectos de terceros (2 sesiones, fixtures de un colega usuario) · Survey continuo asistido · Docs site MkDocs · Beta pública: anuncio + retro |
| F7 (4) | S045–S048 | Grafo de interferencia + coloreo de canales · Sugerencia de potencia · Posiciones candidatas · Justificación reproducible + retro |
| F8 (4) | S049–S052 | Port AIProvider + backend OpenAI-compatible local · Contexto analítico JSON · Consentimiento + vista previa payload · Test de red cero-fugas + retro |
| F9 (6) | S053–S058 | Fuzzing parser/contenedor · Auditoría NFRs · Firma de código · Docs finales + SDK plugins · Onboarding de maintainer · Release 1.0 |

# 7. Arranque inmediato (checklist del fundador)
- Registrar la marca digital (verificado 02-08-2026: org GitHub 'openzonda' libre; sin paquete PyPI 'openzonda'; openzonda.org/.com/.dev/.io/.cl sin DNS — confirmar en el registrador antes de pagar): crear org GitHub, repo openzonda-docs, registrar openzonda.org (+.cl recomendado), proyecto Jira key OPENZONDA con tablero Kanban de 5 columnas.
- Instalar en el equipo de desarrollo: Git, uv, Node LTS (para tooling), WiX v4, Claude Code; verificar acceso MCP Atlassian desde Code.
- Pedir a Claude (chat) la creación del primer conjunto de tarjetas (OPENZONDA-1..22) desde el catálogo §5 — cuando tú lo decidas.
- Copiar los tres documentos (diseño, plan, plan operativo) a una carpeta local para que S001 los migre al repo documental.
- Ejecutar la sesión S001.

Fin del plan operativo — v1.1. Vive en openzonda-docs/design/ y se actualiza por ADR.
