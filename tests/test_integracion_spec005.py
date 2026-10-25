"""Regresi\u00f3n de extremo a extremo del grafo multiagente, sin red."""
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
    "ruta": {"duracion_min": 12, "tramos": [{"modo": "SUBWAY", "linea": "1"}]},
}


def test_flujo_integrado_rag_rutas_hitl_y_aprobacion(monkeypatch):
    """RF-1, RF-3 y RF-29 a RF-31: encadena, pausa y finaliza al aprobar."""
    ejecutor = EjecutorFalso(
        {
            "rag_ask": "Atocha y Sol est\u00e1n conectadas por la l\u00ednea 1.",
            "planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False),
        }
    )
    modelos = {
        "rag": LLMFalso([
            {"tool": "rag_ask", "args": {"consulta": "conexi\u00f3n Atocha Sol"}},
            {"final": "Hay evidencia sobre la conexi\u00f3n."},
        ]),
        "rutas": LLMFalso([
            {"tool": "planificar_ruta", "args": {"origen": "Atocha", "destino": "Sol"}},
            {"final": "He preparado una ruta para revisi\u00f3n."},
        ]),
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rag", "rutas"]},
        modelos_especialistas=modelos,
        ejecutar=ejecutor,
        modelo_sintetizador=lambda estado: "Ruta preparada para tu aprobaci\u00f3n.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    pendiente = agent.procesar_turno({}, "Dime c\u00f3mo ir de Atocha a Sol.", "integrado-hitl")

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["rag_ask", "planificar_ruta"]
    assert pendiente["hitl_pendiente"] is True
    assert pendiente["done"] is False
    assert pendiente["plan"] == [{"id": "ruta-1", "resultado": RUTA_OK}]

    aprobada = agent.aprobar_plan({"plan_id_seleccionado": "ruta-1"}, "integrado-hitl", True)
    snapshot = grafo.get_state(configuracion_hilo("integrado-hitl"))

    assert aprobada["done"] is True
    assert aprobada["hitl_pendiente"] is False
    assert aprobada["plan"] == []
    assert snapshot.values["plan_aprobado"]["id"] == "ruta-1"


def test_flujo_integrado_limite_tools_conserva_el_resumen(monkeypatch):
    """RF-39 a RF-41 y RF-50: dos nodos agotan un presupuesto compartido."""
    monkeypatch.setattr(config, "MAX_CICLOS_TOOLS", 2)
    ejecutor = EjecutorFalso(
        {"rag_ask": "Evidencia CRTM disponible.", "hora_actual": "Son las 18:00."}
    )
    modelos = {
        "rag": LLMFalso([
            {"tool": "rag_ask", "args": {"consulta": "zona"}},
            {"final": "La evidencia est\u00e1 disponible."},
        ]),
        "auxiliar": LLMFalso([
            {"tool": "hora_actual", "args": {}},
            {"final": "Son las 18:00."},
        ]),
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rag", "auxiliar", "tarifas"]},
        modelos_especialistas=modelos,
        ejecutar=ejecutor,
        modelo_sintetizador=lambda estado: "Esta s\u00edntesis no debe ejecutarse al alcanzar el l\u00edmite.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    salida = agent.procesar_turno({}, "Consulta documental y hora.", "integrado-limite")
    snapshot = grafo.get_state(configuracion_hilo("integrado-limite"))

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["rag_ask", "hora_actual"]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["rag_ask", "hora_actual"]
    assert salida["done"] is True
    assert salida["hitl_pendiente"] is False
    assert "m\u00e1ximo de tools" in salida["respuesta"].lower()
    assert snapshot.values["tools_turno"] == 2
