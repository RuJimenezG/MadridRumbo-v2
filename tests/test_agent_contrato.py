"""Contrato público de ``src.agent`` sin proveedores ni tools reales."""
from __future__ import annotations

from copy import deepcopy
from inspect import signature

import pytest

import src.agent as agent
from src.graph import crear_grafo, recuperar_estado


CLAVES_PUBLICAS = {"respuesta", "plan", "log", "traza", "hitl_pendiente", "done"}


@pytest.fixture
def grafo_falso(monkeypatch):
    """Inyecta un grafo persistente de salida conocida en la fachada perezosa."""
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": []},
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    return grafo


def _comprobar_contrato(resultado):
    """Verifica la forma estable que consumirán los futuros clientes."""
    assert set(resultado) == CLAVES_PUBLICAS
    assert isinstance(resultado["respuesta"], str)
    assert isinstance(resultado["plan"], list)
    assert isinstance(resultado["log"], list)
    assert isinstance(resultado["traza"], list)
    assert isinstance(resultado["hitl_pendiente"], bool)
    assert isinstance(resultado["done"], bool)
    assert all(set(entrada) == {"tool", "args", "status", "preview"} for entrada in resultado["traza"])


def test_fachada_expone_las_dos_firmas_y_las_seis_claves(grafo_falso):
    """RF-23 a RF-28: ambas operaciones tienen el contrato público acordado."""
    assert list(signature(agent.procesar_turno).parameters) == ["estado", "mensaje", "thread_id"]
    assert list(signature(agent.aprobar_plan).parameters) == ["estado", "thread_id", "aprobado"]

    resultado_turno = agent.procesar_turno({}, "Consulta de prueba.", "contrato-turno")
    resultado_aprobacion = agent.aprobar_plan({}, "contrato-turno", True)

    _comprobar_contrato(resultado_turno)
    _comprobar_contrato(resultado_aprobacion)
    assert "No existe un plan pendiente" in resultado_aprobacion["respuesta"]


@pytest.mark.parametrize(
    ("estado", "mensaje", "thread_id", "fragmento"),
    [
        ({}, "Consulta válida.", "", "thread_id"),
        ([], "Consulta válida.", "hilo-invalido", "estado"),
        ({}, "   ", "hilo-vacio", "consulta válida"),
    ],
)
def test_validaciones_de_procesar_turno_no_crean_ni_invocan_grafo(
    monkeypatch, estado, mensaje, thread_id, fragmento
):
    """RF-52, RF-54 y RF-55: los controles cortan sin efectos colaterales."""
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: (_ for _ in ()).throw(AssertionError("no debe ejecutarse")))

    resultado = agent.procesar_turno(estado, mensaje, thread_id)

    _comprobar_contrato(resultado)
    assert fragmento.lower() in resultado["respuesta"].lower()
    assert resultado["done"] is False


def test_estado_vacio_recupera_el_checkpoint_en_lugar_de_sustituirlo(grafo_falso):
    """RF-53: una segunda llamada con estado vacío conserva el contexto del hilo."""
    agent.procesar_turno({}, "Primer mensaje persistido.", "hilo-recuperable")
    resultado = agent.procesar_turno({}, "Segundo mensaje persistido.", "hilo-recuperable")
    recuperado = recuperar_estado(grafo_falso, "hilo-recuperable")

    _comprobar_contrato(resultado)
    assert [entrada["content"] for entrada in recuperado["historial"]] == [
        "Primer mensaje persistido.",
        "Segundo mensaje persistido.",
    ]


def test_aprobacion_sin_snapshot_o_plan_no_modifica_el_checkpoint(grafo_falso):
    """RF-51: la aprobación inválida avisa y no escribe ninguna conversación."""
    sin_snapshot = agent.aprobar_plan({}, "hilo-inexistente", True)
    assert recuperar_estado(grafo_falso, "hilo-inexistente") == {}

    agent.procesar_turno({}, "Turno sin ruta.", "hilo-sin-plan")
    antes = deepcopy(recuperar_estado(grafo_falso, "hilo-sin-plan"))
    sin_plan = agent.aprobar_plan({}, "hilo-sin-plan", True)
    despues = recuperar_estado(grafo_falso, "hilo-sin-plan")

    _comprobar_contrato(sin_snapshot)
    _comprobar_contrato(sin_plan)
    assert "No existe un plan pendiente" in sin_snapshot["respuesta"]
    assert "No existe un plan pendiente" in sin_plan["respuesta"]
    assert despues == antes


def test_validacion_de_aprobacion_no_crea_grafo_con_thread_o_estado_invalidos(monkeypatch):
    """RF-51, RF-52 y RF-54: no hay lectura ni escritura tras una entrada inválida."""
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: (_ for _ in ()).throw(AssertionError("no debe ejecutarse")))

    resultado_thread = agent.aprobar_plan({}, "  ", True)
    resultado_estado = agent.aprobar_plan([], "hilo", True)

    _comprobar_contrato(resultado_thread)
    _comprobar_contrato(resultado_estado)
    assert resultado_thread["done"] is False
    assert resultado_estado["done"] is False


def test_aprobacion_sin_grafo_ni_snapshot_no_inicializa_la_fachada(monkeypatch):
    """RF-51: una aprobación aislada no crea un grafo que no puede reanudar."""
    monkeypatch.setattr(agent, "_GRAFO", None)
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: (_ for _ in ()).throw(AssertionError("no debe crearse")))

    resultado = agent.aprobar_plan({}, "hilo-ausente", True)

    _comprobar_contrato(resultado)
    assert "No existe un plan pendiente" in resultado["respuesta"]
