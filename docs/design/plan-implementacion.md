
WiFi Survey AI
Plan de Implementación — v1.0
Hoja de ruta ejecutable desde repositorio vacío hasta release 1.0 profesional y abierta

| Campo | Valor |
| --- | --- |
| Documento | Plan de implementación (complementa el Diseño de Software v0.2) |
| Fecha | 02-08-2026 |
| Horizonte | F0 → F9 (release 1.0) |
| Modelo de esfuerzo | Escenario A: 10–15 h/semana (fundador) · Escenario B: full-time |
| Estrategia de adopción | Alpha privada con colegas desde F3; beta pública desde F6 |
| Principio rector | Cada fase termina con software instalable y demo-able, nunca con 'código a medio hacer' |

# Tabla de contenidos
Actualizar campos en Word (Ctrl+A, F9).

# 1. Estrategia de ejecución

## 1.1 Principios del plan
- Walking skeleton primero: en F0 ya existe un instalador MSI firmable que instala una ventana Qt vacía y pasa el pipeline completo de release. Todo lo demás se construye sobre ese esqueleto que siempre funciona.
- Vertical slices, no capas horizontales: cada fase entrega una funcionalidad completa de punta a punta (UI → dominio → persistencia), no 'toda la capa de dominio' sin nada visible.
- El riesgo técnico se ataca primero: la captura Native WiFi (F2) es el mayor riesgo del proyecto y se resuelve antes de invertir en heatmaps o predictivo. Si la captura no es viable con calidad profesional, hay que saberlo en la semana 12, no en el mes 10.
- Colegas como multiplicador desde F3: el software se comparte en alpha privada apenas hay survey funcional. Sus NICs distintas construyen la lista de hardware validado; su feedback profesional dirige F4–F7.
- Cadencia de release quincenal: desde F1, cada 2 semanas se publica un pre-release instalable (0.1.0-alpha.N) aunque el cambio sea pequeño. La disciplina de release es un músculo que se entrena desde el día 1.

## 1.2 Cronograma resumen

| Fase | Contenido | Esc. A (parcial) | Esc. B (full-time) | Hito de salida |
| --- | --- | --- | --- | --- |
| F0 | Fundaciones + walking skeleton | Sem 1–4 | Sem 1–2 | MSI 'hello Qt' pasa smoke test en Win10/11 |
| F1 | Shell + proyecto + persistencia | Sem 5–10 | Sem 3–5 | Round-trip .wifisurvey verificado |
| F2 | Captura Native WiFi + parser IEs | Sem 11–18 | Sem 6–9 | BSS reales con dBm + capacidades en 3 NICs distintas |
| F3 | Survey engine + ALPHA PRIVADA | Sem 19–26 | Sem 10–13 | Survey de 50 puntos en site real; 3 colegas usando |
| F4 | Heatmaps + reporting | Sem 27–34 | Sem 14–18 | Reporte PDF profesional presentable a un cliente |
| F5 | RF predictivo | Sem 35–42 | Sem 19–23 | Error medio ≤ 6 dB en 2 sites de referencia |
| F6 | Analytics + import de terceros + BETA PÚBLICA | Sem 43–52 | Sem 24–29 | Import de proyectos de terceros real; anuncio público |
| F7 | Optimización de APs | Sem 53–58 | Sem 30–33 | Sugerencias justificadas y reproducibles |
| F8 | IA advisory local-first | Sem 59–64 | Sem 34–37 | Cero llamadas de red sin consentimiento (verificado) |
| F9 | Hardening + docs → 1.0 | Sem 65–72 | Sem 38–42 | NFRs verdes; 2+ maintainers; release 1.0 |

★ Lectura realista: con dedicación parcial, 1.0 llega en ~16–18 meses; full-time, ~10 meses. La alpha privada con colegas (F3) llega en ~6 meses parcial / ~3 meses full-time. El plan prioriza que ese primer momento compartible llegue lo antes posible con calidad real.

# 2. F0 — Fundaciones y walking skeleton
Objetivo: repositorio profesional + pipeline completo build→test→package→install funcionando antes de escribir lógica de negocio. Es la fase más importante del proyecto: define la calidad de todo lo que sigue.

