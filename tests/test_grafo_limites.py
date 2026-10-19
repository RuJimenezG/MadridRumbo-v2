"""Límites transversales de turnos y tools del grafo, sin APIs externas."""
from __future__ import annotations

import json

import config
import src.agent as agent
from src.graph import configuracion_hilo, crear_grafo
from tests.dobles_grafo import EjecutorFalso, LLMFalso


RUTA_OK = {
    "estado": "ok",
    "origen": {"direccion": "Atocha"},
    "destino": {"direccion": "Sol"},
    "ruta": {"duracion_min": 12, "tramos": []},
}


def test_limite_turnos_devuelve_resumen_sin_ejecutar_especialistas(monkeypatch):
    """RF-38, RF-40 y RF-41: tras el tope solo corre el terminal del grafo."""
    monkeypatch.setattr(config, "MAX_TURNOS_CONVERSACION", 1)
    llamadas = {"supervisor": 0, "sintetizador": 0}

    def supervisor(mensajes):
        llamadas["supervisor"] += 1
        return {"roles": []}

    def sintetizar(contexto):
        llamadas["sintetizador"] += 1
        return "Resumen del primer turno."

    grafo = crear_grafo(modelo_supervisor=supervisor, modelo_sintetizador=sintetizar)
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    primero = agent.procesar_turno({}, "Primer turno.", "limite-turnos")
    antes = dict(llamadas)
    segundo = agent.procesar_turno({}, "Segundo turno.", "limite-turnos")
    snapshot = grafo.get_state(configuracion_hilo("limite-turnos"))

    assert primero["done"] is True
    assert llamadas == antes
    assert segundo["done"] is True
    assert "máximo de turnos" in segundo["respuesta"].lower()
    assert snapshot.values["turnos_completados"] == 1


def test_presupuesto_tools_es_compartido_por_los_especialistas(monkeypatch):
    """RF-39 y RF-50: el segundo nodo no ejecuta una tool tras agotar el cupo."""
    monkeypatch.setattr(config, "MAX_CICLOS_TOOLS", 1)
    ejecutor = EjecutorFalso({"rag_ask": "Evidencia CRTM.", "hora_actual": "Son las 18:00."})
    modelos = {
        "rag": LLMFalso([
            {"tool": "rag_ask", "args": {"consulta": "zona"}},
            {"final": "La evidencia está disponible."},
        ]),
        "auxiliar": LLMFalso([
            {"tool": "hora_actual", "args": {}},
            {"final": "Son las 18:00."},
        ]),
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rag", "auxiliar"]},
        modelos_especialistas=modelos,
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Síntesis que no debe ejecutarse al alcanzar el límite.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    salida = agent.procesar_turno({}, "Consulta documental y hora.", "limite-tools")
    snapshot = grafo.get_state(configuracion_hilo("limite-tools"))

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["rag_ask"]
    assert salida["done"] is True
    assert "máximo de tools" in salida["respuesta"].lower()
    assert snapshot.values["tools_turno"] == 1


def test_presupuesto_de_tools_persiste_al_rechazar_un_plan(monkeypatch):
    """RF-50: el rechazo conserva el presupuesto y no permite una tercera llamada."""
    monkeypatch.setattr(config, "MAX_CICLOS_TOOLS", 2)
    ejecutor = EjecutorFalso({"planificar_ruta": [json.dumps(RUTA_OK), json.dumps(RUTA_OK)]})
    rutas = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Atocha", "destino": "Sol"}},
        {"final": "Ruta propuesta."},
    ])
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        modelos_especialistas={"rutas": rutas},
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Ruta para revisión.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    inicial = agent.procesar_turno({}, "De Atocha a Sol.", "limite-rechazo")
    salida = agent.aprobar_plan({"plan_id_seleccionado": inicial["plan"][0]["id"]}, "limite-rechazo", False)
    snapshot = grafo.get_state(configuracion_hilo("limite-rechazo"))

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["planificar_ruta", "planificar_ruta"]
    assert salida["done"] is True
    assert salida["hitl_pendiente"] is False
    assert "máximo de tools" in salida["respuesta"].lower()
    assert snapshot.values["tools_turno"] == 2
