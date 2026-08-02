# ADR-008 — Composition root en un paquete propio

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect, fundador

## Contexto

ADR-003 fija la arquitectura hexagonal y la hace verificable con `import-linter`. Uno de sus
contratos prohíbe que la UI (`desktop`) importe infraestructura: `persistence`, `wifi`,
`windows` o `ctypes`.

Al implementar el walking skeleton (F0.4) aparece la tensión clásica de toda arquitectura
de puertos y adaptadores: **alguien tiene que instanciar los adaptadores concretos y
conectarlos a los puertos**. Ese "alguien" necesita, por definición, importar tanto la
infraestructura como la UI. Si el punto de entrada vive dentro de `desktop`, entonces
`desktop` importa `persistence` y el contrato se rompe — o hay que perforarlo con una
excepción.

El problema aparece ya en la primera línea de código de interfaz: el DoD de F0.4 pide
`settings.json` versionado y detección de modo portable, es decir acceso a disco.

## Decisión

El punto de entrada y el cableado de dependencias viven en un **paquete propio**,
`apps/openzonda` (módulo importable `openzonda`), separado de `apps/desktop`.

- `openzonda` es el **único** paquete autorizado a importar `persistence` y, en el futuro,
  `wifi` y `windows`. Contiene `__main__.py`, la resolución de rutas de aplicación, la
  configuración de logging y el ensamblado de adaptadores.
- `desktop` queda reducido a vistas y ViewModels. Recibe sus colaboradores **por
  constructor**; nunca los construye ni los busca.
- Los puertos se declaran como `Protocol` en `application`; sus implementaciones viven en
  `persistence` y demás adaptadores.

Esto añade un paquete a la lista de §7.3 del diseño, que no lo contemplaba.

## Consecuencias

- **Positivas:** el contrato de capas se mantiene íntegro, sin excepciones ni exclusiones;
  `desktop` es testeable sin tocar disco, porque sus dependencias se inyectan y en test se
  sustituyen por dobles; el grafo de dependencias tiene una única raíz explícita en lugar
  de acoplamientos dispersos por los módulos de UI.
- **Aceptadas:** un paquete más que mantener, y una indirección extra al leer el código —
  para saber qué implementación concreta usa la UI hay que mirar el composition root, no el
  punto de uso. Es el coste normal de la inversión de dependencias.
- **Alternativas descartadas:**
  - *Settings dentro de `desktop` con `json` y `pathlib` de la biblioteca estándar.* No
    rompería el contrato de `import-linter` —no importa el paquete `persistence`— pero sí
    su intención: la UI quedaría tocando el sistema de archivos, y habría que deshacerlo en
    F1.4. Un contrato que se cumple en la letra mientras se viola en el espíritu es peor
    que no tenerlo, porque da falsa confianza.
  - *Excluir el punto de entrada del contrato.* Mantendría el layout del diseño intacto a
    cambio de abrir un agujero permanente en la barrera. Las excepciones de este tipo no se
    quedan quietas: la siguiente petición razonable las ensancha.

## Verificación

Contrato `layers` de `import-linter` con `openzonda` en la capa superior:

    openzonda → desktop → application → domain

Se mantiene además el contrato `forbidden` existente que impide a `desktop` importar
`persistence`, `wifi`, `windows` o `ctypes`. La combinación hace que un intento de cablear
adaptadores desde la UI rompa CI.

Los tests de `tests/integration/test_contratos_de_capas.py` (OZ-23) cubren estas barreras
inyectando imports ilegales y exigiendo que el linter los rechace.
