
WiFi Survey AI
Documento de Diseño de Software — v0.2
Plataforma open source de site survey WiFi de nivel profesional para Windows 10/11

| Campo | Valor |
| --- | --- |
| Estado | Draft técnico / baseline de implementación |
| Versión | 0.2 (supersede v0.1) |
| Fecha | 02-08-2026 |
| Plataforma objetivo | Windows 10 22H2 / Windows 11 x64 |
| Licencia | Apache License 2.0 |
| Distribución | Instalador Win32 (WiX) + portable ZIP + source |
| Idiomas | Español / Inglés (i18n desde arquitectura) |
| Persistencia | SQLite + contenedor de proyecto .wifisurvey |
| Audiencia | Ingenieros de red, integradores, comunidad open source |

| Versión | Fecha | Cambios |
| --- | --- | --- |
| 0.1 | 01-08-2026 | Baseline inicial: arquitectura, packaging, criterios v0.1 |
| 0.2 | 02-08-2026 | Posicionamiento competitivo; restricciones físicas de captura en Windows (permisos de ubicación, throttling, ausencia de monitor mode); parsing de Information Elements; especificación de interpolación y modelos RF; interoperabilidad .esx; concurrencia; supply chain; NFRs medibles; gobernanza OSS; ADR-003 a ADR-006; riesgos |

# Tabla de contenidos
Nota: actualizar campos en Word (Ctrl+A, F9) para poblar la tabla.

# 1. Resumen ejecutivo
WiFi Survey AI es una aplicación desktop open source para site surveys WiFi en Windows, con ambición de alcanzar paridad funcional progresiva con herramientas comerciales como Ekahau AI Pro y Hamina en el segmento de survey pasivo, heatmapping y diseño predictivo, sin requerir hardware propietario para el caso de uso base.
La estrategia de producto se apoya en tres pilares: (1) honestidad metrológica — el sistema distingue siempre entre dato observado, derivado e interpolado, y declara explícitamente las limitaciones físicas de la captura con NICs consumer; (2) arquitectura hexagonal con núcleo RF determinista, versionado y testeable por regresión; (3) extensibilidad plugin-first, incluyendo interoperabilidad con formatos de la industria (importación Ekahau .esx) como palanca de adopción.
El MVP (v0.1 funcional) entrega: gestión de proyectos, calibración de planos, captura pasiva vía Windows Native Wi-Fi API, survey stop-and-go, heatmaps de RSSI/cobertura y exportación básica. Las fases posteriores agregan motor predictivo multi-wall, análisis de canal/capacidad, optimización de APs e IA advisory local-first.

# 2. Posicionamiento y análisis competitivo
Para diseñar un producto 'comparable con Ekahau' es necesario ser preciso sobre qué se puede igualar por software y qué depende de hardware dedicado. La siguiente matriz define el posicionamiento honesto del producto:

| Producto | Fortaleza | Limitación relevante | Posición de WiFi Survey AI |
| --- | --- | --- | --- |
| Ekahau AI Pro + Sidekick 2 | Medición multi-radio calibrada, spectrum analysis, ecosistema completo | Coste elevado, hardware propietario, cerrado | No competimos en spectrum analysis hardware; competimos en survey pasivo, predictivo y reporting con coste cero |
| Hamina | Diseño predictivo cloud, UX moderna | Cloud-first, suscripción | Alternativa offline-first y open source para predictivo |
| NetSpot | Survey pasivo accesible en Win/macOS | Motor RF simple, extensibilidad limitada | Superar en rigor RF, modelo de datos y extensibilidad |
| Acrylic WiFi Heatmaps | Survey Windows con GPS | Cerrado, motor predictivo básico | Paridad en captura + superioridad en apertura y análisis |
| Kismet / herramientas OSS | Captura avanzada multi-plataforma | No orientado a site survey con planos ni heatmaps profesionales | Complementario; posible fuente de datos vía plugin |

## 2.1 Diferenciadores de diseño
- Trazabilidad metrológica total: cada píxel de un heatmap puede rastrearse hasta las muestras que lo originaron, con distancia a la muestra más cercana y algoritmo de interpolación usado.
- Motor RF versionado con tests de regresión: los resultados predictivos son reproducibles bit a bit para un mismo (input, versión de modelo).
- Interoperabilidad de entrada: importación de proyectos Ekahau .esx (contenedor ZIP con JSON) para reducir el coste de cambio de los usuarios profesionales.
- Extracción de Information Elements (IEs) de beacons vía Native Wi-Fi API: capacidades 802.11n/ac/ax/be, ancho de canal, BSS Load (recuento de estaciones y utilización de canal QBSS), MU-MIMO/OFDMA — habilita análisis de capacidad sin monitor mode.
- Open source con gobernanza seria: DCO, semver, ADRs públicos, releases firmadas y reproducibles con SBOM.

# 3. Alcance y no-alcance

## 3.1 En alcance (v0.1 → 1.0)
- Survey pasivo con NIC integrada o USB soportada por drivers Windows estándar.
- Heatmaps: RSSI, cobertura por umbral, canal primario, ancho de canal, densidad de APs, SNR cuando el driver exponga noise (raro en Windows; ver §7).
- Diseño predictivo: log-distance y multi-wall sobre plano calibrado con muros y materiales.
- Análisis: co-channel/adjacent-channel interference, solapamiento de cobertura, roaming candidates por umbral, capacidad estimada vía BSS Load.
- Reporting PDF/HTML y export CSV/JSON/GeoJSON.

