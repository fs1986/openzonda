# OpenZonda — Design Brief de UI/UX para Mockups

> Documento de encargo para el diseñador · v1.0 · 2026-08-02

| Campo | Valor |
|---|---|
| Producto | OpenZonda — aplicación de site survey WiFi profesional, open source |
| Plataforma | Aplicación de escritorio nativa Windows 10/11 (Qt / PySide6) |
| Encargo | Mockups de alta fidelidad + sistema visual (design system ligero) |
| Referentes de mercado | Ekahau AI Pro, Hamina, NetSpot |

**Cómo leer este brief:** las secciones 1–4 son contexto obligatorio (qué es el producto, quién lo usa y una regla de diseño única que no debe romperse). La sección 5 lista las pantallas a diseñar en orden de prioridad. Las secciones 6–9 definen el sistema visual, los entregables y los límites técnicos. Si solo lees una cosa, lee la sección 3.

---

## 1. Qué es OpenZonda (en 60 segundos)

OpenZonda es una herramienta de escritorio para hacer *site surveys* de WiFi: un ingeniero recorre un edificio con un plano cargado en la app, va marcando su posición sobre ese plano, y en cada punto la aplicación mide las redes WiFi visibles (potencia de señal, canal, tecnología). Con esas mediciones genera mapas de calor (*heatmaps*) que muestran, por ejemplo, dónde la cobertura es buena y dónde hay zonas muertas.

Es una alternativa abierta y gratuita a productos comerciales caros como Ekahau AI Pro. El usuario objetivo es un profesional de redes, no un consumidor. El valor de la herramienta está en la precisión y en la honestidad de sus datos: es una herramienta de trabajo con la que alguien entrega un informe a su cliente y lo defiende técnicamente.

### 1.1 Los tres momentos de uso

- **Preparar (escritorio):** crear el proyecto, cargar el plano del edificio, calibrar su escala (decirle a la app cuántos metros mide una pared para que las distancias sean reales).
- **Medir (en terreno, de pie, caminando):** recorrer el espacio, hacer clic en el plano en cada punto donde uno está parado, y capturar. Este es el momento crítico: se hace de pie, a veces con poca luz, idealmente con una sola mano.
- **Analizar y reportar (escritorio):** ver los heatmaps, detectar problemas (interferencia, zonas sin cobertura), y exportar un informe en PDF para el cliente.

---

## 2. Usuario y contexto

| Atributo | Detalle de diseño |
|---|---|
| Perfil | Ingeniero/técnico de redes WiFi. Alta alfabetización técnica. Espera densidad de información, no simplificación. |
| Referencia mental | Ya usa (o conoce) Ekahau, NetSpot o similares. El diseño debe sentirse familiar para ese mundo, pero más limpio. |
| Dispositivo | Laptop Windows. Pantallas de 13" a 27", muchas de alta densidad (high-DPI). Se usa con mouse/trackpad y teclado; no es táctil. |
| Entorno de medición | De pie, caminando por oficinas/bodegas/hospitales. A veces poca luz. Por eso el modo oscuro es el modo por defecto, no una opción secundaria. |
| Estado mental en terreno | Concentrado en no perder el ritmo del recorrido. Cualquier fricción (un diálogo que interrumpe, un botón pequeño) le hace perder puntos de medición. |
| Idiomas | Español e inglés. Los textos deben poder alargarse ~30% al traducir sin romper el layout. |

---

## 3. Regla de diseño innegociable: honestidad del dato

> ★ **Esta es la sección más importante del brief.** El diferenciador de OpenZonda frente a herramientas gratuitas es que nunca miente sobre la calidad de un dato. El diseño debe hacer visible, en todo momento, de dónde viene cada número. Un mockup que muestre un heatmap bonito sin comunicar esto habrá fallado en lo esencial.

Cada valor que la app muestra pertenece a una de cuatro categorías, y el diseño debe distinguirlas visualmente (por color, ícono, etiqueta o textura — a definir por el diseñador, pero deben ser inconfundibles):

| Categoría | Qué significa | Ejemplo visible en pantalla |
|---|---|---|
| **Observado** | Medido directamente por la app en ese punto. | Un punto de medición sobre el plano; una fila en la tabla de redes. |
| **Derivado** | Calculado a partir de mediciones (ej. la posición interpolada al caminar). | Debe verse distinto de un punto observado — más tenue, o con otro contorno. |
| **Estimado** | Aproximado, de menor confianza (ej. señal obtenida por un método de respaldo). | Marca clara de "dato aproximado". No debe confundirse con una medición real. |
| **Predictivo** | Simulado por un modelo, no medido (ej. cómo se vería la señal si moviéramos un router). | Un heatmap predictivo debe llevar un sello permanente "PREDICTIVO" que sobreviva incluso a una captura de pantalla. |

