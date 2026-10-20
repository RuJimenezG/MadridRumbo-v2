"""Tests de T22 (spec 004): la pregunta de zona al RAG usa el municipio de origen y destino (RF-54) y solo se
entrega ruta si cada extremo está verificado en la Comunidad de Madrid (RF-55). Sin red, RAG ni LLM.
"""
import pytest

import config
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import BERNABEU, SOL, Escenario, nominatim, ZONA


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def sin_campos(lugar, *campos):
    """Copia de un resultado de Nominatim sin esos campos de `address`."""
    return {**lugar, "address": {k: v for k, v in lugar["address"].items() if k not in campos}}


# --- RF-54: municipios en la pregunta de zona ---

def test_pregunta_de_zona_usa_municipio_de_origen_y_destino(esc):
    esc.nominatim = [[SOL], [nominatim("Plaza Mayor, Alcalá de Henares", 40.482, -3.363, "Alcalá de Henares")]]
    r = pr.planificar_ruta("Sol", "Alcalá")
    assert r["estado"] == "ok"
    assert esc.preguntas[0] == config.PREGUNTA_ZONA.format(origen="Madrid", destino="Alcalá de Henares")
    # Las paradas de Google ("Sol", "Plaza de Castilla") ya no entran en ninguna pregunta.
    assert all("Plaza de Castilla" not in p for p in esc.preguntas)
    assert esc.preguntas[1] == config.PREGUNTA_PRECIO.format(titulo="billete sencillo", zona=ZONA)


def test_zona_antes_que_precio_y_maximo_2_llamadas_con_municipios(esc):
    pr.planificar_ruta("Sol", "Bernabéu")
    assert esc.orden == ["nominatim", "nominatim", "google", "rag", "rag"]
    assert "zona tarifaria" in esc.preguntas[0] and "precio" in esc.preguntas[1]


def test_google_caido_usa_los_mismos_municipios(esc):
    esc.google = TimeoutError("t")
    esc.nominatim = [[SOL], [nominatim("Plaza Mayor, Getafe", 40.305, -3.73, "Getafe")]]
    pr.planificar_ruta("Sol", "Getafe")
    assert esc.preguntas[0] == config.PREGUNTA_ZONA.format(origen="Madrid", destino="Getafe")


# --- RF-55: sin municipio o sin Comunidad de Madrid verificada no hay ruta ---

@pytest.mark.parametrize("candidato, esperado", [
    ({"municipio": "Madrid", "iso": "ES-MD", "region": None}, True),
    ({"municipio": "Madrid", "iso": None, "region": "Comunidad de Madrid"}, True),
    ({"municipio": "Madrid", "iso": "ES-MD", "region": "Comunidad de Madrid"}, True),
    ({"municipio": "Madrid", "iso": "ES-MD", "region": "Madrid, Comunidade"}, True),     # el ISO no depende del idioma
    ({"municipio": "Illescas", "iso": "ES-CM", "region": "Castilla-La Mancha"}, False),
    ({"municipio": "Madrid", "iso": None, "region": None}, False),
    ({"municipio": None, "iso": "ES-MD", "region": "Comunidad de Madrid"}, False),
    ({"municipio": "  ", "iso": "ES-MD", "region": None}, False),
    ({"iso": "ES-MD"}, False),
])
def test_verificar_candidato(candidato, esperado):
    assert pr.verificar_candidato(candidato) is esperado


def test_geocodificar_extrae_region_e_iso(monkeypatch):
    lugar = {**SOL, "address": {"city": "Madrid", "state": "Comunidad de Madrid", "ISO3166-2-lvl4": "ES-MD"}}
    monkeypatch.setattr(pr, "_http_json", lambda *a, **k: [lugar, sin_campos(SOL, "ISO3166-2-lvl4")])
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    c = pr.geocodificar("Sol")["candidatos"]
    assert (c[0]["region"], c[0]["iso"]) == ("Comunidad de Madrid", "ES-MD")
    assert (c[1]["region"], c[1]["iso"]) == (None, None)


@pytest.mark.parametrize("rol, nominatim_respuestas", [
    ("origen", [[sin_campos(SOL, "city")], [BERNABEU]]),
    ("destino", [[SOL], [sin_campos(BERNABEU, "city")]]),
    ("origen", [[nominatim("Illescas", 40.12, -3.84, "Illescas", iso="ES-CM")], [BERNABEU]]),
    ("destino", [[SOL], [sin_campos(BERNABEU, "ISO3166-2-lvl4")]]),
])
def test_extremo_no_verificado_no_entrega_ruta(esc, rol, nominatim_respuestas):
    esc.nominatim = nominatim_respuestas
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "direccion_no_encontrada" and r["ruta"] is None
    assert f"dirección de {rol}" in r["mensaje"] and "No se pudo verificar" in r["mensaje"]
    assert "Comunidad de Madrid" in r["mensaje"]
    assert esc.orden == ["nominatim", "nominatim"]              # ni Google ni RAG
    assert r["zona"]["estado"] == r["precio"]["estado"] == "omitida"


def test_ambos_extremos_no_verificados_se_listan_los_dos(esc):
    esc.nominatim = [[sin_campos(SOL, "city")], [sin_campos(BERNABEU, "city")]]
    m = pr.planificar_ruta("Sol", "Bernabéu")["mensaje"]
    assert "dirección de origen" in m and "dirección de destino" in m


def test_la_verificacion_va_despues_de_ambito_y_ambiguedad(esc):
    # Un extremo fuera de cobertura sigue dando fuera_cobertura (RF-4), aunque el otro no esté verificado.
    from tests.dobles_ruta import BARCELONA
    esc.nominatim = [[BARCELONA], [sin_campos(BERNABEU, "city")]]
    assert pr.planificar_ruta("Barcelona", "Bernabéu")["estado"] == "fuera_cobertura"