## 3.2 Fuera de alcance explícito
- Spectrum analysis de capa física (requiere hardware SDR o analizador dedicado; se deja puerto de extensión para dispositivos USB de terceros).
- Packet capture / monitor mode: Windows no expone monitor mode de forma utilizable con NICs consumer; no se promete análisis de tramas ni retries reales.
- Survey activo (iperf/throughput) en el MVP; se especifica como plugin en fase F6.
- Backends macOS/Linux en 1.0 (las interfaces del dominio los contemplan; la implementación se difiere).

# 4. Requisitos de plataforma

| Elemento | Decisión |
| --- | --- |
| Arquitectura | x86-64 (AMD64) oficial; ARM64 evaluable post-1.0 |
| Windows mínimo | Windows 10 22H2 x64 (compatibilidad técnica; el OS está fuera de soporte general desde octubre 2025 — se documenta explícitamente) |
| Windows recomendado | Windows 11 x64 (23H2 o superior) |
| RAM | 4 GB disponibles mínimo; 8 GB recomendados |
| CPU | x64, 2+ núcleos; 4+ recomendado para heatmaps de alta resolución |
| GPU | No requerida en MVP; render acelerado opcional futuro |
| Adaptador WiFi | Cualquier NIC con driver WLAN estándar; se mantiene lista pública de adaptadores validados con notas de calidad de RSSI |
| Permisos | Instalación per-user sin admin; ver §4.1 sobre permiso de ubicación |
| Internet | No requerida para operación normal |
| Runtimes externos | Ninguno: Python/Qt embebidos en el bundle |

## 4.1 Permiso de ubicación (crítico)
Desde Windows 10, y con endurecimiento progresivo en Windows 11 (especialmente 24H2), el acceso a resultados de escaneo WLAN (WlanGetNetworkBssList, WlanGetAvailableNetworkList) está condicionado al permiso de ubicación del sistema y de la aplicación, porque los BSSIDs son datos geolocalizables. Si el permiso está denegado, la API puede devolver listas vacías o acceso denegado sin error evidente.
Requisitos de diseño derivados:
- Onboarding de primera ejecución que detecta el estado del permiso de ubicación y guía al usuario a habilitarlo (deep link a ms-settings:privacy-location).
- Diagnóstico en runtime: si un escaneo devuelve 0 BSS con adaptador activo, el sistema debe distinguir entre 'sin redes', 'radio apagada', 'permiso denegado' y 'driver sin soporte', y comunicarlo explícitamente (principio fail-safe).
- El instalador y la documentación declaran este requisito; el diagnóstico exportable incluye el estado del permiso.

# 5. Restricciones físicas de la captura en Windows
Este capítulo existe para que ninguna decisión de producto contradiga la física ni el comportamiento real del stack WLAN de Windows. Es la base de la credibilidad del proyecto frente a usuarios profesionales.

| Restricción | Realidad técnica | Implicación de diseño |
| --- | --- | --- |
| RSSI no calibrado | Cada NIC/driver reporta RSSI con offsets y curvas distintas; no equivale a un Sidekick multi-radio calibrado | Perfil de adaptador con offset configurable; los reportes declaran el adaptador usado; opción de calibración relativa por el usuario |
| Throttling de escaneo | WlanScan está limitado por el OS (~4 s por interfaz) y puede degradarse si la NIC está asociada y con tráfico | Cadencia de muestreo objetivo 3–5 s; el survey engine no promete tasas mayores; timestamps por muestra |
| Escaneo parcial en conexión | Una NIC asociada puede escanear solo canales parciales para no interrumpir tráfico | Recomendar survey con NIC desconectada; advertencia en UI si está asociada |
| Sin noise floor | El stack WLAN de Windows no expone noise en la práctica totalidad de drivers consumer | SNR se marca como 'no disponible' salvo driver que lo soporte; nunca se estima noise y se presenta como medido |
| Sin monitor mode | No hay captura de tramas 802.11 utilizable con NICs consumer en Windows | No se prometen métricas de retries/airtime reales; capacidad se estima vía BSS Load (IE QBSS) y heurísticas declaradas |
| Banda 6 GHz | Visibilidad de WiFi 6E/7 depende de NIC + driver + versión de Windows | capabilities() del scanner reporta bandas soportadas; la UI degrada con explicación |
| Una muestra = un punto | El usuario marca su posición manualmente en el plano (sin GPS indoor) | UX de survey optimizada para stop-and-go; modo continuo con interpolación de trayectoria marcada como derivada |

# 6. Stack tecnológico