## 2.1 Work breakdown

| # | Tarea | Detalle técnico | DoD (Definition of Done) |
| --- | --- | --- | --- |
| F0.1 | Bootstrap del monorepo | uv workspace; pyproject por paquete (domain, application, wifi, persistence…); Python 3.13 pinned; estructura de §7.3 del diseño | uv sync limpio en Windows/Linux; import cruzado entre paquetes funciona |
| F0.2 | Calidad de código | ruff (reglas estrictas), mypy --strict en domain/rf_engine, pre-commit, import-linter con contratos de capas | PR de prueba que viola una capa es rechazado por CI |
| F0.3 | CI base | GitHub Actions: lint+type+test en ubuntu (rápido) y windows-latest (fiel); cache de uv | Pipeline < 5 min en PR típico |
| F0.4 | Walking skeleton Qt | apps/desktop con MainWindow vacía PySide6, logging estructurado, settings.json versionado, modo portable detectado | Ventana abre y cierra limpia; log JSON generado |
| F0.5 | Packaging PyInstaller | spec onedir; excluir módulos innecesarios; hook de versión desde git tag | Bundle < 180 MB; arranque < 4 s en VM |
| F0.6 | Instalador WiX v5 | MSI per-user, UpgradeCode fijo, MajorUpgrade, shortcut, uninstaller, preflight x64/espacio | Install→upgrade→uninstall limpio verificado por script en VM |
| F0.7 | Pipeline de release | Workflow por tag: build → smoke test en runners Win → SHA256SUMS → SBOM CycloneDX → GitHub Release draft | Tag v0.0.1 produce release completa sin intervención manual |
| F0.8 | Gobernanza y docs base | README con visión y capturas, CONTRIBUTING, GOVERNANCE, SECURITY, CODE_OF_CONDUCT, plantillas issue/PR, ADR/ con 001–006 | Un desarrollador externo puede compilar siguiendo BUILD.md sin preguntar nada |

## 2.2 Decisiones a cerrar en F0
- Nombre definitivo y verificación de disponibilidad (dominio, GitHub org, PyPI). Recomendación: registrar org de GitHub dedicada, no repo personal — transmite proyecto serio a los colegas.
- Gestor de entorno: uv (lock con hashes, rápido, workspace nativo).
- Runner de smoke test: GitHub-hosted windows-latest cubre Win Server; agregar VM Windows 11 real (self-hosted o Azure DevTest) antes de F3 para validar contra el stack WLAN de cliente, que difiere de Server.

# 3. F1 — Desktop shell, proyecto y persistencia
Objetivo: la aplicación gestiona proyectos reales: crear, abrir, guardar .wifisurvey, cargar y calibrar planos. Sin WiFi todavía — el dominio y la persistencia se estabilizan primero contra tests, no contra una radio.

## 3.1 Work breakdown

| # | Tarea | Detalle técnico | DoD |
| --- | --- | --- | --- |
| F1.1 | Entidades de dominio | Project, Site, Floor, FloorPlan, Calibration como dataclasses frozen; value objects para unidades (Dbm, Meters, Pixels) que impiden mezclar magnitudes | mypy --strict verde; property tests de invariantes |
| F1.2 | Migraciones SQLite | Runner propio minimalista: 0001_init.sql…; user_version; transaccional; WAL; PRAGMA foreign_keys=ON | Abrir DB futura falla con mensaje claro; migración parcial hace rollback |
| F1.3 | Contenedor .wifisurvey | ZIP con manifest.json (schema_version, app_version, hashes de assets); escritura atómica temp+fsync+rename; validación anti path-traversal y límites de tamaño al abrir | Test round-trip por hash; test kill -9 durante guardado; test de ZIP hostil |
| F1.4 | Shell de UI | MainWindow con docks (árbol de proyecto, propiedades, log); patrón ViewModel: la vista no toca servicios directamente | Crear/abrir/guardar/cerrar desde UI; recientes; título con estado dirty |
| F1.5 | Visor de plano | QGraphicsView con zoom/pan suaves (rueda + arrastre), render del PNG/JPG, capas (plano, futuro: muestras, heatmap) | Plano de 8000×6000 px navega fluido (< 16 ms/frame) |
| F1.6 | Calibración | Herramienta de 2 puntos + distancia real; almacenar factor y error estimado; re-calibrable | Calibrar, guardar, reabrir: factor idéntico; UI muestra escala en la barra de estado |
| F1.7 | i18n bootstrap | Todos los strings en tr(); .ts/.qm para es/en; selector de idioma | Cambio de idioma sin reiniciar o con reinicio declarado |