### Dos consecuencias concretas para el diseño

- **Máscara de confianza en heatmaps:** las zonas del plano lejos de cualquier medición NO se colorean con un valor inventado. Se muestran neutras/con textura, comunicando "aquí no hay datos suficientes". Diseñar cómo se ve esa zona "sin confianza" es parte del encargo.
- **Señal no disponible ≠ señal cero:** cuando un dato no se puede medir (ej. SNR), la UI dice "no disponible", nunca muestra un 0 que parezca una medición. Diseñar ese estado vacío.

---

## 4. Restricciones técnicas (marco fijo)

Estas condiciones vienen de la arquitectura ya decidida. No son negociables; son el lienzo dentro del cual se diseña.

| Restricción | Implicación para el diseño |
|---|---|
| Escritorio nativo Qt (PySide6) | No es web. Usar patrones de aplicación de escritorio: barra de menú, barra de herramientas, paneles acoplables (docks), barra de estado. No patrones móviles ni de landing web. |
| Ventana con paneles acoplables (docks) | El usuario puede mover/ocultar paneles laterales alrededor de un área central. Diseñar el layout por defecto, pero asumiendo que los docks se reorganizan. |
| Modo oscuro por defecto | El tema oscuro es el principal (uso en terreno con poca luz). Entregar también el tema claro, pero el oscuro manda. |
| High-DPI | Iconos y assets vectoriales o @2x/@3x. Nada rasterizado de baja resolución. |
| Teclado como ciudadano de primera | Todo flujo debe tener atajo de teclado. Mostrar los atajos en la UI (tooltips, junto a acciones). El flujo de medición se opera casi sin mouse. |
| Accesibilidad de color | Los mapas de calor deben tener una opción apta para daltonismo. Evitar rojo/verde como único diferenciador de estado. |
| i18n (es/en) | No hardcodear anchos a un texto en español; el inglés o alemán pueden ser más largos/cortos. |

---

## 5. Pantallas a diseñar (por prioridad)

Ordenadas por importancia. Si el tiempo es limitado, las tres primeras son las críticas. Para cada una: diseñar el estado normal, el estado vacío (sin datos aún) y el estado de error donde aplique.

### 5.1 — PRIORIDAD MÁXIMA · Pantalla de Survey (medición)

El corazón de la app. Es donde el usuario pasa el tiempo en terreno. Layout típico:

- **Centro:** el plano del edificio, con zoom y desplazamiento (pan). Sobre él se dibujan los puntos de medición ya capturados, coloreados según la señal.
- **Panel lateral (dock):** árbol del proyecto (sitios, pisos, sesiones de medición).
- **Panel de redes en vivo:** tabla que se actualiza cada ~4 segundos con las redes WiFi visibles ahora mismo: nombre de red, identificador, señal en dBm, banda (2.4/5/6 GHz), canal, ancho de canal, tecnología (WiFi 5/6/6E/7), seguridad. Es una tabla densa — pensarla como una herramienta de analista, no como una lista simplificada.
- **Acción central:** "capturar en este punto". Un clic en el plano marca la posición y captura. Atajo de teclado para recapturar (barra espaciadora) y deshacer el último punto (Z). Sin diálogos que interrumpan el ritmo.
- **Indicador de estado del hardware:** un lugar visible que diga si la antena WiFi está lista o si hay un problema (ver 5.5).

> ★ **Prueba de fuego de esta pantalla:** ¿puede el usuario, de pie y con una mano, marcar 50 puntos en 20 minutos sin frustrarse? El diseño debe optimizar ese recorrido repetitivo.

### 5.2 — PRIORIDAD MÁXIMA · Vista de Heatmap (análisis)

- El mismo plano, pero cubierto por un mapa de calor de color continuo (ej. de rojo=malo a verde/azul=bueno, con opción daltónica).
- Selector del tipo de mapa: señal (RSSI), cobertura por umbral, canal, densidad de redes, etc.
- Leyenda de color siempre visible, con la escala numérica (ej. −30 a −90 dBm).
- Las zonas sin datos suficientes se ven neutras/con textura (la "máscara de confianza" de la sección 3), no coloreadas con un valor inventado. Diseñar ese aspecto es clave.
- Un heatmap predictivo (simulado) debe llevar un sello "PREDICTIVO" permanente.

### 5.3 — PRIORIDAD ALTA · Gestión de proyecto y carga/calibración de plano

- Pantalla de inicio / proyectos recientes: crear nuevo, abrir, recientes.
- Cargar imagen de plano (PNG/JPG) y encuadrarla.
- **Herramienta de calibración:** el usuario traza una línea sobre algo de medida conocida en el plano (ej. una pared de 5 m) y escribe la distancia real. Diseñar esa interacción de "dos puntos + medida".