| Capa | Tecnología | Licencia | Regla |
| --- | --- | --- | --- |
| UI | PySide6 (Qt 6) | LGPL-3.0 | Solo presentación; sin lógica RF. LGPL cumplida por enlace dinámico en bundle |
| Application | Python 3.13 | PSF | Casos de uso, orquestación, transacciones |
| Domain | Python + typing estricto | — | Cero dependencias de UI/IO; mypy --strict |
| RF/Geometry | Python + NumPy; núcleos Rust (PyO3) para hotspots | MIT/Apache | API estable; resultados deterministas |
| Interpolación | SciPy (griddata, RBF) | BSD | IDW propia + RBF; kriging futuro (pykrige) |
| DB | SQLite (WAL) | PD | Una DB por proyecto; migraciones versionadas |
| Serialización | JSON Schema versionado | — | Contratos de import/export |
| Visualización | Matplotlib (Agg) + QPainter para overlay interactivo | PSF-like | Colormaps perceptuales (viridis/turbo) |
| Imagen | Pillow; OpenCV solo si se requiere (vectorización de muros) | MIT-like/Apache | Evaluar coste de bundle antes de incluir OpenCV |
| Packaging | PyInstaller (onedir) | GPL con excepción | onedir, no onefile: arranque más rápido y firma por archivo |
| Installer | WiX Toolset v4 (MSI per-user) | MS-RL | Upgrade codes estables; MSIX post-1.0 |
| Testing | pytest, hypothesis, mypy, ruff | MIT | CI bloqueante |
| CI/CD | GitHub Actions | — | Builds reproducibles, SBOM, firma |

Justificación PyInstaller onedir vs onefile: onefile desempaqueta a temp en cada arranque (lento, dispara antivirus y complica firma). onedir permite firmar cada binario, mejora el arranque y es el formato que WiX empaqueta de forma natural.

# 7. Arquitectura

## 7.1 Vista lógica (hexagonal / ports & adapters)
┌───────────────────────────────────────────────┐
│                Desktop UI (PySide6)           │
│   views · viewmodels · Qt models · i18n       │
└───────────────┬───────────────────────────────┘
                │  señales/slots + DTOs
┌───────────────▼───────────────────────────────┐
│           Application Services                │
│  ProjectService  SurveyService  AnalysisSvc   │
│  SimulationService  ReportService  AIService  │
└───────────────┬───────────────────────────────┘
                │  interfaces (ports)
┌───────────────▼───────────────────────────────┐
│                Domain Core                    │
│  Project Site Floor FloorPlan Calibration     │
│  SurveySession Measurement BSS AccessPoint    │
│  Wall Material RFModel Heatmap AnalysisResult │
└───────────────┬───────────────────────────────┘
                │  ports (Protocols)
┌───────────────▼───────────────────────────────┐
│           Infrastructure Adapters             │
│  WindowsNativeWifiAdapter  NetshFallback      │
│  SQLiteRepository  ProjectFileRepository      │
│  PDFExporter  EsxImporter  AIProvider(local)  │
└───────────────────────────────────────────────┘
Reglas de dependencia (verificadas en CI con import-linter): UI → Application → Domain. Infrastructure implementa ports del Domain/Application. La UI no importa infraestructura; el Domain no importa nada externo salvo stdlib/NumPy.

## 7.2 Modelo de concurrencia
- Hilo principal: exclusivo de Qt (UI). Prohibido bloquear >16 ms; toda operación >50 ms va a worker.
- Scanner thread: bucle de adquisición con cadencia configurable (default 4 s), publica BssObservation a través de una cola thread-safe; la UI consume vía señal Qt.
- Compute pool: ProcessPoolExecutor para interpolación/predicción (evita GIL en mallas grandes); resultados cacheados por hash de inputs.
- IO thread: persistencia SQLite en hilo dedicado con cola de escritura; WAL habilitado; una conexión por hilo.
- Cancelación cooperativa: todo trabajo largo acepta un token de cancelación; cerrar un proyecto cancela trabajos pendientes de forma limpia.

## 7.3 Estructura del repositorio
wifi-survey-ai/
  apps/desktop/            # entry point, UI, packaging hooks
  packages/
    domain/                # entidades, value objects, ports
    application/           # casos de uso, servicios
    wifi/                  # ports de captura + parsing IEs
    rf_engine/             # modelos RF versionados
    geometry/              # muros, calibración, colisiones
    heatmap/               # interpolación y render
    analytics/             # canal, capacidad, roaming
    reporting/             # PDF/HTML/CSV/GeoJSON
    interop/               # importadores (.esx) / exportadores
    ai/                    # advisory layer (opcional)
    persistence/           # SQLite, migraciones, .wifisurvey
  native/windows/          # adaptador Native WiFi (ctypes/pybind)
  tests/{unit,integration,rf,fixtures}/
  docs/  packaging/windows/  scripts/
  pyproject.toml  LICENSE  README.md  CONTRIBUTING.md
  SECURITY.md  CHANGELOG.md  GOVERNANCE.md  ADR/

# 8. Modelo de dominio y esquema de datos

## 8.1 Entidades y responsabilidades

| Entidad | Responsabilidad | Notas de diseño |
| --- | --- | --- |
| Project | Contenedor lógico raíz | schema_version; UUID; metadatos sin PII obligatoria |
| Site / Floor | Ubicación lógica y niveles | Orden de plantas; altura entre plantas para atenuación inter-piso futura |
| FloorPlan | Imagen/vector + transformación | Hash del asset; DPI; rotación |
| Calibration | Escala píxel↔metro | Dos puntos + distancia real; error de calibración almacenado |
| SurveySession | Ejecución de un survey | Adaptador usado, perfil de offset, filtros, modo (stop-and-go/continuo) |
| Measurement | Muestra RF observada | Inmutable post-persistencia; origen (native/netsh); flags de calidad |
| BSS | Identidad observable (BSSID) | IEs crudos + parseados: PHY, ancho, banda, QBSS, seguridad |
| AccessPoint | AP lógico (agrupa BSS) | Agrupación por heurística OUI+SSID editable por el usuario |
| Wall / Material | Geometría con atenuación | Materiales con pérdida dB configurable y biblioteca por defecto (drywall 3 dB, ladrillo 8–10 dB, hormigón 12–20 dB, vidrio 2–4 dB — valores editables y documentados) |
| RFModel | Modelo predictivo versionado | Parámetros + versión persistidos con cada resultado |
| Heatmap | Derivado visual | Nunca fuente primaria; referencia a muestras y algoritmo |
| AnalysisResult | Salida analítica versionada | Reproducible; invalidada si cambian inputs |

