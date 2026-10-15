"""Tests de la capa de registro de planificar_ruta (spec 004, RF-30 y RF-42). Sin red, RAG ni LLM.

Usan el `ejecutar_tool` y la allowlist reales de `src/tools/__init__.py`; lo externo va con dobles.
"""
import json

import pytest

import config
from src.tools import TOOLS_PERMITIDAS, ejecutar_tool
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import BARCELONA, BERNABEU, Escenario

SECRETO = "CLAVE-SECRETA-XYZ"


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def test_registrada_en_la_allowlist():
    # Registro en el mecanismo existente, y todo lo que el especialista de rutas puede pedir está permitido.
    assert TOOLS_PERMITIDAS["planificar_ruta"] is pr.planificar_ruta_texto
    assert all(t in TOOLS_PERMITIDAS for t in config.TOOLS_POR_ESPECIALISTA["rutas"])


def test_json_con_estado_primero_y_sin_escapar_acentos(esc):
    texto = pr.planificar_ruta_texto(origen="Sol", destino="Bernabéu")
    assert isinstance(texto, str) and texto.startswith('{"estado": "ok"')
    datos = json.loads(texto)
    assert list(datos)[0] == "estado" and datos["ruta"]["duracion_min"] == 22
    assert "«" in texto and "\\u" not in texto          # ensure_ascii=False


@pytest.mark.parametrize("args,faltan", [
    ({}, "el origen y el destino"),
    ({"origen": "Sol"}, "el destino"),
    ({"destino": "Sol"}, "el origen"),
    ({"origen": None, "destino": 5}, "el origen y el destino"),
])
def test_argumentos_ausentes_dan_faltan_datos(esc, args, faltan):
    # Sin origen o sin destino válido no se lanza TypeError: es faltan_datos y no se llama a nada externo.
    datos = json.loads(pr.planificar_ruta_texto(**args))
    assert datos["estado"] == "faltan_datos" and faltan in datos["mensaje"]
    assert esc.orden == []


def test_argumentos_desconocidos_se_ignoran(esc):
    # Un argumento que la tool no declara (p. ej. inventado por el LLM) no la hace fallar ni se usa.
    datos = json.loads(pr.planificar_ruta_texto(origen="Sol", destino="Bernabéu", moneda="USD", hora=1))
    assert datos["estado"] == "ok"
    # Y con argumentos de tipo inesperado tampoco se lanza excepción.
    datos = json.loads(pr.planificar_ruta_texto(origen="Sol", destino="Bernabéu", hora_salida={"a": 1}, titulo=["x"]))
    assert datos["estado"] == "hora_no_interpretable"


def test_traza_refleja_estado(esc):
    # RF-30: cada invocación deja una entrada en la traza y su extracto empieza por el estado del resultado.
    esc.nominatim = [[BARCELONA], [BERNABEU]]
    traza = []
    args = {"origen": "Calle Mayor, Barcelona", "destino": "Bernabéu"}
    resultado = ejecutar_tool("planificar_ruta", args, traza)
    assert len(traza) == 1
    assert traza[0]["tool"] == "planificar_ruta" and traza[0]["args"] == args and traza[0]["status"] == "ok"
    assert traza[0]["preview"].startswith('{"estado": "fuera_cobertura"')
    assert json.loads(resultado)["estado"] == "fuera_cobertura"


def test_error_interno_queda_en_traza(esc, monkeypatch):
    # RF-42: el fallo inesperado queda en la traza. `ejecutar_tool` marca "error" solo si el texto empieza por
    # "ERROR"; error_interno es un fallo controlado (JSON que empieza por {"estado"), así que el status es "ok"
    # y el error se ve en el extracto: {"estado": "error_interno", ...}. No se toca el contrato de ejecutar_tool.
    def falla(*_a, **_k):
        raise RuntimeError(f"fallo interno con clave {SECRETO}")

    monkeypatch.setattr(pr, "consultar_google", falla)
    traza = []
    resultado = ejecutar_tool("planificar_ruta", {"origen": "Sol", "destino": "Bernabéu"}, traza)
    assert len(traza) == 1 and traza[0]["status"] == "ok"
    assert traza[0]["preview"].startswith('{"estado": "error_interno"')
    assert json.loads(resultado)["estado"] == "error_interno"
    assert SECRETO not in resultado and SECRETO not in repr(traza)
    assert esc.cuantas("rag") == 0                      # tras el error no hay más llamadas
