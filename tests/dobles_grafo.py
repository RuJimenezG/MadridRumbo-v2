"""Dobles reutilizables para el grafo multiagente, sin red ni proveedores."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping


class LLMFalso:
    """Devuelve respuestas prefijadas y conserva los mensajes recibidos."""

    def __init__(self, respuestas: list[Any]):
        self._respuestas = list(respuestas)
        self.llamadas: list[list[dict[str, Any]]] = []

    def __call__(self, mensajes: list[dict[str, Any]]) -> Any:
        self.llamadas.append(deepcopy(mensajes))
        if not self._respuestas:
            raise AssertionError("El LLM falso no tiene más respuestas configuradas.")

        respuesta = self._respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return deepcopy(respuesta)


class SintetizadorFalso:
    """Devuelve síntesis prefijadas y permite simular un fallo controlado."""

    def __init__(self, respuestas: list[Any]):
        self._respuestas = list(respuestas)
        self.llamadas: list[dict[str, Any]] = []

    def __call__(self, estado: Mapping[str, Any]) -> Any:
        self.llamadas.append(deepcopy(dict(estado)))
        if not self._respuestas:
            raise AssertionError("El sintetizador falso no tiene más respuestas configuradas.")

        respuesta = self._respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return deepcopy(respuesta)


class EjecutorFalso:
    """Ejecuta resultados prefijados y escribe la misma traza que una tool real."""

    def __init__(self, resultados: Mapping[str, Any]):
        self.resultados = dict(resultados)
        self.llamadas: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, nombre: str, args: dict[str, Any], traza: list[dict[str, Any]]) -> str:
        args_copia = deepcopy(args or {})
        self.llamadas.append((nombre, args_copia))
        configurado = self.resultados.get(nombre, f"ERROR: tool falsa no configurada: {nombre}")

        if isinstance(configurado, list):
            if not configurado:
                resultado = f"ERROR: tool falsa sin más resultados: {nombre}"
            else:
                resultado = configurado.pop(0)
        elif isinstance(configurado, Callable):
            resultado = configurado(**args_copia)
        else:
            resultado = configurado

        texto = str(resultado)
        traza.append(
            {
                "tool": nombre,
                "args": args_copia,
                "status": "error" if texto.startswith("ERROR") else "ok",
                "preview": texto[:120],
            }
        )
        return texto


class CheckpointerFalso:
    """Almacén mínimo de snapshots aislados para pruebas unitarias sin LangGraph."""

    def __init__(self):
        self._snapshots: dict[str, dict[str, Any]] = {}

    def guardar(self, thread_id: str, estado: Mapping[str, Any]) -> None:
        self._snapshots[thread_id] = deepcopy(dict(estado))

    def recuperar(self, thread_id: str) -> dict[str, Any] | None:
        estado = self._snapshots.get(thread_id)
        return deepcopy(estado) if estado is not None else None