## 8.2 Esquema SQLite (núcleo)
measurement(
  id INTEGER PK, session_id FK, ts_utc TEXT, ts_mono_ns INTEGER,
  x_px REAL, y_px REAL, x_m REAL, y_m REAL,
  bssid TEXT, ssid TEXT, rssi_dbm INTEGER,
  freq_mhz INTEGER, channel INTEGER, chan_width_mhz INTEGER,
  phy TEXT, noise_dbm INTEGER NULL, source TEXT,   -- native|netsh
  quality_flags INTEGER, adapter_profile_id FK
)
bss(bssid PK, ssid, oui, security, ies BLOB, ies_parsed JSON,
    qbss_sta_count INT NULL, qbss_chan_util REAL NULL, last_seen)
-- Índices: (session_id, ts_utc), (bssid, session_id), espacial simple por bucket
Migraciones: numeración lineal (0001_init.sql…), aplicadas en apertura de proyecto dentro de una transacción; user_version de SQLite refleja el schema_version. Abrir un proyecto de versión mayor a la soportada falla con mensaje claro (forward-incompatible explícito).

# 9. Captura WiFi en Windows

## 9.1 Backend de producción: Native Wi-Fi API
- WlanOpenHandle → WlanEnumInterfaces → WlanScan → WlanRegisterNotification (scan complete) → WlanGetNetworkBssList.
- RSSI en dBm desde WLAN_BSS_ENTRY.lRssi; frecuencia central (ulChCenterFrequency) → canal y banda; el porcentaje de netsh jamás se presenta como dBm.
- Parsing de IEs (diferenciador): cada WLAN_BSS_ENTRY expone el blob de Information Elements (ulIeOffset/ulIeSize). Se parsean: SSID, HT/VHT/HE/EHT capabilities (PHY y ancho de canal reales), RSN/seguridad, y BSS Load (IE 11: station count y channel utilization) — insumo directo del análisis de capacidad sin monitor mode.
- Notificaciones asincrónicas: el scan se dispara y se espera wlan_notification_acm_scan_complete con timeout; nunca polling ciego.

## 9.2 Contrato del scanner
class WifiScanner(Protocol):
    def capabilities(self) -> WifiCapabilities: ...   # bandas, dwell, fuente RSSI
    def scan(self) -> list[BssObservation]: ...        # bloqueante con timeout
    def start_monitoring(self, cb, interval_s: float) -> None: ...
    def stop_monitoring(self) -> None: ...
    def health(self) -> ScannerHealth: ...             # permiso ubicación, radio, driver

## 9.3 Fallback netsh
netsh wlan show networks mode=bssid se mantiene únicamente como diagnóstico y fallback degradado. Toda muestra originada en netsh se persiste con source='netsh' y la UI la muestra con distintivo visual; su 'señal %' se convierte a dBm aproximado (dBm ≈ %/2 − 100) solo con etiqueta de dato estimado.

# 10. Survey engine

## 10.1 Modos de survey

| Modo | Mecánica | Clasificación del dato |
| --- | --- | --- |
| Stop-and-go (default) | El usuario hace clic en su posición; se capturan N escaneos (default 2) y se asocian al punto | Observado |
| Continuo asistido | El usuario marca inicio y fin de un tramo caminado a paso constante; las muestras intermedias se posicionan por interpolación temporal lineal | Posición derivada (flag); RSSI observado |
| Punto de re-medición | Repetir captura sobre un punto existente crea una nueva serie, no sobreescribe | Observado, versionado por sesión |

## 10.2 Validación de muestras
- Rechazo de duplicados exactos (mismo BSSID + timestamp de scan) para no inflar densidad.
- Flags de calidad: NIC asociada durante el scan, scan parcial detectado, RSSI fuera de rango físico (−10..−100 dBm), reloj no monotónico.
- Cada sesión registra adapter_profile (NIC, driver, offset aplicado) para trazabilidad entre equipos.

# 11. Heatmap engine

## 11.1 Mapas y fuentes

| Mapa | Fuente | Tipo |
| --- | --- | --- |
| RSSI por SSID/BSSID | Measurement.rssi_dbm | Observado + interpolado |
| Cobertura (umbral) | Derivado de RSSI vs threshold configurable (default −67 dBm) | Derivado |
| Canal primario / ancho | Observaciones de canal + IEs | Observado |
| Densidad de APs | BSS por celda sobre umbral | Derivado |
| Utilización de canal | QBSS channel utilization (IE BSS Load) | Observado (declarando que lo reporta el AP) |
| SNR / Noise | Solo si driver expone noise | Observado; en ausencia: 'no disponible', nunca estimado |
| RSSI predictivo | RFModel + geometría + configuración de APs | Predictivo |

