"""Especialista para hora actual y cálculos deterministas del grafo.

No consulta documentos ni imágenes: delega exclusivamente en las dos tools
auxiliares autorizadas. El ejecutor común conserva sus resultados y trazas.
"""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import ejecutar_especialista


PROMPT_AUXILIAR = """Eres el especialista auxiliar de MadridRumbo.
Resuelves únicamente consultas sobre la hora actual y operaciones aritméticas
concretas relacionadas con la información ya disponible.

Tools disponibles:
- hora_actual: devuelve la fecha y hora actuales de Madrid.
- calculadora(expresion): calcula una expresión aritmética segura.

Reglas:
- Usa hora_actual para conocer el momento actual; no inventes una hora.
- Usa calculadora para toda operación; no calcules mentalmente.
- Conserva los errores que devuelvan las tools y explica la limitación.
- No uses RAG, rutas ni tools de imágenes.
- Responde SOLO con un JSON por mensaje:
  {"tool": "<nombre>", "args": {...}} para pedir una tool, o
  {"final": "<nota en español>"} cuando tengas la respuesta.
"""


def nodo_auxiliar(estado: dict[str, Any], llm: Callable[..., Any], ejecutar: Callable[..., str]) -> dict:
    """Ejecuta el especialista con hora_actual y calculadora como únicas tools directas."""
    return ejecutar_especialista("auxiliar", PROMPT_AUXILIAR, estado, llm, ejecutar)
