"""Estructuras y saneado del registro público efímero de depuración.

Este módulo no conoce el grafo ni el checkpointer: cada fachada creará una
``SesionDepuracion`` para una sola invocación y proyectará sus entradas al
resultado público. Ningún valor entra al registro sin pasar por ``sanear_valor``.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Literal, TypedDict

import config


TipoEntrada = Literal["nodo", "tool", "control"]
ResultadoEntrada = Literal["completado", "fallido", "rechazado"]

TIPOS_PERMITIDOS: frozenset[str] = frozenset({"nodo", "tool", "control"})
RESULTADOS_PERMITIDOS: frozenset[str] = frozenset({"completado", "fallido", "rechazado"})

MARCADOR_OCULTO = "[oculto por seguridad]"
CAMPOS_CREDENCIAL: frozenset[str] = frozenset(
    {
        "api_key",
        "token",
        "secret",
        "password",
        "authorization",
        "cookie",
        "credentials",
    }
)
CAMPOS_CONTENIDO_INTERNO: frozenset[str] = frozenset(
    {
        "prompt",
        "system_prompt",
        "user_prompt",
        "response_body",
        "cuerpo_respuesta",
    }
)


def _campo_ocultable(nombre_campo: str) -> bool:
    """Indica si un nombre de campo identifica contenido que no es publicable."""
    nombre_normalizado = nombre_campo.casefold()
    return nombre_normalizado in CAMPOS_CREDENCIAL | CAMPOS_CONTENIDO_INTERNO


def _resumen_no_serializable(valor: Any) -> dict[str, str]:
    """Resume un valor sin usar ``repr``, que podría revelar información sensible."""
    return {
        "tipo": type(valor).__name__,
        "resumen": "Valor no serializable omitido.",
    }


def _supera_limite_json(valor: Any) -> bool:
    """Mide el valor tras saneado usando una representación JSON estricta."""
    try:
        representacion = json.dumps(valor, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return True
    return len(representacion) > config.LOG_DEPURACION_MAX_CARACTERES


def sanear_valor(valor: Any, nombre_campo: str = "valor") -> Any:
    """Hace publicable un valor de depuración sin exponer secretos ni objetos crudos.

    La función conserva de forma recursiva los valores JSON no sensibles. Los
    secretos, prompts y cuerpos externos se sustituyen antes de serializar; los
    valores que JSON no puede representar se resumen sin recurrir a ``repr``.
    """
    if _campo_ocultable(nombre_campo):
        return MARCADOR_OCULTO

    if isinstance(valor, dict):
        saneado = {
            clave: sanear_valor(elemento, str(clave))
            for clave, elemento in valor.items()
        }
    elif isinstance(valor, list):
        saneado = [sanear_valor(elemento, nombre_campo) for elemento in valor]
    elif isinstance(valor, tuple):
        saneado = [sanear_valor(elemento, nombre_campo) for elemento in valor]
    elif isinstance(valor, (str, int, float, bool)) or valor is None:
        saneado = valor
    else:
        saneado = _resumen_no_serializable(valor)

    if _supera_limite_json(saneado):
        return {
            "omitido": "longitud",
            "campo": nombre_campo,
            "limite": config.LOG_DEPURACION_MAX_CARACTERES,
        }
    return saneado


class EntradaDepuracion(TypedDict):
    """Forma estable de un paso del registro público de depuración."""

    paso: int
    tipo: TipoEntrada
    nodo: str
    entrada: Any
    salida: Any
    resultado: ResultadoEntrada
    detalle: Any | None


class SesionDepuracion:
    """Acumula pasos ordenados para una única llamada pública al grafo."""

    def __init__(self) -> None:
        self._entradas: list[EntradaDepuracion] = []

    @property
    def entradas(self) -> list[EntradaDepuracion]:
        """Devuelve una copia aislada para que un cliente no altere la sesión."""
        return deepcopy(self._entradas)

    def registrar(
        self,
        tipo: TipoEntrada,
        nodo: str,
        entrada: Any,
        salida: Any,
        *,
        resultado: ResultadoEntrada = "completado",
        detalle: Any | None = None,
    ) -> EntradaDepuracion:
        """Añade una entrada válida y consecutiva al registro de esta sesión."""
        if tipo not in TIPOS_PERMITIDOS:
            raise ValueError("tipo de entrada de depuración no permitido")
        if resultado not in RESULTADOS_PERMITIDOS:
            raise ValueError("resultado de entrada de depuración no permitido")
        if not isinstance(nodo, str) or not nodo.strip():
            raise ValueError("nodo de entrada de depuración no válido")
        if resultado == "completado" and detalle is not None:
            raise ValueError("detalle debe ser nulo en una entrada completada")

        registro: EntradaDepuracion = {
            "paso": len(self._entradas) + 1,
            "tipo": tipo,
            "nodo": nodo,
            "entrada": sanear_valor(entrada, "entrada"),
            "salida": sanear_valor(salida, "salida"),
            "resultado": resultado,
            "detalle": sanear_valor(detalle, "detalle") if detalle is not None else None,
        }
        self._entradas.append(registro)
        return deepcopy(registro)
