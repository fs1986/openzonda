# ADR-007 — Binding a `wlanapi.dll` mediante `ctypes`

- **Estado:** Aceptado
- **Fecha:** 2026-08-02
- **Decisores:** architect, dev-core

## Contexto

ADR-005 fija la Native Wi-Fi API como fuente primaria de captura. Falta decidir **cómo**
se llama a `wlanapi.dll` desde Python, y esa decisión condiciona el toolchain de todo el
proyecto: quien elija una extensión compilada obliga a tener compilador en CI y en la
máquina de cada contribuidor, y añade un paso de build a un proyecto que ADR-002 quiere
autocontenido y sencillo de empaquetar.

La carga real es baja: unas decenas de BSS cada 4 s (cadencia impuesta por el throttling
de scan de Windows). El coste de llamada no es el factor limitante en ningún escenario
previsible del producto.

## Decisión

Los bindings se implementan con **`ctypes` de la biblioteca estándar**. No se introduce
ninguna extensión compilada para la capa de captura.

## Consecuencias

- **Positivas:** cero toolchain C++ para desarrollar o construir OpenZonda; `wlanapi.dll`
  es una API C estable desde hace más de quince años con estructuras documentadas;
  el depurado es Python puro; CI no necesita paso de compilación, lo que mantiene los
  tiempos de build bajos y la barrera de entrada para contribuidores al mínimo.
- **Aceptadas:** los `struct` se definen a mano, lo que es propenso a errores de offset.
  Un offset mal calculado no produce una excepción: produce **datos silenciosamente
  corruptos**, que es el peor modo de fallo posible para un producto cuyo invariante es la
  honestidad metrológica (ADR-006). La mitigación es obligatoria, no opcional — ver
  Verificación.
- **Alternativas descartadas:**
  - *pybind11 / C++*: tipado nativo y algo más de velocidad, pero exige MSVC en CI y en
    cada contribuidor. La ganancia de rendimiento es irrelevante a esta cadencia.
  - *Rust + PyO3*: seguridad de memoria a cambio del mismo coste de toolchain. Se reserva
    para posibles hotspots numéricos del RF engine (F5), no para IO de baja frecuencia.

## Verificación

1. **Test de tamaño y offsets por cada `struct`.** Todo `struct` `WLAN_*` se define junto
   a un test que compara `ctypes.sizeof()` y los offsets de sus campos contra los valores
   documentados del SDK, citados en comentarios en el propio código. Un binding sin ese
   test no se acepta.
2. **Fixtures grabados.** El parsing completo se valida contra capturas reales de BSS
   almacenadas como golden files, de modo que un cambio de layout se detecte por regresión
   y no en terreno.
3. El contrato de capas de ADR-003 impide que la UI importe `ctypes` directamente; los
   bindings viven detrás de un port y su violación rompe CI (verificado por los tests de
   `tests/integration/test_contratos_de_capas.py`).