★ Anti-patrón a evitar en F1: sobre-diseñar la UI. El shell debe ser funcional y sobrio; el pulido visual llega en F4 cuando haya heatmaps que mostrar. En F1 la inversión de calidad va al modelo de datos y al contenedor de proyecto, que son casi imposibles de cambiar después sin dolor.

# 4. F2 — Captura Native WiFi y parser de IEs (especificación ejecutable)
Objetivo: obtener BSS reales con RSSI en dBm y capacidades completas, con diagnóstico de fallos de primera clase. Es el corazón técnico del producto y el capítulo más detallado de este plan.

## 4.1 Decisión de binding: ctypes (ADR-007)

| Opción | Pros | Contras | Veredicto |
| --- | --- | --- | --- |
| ctypes (stdlib) | Cero toolchain C++; wlanapi.dll es una API C estable de 15+ años; estructuras documentadas; debugging puro Python; sin paso de compilación en CI | Definición manual de structs (propensa a errores de offset si se hace sin tests) | ELEGIDA |
| pybind11 / C++ | Tipado nativo, marginalmente más rápido | Toolchain MSVC en CI y contribuidores; complejidad de build; la perf no lo justifica (decenas de BSS cada 4 s es carga trivial) | Descartada |
| Rust + PyO3 | Memoria segura | Mismo coste de toolchain; se reserva para hotspots numéricos del RF engine (F5), no para IO de baja frecuencia | Descartada aquí |

Mitigación del contra de ctypes: cada struct se define junto a un test que verifica ctypes.sizeof() contra el tamaño esperado del SDK, y los fixtures grabados validan el parsing completo contra datos reales.

## 4.2 Flujo de captura (secuencia normativa)
1. WlanOpenHandle(2)                      → handle de cliente
2. WlanEnumInterfaces                     → interfaces WLAN (GUID, estado)
3. WlanQueryInterface(radio_state)        → radio ON/OFF (para health)
4. WlanRegisterNotification(ACM)          → callback scan_complete/scan_fail
5. WlanScan(guid, NULL)                   → dispara escaneo
6. wait(evento, timeout=6 s)              → scan_complete | scan_fail | timeout
7. WlanGetNetworkBssList(guid, dot11_BSS_type_any)
                                          → WLAN_BSS_LIST
8. por cada WLAN_BSS_ENTRY:
     rssi_dbm   = lRssi
     freq_khz   = ulChCenterFrequency  → banda + canal
     phy_hint   = uPhyId → tabla de PHY types
     ies_blob   = bytes[ulIeOffset : ulIeOffset+ulIeSize]
     parsed     = parse_ies(ies_blob)
9. WlanCloseHandle en shutdown (y siempre vía context manager)
- El callback de notificación corre en un hilo de wlanapi: solo señaliza un threading.Event; jamás toca Qt ni la DB desde ahí.
- scan_fail y timeout se registran con el código de razón; tres timeouts consecutivos degradan a intervalo largo y notifican a la UI (fail-safe).
- Si la NIC está asociada, se anota connected_during_scan=true en cada muestra de ese ciclo (flag de calidad definido en el diseño §10.2).

## 4.3 health(): diagnóstico de primera clase

