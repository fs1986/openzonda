\# CLAUDE.md — OpenZonda



> Contexto permanente para Claude Code. Se carga en la sesión principal y en los

> subagentes. Las reglas de este archivo son vinculantes para todos los agentes.



\## Qué es OpenZonda



Aplicación desktop \*\*open source\*\* (Apache-2.0) para \*\*site surveys WiFi\*\* en Windows

10/11, con ambición de paridad progresiva con las herramientas comerciales de referencia en survey pasivo, heatmapping y

diseño predictivo — \*\*sin hardware propietario\*\* en el caso base.



Documentos fuente (monorepo `openzonda`, leer antes de decidir):

\- `docs/design/software-design-v0.2.md` — diseño de software (fuente de verdad)

\- `docs/design/plan-implementacion.md` — hoja de ruta F0–F9

\- `docs/design/plan-operativo-sesiones.md` — protocolo de sesión, agentes, matriz de modelos

\- `ADR/` — decisiones de arquitectura (inmutables)

\- Los `.md` de `docs/design/` son la fuente de verdad. Los `.docx` originales se conservan solo en local (`.private/`, fuera del repo por metadatos personales).



\## Principio rector: honestidad metrológica



El mayor diferenciador del producto y su invariante no negociable. Todo dato se clasifica

como \*\*observado / derivado / estimado / predictivo\*\*, y esa clasificación vive en el

\*\*modelo de datos\*\*, no solo en la UI. Degradar esta distinción en silencio está

\*\*prohibido\*\* (ver Decisiones inmutables).



\## Arquitectura (hexagonal / ports \& adapters)



Dependencias permitidas, verificadas en CI con `import-linter`:



UI (PySide6) → Application → Domain

Infrastructure implementa ports del Domain/Application





\- La \*\*UI nunca importa\*\* infraestructura ni APIs de Windows directamente.

\- El \*\*Domain no importa nada\*\* externo salvo stdlib y NumPy.

\- La captura, persistencia y export son \*\*adapters\*\* detrás de ports (Protocols).



Paquetes: `domain/ application/ wifi/ rf\_engine/ geometry/ heatmap/ analytics/

reporting/ interop/ ai/ persistence/` + `native/windows/` + `apps/desktop/`.



\## Decisiones INMUTABLES (requieren ADR nuevo para cambiarse)



1\. No cambiar el formato de proyecto `.wifisurvey` sin migración de schema.

2\. No introducir dependencia de cloud para que el survey básico funcione.

3\. No convertir una estimación en medición sin marcarla como derivada; \*\*no estimar

&#x20;  noise/SNR y presentarlo como observado\*\*.

4\. No acoplar la UI a una API de Windows.

5\. No requerir Python/Node instalados en el equipo del usuario final.

6\. No eliminar proyectos en upgrade/uninstall sin confirmación explícita.

7\. No cambiar un modelo RF sin actualizar sus fixtures/golden y \*\*subir su versión\*\*.

8\. No cargar plugins automáticamente desde un archivo de proyecto.

9\. No añadir telemetría de ningún tipo.



\## Protocolo de sesión (obligatorio, sin excepción)



Cada sesión = 1 tarjeta Jira (`OPENZONDA-N`) = 1 rama `feature/openzonda-N-slug`.



1\. \*\*pm-jira\*\* lee la tarjeta, verifica dependencias, la pasa a \*In Progress\*.

2\. \*\*architect\*\* valida capas y decisiones inmutables; si hay decisión nueva → borrador de ADR.

3\. \*\*qa\*\* escribe los tests del contrato (fallando) \*\*antes\*\* de implementar.

4\. \*\*dev-core/dev-ui/devops\*\* implementan hasta poner los tests en verde.

5\. \*\*qa + security\*\* revisan; qa emite `VERDICT: PASS|FAIL`.

6\. \*\*docs\*\* actualiza docs/CHANGELOG y genera el session log en `docs/sessions/`.

7\. \*\*pm-jira\*\* comenta la tarjeta (resumen + link al log + VERDICT), la pasa a \*Review\*.

8\. \*\*El fundador\*\* revisa el PR, ejecuta validaciones `\[HW]` y mergea → \*Done\*.



\*\*Regla de oro:\*\* una sesión sin session log y sin tarjeta cerrada no existió.



\## Reglas de trabajo



\- \*\*Commits convencionales\*\* con scope de paquete: `feat(wifi): ...`, `test(rf): ...`,

&#x20; `docs: ...`, `fix(persistence): ...`, `chore(ci): ...`.

\- \*\*Una rama por tarjeta\*\*; PR aunque el fundador sea el único humano (la revisión la

&#x20; hacen architect+qa+security antes de pedir merge).

\- \*\*Nunca mergear sin `VERDICT: PASS` de qa.\*\*

\- \*\*Ninguna dependencia nueva\*\* entra sin pasar por el agente `security` (lockfile con

&#x20; hashes vía `uv`; se registra en el SBOM).

\- Prohibido `localStorage`/estado global oculto; el estado de UI vive en ViewModels.

\- Todo trabajo > 50 ms fuera del hilo de Qt; captura y cómputo en workers con cancelación.



\## Matriz de modelos IA (frontmatter `model:` por agente)



| Agente | Modelo | |

|---|---|---|

| Sesión principal | `opusplan` | Opus planifica, Sonnet ejecuta |

| architect, security | `opus` | decisiones caras, bajo volumen |

| dev-core, dev-ui, qa, devops, scrum | `sonnet` | implementación y análisis |

| docs, pm-jira | `haiku` | formato definido, mecánico |



\*\*Escalado ★ → opus\*\* en el líder de implementación solo en: contenedor `.wifisurvey`,

bindings ctypes + flujo de notificaciones, parser de IEs, RF engine e importador de proyectos de terceros.

No fijar `CLAUDE\_CODE\_SUBAGENT\_MODEL` global (pisaría esta matriz).



\## Restricciones físicas de Windows (no contradecirlas nunca)



\- \*\*Permiso de ubicación\*\*: `WlanGetNetworkBssList` devuelve vacío sin él. `health()`

&#x20; distingue: sin redes / radio off / permiso denegado / driver sin soporte.

\- \*\*RSSI no calibrado\*\*: cada NIC difiere; perfil de adaptador con offset; el reporte

&#x20; declara la NIC usada.

\- \*\*Throttling de scan\*\* \~4 s/interfaz → cadencia objetivo 3–5 s.

\- \*\*Sin noise floor\*\* en la mayoría de drivers → SNR "no disponible", nunca estimado.

\- \*\*Sin monitor mode\*\* → capacidad se estima vía BSS Load (IE QBSS), declarado como heurística.



\## Stack



Python 3.13 · PySide6 (Qt6, LGPL, enlace dinámico) · NumPy/SciPy · SQLite (WAL) ·

Matplotlib · ctypes para wlanapi.dll · PyInstaller (onedir) · WiX v4 (MSI per-user) ·

pytest/hypothesis/mypy(strict)/ruff · uv · GitHub Actions.



\## Comandos



```bash

uv sync                      # entorno

uv run pytest                # tests

uv run pytest tests/rf -q    # regresión RF (golden files)

uv run mypy packages/domain packages/rf\_engine --strict

uv run ruff check .

uv run lint-imports          # contratos de capas (import-linter)

```

