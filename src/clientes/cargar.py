"""Elige el grafo que usan los clientes: el real o, si se pide, el simulado (spec 008, RF-28 y RF-29)."""
import importlib
import os

import config
from src.clientes.grafo_falso import GrafoFalso

# Funciones que debe exponer el grafo real, según el contrato de `contrato.py`.
FUNCIONES_CONTRATO = ("procesar_turno", "aprobar_plan")

AVISO_SIMULADO = (
    "MODO SIMULADO: se usa un grafo de pruebas, no el grafo real. "
    "Las respuestas son texto fijo."
)


class GrafoNoDisponible(Exception):
    """No hay un grafo utilizable para los clientes; el mensaje está pensado para la persona usuaria."""


def _instrucciones_modo_simulado() -> str:
    return (
        f"Para probar los clientes sin el grafo real, activa el modo simulado con la variable de "
        f"entorno {config.VARIABLE_MODO_SIMULADO}={config.VALOR_MODO_SIMULADO}."
    )


def cargar_agente(entorno=None):
    """Devuelve `(agente, aviso)`; `aviso` es un texto en modo simulado y `None` con el grafo real.

    `entorno` es un diccionario de variables de entorno (por defecto, las del proceso).
    Lanza `GrafoNoDisponible` si no hay grafo real y no se ha pedido el simulado.
    """
    entorno = os.environ if entorno is None else entorno

    if entorno.get(config.VARIABLE_MODO_SIMULADO) == config.VALOR_MODO_SIMULADO:
        return GrafoFalso(), AVISO_SIMULADO

    try:
        modulo = importlib.import_module(config.MODULO_GRAFO_REAL)
    except ImportError:
        raise GrafoNoDisponible(
            f"El grafo multiagente todavía no está disponible ({config.MODULO_GRAFO_REAL}). "
            + _instrucciones_modo_simulado()
        ) from None

    faltan = [nombre for nombre in FUNCIONES_CONTRATO if not callable(getattr(modulo, nombre, None))]
    if faltan:
        raise GrafoNoDisponible(
            f"El grafo ({config.MODULO_GRAFO_REAL}) no cumple el contrato de los clientes: "
            f"le falta {', '.join(faltan)}."
        )
    return modulo, None
