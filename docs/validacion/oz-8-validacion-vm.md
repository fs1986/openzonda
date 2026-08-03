# OZ-8 · Checklist de validación [HW] en VM Windows 11 build 26200

> Para el PO. Reusa el snapshot limpio de la VM (build 26200) usado en OZ-4/OZ-33. Instalá el
> MSI del build con OZ-8 (ver «Entrega» al pie). Registrá la evidencia indicada en cada paso;
> con eso OZ-8 pasa de In Review a Done. Cualquier paso en rojo: no cerrar, comentar en OZ-8.

## Pre-requisitos

- [ ] VM Windows 11 24H2/25H2, build 26200 (verificar con `winver`).
- [ ] MSI de OZ-8 instalado (per-user, sin elevación). La app **abre** (guard de OZ-33 ok).
  - *Evidencia:* captura de la ventana de Inicio + `winver`.

## 1. Arranque y pantalla de Inicio

- [ ] Al abrir, se ve la pantalla **Inicio** con «Nuevo proyecto» / «Abrir proyecto…» y, si es
      primer uso, «No hay proyectos recientes todavía».
  - *Evidencia:* captura de la pantalla de Inicio.

## 2. Crear → guardar → cerrar → reabrir (round-trip real, el corazón de F1.4)

- [ ] «Nuevo proyecto»: el título muestra `• Proyecto sin título — OpenZonda` (la `•` = sin
      guardar) y aparece la vista de Proyecto con el nombre editable.
- [ ] Renombrar el proyecto (p. ej. «Prueba VM»). La `•` sigue mientras no se guarde.
- [ ] Guardar (Ctrl+S) → elegir una ruta `...\Prueba VM.wifisurvey`. La `•` desaparece y la
      barra de estado muestra la ruta.
  - *Evidencia:* captura del título sin `•` + el archivo `.wifisurvey` en el explorador.
- [ ] Cerrar el proyecto (Ctrl+W) → vuelve a Inicio; «Prueba VM» aparece en **Recientes**.
- [ ] Reabrir desde Recientes (doble clic) → se abre con el **mismo nombre**.
  - *Evidencia:* captura del proyecto reabierto con el nombre correcto.
- [ ] **Criterio clave:** el proyecto reabierto es idéntico al guardado (nombre y contenido).

## 3. Migraciones desde el ejecutable congelado (cierra diferida de OZ-6/OZ-7)

- [ ] Que los pasos del punto 2 funcionen desde el `.exe` instalado **es** la verificación:
      crear/abrir un proyecto real ejercita por primera vez la carga de migraciones SQL
      empaquetadas (`importlib.resources`) en un binario congelado. Si el punto 2 pasó, esta
      queda cubierta.
  - *Evidencia:* implícita en el punto 2 (no requiere captura extra).

## 4. Cambios sin guardar (dirty)

- [ ] Con un proyecto abierto y renombrado (sin guardar), intentar **cerrar la ventana** →
      aparece «Cambios sin guardar» con Guardar / Descartar / Cancelar.
- [ ] «Cancelar» → la ventana no se cierra. «Descartar» → se cierra sin guardar.
  - *Evidencia:* captura del diálogo.

## 5. Upgrade preserva settings y recientes (inmutable nº6)

- [ ] Con al menos un reciente registrado, instalar encima una versión mayor (si el PO dispone
      de otro MSI) **o** reiniciar la app: los **recientes y la geometría** de la ventana
      sobreviven.
  - *Evidencia:* captura de Recientes tras reiniciar.

## 6. Reciente roto (archivo movido)

- [ ] Cerrar la app. Mover/renombrar el `.wifisurvey` de «Prueba VM» en el explorador. Abrir la
      app: en Recientes, la entrada sigue, marcada **«no disponible»** con ícono de advertencia,
      y no se puede abrir.
- [ ] «Quitar de recientes» la elimina; sin ese clic, **no** desaparece sola.
  - *Evidencia:* captura de la entrada marcada no disponible.

## 7. Cierre limpio

- [ ] Cerrar la app sin proyecto abierto no pide nada y cierra sin error.
- [ ] Reabrir: la ventana recuerda su tamaño/posición.

## Resultado

- [ ] Todos los pasos en verde → comentar OZ-8 con la evidencia y pasar a **Done**.
- [ ] Algún paso en rojo → dejar OZ-8 en **In Review** y comentar el paso y la captura.

## Entrega del build

El MSI de OZ-8 sale del pipeline `release.yml` (misma vía que OZ-33): mergear el PR de OZ-8 a
`main`, taguear una versión mayor (p. ej. `v0.0.4`) desde `main` actualizado, y descargar el
MSI del release en borrador / artifact del run. **No** taguear sin verificar antes con
`git log --oneline` que el commit correcto está en la cima de `main` (lección de v0.0.2).
