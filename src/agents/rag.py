"""Especialista documental del grafo multiagente.

Este nodo es el único especialista dedicado a pedir evidencia directamente a
``rag_ask``. El ejecutor compartido aplica la allowlist y deja la traza de cada
llamada antes de devolver la nota que usará el sintetizador.
"""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import ejecutar_especialista


PROMPT_RAG = """Eres el especialista documental de MadridRumbo.
Respondes solo con la evidencia que aporta el corpus CRTM a la consulta de la
persona usuaria.

Tool disponible:
- rag_ask(consulta): consulta los documentos oficiales del CRTM.

Reglas:
- Usa rag_ask para buscar la evidencia antes de responder.
- Conserva literalmente una abstención o error que devuelva la tool; no inventes datos.
- Indica en la nota final que la información procede del corpus cuando haya evidencia.
- Responde SOLO con un JSON por mensaje:
  {"tool": "rag_ask", "args": {"consulta": "..."}} para pedir la tool, o
  {"final": "<nota en español>"} cuando tengas la respuesta.
"""


def nodo_rag(estado: dict[str, Any], llm: Callable[..., Any], ejecutar: Callable[..., str]) -> dict:
    """Ejecuta RAG mediante la única tool directa autorizada para este nodo."""
    return ejecutar_especialista("rag", PROMPT_RAG, estado, llm, ejecutar)
