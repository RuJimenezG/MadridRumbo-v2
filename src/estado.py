"""Estado interno y proyección pública del grafo multiagente.

Este módulo no construye el grafo ni inicializa proveedores. Centraliza las
estructuras que más adelante persistirá LangGraph y la forma estable que
consumen los futuros clientes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Annotated, Any, Mapping, TypedDict, TypeVar

from src.supervisor import RESUMENES_DIAGNOSTICO

class EntradaTraza(TypedDict):
    """Entrada pública de auditoría de una invocación de tool."""

    tool: str
    args: dict[str, Any]
    status: str
    preview: str


class PlanPendiente(TypedDict):
    """Plan persistido con sus argumentos privados de replanificación."""

    id: str
    resultado: dict[str, Any]
    args: dict[str, Any]


T = TypeVar("T")


def acumular_listas(anterior: list[T] | None, nuevo: list[T] | None) -> list[T]:
    """Devuelve un reducer no mutable para las colecciones auditables."""
    return list(anterior or []) + list(nuevo or [])


class EstadoGrafo(TypedDict, total=False):
    """Campos persistentes y temporales usados por el futuro StateGraph."""

    mensaje: str
    historial: Annotated[list[dict[str, str]], acumular_listas]
    cola_roles: list[str]
    notas: Annotated[list[str], acumular_listas]
    resultados: Annotated[list[dict[str, Any]], acumular_listas]
    log: Annotated[list[str], acumular_listas]
    traza: Annotated[list[EntradaTraza], acumular_listas]
    planes_pendientes: list[PlanPendiente]
    plan_id_seleccionado: str | None
    plan_aprobado: dict[str, Any] | None
    replanificar_args: dict[str, Any] | None
    replanificar_desde_id: str | None
    decision_hitl: dict[str, Any] | None
    turnos_completados: int
    tools_turno: int
    turno_contabilizado: bool
    limite_turnos: bool
    limite_tools_alcanzado: bool
    respuesta: str
    hitl_pendiente: bool
    done: bool


def crear_estado_inicial(mensaje: str = "") -> EstadoGrafo:
    """Crea un estado aislado, sin compartir colecciones entre conversaciones."""
    return {
        "mensaje": mensaje,
        "historial": [],
        "cola_roles": [],
        "notas": [],
        "resultados": [],
        "log": [],
        "traza": [],
        "planes_pendientes": [],
        "plan_id_seleccionado": None,
        "plan_aprobado": None,
        "replanificar_args": None,
        "replanificar_desde_id": None,
        "decision_hitl": None,
        "turnos_completados": 0,
        "tools_turno": 0,
        "turno_contabilizado": False,
        "limite_turnos": False,
        "limite_tools_alcanzado": False,
        "respuesta": "",
        "hitl_pendiente": False,
        "done": False,
    }


def crear_plan(
    plan_id: str,
    resultado: Mapping[str, Any],
    args: Mapping[str, Any] | None = None,
) -> PlanPendiente:
    """Crea un plan estable y guarda aparte los argumentos necesarios al rechazarlo."""
    if not isinstance(plan_id, str) or not plan_id.strip():
        raise ValueError("El identificador del plan debe ser un texto no vacío.")

    return {
        "id": plan_id,
        "resultado": deepcopy(dict(resultado)),
        "args": deepcopy(dict(args or {})),
    }


def _proyectar_planes(planes: object) -> list[dict[str, Any]]:
    """Elimina argumentos internos antes de devolver los planes al cliente."""
    if not isinstance(planes, list):
        return []

    resultado: list[dict[str, Any]] = []
    for plan in planes:
        if not isinstance(plan, Mapping):
            continue
        plan_id = plan.get("id")
        plan_resultado = plan.get("resultado")
        if not isinstance(plan_id, str) or not isinstance(plan_resultado, Mapping):
            continue
        resultado.append({"id": plan_id, "resultado": deepcopy(dict(plan_resultado))})
    return resultado


def _proyectar_traza(entradas: object) -> list[EntradaTraza]:
    """Normaliza la traza al contrato de cuatro campos sin exponer metadatos internos."""
    if not isinstance(entradas, list):
        return []

    traza: list[EntradaTraza] = []
    for entrada in entradas:
        if not isinstance(entrada, Mapping):
            continue
        args = entrada.get("args")
        traza.append(
            {
                "tool": str(entrada.get("tool", "")),
                "args": deepcopy(dict(args)) if isinstance(args, Mapping) else {},
                "status": str(entrada.get("status", "")),
                "preview": str(entrada.get("preview", "")),
            }
        )
    return traza


def _entrada_diagnostico_supervisor(diagnostico: object) -> str | None:
    """Convierte una categoría permitida en la única entrada pública segura."""
    if not isinstance(diagnostico, Mapping):
        return None
    categoria = diagnostico.get("categoria")
    resumen = RESUMENES_DIAGNOSTICO.get(categoria)
    if not isinstance(categoria, str) or not isinstance(resumen, str):
        return None
    return f"Supervisor: categoria={categoria}; resumen={resumen}"


def proyectar_resultado(
    estado: Mapping[str, Any],
    *,
    diagnostico_supervisor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Devuelve exclusivamente el contrato público que expondrá src.agent."""
    respuesta = estado.get("respuesta", "")
    log = estado.get("log", [])
    log_publico = list(log) if isinstance(log, list) else []
    entrada_diagnostico = _entrada_diagnostico_supervisor(diagnostico_supervisor)
    if entrada_diagnostico:
        log_publico.append(entrada_diagnostico)

    return {
        "respuesta": respuesta if isinstance(respuesta, str) else str(respuesta),
        "plan": _proyectar_planes(estado.get("planes_pendientes", [])),
        "log": log_publico,
        "traza": _proyectar_traza(estado.get("traza", [])),
        "hitl_pendiente": bool(estado.get("hitl_pendiente", False)),
        "done": bool(estado.get("done", False)),
    }
