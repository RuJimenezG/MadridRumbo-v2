"""Tests de T24 (spec 004): `opcion_origen` y `opcion_destino` resuelven un extremo ambiguo con el mismo texto,
tomando esa posición de la lista de candidatos (RF-8 se mantiene sin opción). Sin red, RAG ni LLM.
"""
import json

import pytest

from src.agents.rutas import PROMPT_RUTAS
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import ATOCHA, BERNABEU, RETIRO, SOL, Escenario


@pytest.fixture
def esc(monkeypatch):
    e = Escenario(monkeypatch)
    e.nominatim = [[ATOCHA, RETIRO, BERNABEU], [SOL]]   # origen ambiguo con 3 candidatos
    return e


def test_sin_opcion_sigue_siendo_ambigua(esc):
    r = pr.planificar_ruta("Atocha", "Sol")
    assert r["estado"] == "ambigua" and esc.cuantas("google") == 0


def test_opcion_elige_ese_candidato_e_indica_como_corregir(esc):
    r = pr.planificar_ruta("Atocha", "Sol", opcion_origen=2)
    assert r["estado"] == "ok"
    assert r["origen"]["direccion"] == RETIRO["display_name"]
    assert "opción 2" in r["mensaje"] and "origen" in r["mensaje"] and "otra opción" in r["mensaje"]


@pytest.mark.parametrize("opcion", [9, 0, -1, "x", True, None])
def test_opcion_inexistente_usa_la_1(esc, opcion):
    r = pr.planificar_ruta("Atocha", "Sol", opcion_origen=opcion)
    if opcion is None:
        assert r["estado"] == "ambigua"
    else:
        assert r["estado"] == "ok" and r["origen"]["direccion"] == ATOCHA["display_name"]
        assert "opción 1" in r["mensaje"]


def test_opcion_en_destino_y_limites_de_llamadas(esc):
    esc.nominatim = [[SOL], [ATOCHA, RETIRO]]
    r = pr.planificar_ruta("Sol", "Atocha", opcion_destino=2)
    assert r["estado"] == "ok" and r["destino"]["direccion"] == RETIRO["display_name"]
    assert esc.orden == ["nominatim", "nominatim", "google", "rag", "rag"]


def test_opcion_en_extremo_no_ambiguo_se_ignora(esc):
    esc.nominatim = [[SOL], [BERNABEU]]
    r = pr.planificar_ruta("Sol", "Bernabéu", opcion_origen=3)
    assert r["estado"] == "ok" and "opción" not in r["mensaje"]


def test_el_filtro_de_la_allowlist_deja_pasar_las_opciones(esc):
    r = json.loads(pr.planificar_ruta_texto(origen="Atocha", destino="Sol", opcion_origen=2, otra="x"))
    assert r["estado"] == "ok"


def test_prompt_explica_la_aclaracion_con_opcion():
    assert "opcion_origen" in PROMPT_RUTAS and "opcion_destino" in PROMPT_RUTAS
    assert "ORIGINAL" in PROMPT_RUTAS and "opcion 1" in PROMPT_RUTAS
