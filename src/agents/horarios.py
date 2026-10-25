"""Especialista de horarios del grafo multiagente.

Conserva la secuencia heredada de consultar el momento actual y la evidencia
documental necesaria para responder sobre servicio, mediante dependencias que
el futuro grafo podrá inyectar en pruebas o producción.
"""
from __future__ import annotations

from typing import Any, Callable

from src.agents.base import ejecutar_especialista


PROMPT_HORARIOS = """Eres el especialista en horarios de MadridRumbo.
Respondes a preguntas sobre cuándo, a qué hora y hasta cuándo hay servicio de
transporte público de Madrid.

Tools disponibles únicamente:
- hora_actual: devuelve fecha, hora y tipo de día. Úsala si la consulta depende
  de "ahora", "hoy" o "esta noche".
- rag_ask(consulta): consulta los documentos oficiales para obtener horarios.

Reglas:
- Conserva las respuestas, abstenciones y errores de ambas tools; no inventes horarios.
- No pidas ninguna tercera tool ni repitas una consulta documental ya disponible.
- Responde SOLO con un JSON por mensaje:
  {"tool": "<nombre>", "args": {...}} para pedir una tool, o
  {"final": "<nota en español>"} cuando tengas la respuesta.
"""


def nodo_horarios(estado: dict[str, Any], llm: Callable[..., Any], ejecutar: Callable[..., str]) -> dict:
    """Ejecuta horarios con hora_actual y rag_ask como únicas dependencias directas."""
    return ejecutar_especialista("horarios", PROMPT_HORARIOS, estado, llm, ejecutar)
