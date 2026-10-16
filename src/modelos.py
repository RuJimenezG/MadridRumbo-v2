"""Adaptadores perezosos de modelos para la orquestación multiagente.

La importación de este módulo no configura credenciales ni crea clientes. Los
clientes de Gemini solo se construyen al generar una respuesta de producción;
en tests, cada adaptador recibe una función generadora falsa.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from typing import Any, Callable, Mapping


Generador = Callable[[str], Any]


def _formatear_entrada(entrada: object) -> str:
    """Convierte una conversación o una instrucción en un prompt de texto."""
    if isinstance(entrada, str):
        return entrada
    if isinstance(entrada, list):
        partes = []
        for mensaje in entrada:
            if not isinstance(mensaje, Mapping):
                continue
            rol = str(mensaje.get("role", "user"))
            contenido = str(mensaje.get("content", ""))
            partes.append(f"{rol}: {contenido}")
        return "\n".join(partes)
    return str(entrada)


def _parsear_objeto(respuesta: Any) -> dict[str, Any]:
    """Acepta un objeto inyectado o JSON de un modelo y rechaza formatos ambiguos."""
    if isinstance(respuesta, Mapping):
        return deepcopy(dict(respuesta))

    if not isinstance(respuesta, str):
        raise ValueError("Respuesta del modelo no interpretable.")

    texto = respuesta.strip()
    marcador_codigo = chr(96) * 3
    if texto.startswith(marcador_codigo) and texto.endswith(marcador_codigo):
        lineas = texto.splitlines()
        texto = "\n".join(lineas[1:-1]).strip()

    try:
        objeto = json.loads(texto)
    except json.JSONDecodeError as exc:
        raise ValueError("Respuesta del modelo no interpretable.") from exc

    if not isinstance(objeto, dict):
        raise ValueError("Respuesta del modelo no interpretable.")
    return objeto


def _crear_cliente_gemini() -> Any:
    """Configura Gemini y crea el cliente solo cuando se necesita de verdad."""
    from model_auth import configurar_gemini_api_key

    configurar_gemini_api_key()

    from google import genai

    return genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


class GeneradorGemini:
    """Generador de producción que retrasa cliente y dependencias de Gemini."""

    def __init__(self, crear_cliente: Callable[[], Any] | None = None):
        self._crear_cliente = crear_cliente or _crear_cliente_gemini
        self._cliente: Any | None = None

    def __call__(self, prompt: str) -> str:
        if self._cliente is None:
            self._cliente = self._crear_cliente()

        from config import GENERATION_MODEL, TEMPERATURE
        from google.genai import types

        respuesta = self._cliente.models.generate_content(
            model=GENERATION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=TEMPERATURE),
        )
        texto = getattr(respuesta, "text", None)
        if not isinstance(texto, str) or not texto.strip():
            raise RuntimeError("El modelo no devolvió contenido.")
        return texto


class ModeloEstructurado:
    """Adapta Gemini a la salida de diccionario usada por supervisor y tools."""

    def __init__(self, generar: Generador | None = None):
        self._generar = generar or GeneradorGemini()

    def __call__(self, entrada: object) -> dict[str, Any]:
        return _parsear_objeto(self._generar(_formatear_entrada(entrada)))


class ModeloSintetizador:
    """Adapta Gemini a una respuesta de síntesis textual en español."""

    def __init__(self, generar: Generador | None = None):
        self._generar = generar or GeneradorGemini()

    def __call__(self, estado: Mapping[str, Any]) -> str:
        datos = json.dumps(dict(estado), ensure_ascii=False, default=str)
        prompt = (
            "Resume en español sencillo únicamente la información disponible. "
            "No inventes datos.\n\nResultados del grafo:\n"
            f"{datos}"
        )
        respuesta = self._generar(prompt)
        if not isinstance(respuesta, str) or not respuesta.strip():
            raise ValueError("Respuesta del sintetizador no interpretable.")
        return respuesta


def crear_modelo_supervisor(generar: Generador | None = None) -> ModeloEstructurado:
    """Construye el adaptador estructurado que usará el Supervisor."""
    return ModeloEstructurado(generar=generar)


def crear_modelo_especialista(generar: Generador | None = None) -> ModeloEstructurado:
    """Construye el adaptador estructurado que usarán los especialistas."""
    return ModeloEstructurado(generar=generar)


def crear_modelo_sintetizador(generar: Generador | None = None) -> ModeloSintetizador:
    """Construye el adaptador textual que usará el Sintetizador."""
    return ModeloSintetizador(generar=generar)