## 11.2 Interpolación (especificación)
- Algoritmo default: IDW (inverse distance weighting) con exponente p=2, radio de búsqueda máximo configurable (default 8 m).
- Alternativa: RBF thin-plate (SciPy) para superficies suaves; kriging ordinario en roadmap (pykrige) con variograma exponencial.
- Máscara de confianza: ningún píxel se colorea a más de d_max metros (default 8 m) de una muestra real; las zonas sin datos se renderizan neutras con trama, no se extrapola. Overlay opcional de 'distancia a muestra más cercana'.
- Resolución de malla: objetivo 0.25 m/celda hasta 5 000 m²; degradación automática de resolución por encima, con aviso.
- Colormaps perceptualmente uniformes (viridis default; turbo opcional); escala fija por defecto (−30 a −90 dBm) para comparabilidad entre proyectos; leyenda embebida en todo export.
- Los valores interpolados jamás se persisten como Measurement. El heatmap referencia sesión, algoritmo, parámetros y hash de muestras.

# 12. RF engine predictivo
Librería pura, sin dependencias de UI, determinista y versionada. Cada resultado persiste: modelo, versión, parámetros, fecha y hash de inputs.
RFModel.predict(tx_power_dbm, antenna_gain_dbi, frequency_mhz,
                distance_m, path: list[WallCrossing],
                environment: EnvParams) -> PredictedSignal

## 12.1 Modelos

| Modelo | Versión inicial | Descripción |
| --- | --- | --- |
| log_distance | 1.x (MVP) | PL(d) = PL(d0) + 10·n·log10(d/d0); n configurable por entorno (default 3.0 indoor); d0 = 1 m con FSPL |
| multi_wall | F5 | Log-distance + Σ pérdidas por muro atravesado según material (estilo COST 231 MWM); ray casting 2D contra geometría de muros |
| itu_indoor | F5+ | ITU-R P.1238 como modelo alternativo seleccionable, con coeficientes por banda |

## 12.2 Validación
- Fixtures de regresión: escenarios sintéticos con salida esperada exacta (golden files); cambiar un modelo sin actualizar fixtures rompe CI (ver §21, decisión inmutable).
- Validación empírica: comparación predicción vs survey real en al menos 2 sites de referencia antes de promover un modelo a default; error objetivo: media |Δ| ≤ 6 dB, p90 ≤ 10 dB (métrica publicada, no oculta).

# 13. Motor de análisis
- Interferencia co-canal: BSS que comparten canal primario con solapamiento de cobertura sobre umbral; severidad ponderada por RSSI del interferente.
- Interferencia de canal adyacente en 2.4 GHz: solapamiento espectral real (canales 1/6/11 vs intermedios) calculado por máscara espectral simplificada.
- Roaming: para cada celda, lista ordenada de BSS candidatos sobre umbral; detección de zonas de 'sticky client risk' (única BSS marginal).
- Capacidad: estimación declarada como heurística basada en QBSS (station count + channel utilization), PHY/ancho por IEs y solapamiento; nunca se presenta como throughput medido.
- Todos los resultados son AnalysisResult versionados e invalidados automáticamente si cambian las muestras o parámetros de entrada.

# 14. Interoperabilidad y formatos

## 14.1 Formato de proyecto .wifisurvey
proyecto.wifisurvey  (ZIP)
  manifest.json        # schema_version, app_version, hashes
  data/survey.sqlite   # persistencia estructurada
  assets/floor-01.png  # planos embebidos (siempre copia, no ruta absoluta)
  exports/             # opcional
- Autocontenido y trasladable por diseño: nunca rutas absolutas; assets siempre embebidos con hash.
- Escritura atómica: guardar = escribir temp + fsync + rename; el archivo nunca queda corrupto por un crash.

## 14.2 Importadores / exportadores

| Formato | Dirección | Fase | Notas |
| --- | --- | --- | --- |
| Ekahau .esx | Import | F6 | ZIP con JSONs; se importan planos, APs, muros y surveys en modo best-effort con reporte de fidelidad |
| CSV / JSON | Export | MVP | Muestras crudas y resultados; schema JSON publicado |
| GeoJSON | Export | F4 | Geometría y muestras georreferenciables |
| PDF / HTML | Export | F4 | Reporting con plantillas; heatmaps con leyenda y metadatos de sesión |
| KML | Export | Post-1.0 | Solo si hay georreferenciación del plano |

# 15. Capa de IA (advisory, opcional)
- Principio rector: la IA explica y sugiere; nunca modifica mediciones, nunca sustituye cálculo físico, y toda recomendación cita los datos que la sustentan.
- Local-first: soporte para modelos locales (backend OpenAI-compatible configurable, p. ej. llama.cpp/Ollama del propio usuario); proveedores cloud solo con consentimiento explícito por proyecto y con vista previa de los datos que se enviarían.
- Casos de uso F8: resumen ejecutivo del survey, explicación de zonas problemáticas, sugerencias de canal/potencia justificadas contra el análisis determinista, generación de texto de reporte.
- Arquitectura: AIProvider es un port; el dominio produce un 'contexto analítico' estructurado (JSON) y la IA opera solo sobre ese contexto, nunca sobre la DB directamente.

