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


def test_procesar_turno_inicializa_el_contexto_sin_imagen_valida(monkeypatch):
    """RF-8 y RF-17: la fachada no hereda ni acepta contexto visual público."""
    grafo = object()
    contextos = []

    monkeypatch.setattr(agent, "_obtener_grafo", lambda: grafo)
    monkeypatch.setattr(agent, "recuperar_estado", lambda recibido, hilo: {})

    def invocar(recibido, estado, hilo, *, contexto):
        assert recibido is grafo
        contextos.append(dict(contexto))
        return {
            "respuesta": "Resumen controlado.",
            "planes_pendientes": [],
            "log": [],
            "traza": [],
            "hitl_pendiente": False,
            "done": True,
        }

    monkeypatch.setattr(agent, "invocar_grafo", invocar)

    resultado = agent.procesar_turno(
        {"imagen_valida": True},
        "¿Cuánto cuesta el Combinado Metro?",
        "hilo-contexto-inicial",
    )

    _comprobar_contrato(resultado)
    assert contextos == [
        {
            "diagnostico_supervisor": None,
            "correcciones_tarifas": 0,
            "imagen_valida": False,
        }
    ]
    assert "imagen_valida" not in resultado


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


def test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo(grafo_falso):
    """RF-10 a RF-16 y RF-25: solo el resultado actual recibe el diagnóstico."""
    primero = agent.procesar_turno({}, "Primer turno.", "hilo-diagnostico")
    segundo = agent.procesar_turno({}, "Segundo turno.", "hilo-diagnostico")
    snapshot = recuperar_estado(grafo_falso, "hilo-diagnostico")
    esperado = "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada."

    _comprobar_contrato(primero)
    _comprobar_contrato(segundo)
    assert primero["log"] == [esperado]
    assert segundo["log"] == [esperado]
    assert snapshot["log"] == []
    assert "diagnostico_supervisor" not in snapshot
    assert all(esperado not in entrada["content"] for entrada in snapshot["historial"])


def test_correccion_semantica_se_expone_solo_en_el_turno_que_la_origina(monkeypatch):
    """RF-14 a RF-19: el indicador es público, seguro y efímero."""
    def supervisor(mensajes):
        return {"roles": ["tarifas"]} if "Combinado Metro" in mensajes[-1]["content"] else {"roles": []}

    grafo = crear_grafo(
        modelo_supervisor=supervisor,
        especialistas={"rag": lambda estado: {}},
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    primero = agent.procesar_turno(
        {},
        "¿Cuánto cuesta el Combinado Metro?",
        "hilo-correccion-semantica",
    )
    segundo = agent.procesar_turno(
        {},
        "Consulta posterior sin tarifas.",
        "hilo-correccion-semantica",
    )
    snapshot = recuperar_estado(grafo, "hilo-correccion-semantica")

    _comprobar_contrato(primero)
    _comprobar_contrato(segundo)
    assert primero["log"] == [
        "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada.",
        "Supervisor: correccion_semantica=aplicada; resumen=Se redirigieron 1 derivaciones incompatibles de tarifas a rag.",
    ]
    assert segundo["log"] == [
        "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada."
    ]
    assert "correccion_semantica" not in str(snapshot)
    assert "correcciones_tarifas" not in snapshot
    assert "diagnostico_supervisor" not in snapshot
    assert "correccion_semantica" not in str(snapshot["historial"])
    assert "correccion_semantica" not in str(primero["traza"])


def test_reanudacion_hitl_no_reutiliza_correccion_semantica(monkeypatch):
    """RF-15 y RF-17: la reanudación no recupera el contexto de otro turno."""
    ruta = {
        "estado": "ok",
        "origen": {"direccion": "Atocha"},
        "destino": {"direccion": "Sol"},
        "ruta": {"duracion_min": 12, "tramos": []},
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["tarifas", "rutas"]},
        especialistas={
            "rag": lambda estado: {},
            "rutas": lambda estado: {
                "resultados": [
                    {
                        "especialista": "rutas",
                        "tool": "planificar_ruta",
                        "status": "ok",
                        "resultado": ruta,
                        "args": {"origen": "Atocha", "destino": "Sol"},
                    }
                ]
            },
        },
        modelo_sintetizador=lambda contexto: "Ruta lista para revisión.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    inicial = agent.procesar_turno(
        {},
        "¿Cuánto cuesta ir de Atocha a Sol con Combinado Metro?",
        "hilo-correccion-hitl",
    )
    reanudado = agent.aprobar_plan(
        {"plan_id_seleccionado": inicial["plan"][0]["id"]},
        "hilo-correccion-hitl",
        True,
    )
    snapshot = recuperar_estado(grafo, "hilo-correccion-hitl")

    assert "correccion_semantica=aplicada" in "\n".join(inicial["log"])
    assert reanudado["log"] == []
    assert "correccion_semantica" not in str(snapshot)
    assert "correcciones_tarifas" not in snapshot


def test_fallback_publico_solo_expone_categoria_y_resumen_canonicos(monkeypatch):
    """RF-10 a RF-14: ni el JSON crudo ni datos internos llegan al contrato público."""
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: "RESPUESTA_CRUDA_TOKEN_DE_PRUEBA",
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    resultado = agent.procesar_turno({}, "¿Qué hora es?", "hilo-fallback-publico")
    snapshot = recuperar_estado(grafo, "hilo-fallback-publico")

    _comprobar_contrato(resultado)
    assert resultado["log"] == [
        "Supervisor: categoria=json_invalido; resumen=La decisión no contiene JSON válido; se aplicó el fallback."
    ]
    assert "RESPUESTA_CRUDA_TOKEN_DE_PRUEBA" not in str(resultado)
    assert snapshot["log"] == []
    assert "diagnostico_supervisor" not in snapshot


def test_reanudacion_hitl_no_reproyecta_el_diagnostico_del_turno_inicial(monkeypatch):
    """RF-25: aprobar un plan no reutiliza la categoría del Supervisor anterior."""
    ruta = {
        "estado": "ok",
        "origen": {"direccion": "Atocha"},
        "destino": {"direccion": "Sol"},
        "ruta": {"duracion_min": 12, "tramos": []},
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        especialistas={
            "rutas": lambda estado: {
                "resultados": [
                    {
                        "especialista": "rutas",
                        "tool": "planificar_ruta",
                        "status": "ok",
                        "resultado": ruta,
                        "args": {"origen": "Atocha", "destino": "Sol"},
                    }
                ]
            }
        },
        modelo_sintetizador=lambda contexto: "Ruta lista para revisión.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    inicial = agent.procesar_turno({}, "De Atocha a Sol.", "hilo-diagnostico-hitl")
    reanudado = agent.aprobar_plan(
        {"plan_id_seleccionado": inicial["plan"][0]["id"]},
        "hilo-diagnostico-hitl",
        True,
    )
    snapshot = recuperar_estado(grafo, "hilo-diagnostico-hitl")

    assert inicial["log"] == [
        "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada."
    ]
    assert reanudado["log"] == []
    assert "diagnostico_supervisor" not in snapshot


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