| Chequeo | Mecanismo | Resultado para la UI |
| --- | --- | --- |
| Servicio WLAN | WlanOpenHandle falla → wlansvc detenido | 'El servicio WLAN de Windows no está activo' + acción |
| Adaptador presente | WlanEnumInterfaces vacío | 'No se detecta adaptador WiFi' |
| Radio encendida | WlanQueryInterface(wlan_intf_opcode_radio_state) | 'La radio está apagada (switch físico/avión)' |
| Permiso de ubicación | GetNetworkBssList → ERROR_ACCESS_DENIED, o lista vacía con radio ON: verificación cruzada vía WinRT Geolocator.RequestAccessAsync | Botón directo a ms-settings:privacy-location |
| Driver degradado | Scans repetidos sin resultados con todo lo anterior OK | 'Driver sin soporte de scan estando asociado' + link a hardware validado |

## 4.4 Parser de Information Elements (especificación)
Parser TLV puro (bytes → dataclass), sin dependencias, ubicado en packages/wifi/ies.py. Robusto por diseño: un IE malformado se registra y se salta, jamás rompe el scan completo. Elementos de la v1 del parser:

| EID | Elemento | Extrae | Uso en producto |
| --- | --- | --- | --- |
| 0 | SSID | Nombre (con manejo de hidden/UTF-8 inválido) | Identidad de red |
| 1 / 50 | Supported Rates / Extended | Rates básicos | Detección de redes legacy-only |
| 11 | BSS Load (QBSS) | station_count, channel_utilization (0–255), admission capacity | Análisis de capacidad — diferenciador clave |
| 45 / 61 | HT Capabilities / Operation | 802.11n; canal secundario → ancho 20/40 | PHY y ancho reales en 2.4/5 GHz |
| 48 | RSN | Cipher suites, AKM (WPA2/WPA3/SAE/802.1X) | Columna de seguridad |
| 191 / 192 | VHT Capabilities / Operation | 802.11ac; ancho 80/160 | PHY y ancho en 5 GHz |
| 255+35 / 255+36 | HE Capabilities / Operation (ext) | 802.11ax; incl. 6 GHz Operation Info | WiFi 6/6E |
| 255+108 / 255+106 | EHT Capabilities / Operation (ext) | 802.11be; ancho hasta 320 | WiFi 7 |
| 221 | Vendor specific | OUI + subtipo (al menos: WPS, WMM) | Fingerprinting básico de fabricante |

- Derivación de canal/ancho: el ancho efectivo se resuelve por precedencia EHT > HE > VHT > HT; el canal primario se toma del Operation element correspondiente y se valida contra ulChCenterFrequency.
- El blob crudo de IEs siempre se persiste (columna bss.ies BLOB): permite re-parsear históricos cuando el parser mejore — los datos capturados nunca caducan.

## 4.5 Fixtures y estrategia de test
- Herramienta oz-capture (CLI incluida en el repo): ejecuta el flujo de captura y serializa cada WLAN_BSS_ENTRY crudo a JSON (metadatos + blob base64). Es también la herramienta que los colegas ejecutarán para aportar fixtures de sus NICs con un solo comando.
- Golden tests: cada fixture tiene su parsing esperado versionado; CI corre el parser contra todos los fixtures sin necesitar radio.
- Property tests (hypothesis): el parser nunca lanza excepción con bytes arbitrarios; nunca lee fuera del blob.
- Tests de struct: sizeof/offsets de cada estructura ctypes verificados.
- Job nightly opcional en máquina self-hosted con NIC real: captura en vivo + aserciones de sanidad (RSSI en rango, al menos 1 BSS en entorno urbano).

## 4.6 DoD de F2
- Scan completo (flujo 4.2) funciona en 3 NICs distintas (mínimo: una Intel AX2xx, una Realtek USB, una tercera distinta) con fixtures aportadas.
- health() distingue correctamente las 5 causas de la tabla 4.3, verificado manualmente apagando radio/permiso/servicio.
- Parser de IEs pasa golden tests de las 3 NICs y property tests.
- Panel de escaneo en vivo en la UI: tabla de BSS con SSID, BSSID, dBm, banda, canal, ancho, PHY, seguridad, QBSS — refresco cada 4 s sin congelar la UI.
- netsh fallback implementado y visualmente diferenciado como estimado.

