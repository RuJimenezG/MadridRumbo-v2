"""Especialista de tarifas que extrae texto e importes de una imagen.

La operación posterior se delega en ``nodo_auxiliar``. Este nodo no consulta
documentos ni realiza aritmética: conserva la información visible que necesita
el resto del grafo.
"""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import ejecutar_especialista


MARCADOR_REDIRECCION_A_RAG = "_redirigir_tarifas_a_rag"
_NOTA_SIN_IMAGEN_VALIDA = (
    "[tarifas] Se redirigió la consulta a rag porque no hay una imagen válida."
)


PROMPT_TARIFAS = """Eres el especialista de tarifas de MadridRumbo.
Extraes los textos e importes visibles en una imagen relacionada con tarifas de
transporte público de Madrid.

Tool disponible:
- describir_imagen(pregunta): lee la imagen y devuelve sus textos e importes.

Reglas:
- Usa describir_imagen para obtener los importes antes de redactar la nota.
- Conserva exactamente los importes leídos y su procedencia (la imagen).
- Si se solicita un total, no hagas cálculos: explica que nodo_auxiliar usará
  los importes extraídos para realizar la operación posterior.
- Si no hay importes legibles o la tool falla, conserva esa limitación; no
  inventes precios ni resultados.
- Responde SOLO con un JSON por mensaje:
  {"tool": "describir_imagen", "args": {...}} para pedir la tool, o
  {"final": "<nota en español>"} cuando tengas la respuesta.
"""


def redireccionar_tarifas_sin_imagen() -> dict[str, Any]:
    """Devuelve una señal interna para que el grafo derive el turno a RAG."""
    return {
        MARCADOR_REDIRECCION_A_RAG: True,
        "notas": [_NOTA_SIN_IMAGEN_VALIDA],
        "traza": [],
    }


def nodo_tarifas(
    estado: dict[str, Any],
    llm: Callable[..., Any],
    ejecutar: Callable[..., str],
    *,
    tiene_imagen_valida: bool = False,
) -> dict[str, Any]:
    """Ejecuta la extracción de tarifas mediante su única tool directa permitida."""
    if tiene_imagen_valida is not True:
        return redireccionar_tarifas_sin_imagen()
    return ejecutar_especialista("tarifas", PROMPT_TARIFAS, estado, llm, ejecutar)