### 5.4 — PRIORIDAD MEDIA · Reporte / exportación

- Vista previa del informe PDF que recibe el cliente: portada, metodología (qué antena se usó, cuándo), heatmaps con leyenda, tabla de redes, hallazgos.
- Diálogo de exportación (PDF, CSV, JSON) con opciones.

### 5.5 — PRIORIDAD MEDIA · Estados de diagnóstico y error

OpenZonda depende de la antena WiFi del equipo y de permisos del sistema. El diseño debe comunicar con claridad estos estados sin datos, que son frecuentes y hoy confunden a los usuarios de otras herramientas:

- Permiso de ubicación desactivado (Windows lo exige para ver redes) → mensaje claro + botón que lleva a la configuración.
- Antena WiFi apagada / no detectada / servicio del sistema caído → cada caso con su mensaje distinto.
- Onboarding de primera ejecución que verifica que todo esté listo antes del primer survey.

---

## 6. Sistema visual a definir

Parte del encargo es proponer el lenguaje visual. No hay marca previa que respetar más allá del nombre "OpenZonda" (zonda = viento andino; hay libertad creativa). Definir:

| Elemento | Qué se espera |
|---|---|
| Paleta | Tema oscuro (principal) y claro. Un color de acento de marca. Escalas de color perceptualmente uniformes para heatmaps (tipo viridis/turbo) + una variante daltónica. |
| Tipografía | Una familia para UI (legible en tamaños pequeños y densos) y una monoespaciada para datos técnicos (BSSID, valores). Fuentes libres (el proyecto es open source): sugerido explorar Inter, IBM Plex, Source Sans/Mono. |
| Iconografía | Set coherente para acciones (capturar, calibrar, exportar, capas). Estilo lineal recomendado. Vectorial. |
| Codificación de estado | El sistema visual para distinguir observado/derivado/estimado/predictivo (sección 3). Es el elemento de identidad más importante y propio del producto. |
| Componentes densos | Tablas de datos, leyendas, tooltips, badges de estado — el producto vive de mostrar mucha información técnica ordenada. |

---

## 7. Entregables esperados

1. Mockups de alta fidelidad de las pantallas de la sección 5, en tema oscuro (y las críticas también en claro), a resolución high-DPI.
2. Para las pantallas críticas (5.1 y 5.2): sus estados vacío, con datos y de error/sin-datos.
3. Un flujo navegable (prototipo clickable) del recorrido completo: crear proyecto → cargar plano → calibrar → medir → ver heatmap → exportar.
4. Mini design system: paleta, tipografía, iconos, componentes base (botón, tabla, badge de estado, leyenda), y las reglas de codificación observado/derivado/estimado/predictivo.
5. Especificaciones de handoff: spacing, tamaños, tokens de color, estados de interacción — para que se pueda implementar en Qt.

**Formato**

- Figma preferido (permite prototipo navegable y handoff). Entregar acceso al archivo, no solo imágenes exportadas.
- Assets de iconos en SVG.

---

## 8. Qué NO hacer (errores a evitar)

- No diseñar una web app ni una landing: es una herramienta de escritorio densa, no un sitio de marketing.
- No "simplificar" escondiendo datos técnicos: el usuario los quiere. Ordenar ≠ ocultar.
- No colorear un heatmap completo donde no hay mediciones: viola la regla de la sección 3.
- No usar rojo/verde como único diferenciador (accesibilidad).
- No poner diálogos modales en el flujo de captura: rompen el ritmo del survey.
- No inventar métricas que la app no produce (ej. "velocidad garantizada"): solo se diseña lo que existe en el modelo de datos.

---

## 9. Referencias e insumos

Para calibrar el nivel esperado, pedir al diseñador que revise capturas de estas herramientas (referencia de mercado, no de estilo a copiar):

- **Ekahau AI Pro** — el estándar profesional; observar su vista de survey y sus heatmaps.
- **NetSpot** — alternativa más accesible en Windows/macOS; buen ejemplo de survey simplificado.
- **Hamina** — referencia de UX moderna en diseño predictivo.

Documentos internos que se pueden compartir con el diseñador si necesita más profundidad: el **Diseño de Software v0.2** (arquitectura y modelo de datos) y el **Plan de Implementación** (secciones de heatmap, survey engine y captura). Este brief destila lo relevante para diseño; los otros dos son la fuente técnica completa.

**Contacto del producto:** el fundador (Product Owner). Dudas sobre comportamiento o prioridad se resuelven con él antes de asumir.

---

*Fin del brief — v1.0*
