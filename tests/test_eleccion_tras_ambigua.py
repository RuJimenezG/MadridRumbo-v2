"""Spec 010, T16 (RF-45 y RF-46): tras una ruta ambigua, una respuesta solo con números va a `rutas`, no a la calculadora.

Caso real: «2 y 2» tras las opciones de «Sol» fue a `calculadora` y la ruta volvió a salir ambigua. Sin LLM ni red.
"""
import json

import pytest

from src.agents.rutas import nodo_rutas
from src.supervisor import decidir_decision_supervisor
from src.supervisor_reglas import eleccion_tras_ambigua, interpretar_eleccion
from tests.dobles_grafo import EjecutorFalso, LLMFalso

ARGS = {"origen": "Plaza de Cataluña", "destino": "Sol", "titulo": "abono joven"}


def ambigua(origen=False, destino=True):
    """Resultado `ambigua` de planificar_ruta con candidatos en los extremos indicados."""
    opciones = [{"direccion": "Uno"}, {"direccion": "Dos"}]
    return json.dumps({"estado": "ambigua", "candidatos": {"origen": opciones if origen else [],
                                                           "destino": opciones if destino else []}})


def estado(mensaje, resultado=None, turno=1, args=None):
    """Estado del turno 2: el historial ya incluye el mensaje actual (lo añade `_registrar_mensaje`)."""
    historial = [{"role": "user", "content": "¿Cómo voy de Plaza de Cataluña a Sol?"},
                 {"role": "user", "content": mensaje}]
    entrada = {"especialista": "rutas", "tool": "planificar_ruta", "status": "ok",
               "resultado": resultado or ambigua(), "args": dict(args or ARGS)}
    if turno is not None:
        entrada["turno"] = turno
    return {"mensaje": mensaje, "historial": historial, "resultados": [entrada], "notas": [], "traza": []}


@pytest.mark.parametrize("mensaje, esperado", [
    ("2 y 2", {"origen": 2, "destino": 2, "sueltos": []}),
    ("3 y 1", {"origen": 3, "destino": 1, "sueltos": []}),
    ("1", {"origen": None, "destino": None, "sueltos": [1]}),
    ("la 2 y la 1", {"origen": 2, "destino": 1, "sueltos": []}),
    ("origen 2, destino 1", {"origen": 2, "destino": 1, "sueltos": []}),
    ("destino 1", {"origen": None, "destino": 1, "sueltos": []}),
    ("La opción 2.", {"origen": None, "destino": None, "sueltos": [2]}),
])
def test_interpretar_eleccion(mensaje, esperado):
    assert interpretar_eleccion(mensaje) == esperado


@pytest.mark.parametrize("mensaje", ["2+2", "cuánto es 2 y 2", "suma 2 y 2", "1 2 3", "", "Sol", None, 0])
def test_lo_que_no_es_solo_una_eleccion_no_se_interpreta(mensaje):
    assert interpretar_eleccion(mensaje) is None


def test_dos_numeros_van_a_origen_y_destino():
    args = eleccion_tras_ambigua(estado("2 y 2"))
    assert args == {**ARGS, "opcion_origen": 2, "opcion_destino": 2}


def test_un_numero_va_al_extremo_ambiguo():
    assert eleccion_tras_ambigua(estado("1"))["opcion_destino"] == 1
    a = eleccion_tras_ambigua(estado("2", ambigua(origen=True, destino=False)))
    assert a["opcion_origen"] == 2 and "opcion_destino" not in a


def test_un_numero_con_los_dos_extremos_ambiguos_no_se_interpreta():
    assert eleccion_tras_ambigua(estado("1", ambigua(origen=True, destino=True))) is None


def test_se_quitan_las_marcas_de_la_capa_2_y_opciones_anteriores():
    previos = {**ARGS, "opcion_origen": 3, "probable_destino": True, "texto_alternativo_destino": "x"}
    assert eleccion_tras_ambigua(estado("destino 1", args=previos)) == {**ARGS, "opcion_destino": 1}


@pytest.mark.parametrize("caso", ["ok", "turno_viejo", "sin_resultados", "otra_tool"])
def test_sin_ambigua_del_turno_anterior_no_hay_eleccion(caso):
    if caso == "ok":
        e = estado("2 y 2", json.dumps({"estado": "ok"}))
    elif caso == "turno_viejo":
        e = estado("2 y 2", turno=0)
    elif caso == "sin_resultados":
        e = {**estado("2 y 2"), "resultados": []}
    else:
        e = estado("2 y 2")
        e["resultados"][0]["tool"] = "calculadora"
    assert eleccion_tras_ambigua(e) is None


def test_sin_marca_de_turno_se_acepta():
    assert eleccion_tras_ambigua(estado("1", turno=None)) is not None


def test_supervisor_encola_solo_rutas_sin_llamar_al_llm():
    llm = LLMFalso([])          # cualquier llamada fallaría: no tiene respuestas
    decision = decidir_decision_supervisor(estado("2 y 2"), modelo=llm)
    assert decision.roles == ["rutas"] and not decision.uso_fallback and llm.llamadas == []


def test_sin_ambigua_previa_el_supervisor_decide_como_siempre():
    llm = LLMFalso([{"roles": ["auxiliar"]}])
    e = estado("2 y 2", json.dumps({"estado": "ok"}))
    assert decidir_decision_supervisor(e, modelo=llm).roles == ["auxiliar"]


def test_rutas_repite_la_llamada_con_las_opciones_sin_llm():
    llm = LLMFalso([])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps({"estado": "ok"})})
    salida = nodo_rutas(estado("la 2 y la 1"), llm, ejecutor)
    assert ejecutor.llamadas == [("planificar_ruta", {**ARGS, "opcion_origen": 2, "opcion_destino": 1})]
    assert llm.llamadas == []
    assert salida["resultados"][-1]["args"]["opcion_destino"] == 1
