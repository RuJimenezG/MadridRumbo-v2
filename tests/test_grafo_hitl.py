"""Normalización y pausa HITL de rutas, sin APIs ni reanudación humana."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

import src.agent as agent
from src.graph import (
    configuracion_hilo,
    crear_grafo,
    invocar_grafo,
    normalizar_planes_rutas,
    reanudar_grafo,
)


RUTA_OK = {
    "estado": "ok",
    "origen": {"direccion": "Atocha"},
    "destino": {"direccion": "Sol"},
    "ruta": {"duracion_min": 12, "tramos": [{"modo": "SUBWAY", "linea": "1"}]},
}


def _resultado_rutas(resultado, args=None):
    """Da al normalizador el resultado íntegro y los argumentos de la tool."""
    return {
        "resultados": [
            {
                "especialista": "rutas",
                "tool": "planificar_ruta",
                "status": "ok",
                "resultado": resultado,
                "args": args or {"origen": "Atocha", "destino": "Sol"},
            }
        ]
    }


@pytest.mark.parametrize("resultado", [RUTA_OK, json.dumps(RUTA_OK, ensure_ascii=False)])
def test_normalizador_convierte_resultado_ok_json_o_dict_en_plan(resultado):
    """RF-12 y RF-29: una ruta válida se vuelve un plan persistible con ID."""
    salida = normalizar_planes_rutas(_resultado_rutas(resultado))

    assert salida["hitl_pendiente"] is True
    assert salida["done"] is False
    assert salida["planes_pendientes"] == [
        {
            "id": "ruta-1",
            "resultado": RUTA_OK,
            "args": {"origen": "Atocha", "destino": "Sol"},
        }
    ]


def test_normalizador_asigna_ids_estables_a_varios_planes():
    """RF-47: cada resultado de rutas recibe un identificador independiente y estable."""
    segunda = {
        **RUTA_OK,
        "ruta": {"duracion_min": 20, "tramos": [{"modo": "BUS", "linea": "27"}]},
    }
    estado = {
        "resultados": _resultado_rutas(RUTA_OK)["resultados"]
        + _resultado_rutas(segunda, {"origen": "Atocha", "destino": "Cibeles"})["resultados"]
    }

    salida = normalizar_planes_rutas(estado)

    assert [plan["id"] for plan in salida["planes_pendientes"]] == ["ruta-1", "ruta-2"]
    assert [plan["resultado"]["ruta"]["duracion_min"] for plan in salida["planes_pendientes"]] == [12, 20]
    assert normalizar_planes_rutas({**estado, **salida}) == {}


def _grafo_rutas(resultado):
    """Compila un grafo cuyo especialista de rutas entrega el resultado elegido."""
    return crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        especialistas={"rutas": lambda estado: _resultado_rutas(resultado)},
        modelo_sintetizador=lambda contexto: "Ruta sintetizada para revisión.",
    )


def test_ruta_valida_persiste_respuesta_y_se_pausa_antes_de_aplicarse():
    """RF-29 y RF-30: HITL se interrumpe tras guardar plan, síntesis y done falso."""
    grafo = _grafo_rutas(RUTA_OK)
    salida = invocar_grafo(grafo, {"mensaje": "De Atocha a Sol."}, "hitl-ruta-ok")
    snapshot = grafo.get_state(configuracion_hilo("hitl-ruta-ok"))

    assert salida["hitl_pendiente"] is True
    assert salida["done"] is False
    assert salida["respuesta"] == "Ruta sintetizada para revisión."
    assert salida["planes_pendientes"][0]["id"] == "ruta-1"
    assert snapshot.next == ("pausa_hitl",)


@pytest.mark.parametrize("estado_ruta", ["aclaracion", "ambigua", "sin_ruta", "error_interno"])
def test_resultados_de_rutas_no_aplicables_no_interrumpen(estado_ruta):
    """RF-34: las aclaraciones, ambigüedades y errores terminan sin pedir aprobación."""
    resultado = {"estado": estado_ruta, "texto": "Se necesita más información."}
    grafo = _grafo_rutas(resultado)

    salida = invocar_grafo(grafo, {"mensaje": "Consulta de ruta."}, f"sin-hitl-{estado_ruta}")
    snapshot = grafo.get_state(configuracion_hilo(f"sin-hitl-{estado_ruta}"))

    assert salida.get("planes_pendientes", []) == []
    assert salida["hitl_pendiente"] is False
    assert salida["done"] is True
    assert snapshot.next == ()


def _grafo_varios_planes():
    """Crea dos propuestas para verificar que solo se acepta la elegida."""
    alternativa = {
        **RUTA_OK,
        "ruta": {"duracion_min": 20, "tramos": [{"modo": "BUS", "linea": "27"}]},
    }

    def sintetizar(contexto):
        for nota in contexto["notas"]:
            if nota.startswith("[rutas] Plan aprobado"):
                return nota
        return "Dos rutas pendientes de revisión."

    return crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        especialistas={
            "rutas": lambda estado: {
                "resultados": _resultado_rutas(RUTA_OK)["resultados"]
                + _resultado_rutas(alternativa, {"origen": "Atocha", "destino": "Cibeles"})["resultados"]
            }
        },
        modelo_sintetizador=sintetizar,
    )


def test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido(monkeypatch):
    """RF-31 y RF-47: el selector elige una ruta y el terminal fija done."""
    grafo = _grafo_varios_planes()
    invocar_grafo(grafo, {"mensaje": "Dame alternativas."}, "hitl-aprobar")
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    salida = agent.aprobar_plan({"plan_id_seleccionado": "ruta-2"}, "hitl-aprobar", True)
    snapshot = grafo.get_state(configuracion_hilo("hitl-aprobar"))

    assert salida["done"] is True
    assert salida["hitl_pendiente"] is False
    assert salida["plan"] == []
    assert "ruta-2" in salida["respuesta"]
    assert snapshot.values["plan_aprobado"]["id"] == "ruta-2"
    assert snapshot.values["planes_pendientes"] == []
    assert snapshot.next == ()


def test_varios_planes_exigen_un_selector_y_no_reanudan_el_checkpoint(monkeypatch):
    """RF-47: sin ID concreto no se acepta ninguno ni se modifica la pausa."""
    grafo = _grafo_varios_planes()
    invocar_grafo(grafo, {"mensaje": "Dame alternativas."}, "hitl-sin-selector")
    antes = deepcopy(grafo.get_state(configuracion_hilo("hitl-sin-selector")).values)
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    salida = agent.aprobar_plan({}, "hitl-sin-selector", True)
    despues = grafo.get_state(configuracion_hilo("hitl-sin-selector"))

    assert salida["done"] is False
    assert "identificador" in salida["respuesta"].lower()
    assert despues.values == antes
    assert despues.next == ("pausa_hitl",)


def test_reanudar_grafo_usa_command_con_el_thread_id_persistido():
    """RF-31: la utilidad de bajo nivel continúa exactamente el checkpoint pausado."""
    grafo = _grafo_varios_planes()
    invocar_grafo(grafo, {"mensaje": "Dame alternativas."}, "hitl-command")

    salida = reanudar_grafo(
        grafo,
        {"aprobado": True, "plan_id_seleccionado": "ruta-1"},
        "hitl-command",
    )

    assert salida["done"] is True
    assert salida["plan_aprobado"]["id"] == "ruta-1"


def _grafo_replanificacion(contadores, llamadas_rutas):
    """Crea dos respuestas secuenciales de rutas para probar el rechazo."""
    alternativa = {
        **RUTA_OK,
        "ruta": {"duracion_min": 18, "tramos": [{"modo": "BUS", "linea": "27"}]},
    }
    respuestas = [RUTA_OK, alternativa]

    def supervisor(mensajes):
        contadores["supervisor"] += 1
        return {"roles": ["rutas"]}

    def rutas(estado):
        contadores["rutas"] += 1
        args = estado.get("replanificar_args") or {"origen": "Atocha", "destino": "Sol"}
        llamadas_rutas.append(deepcopy(args))
        return _resultado_rutas(respuestas.pop(0), args)

    def sintetizar(contexto):
        contadores["sintetizador"] += 1
        return "Ruta lista para revisión."

    return crear_grafo(
        modelo_supervisor=supervisor,
        especialistas={"rutas": rutas},
        modelo_sintetizador=sintetizar,
    )


def test_rechazo_descarta_el_plan_y_replanifica_con_los_args_persistidos(monkeypatch):
    """RF-32 y RF-33: rechazo reutiliza los argumentos en el mismo thread_id."""
    contadores = {"supervisor": 0, "rutas": 0, "sintetizador": 0}
    llamadas_rutas = []
    grafo = _grafo_replanificacion(contadores, llamadas_rutas)
    invocar_grafo(grafo, {"mensaje": "De Atocha a Sol."}, "hitl-rechazo")
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    salida = agent.aprobar_plan({"plan_id_seleccionado": "ruta-1"}, "hitl-rechazo", False)
    snapshot = grafo.get_state(configuracion_hilo("hitl-rechazo"))

    assert llamadas_rutas == [
        {"origen": "Atocha", "destino": "Sol"},
        {"origen": "Atocha", "destino": "Sol"},
    ]
    assert contadores["supervisor"] == 1
    assert contadores["rutas"] == 2
    assert salida["done"] is False
    assert salida["hitl_pendiente"] is True
    assert [plan["id"] for plan in salida["plan"]] == ["ruta-2"]
    assert snapshot.next == ("pausa_hitl",)


def test_mensaje_nuevo_con_plan_pendiente_no_ejecuta_nodos_ni_tools(monkeypatch):
    """RF-48 y RF-49: la fachada devuelve el aviso sin reanudar el grafo."""
    contadores = {"supervisor": 0, "rutas": 0, "sintetizador": 0}
    llamadas_rutas = []
    grafo = _grafo_replanificacion(contadores, llamadas_rutas)
    invocar_grafo(grafo, {"mensaje": "De Atocha a Sol."}, "hitl-bloqueado")
    antes = deepcopy(contadores)
    traza_antes = deepcopy(grafo.get_state(configuracion_hilo("hitl-bloqueado")).values["traza"])
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    salida = agent.procesar_turno({}, "Quiero cambiar la ruta.", "hitl-bloqueado")
    despues = grafo.get_state(configuracion_hilo("hitl-bloqueado"))

    assert contadores == antes
    assert llamadas_rutas == [{"origen": "Atocha", "destino": "Sol"}]
    assert salida["hitl_pendiente"] is True
    assert salida["done"] is False
    assert "plan pendiente" in salida["respuesta"].lower()
    assert despues.next == ("pausa_hitl",)
    assert despues.values["traza"] == traza_antes
