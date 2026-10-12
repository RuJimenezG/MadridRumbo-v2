"""
Genera una respuesta usando SOLO el contexto recuperado.
Si no hay evidencia en los documentos del corpus, el modelo debe abstenerse.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GENERATION_MODEL, TEMPERATURE
from src.retrieve import RetrievedChunk, format_context
from prompt import PROMPT_TEMPLATE

client = genai.Client(api_key=GEMINI_API_KEY)

def generate(pregunta: str, chunks: list[RetrievedChunk]) -> str:
    contexto = format_context(chunks)
    prompt = PROMPT_TEMPLATE.format(contexto=contexto, pregunta=pregunta)
    respuesta = client.models.generate_content(
        model=GENERATION_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=TEMPERATURE),
    )
    return respuesta.text