# 5. F3 — Survey engine y alpha privada

## 5.1 Work breakdown

| # | Tarea | DoD |
| --- | --- | --- |
| F3.1 | SurveySession + Measurement con flags de calidad y adapter_profile | Sesión completa persiste y reabre; muestras inmutables |
| F3.2 | Flujo stop-and-go: clic en plano → N scans → punto confirmado con conteo de BSS | 50 puntos capturables en < 25 min en site real |
| F3.3 | Capa de muestras sobre el plano (puntos con color por RSSI del SSID activo) | Feedback visual inmediato tras cada captura |
| F3.4 | Perfiles de adaptador (offset dB opcional, notas) | El reporte declara NIC y perfil usados |
| F3.5 | Export CSV/JSON de muestras crudas | Colegas pueden analizar en sus propias herramientas |
| F3.6 | Atajos de terreno: barra espaciadora = re-capturar, Z = deshacer último punto | Survey operable con una mano |

## 5.2 Lanzamiento de la alpha privada (plan concreto)
- Seleccionar 3–5 colegas con perfiles distintos: al menos uno usuario de una suite comercial de referencia (para el gap analysis más duro), uno con NICs variadas, uno que haga surveys reales de campo.
- Kit de alpha: MSI + guía de 1 página (instalar, permiso de ubicación, primer survey) + link a GitHub Discussions privado del repo.
- Pedido explícito a cada uno: (a) ejecutar oz-capture y subir el fixture de su NIC; (b) un survey real de ≥ 30 puntos; (c) responder 5 preguntas fijas (qué faltó para usarlo en un trabajo real, qué dato no les creyeron, etc.).
- Ciclo quincenal: release alpha nueva + changelog orientado a ellos; los issues de colegas se etiquetan field-feedback y tienen prioridad de triage.
- Salida de F3: tabla pública HARDWARE.md iniciada con las NICs validadas y sus particularidades de RSSI.

# 6. F4–F9 — Plan por fase

## F4 — Heatmaps y reporting profesional
- IDW con máscara de confianza (d_max 8 m) y overlay de distancia a muestra; render Matplotlib Agg → QPixmap cacheado por hash de inputs; recálculo en ProcessPool con cancelación.
- Mapas: RSSI por SSID, cobertura por umbral, canal, ancho, densidad de APs, utilización QBSS.
- Reporte PDF/HTML con plantilla: portada, metodología (NIC, cadencia, fecha), heatmaps con leyenda fija −30/−90, tabla de APs, hallazgos. Criterio: un colega lo entregaría a su cliente sin editar.

## F5 — RF engine predictivo
- Editor de muros sobre el plano (polilíneas + material de biblioteca); ray casting 2D segmento-muro (Rust/PyO3 si el perfil lo exige, Python+NumPy primero).
- log_distance v1 → multi_wall v1 (COST 231 MWM); golden fixtures sintéticos + validación empírica contra 2 surveys reales de F3/F4; publicar el error obtenido en docs (transparencia = credibilidad).
- Colocación manual de APs virtuales con tx power/antena → heatmap predictivo etiquetado como PREDICTIVO en cada export.

## F6 — Analytics, import de proyectos de terceros y beta pública
- Co-channel/adjacent interference, roaming candidates, capacidad heurística (QBSS + PHY + solape) — cada resultado con su explicación metodológica embebida.
- Importador de proyectos de terceros best-effort con reporte de fidelidad (qué se importó, qué se ignoró); fixtures de ≥ 2 versiones del formato aportadas por un colega usuario de la herramienta.
- Beta pública: anuncio (blog propio + r/wifi + LinkedIn), README con GIF de demo, docs site MkDocs publicado, plantilla de issue 'hardware report'.

## F7 — Optimización de APs
- Sugerencias de canal (grafo de interferencia + coloreo), potencia y posiciones candidatas (búsqueda sobre grid con función objetivo de cobertura/solape declarada). Determinista, con semilla fija y justificación por sugerencia.