# 16. Extensibilidad y plugins
- Mecanismo: entry points de Python (grupo wifisurveyai.plugins) cargados desde un directorio de plugins del usuario; sin ejecución de código arbitrario en apertura de proyecto.
- Superficies de extensión: WifiScanner (nuevos backends/hardware), Importer/Exporter, RFModel, AnalysisModule, ReportSection.
- La API pública de plugins sigue semver independiente del app version; se publica un paquete wifisurveyai-plugin-sdk con stubs tipados.
- Los plugins declaran permisos (red, filesystem fuera del proyecto) en su manifest; la UI los muestra antes de habilitar.

# 17. Seguridad, privacidad y supply chain

## 17.1 Privacidad del dato de survey
- No se registran contraseñas WiFi, ni tráfico de usuarios, ni packet capture.
- BSSID/SSID son datos técnicos pero geolocalizables: se almacenan localmente y el export ofrece anonimización opcional (hash de BSSIDs con salt por proyecto) para compartir proyectos públicamente.
- Telemetría inexistente en MVP; si algún día se propone, será opt-in, documentada campo a campo y con ADR público.
- Logs sin secretos; el bundle de diagnóstico muestra su contenido antes de exportar.

## 17.2 Supply chain y releases
- Dependencias con lockfile y hashes (uv/pip-tools); Dependabot/Renovate activo; política de revisión para dependencias nuevas.
- SBOM (CycloneDX) publicado con cada release; builds de release desde CI limpio, nunca desde máquinas personales.
- Firma de código: releases oficiales firmadas cuando exista certificado (objetivo: certificado OV vía sponsors/OpenCollective); mientras tanto, SHA256SUMS firmado con clave del proyecto y documentación del aviso SmartScreen.
- SECURITY.md con proceso de divulgación coordinada y ventana de respuesta objetivo de 14 días.

## 17.3 Modelo de amenazas (resumen)

| Amenaza | Mitigación |
| --- | --- |
| Proyecto .wifisurvey malicioso (zip bomb, path traversal, SQLite hostil) | Extracción con validación de rutas, límites de tamaño, apertura de SQLite en modo defensivo (query_only hasta migrar; PRAGMA trusted_schema=OFF) |
| Plugin malicioso | Carga explícita por el usuario, manifest de permisos, sin autoload desde proyectos |
| Dependencia comprometida | Lockfile con hashes, SBOM, revisión de diffs en updates |
| Exfiltración vía capa IA | Consentimiento por proyecto, vista previa del payload, proveedores configurables local-first |

# 18. Instalación, actualización y desinstalación
- Instalador MSI (WiX v4), per-user por defecto (sin elevación); opción all-users con elevación solo si se elige.
- Idempotencia: reejecutar el instalador repara/actualiza sin duplicar accesos; UpgradeCode estable, MajorUpgrade configurado.
- Preflight: arquitectura x64, versión de Windows, espacio en disco.
- Separación estricta binarios/datos: nunca proyectos en Program Files.
%LOCALAPPDATA%\Programs\WiFiSurveyAI\   # binarios (per-user)
%LOCALAPPDATA%\WiFiSurveyAI\{logs,cache}\
%APPDATA%\WiFiSurveyAI\settings.json
Proyectos: carpetas elegidas por el usuario
- Upgrade: preserva settings y jamás toca proyectos; migración de settings versionada.
- Desinstalación: elimina binarios, shortcuts y registro; diálogo explícito con dos opciones — conservar datos/configuración (default) o eliminar todo — y la elección queda registrada en el log de desinstalación.
- Portable ZIP: modo autodetectado por archivo portable.marker junto al ejecutable; en portable, config y logs viven junto a la app.

# 19. Observabilidad y diagnóstico
- Logging estructurado (JSON lines) con niveles configurables; rotación por tamaño (10 MB × 5).
- Taxonomía de errores con códigos estables (WSA-xxxx) usados en UI, logs y documentación — cada mensaje de error de UI enlaza a su página de troubleshooting.
- Bundle de diagnóstico exportable: versión, capacidades del scanner, estado del permiso de ubicación, adaptadores, últimos logs, sin datos de survey salvo inclusión explícita.
- Métricas locales de performance (tiempos de scan, render, interpolación) visibles en un panel de desarrollador oculto (Ctrl+Shift+D).

# 20. Testing y CI/CD
Pull Request:  ruff → mypy(strict en domain/rf) → pytest unit
               → pytest integration → RF regression (golden files)
               → import-linter (capas) → build de paquete
Release tag:   clean build → smoke test VM Win10 22H2 + Win11
               → install/upgrade/uninstall test → SBOM
               → SHA256 → firma → GitHub Release
- Tests de propiedad (hypothesis) en parsing de IEs e interpolación (p. ej.: IDW nunca produce valores fuera del rango de sus muestras).
- Los adaptadores de captura se testean contra fixtures grabadas (registros WLAN_BSS_ENTRY serializados) — CI no necesita radio real; un job opcional self-hosted con NIC real valida nightly.
- Smoke test de release: instalación limpia, arranque, crear proyecto, abrir plano, calibrar, escanear (si hay adaptador), guardar, cerrar, reabrir, actualizar versión, desinstalar conservando datos.

# 21. Requisitos no funcionales (medibles)

