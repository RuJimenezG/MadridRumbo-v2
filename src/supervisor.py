"""Decisión segura del supervisor para la futura ejecución con LangGraph.

El supervisor admite solamente una estructura con una lista de roles. La
validación queda en Python para que una respuesta libre, inválida o fallida del
modelo no pueda activar una arista que el grafo no haya declarado.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from src.modelos import crear_modelo_supervisor
from src.supervisor_reglas import MENSAJE_REFORMULACION, elegir_roles_por_reglas


# Los nombres coinciden con los nodos que declarará el grafo en T12.
ROLES_ADMITIDOS = ("rag", "horarios", "rutas", "auxiliar", "tarifas")
MAX_ROLES_POR_DECISION = 20

ModeloSupervisor = Callable[[list[dict[str, str]]], Mapping[str, Any] | Any]


class DecisionInvalida(ValueError):
    """Indica que una respuesta del modelo no puede convertirse en una cola segura."""


def _mensajes_para_modelo(estado: Mapping[str, Any]) -> list[dict[str, str]]:
    """Construye una entrada mínima sin mutar el historial persistido."""
    mensajes: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Decide los especialistas necesarios. Responde solo con un objeto "
                "estructurado {'roles': [...]} usando rag, horarios, rutas, auxiliar "
                "o tarifas. Usa una lista vacía para finalizar."
            ),
        }
    ]
    historial = estado.get("historial", [])
    if isinstance(historial, list):
        for entrada in historial:
            if not isinstance(entrada, Mapping):
                continue
            rol = entrada.get("role")
            contenido = entrada.get("content")
            if isinstance(rol, str) and isinstance(contenido, str):
                mensajes.append({"role": rol, "content": contenido})

    mensaje = estado.get("mensaje", "")
    mensajes.append({"role": "user", "content": mensaje if isinstance(mensaje, str) else ""})
    return mensajes


def validar_decision(respuesta: object) -> list[str]:
    """Convierte una respuesta estructurada en una cola finita y permitida."""
    if not isinstance(respuesta, Mapping):
        raise DecisionInvalida("La decisión del supervisor no es un objeto.")

    roles = respuesta.get("roles")
    if not isinstance(roles, list):
        raise DecisionInvalida("La decisión del supervisor debe incluir una lista de roles.")
    if len(roles) > MAX_ROLES_POR_DECISION:
        raise DecisionInvalida("La decisión del supervisor supera el máximo de roles.")
    if any(not isinstance(rol, str) or rol not in ROLES_ADMITIDOS for rol in roles):
        raise DecisionInvalida("La decisión del supervisor incluye un rol no permitido.")

    # Una lista vacía representa finish; las repeticiones son válidas por diseño.
    return list(roles)


def decidir_roles(
    estado: Mapping[str, Any],
    modelo: ModeloSupervisor | None = None,
) -> tuple[list[str], bool]:
    """Devuelve la cola y si fue necesario el fallback determinista."""
    mensaje = estado.get("mensaje", "")
    texto = mensaje if isinstance(mensaje, str) else ""
    try:
        modelo_efectivo = modelo or crear_modelo_supervisor()
        return validar_decision(modelo_efectivo(_mensajes_para_modelo(estado))), False
    except Exception:
        return elegir_roles_por_reglas(texto), True


def nodo_supervisor(
    estado: Mapping[str, Any],
    modelo: ModeloSupervisor | None = None,
) -> dict[str, Any]:
    """Prepara la cola del turno o solicita una reformulación si no hay ámbito."""
    roles, uso_fallback = decidir_roles(estado, modelo=modelo)
    actualizacion: dict[str, Any] = {"cola_roles": roles}

    if uso_fallback:
        actualizacion["log"] = ["Supervisor: se aplicó el fallback determinista."]
        if not roles:
            actualizacion["respuesta"] = MENSAJE_REFORMULACION
    else:
        actualizacion["log"] = ["Supervisor: decisión estructurada válida."]

    return actualizacion