## F8 — IA advisory local-first
- AIProvider con backend OpenAI-compatible apuntable a llama.cpp/Ollama local; contexto analítico JSON generado por el dominio; consentimiento por proyecto con vista previa del payload; test de red que verifica cero tráfico sin consentimiento.

## F9 — Hardening y 1.0
- Auditoría de NFRs completa; fuzzing del parser de IEs y del contenedor .wifisurvey; certificado de firma (meta de sponsors); docs completas (usuario, hardware, teoría RF aplicada, SDK de plugins); promoción de ≥ 1 contribuidor recurrente a maintainer antes del tag 1.0.

# 7. Plan de comunidad y adopción profesional

## 7.1 Línea de tiempo de apertura

| Momento | Audiencia | Acción |
| --- | --- | --- |
| F0 | Nadie (repo público desde el día 1 igualmente) | Repo público con README de visión: 'building in public' sin promoción |
| F3 | 3–5 colegas seleccionados | Alpha privada (§5.2); Discussions como canal |
| F4–F5 | Círculo ampliado (~15 profesionales) | Alpha abierta por invitación; primeros posts técnicos en el blog (una serie 'construyendo un site survey WiFi open source' es contenido de altísimo valor para tu blog de ciberseguridad/infra) |
| F6 | Público | Beta + anuncio; Good First Issues curados; HARDWARE.md como página viva |
| F9 | Público + potenciales sponsors | 1.0 + OpenCollective/GitHub Sponsors para financiar certificado de firma y hardware de test |

## 7.2 Qué hace que los colegas profesionales confíen
- El reporte declara metodología y hardware — pueden defenderlo ante su cliente.
- El error del modelo predictivo está publicado, no oculto.
- Releases firmadas con checksums, changelog honesto, issues respondidos.
- Import de proyectos de terceros: pueden probar sin abandonar su herramienta actual.
- La clasificación observado/derivado/predictivo es visible en cada pantalla y export.

# 8. Gestión del plan

## 8.1 Tablero y ritmo
- GitHub Projects con un milestone por fase; los DoD de este documento se copian como issues de tracking al abrir cada fase.
- Regla de corte de alcance: si una fase excede su ventana en > 30%, se recorta alcance de la fase (nunca calidad ni tests) y el recorte queda registrado en el milestone.
- Revisión de plan al cierre de cada fase: 30 minutos, tres preguntas — ¿qué DoD no se cumplió y por qué?, ¿qué aprendimos del feedback de campo?, ¿cambia el orden de la siguiente fase?

## 8.2 Primeras 2 semanas (arranque inmediato)
- Día 1–2: nombre + org GitHub + repo con README de visión, licencia y ADR 001–006 migrados del diseño.
- Día 3–5: F0.1–F0.3 (monorepo uv, ruff/mypy/import-linter, CI verde).
- Día 6–8: F0.4–F0.5 (ventana Qt + PyInstaller onedir arrancando en VM).
- Día 9–12: F0.6 (MSI WiX con install/upgrade/uninstall verificados).
- Día 13–14: F0.7–F0.8 (release v0.0.1 automática por tag + docs de gobernanza). Fin de F0 en escenario full-time; en escenario parcial, mismas tareas distribuidas en 4 semanas.

## 8.3 Riesgos específicos del plan

| Riesgo | Señal temprana | Respuesta |
| --- | --- | --- |
| F2 revela calidad de RSSI inaceptable en NICs comunes | Fixtures de colegas con varianza > 10 dB en punto fijo | Pivotar mensaje: énfasis en cobertura relativa + perfiles de offset; evaluar soporte de un adaptador USB de referencia recomendado |
| La alpha no engancha a los colegas | < 2 surveys reales subidos en 4 semanas | Entrevista 1:1; probablemente falta el reporte PDF (adelantar F4.3) |
| Burn-out del fundador | 2 quincenas sin release | Reducir alcance de fase activa a la mitad; pedir ayuda explícita en Discussions con issues empaquetados |
| Windows cambia permisos WLAN | Fallo del nightly en Insider VM | health() ya aísla la causa; parche de onboarding priorizado |

Fin del plan — v1.0. Este documento se versiona junto al código en /docs/plan/.
