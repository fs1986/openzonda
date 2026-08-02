"""Composition root de OpenZonda (ADR-008).

Único paquete autorizado a importar infraestructura (`persistence` y, más adelante,
`wifi` y `windows`). Aquí se resuelven las rutas, se configura el logging, se instancian
los adaptadores concretos y se inyectan en la UI.

`desktop` recibe todo por constructor y nunca construye ni busca sus colaboradores.
"""
