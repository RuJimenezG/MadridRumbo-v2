"""Fachada pública del grafo multiagente, independiente de CLI y Streamlit."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import config
from src.estado import proyectar_resultado
from src.graph import crear_grafo, invocar_grafo, recuperar_estado, reanudar_grafo


# El grafo se crea al recibir una petición válida para no pedir claves al importarlo.
_GRAFO: Any | None = None
_REFERENCIA_IMAGEN_DEMO = "assets/imagen_demo.jpg"


def _obtener_grafo() -> Any:
    """Devuelve el único grafo del proceso y conserva su checkpointer en memoria."""
    global _GRAFO
    if _GRAFO is None:
        _GRAFO = crear_grafo()
    return _GRAFO


def _resultado_controlado(mensaje: str) -> dict[str, Any]:
    """Construye una respuesta pública sin ejecutar ni modificar el grafo."""
    return {
        "respuesta": mensaje,
        "plan": [],
        "log": [mensaje],
        "traza": [],
        "hitl_pendiente": False,
        # Este falso es protocolario: no es una decisión de finalización del grafo.
        "done": False,
    }


def _validar_thread_id(thread_id: object) -> str | None:
    """Devuelve un mensaje controlado cuando el identificador no permite persistir."""
    if not isinstance(thread_id, str) or not thread_id.strip():
        return "El thread_id debe ser un texto no vacío."
    return None


def _validar_estado(estado: object) -> str | None:
    """Impide que una entrada ajena a un diccionario alcance el checkpointer."""
    if not isinstance(estado, dict):
        return "El estado debe ser un diccionario."
    return None


def _imagen_demo_valida_para(mensaje: object) -> bool:
    """Comprueba localmente la demo solo tras su referencia literal aprobada."""
    if not isinstance(mensaje, str) or _REFERENCIA_IMAGEN_DEMO not in mensaje:
        return False

    try:
        directorio = Path(config.IMAGENES_DIR).resolve()
        nombre_demo = config.IMAGEN_DEMO
        if not isinstance(nombre_demo, str):
            return False
        archivo = (directorio / nombre_demo).resolve()
        if archivo == directorio or directorio not in archivo.parents:
            return False
        if not archivo.is_file() or archivo.suffix.lower() not in config.EXTENSIONES_IMAGEN:
            return False
        return archivo.stat().st_size <= config.IMAGEN_MAX_MB * 1024 * 1024
    except (OSError, TypeError, ValueError):
        return False


def _invocar_turno_con_diagnostico(
    grafo: Any,
    estado: Mapping[str, Any],
    thread_id: str,
) -> dict[str, Any]:
    """Proyecta el diagnóstico efímero sin incorporarlo al checkpoint del grafo."""
    contexto = {
        "diagnostico_supervisor": None,
        "correcciones_tarifas": 0,
        "imagen_valida": _imagen_demo_valida_para(estado.get("mensaje")),
    }
    estado_final = invocar_grafo(grafo, estado, thread_id, contexto=contexto)
    return proyectar_resultado(
        estado_final,
        diagnostico_supervisor=contexto["diagnostico_supervisor"],
        correcciones_tarifas=contexto["correcciones_tarifas"],
    )


def procesar_turno(estado: dict[str, Any], mensaje: str, thread_id: str) -> dict[str, Any]:
    """Procesa un mensaje válido y proyecta exclusivamente las seis claves públicas."""
    error_thread = _validar_thread_id(thread_id)
    if error_thread:
        return _resultado_controlado(error_thread)

    error_estado = _validar_estado(estado)
    if error_estado:
        return _resultado_controlado(error_estado)

    if not isinstance(mensaje, str) or not mensaje.strip():
        return _resultado_controlado("Escribe una consulta válida para MadridRumbo.")

    grafo = _obtener_grafo()
    # El checkpoint es la fuente de verdad; los datos del cliente no lo sustituyen.
    snapshot = recuperar_estado(grafo, thread_id)
    if snapshot.get("hitl_pendiente"):
        resultado = proyectar_resultado(snapshot)
        resultado["respuesta"] = "Hay un plan pendiente en esta conversación. Apruébalo o recházalo antes de enviar otra consulta."
        resultado["log"] = list(resultado["log"]) + ["Se bloqueó un mensaje nuevo mientras había un plan pendiente."]
        resultado["hitl_pendiente"] = True
        resultado["done"] = False
        return resultado

    turnos = snapshot.get("turnos_completados", 0)
    if isinstance(turnos, int) and turnos >= config.MAX_TURNOS_CONVERSACION:
        return _invocar_turno_con_diagnostico(
            grafo,
            {"mensaje": mensaje, "limite_turnos": True},
            thread_id,
        )

    return _invocar_turno_con_diagnostico(
        grafo,
        {
            "mensaje": mensaje,
            "tools_turno": 0,
            "limite_tools_alcanzado": False,
            "turno_contabilizado": False,
            "limite_turnos": False,
        },
        thread_id,
    )


def aprobar_plan(estado: dict[str, Any], thread_id: str, aprobado: bool) -> dict[str, Any]:
    """Aprueba el plan seleccionado reanudando el checkpoint HITL con Command."""
    error_thread = _validar_thread_id(thread_id)
    if error_thread:
        return _resultado_controlado(error_thread)

    error_estado = _validar_estado(estado)
    if error_estado:
        return _resultado_controlado(error_estado)

    # Sin grafo creado en este proceso no puede existir un checkpoint pendiente.
    if _GRAFO is None:
        return _resultado_controlado("No existe un plan pendiente en esta conversación.")

    snapshot = recuperar_estado(_GRAFO, thread_id)
    planes = snapshot.get("planes_pendientes", []) if isinstance(snapshot, Mapping) else []
    if not snapshot or not isinstance(planes, list) or not planes:
        return _resultado_controlado("No existe un plan pendiente en esta conversación.")

    ids = [plan.get("id") for plan in planes if isinstance(plan, Mapping) and isinstance(plan.get("id"), str)]
    seleccionado = estado.get("plan_id_seleccionado")
    if seleccionado is None and len(ids) == 1:
        seleccionado = ids[0]
    if not isinstance(seleccionado, str) or seleccionado not in ids:
        return _resultado_controlado("Indica el identificador del plan pendiente que quieres aprobar.")
    estado_final = reanudar_grafo(
        _GRAFO,
        {"aprobado": aprobado is True, "plan_id_seleccionado": seleccionado},
        thread_id,
    )
    return proyectar_resultado(estado_final)
