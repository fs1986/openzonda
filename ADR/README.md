# Architecture Decision Records (ADR)

Registro de decisiones de arquitectura. Un ADR captura una decisión significativa,
su contexto y sus consecuencias. **Los ADR aceptados son inmutables**: cambiar una
decisión requiere un **ADR nuevo** que la supersede, no editar el anterior.

Las decisiones listadas aquí corresponden a las "Decisiones que NO se cambian sin
ADR" del diseño (§25) y son vinculantes para todos los agentes (ver `CLAUDE.md`).

| ADR | Título | Estado |
|-----|--------|--------|
| [001](ADR-001-baseline-windows.md) | Baseline Windows | Aceptado |
| [002](ADR-002-aplicacion-autocontenida.md) | Aplicación autocontenida | Aceptado |
| [003](ADR-003-arquitectura-hexagonal.md) | Arquitectura hexagonal con verificación automática | Aceptado |
| [004](ADR-004-formato-wifisurvey.md) | Formato de proyecto `.wifisurvey` como ZIP autocontenido | Aceptado |
| [005](ADR-005-captura-native-wifi.md) | Captura vía Native Wi-Fi API con parsing propio de IEs | Aceptado |
| [006](ADR-006-honestidad-metrologica.md) | Honestidad metrológica como invariante de producto | Aceptado |
| [007](ADR-007-binding-ctypes.md) | Binding a `wlanapi.dll` mediante `ctypes` | Aceptado |
| [008](ADR-008-composition-root.md) | Composition root en un paquete propio | Aceptado |
| [009](ADR-009-piso-version-runtime.md) | Piso de versión de Windows: aserción de arranque en runtime | Propuesto |
| [010](ADR-010-modelo-documento.md) | Proyecto como documento (extraer / re-empaquetar) | Propuesto |
| [011](ADR-011-shell-unica.md) | Shell única con vista central reemplazable | Propuesto |

Para proponer una decisión nueva, copia [`template.md`](template.md).
