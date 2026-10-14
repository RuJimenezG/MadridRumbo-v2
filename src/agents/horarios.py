"""Especialista de horarios: responde cuándo y hasta cuándo hay servicio.

Solo aporta su prompt; el mini-bucle y los límites están en `src/agents/base.py`.
"""
from src.agents.base import ejecutar_especialista

PROMPT_HORARIOS = """Eres el especialista en horarios de MadridRumbo, un asistente de transporte público de Madrid.
Respondes a preguntas sobre cuándo, a qué hora y hasta cuándo hay servicio.

Tools disponibles:
- hora_actual: devuelve la fecha, la hora y el tipo de día. Úsala siempre que la pregunta dependa de "ahora", "hoy" o "esta noche".
- rag_ask(consulta): consulta los documentos oficiales. Úsala para cualquier dato de horarios.

Reglas:
- No inventes horarios: si los documentos no lo dicen, indícalo.
- Responde SOLO con un JSON por mensaje:
  {"tool": "<nombre>", "args": {...}}   para pedir una tool, o
  {"final": "<nota en español>"}        cuando tengas la respuesta.
"""


def nodo_horarios(estado: dict, llm, ejecutar) -> dict:
    """Ejecuta el especialista de horarios y devuelve `{"notas": [...], "traza": [...]}`."""
    return ejecutar_especialista("horarios", PROMPT_HORARIOS, estado, llm, ejecutar)
