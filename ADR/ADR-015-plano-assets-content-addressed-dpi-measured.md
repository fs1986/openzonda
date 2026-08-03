# ADR-015 — Plano: assets content-addressed y DPI con procedencia (Measured)

- **Estado:** Aceptado
- **Fecha:** 2026-08-03
- **Decisores:** architect, dev-core, dev-ui, el fundador (PO)

## Contexto

OZ-9a incorpora la carga de planos de planta. Dos preguntas estructurales tenían que
resolverse antes de construir el visor (OZ-36), porque condicionan el modelo de datos y no
son baratas de cambiar después:

1. **Cómo se identifica y almacena la imagen del plano** dentro del contenedor `.wifisurvey`.
   El plano es trabajo de campo referenciado por las muestras: si cambia bajo los pies, las
   coordenadas dejan de significar lo mismo (de ahí que `FloorPlan` ya guarde `asset_sha256`).
   Un mismo plano puede repetirse entre plantas o proyectos.
2. **Cómo se representa el DPI del plano.** El DPI puede venir del archivo (EXIF/pHYs/JFIF) o
   asumirse por defecto (96, el estándar de Windows). Presentar un DPI asumido como si fuera
   medido es exactamente la degradación silenciosa que ADR-006 prohíbe: con un DPI equivocado,
   una distancia calibrada a partir de él sería falsa sin que nadie lo note.

## Decisión

**1. Assets content-addressed.** La imagen del plano se guarda como `assets/<sha256>.<ext>`
dentro del contenedor y del working dir, donde `<sha256>` es el hash del **contenido** y
`<ext>` se deriva por **magic bytes** (el formato real), nunca por el nombre del archivo que
eligió el usuario. La deduplicación es por hash: el mismo contenido produce el mismo nombre y
se almacena una sola vez. El parseo de la imagen (formato, dimensiones, DPI) vive en un módulo
**puro** (`application/plan_image.py`, solo stdlib): lee de las cabeceras sin decodificar el
bitmap, así el límite de píxeles rechaza una bomba de descompresión desde su cabecera.

**2. `FloorPlan.dpi` es `Measured[float]`, no un `float` con un enum al lado.** El número no
existe crudo: viaja siempre envuelto en su procedencia (`OBSERVED` si vino del archivo,
`ESTIMATED` si se asumió 96). El tipo impone la honestidad; no es una convención que haya que
recordar aplicar.

## Consecuencias

- **Positivas:**
  - El plano es autocontenido y trasladable; renombrar el archivo de origen no rompe el
    dedup ni la integridad (el hash es del contenido, la extensión del formato real).
  - Un DPI asumido no puede leerse ni usarse como medido: el sistema de tipos lo impide, y la
    UI lo muestra con doble codificación en texto ("del archivo" vs. "asumido (por defecto)").
  - El parseo puro y sin decodificación da control exacto del rechazo (distingue px de bytes,
    con el valor real) y protege la memoria antes de asignar el bitmap.
- **Aceptadas:**
  - Formatos limitados a PNG/JPG y a ~12000 px por lado / ~50 MB en el alpha. Otros formatos
    (BMP, TIFF, WEBP) se reconocen y se rechazan con mensaje claro, no se soportan.
  - El plano es **obligatorio** por planta (una planta se crea con su plano, no a medias). Un
    modelo de "planta sin plano todavía" queda para una tarjeta futura con su propio ADR.
- **Alternativas descartadas:**
  - Nombrar el asset por el nombre del archivo del usuario: `plano.png` y `plano.PNG` con
    bytes idénticos romperían el dedup, y un nombre hostil escaparía del directorio.
  - `FloorPlan.dpi: float` + un campo `dpi_provenance` separado: un campo aparte se puede
    ignorar; envolver el número en `Measured` hace imposible degradarlo en silencio.
  - Usar Pillow para el parseo: arrastra su maquinaria de bombas de descompresión y decodifica
    de más; para leer formato/dimensiones/DPI basta la cabecera con stdlib.

## Verificación

- `tests/unit/test_plan_image.py`: formato por magic bytes (no por nombre), DPI `OBSERVED`
  desde pHYs/JFIF/EXIF vs. `ESTIMATED` por defecto, y rechazo tipado que **distingue px de
  bytes** con el valor real.
- `tests/integration/test_project_store.py`: round-trip del plano por hash (los bytes
  sobreviven guardar+reabrir), dedup por hash, `read_asset` de un hash ausente = corrupción.
- `tests/integration/test_project_repository.py`: la procedencia del DPI sobrevive el
  round-trip y un DPI observado no vuelve degradado.
- El tipo `Measured[float]` de `FloorPlan.dpi` lo garantiza mypy `--strict` sobre `domain`.