| Atributo | Objetivo | Verificación |
| --- | --- | --- |
| Arranque en frío | ≤ 4 s hasta ventana interactiva (hardware de referencia: i5 gen11, SSD) | Benchmark en CI de release |
| Latencia de UI | Sin bloqueos del main thread > 100 ms | Instrumentación en modo dev + test automatizado |
| Render de heatmap | ≤ 2 s para 1 000 muestras / 2 000 m² a 0.25 m/celda | Benchmark con fixture estándar |
| Memoria | ≤ 800 MB con proyecto de 10 000 muestras y 5 plantas | Perfil en CI |
| Tamaño de instalador | ≤ 250 MB (vigilar coste de OpenCV si se incluye) | Gate en CI |
| Pérdida de datos | Cero por crash: escritura atómica + WAL | Test de kill -9 durante guardado |
| Determinismo RF | Igual input + versión ⇒ igual output bit a bit | Golden files en CI |

# 22. Internacionalización, accesibilidad y UX
- i18n con Qt Linguist desde el día 1; strings externalizados; español e inglés en 1.0; formato de números/unidades por locale (métrico default, imperial opcional).
- Accesibilidad: navegación por teclado completa, colormaps con alternativa apta para daltonismo (cividis), tamaños de fuente respetando el escalado del sistema, soporte high-DPI (Qt AA_EnableHighDpiScaling).
- Principios de UX del survey: el flujo crítico (clic en plano → captura → siguiente punto) debe ejecutarse con una sola mano y sin diálogos modales; atajo de teclado para 'capturar aquí de nuevo'.
- Modo oscuro nativo (paleta Qt) — herramienta usada en terreno con poca luz.

# 23. Gobernanza open source
- Licencia Apache-2.0; contribuciones bajo DCO (Signed-off-by), sin CLA.
- Versionado semver; CHANGELOG mantenido (Keep a Changelog); política de deprecación de API pública de 2 minor versions.
- ADRs en /ADR numerados e inmutables (se reemplazan, no se editan); toda decisión de §25 exige ADR nuevo.
- GOVERNANCE.md: modelo BDFL inicial con camino declarado a comité de maintainers al superar 3 contributors sostenidos.
- Roadmap público en GitHub Projects; releases con notas orientadas a usuario, no solo commits.
- Documentación como producto: sitio (MkDocs Material) con guía de usuario, guía de hardware validado, teoría RF aplicada y API de plugins.

# 24. Criterios de aceptación de v0.1
- El instalador MSI instala y ejecuta en Windows 10 22H2 x64 limpio y Windows 11 x64 limpio, sin Python ni runtimes preinstalados.
- La aplicación arranca sin Internet en ≤ 4 s (hardware de referencia).
- Primera ejecución detecta y guía el estado del permiso de ubicación.
- Crear, guardar, cerrar y reabrir un proyecto .wifisurvey produce datos idénticos (round-trip verificado por hash).
- Cargar un plano PNG/JPG y calibrarlo con error reportado.
- El backend Native WiFi devuelve BSS con RSSI en dBm reales cuando el adaptador lo permite; health() distingue las 4 causas de lista vacía (§4.1).
- Toda muestra distingue observado/derivado/estimado en datos y en UI.
- Generar un heatmap RSSI con máscara de confianza y leyenda a partir de ≥ 20 muestras.
- La desinstalación elimina la aplicación y respeta la elección explícita sobre los datos.
- Un proyecto v0.1 contiene schema_version y abre con mensaje claro en versiones incompatibles.
- kill del proceso durante guardado no corrompe el proyecto.
- La build se reproduce desde el repositorio siguiendo BUILD.md en un runner limpio.

# 25. Decisiones que NO se cambian sin ADR
- Cambiar el formato de proyecto sin schema migration.
- Introducir dependencia de cloud para que el survey básico funcione.
- Convertir una estimación en medición sin marcarla como derivada, o estimar noise/SNR y presentarlo como observado.
- Acoplar la UI a una API de Windows.
- Requerir Python/Node instalados en el equipo del usuario final.
- Eliminar proyectos durante upgrade/uninstall sin confirmación explícita.
- Cambiar un modelo RF sin actualizar fixtures y sin incrementar su versión.
- Cargar plugins automáticamente desde un archivo de proyecto.
- Añadir telemetría de cualquier tipo.

# 26. Roadmap de implementación

| Fase | Entrega | Criterio de salida |
| --- | --- | --- |
| F0 | Repo, arquitectura, CI, packaging base, ADRs | Instalador 'hello world' firmable pasa smoke test en ambas VMs |
| F1 | Desktop shell + project model + SQLite + .wifisurvey | Round-trip de proyecto verificado; migración 0001 aplicada |
| F2 | Backend Native WiFi + parsing IEs + health() | Fixtures de BSS reales capturadas; 4 causas de lista vacía distinguidas |
| F3 | Survey session: stop-and-go + validación + perfiles de adaptador | Survey de 50 puntos completado en site real de prueba |
| F4 | Heatmaps profesionales + máscara de confianza + reporting PDF/HTML | NFR de render cumplido; export con leyenda y metadatos |
| F5 | RF engine predictivo (log-distance → multi-wall) + validación empírica | Error medio ≤ 6 dB en 2 sites de referencia |
| F6 | Analytics (canal/capacidad/roaming) + import .esx + survey continuo | Import .esx de proyecto real con reporte de fidelidad |
| F7 | Optimización de APs (posicionamiento/canal/potencia sugeridos) | Sugerencias reproducibles y justificadas contra analytics |
| F8 | IA advisory local-first opcional | Cero llamadas de red sin consentimiento verificado en test |
| F9 | Hardening, docs, gobernanza → Release 1.0 | Todos los NFRs verdes; docs completas; 2 maintainers activos |

# 27. Riesgos y mitigaciones

| Riesgo | Prob. | Impacto | Mitigación |
| --- | --- | --- | --- |
| Variabilidad de RSSI entre NICs mina la credibilidad | Alta | Alto | Perfiles de adaptador + lista de hardware validado + declaración explícita en reportes (§5) |
| Endurecimiento futuro de permisos WLAN en Windows | Media | Alto | health() + onboarding adaptable; seguimiento de releases de Windows en CI con VMs Insider |
| SmartScreen bloquea instaladores sin firma | Alta | Medio | Documentación clara; roadmap de certificado OV; reputación progresiva |
| Alcance excesivo (comparación con Ekahau completa) | Alta | Alto | No-alcance explícito (§3.2) y roadmap por fases con criterios de salida |
| Fatiga de maintainer (proyecto unipersonal) | Media | Alto | Gobernanza temprana, docs de contribución de calidad, issues 'good first issue' curados |
| Cambio de formato .esx por Ekahau | Media | Bajo | Import best-effort con reporte de fidelidad; tests con fixtures de múltiples versiones |

# 28. Architecture Decision Records

## ADR-001 — Baseline Windows
Decisión: Windows 10 22H2 x64 como mínimo (compatibilidad técnica, no garantía de soporte del OS, cuyo ciclo general terminó en octubre de 2025) y Windows 11 x64 como plataforma principal. Razón: maximizar base instalada sin depender de APIs exclusivas de Windows 11; toda API se comprueba por disponibilidad en runtime, nunca por número de versión.

## ADR-002 — Aplicación autocontenida
Decisión: distribuir runtime Python y Qt dentro del bundle (PyInstaller onedir). Razón: eliminar variabilidad de entorno del usuario. Consecuencia aceptada: instalador de ~150–250 MB.

## ADR-003 — Arquitectura hexagonal con verificación automática
Decisión: capas UI → Application → Domain con Infrastructure como adaptadores de ports, verificadas por import-linter en CI. Razón: portabilidad futura (macOS/Linux), testabilidad del núcleo sin radio real, y frontera limpia para plugins. Alternativa descartada: MVC monolítico (rápido al inicio, deuda estructural inmediata).

## ADR-004 — Formato de proyecto .wifisurvey como ZIP autocontenido
Decisión: contenedor ZIP con manifest.json + SQLite + assets embebidos, escritura atómica. Razón: portabilidad total entre equipos, un solo archivo compartible, migraciones controladas. Alternativa descartada: carpeta suelta (frágil al mover/comprimir) y SQLite único con blobs (planos grandes degradan la DB).

## ADR-005 — Captura vía Native Wi-Fi API con parsing propio de IEs
Decisión: WlanGetNetworkBssList + parser propio de Information Elements como fuente primaria; netsh solo diagnóstico. Razón: dBm reales, capacidades PHY reales y BSS Load habilitan análisis profesional sin monitor mode; netsh es scraping frágil y su % no es dBm. Consecuencia: mantener el parser de IEs actualizado frente a 802.11be y sucesores.

## ADR-006 — Honestidad metrológica como invariante de producto
Decisión: la clasificación observado/derivado/estimado/predictivo es parte del modelo de datos (no solo de la UI) y su degradación silenciosa está prohibida por §25. Razón: es el fundamento de la confianza profesional en una herramienta sin hardware calibrado; es también el principal diferenciador defendible frente a herramientas gratuitas que colorean píxeles sin declarar su origen.

# 29. Glosario

| Término | Definición |
| --- | --- |
| BSS / BSSID | Basic Service Set; identidad radio observable (MAC del AP por radio/SSID) |
| IE (Information Element) | Estructura TLV en beacons/probe responses con capacidades del AP |
| QBSS / BSS Load | IE 11: nº de estaciones asociadas y utilización de canal reportadas por el AP |
| IDW / RBF / Kriging | Métodos de interpolación espacial (determinista simple / funciones de base radial / geoestadístico) |
| MWM (Multi-Wall Model) | Modelo de propagación que suma pérdidas por muros atravesados (COST 231) |
| Golden file | Salida esperada exacta versionada, usada como test de regresión |
| SBOM | Software Bill of Materials: inventario firmado de dependencias de una release |
| DCO | Developer Certificate of Origin: certificación de autoría por commit |

# 30. Referencias técnicas
- Microsoft — Native Wifi API: WlanScan, WlanGetNetworkBssList, WlanRegisterNotification, WLAN_BSS_ENTRY.
- Microsoft — Wi-Fi scanning y requisitos de permiso de ubicación en Windows 11.
- Microsoft — Windows client lifecycle (fin de soporte de Windows 10, oct-2025).
- IEEE 802.11-2020 — Information Elements, BSS Load (element ID 11).
- COST 231 Final Report — Multi-Wall Model; ITU-R P.1238 (propagación indoor).
- WiX Toolset v4 — MSI authoring, MajorUpgrade, per-user installs.
- PyInstaller — modo onedir y firma de binarios.
- CycloneDX — especificación SBOM; Keep a Changelog; Developer Certificate of Origin.

Fin del documento — v0.2
