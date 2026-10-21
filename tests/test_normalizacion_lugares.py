"""Tests de T1 (spec 010, RF-1 a RF-3): prefijos de estación quitados antes de enviar el texto a Nominatim. Sin red."""
from urllib.parse import parse_qs, urlparse

import pytest

from src.tools import planificar_ruta as pr
from tests.dobles_ruta import BERNABEU, SOL, Escenario


def q_enviada(monkeypatch, texto):
    """Geocodifica `texto` con un doble de `_http_json` y devuelve el `q` que recibiría Nominatim y las peticiones."""
    urls = []

    def http_json(url, *, headers=None, body=None, timeout=10):
        urls.append(url)
        return []

    monkeypatch.setattr(pr, "_http_json", http_json)
    monkeypatch.setattr(pr, "_ultima_peticion_nominatim", None)
    pr.geocodificar(texto)
    assert len(urls) == 1                                   # una llamada por texto, sin extras
    return parse_qs(urlparse(urls[0]).query)["q"][0]


@pytest.mark.parametrize("texto, esperado", [
    ("Metro Legazpi", "Legazpi"),
    ("metro legazpi", "legazpi"),
    ("METRO LEGAZPI", "LEGAZPI"),
    ("Estación de metro Concha Espina", "Concha Espina"),
    ("ESTACIÓN DE METRO Concha Espina", "Concha Espina"),
    ("estacion de metro Concha Espina", "Concha Espina"),    # sin tilde
    ("Estación de Atocha", "Atocha"),
    ("Parada de Sol", "Sol"),
    ("parada de autobús Sol", "autobús Sol"),
    ("  Metro:  Legazpi, Madrid", "Legazpi, Madrid"),        # separadores tras el prefijo
    ("Metro - Legazpi", "Legazpi"),
])
def test_prefijos_se_quitan_sin_mayusculas_ni_tildes(monkeypatch, texto, esperado):
    assert pr.normalizar_lugar(texto) == esperado
    assert q_enviada(monkeypatch, texto) == esperado


@pytest.mark.parametrize("texto", ["Metro", "metro ", "Estación de", "Estación de metro", "Parada de", "Metro, "])
def test_si_no_queda_nada_no_cambia(monkeypatch, texto):
    assert pr.normalizar_lugar(texto) == texto
    assert q_enviada(monkeypatch, texto) == texto


@pytest.mark.parametrize("texto", [
    "Legazpi, Madrid", "Concha Espina, Madrid", "Plaza de Legazpi, Madrid", "Puerta del Sol",
    "Metropolitano, Madrid", "Metrosur", "Estaciones de servicio", "Paradas de Sol", "Calle Mayor 5",
])
def test_texto_sin_prefijo_llega_identico_a_nominatim(monkeypatch, texto):
    assert pr.normalizar_lugar(texto) == texto
    assert q_enviada(monkeypatch, texto) == texto


def test_una_sola_pasada():
    assert pr.normalizar_lugar("Parada de metro Sol") == "metro Sol"          # solo «Parada de»; documentado en la spec
    assert pr.normalizar_lugar("Metro metro Sol") == "metro Sol"


def test_no_se_anade_madrid_ni_llamadas_extra(monkeypatch):
    assert q_enviada(monkeypatch, "Metro Legazpi") == "Legazpi"                # no se añade «Madrid»
    assert q_enviada(monkeypatch, "Legazpi") == "Legazpi"


def test_mensajes_conservan_el_texto_original(monkeypatch):
    esc = Escenario(monkeypatch)
    esc.nominatim = [[SOL], [BERNABEU]]
    r = pr.planificar_ruta("Metro Sol", "Estación de metro Bernabéu")
    assert esc.cuantas("nominatim") == 2                                       # sigue habiendo una llamada por extremo
    esc.nominatim = [[], [BERNABEU]]
    r = pr.planificar_ruta("Metro Sol", "Estación de metro Bernabéu")
    assert r["estado"] == "direccion_no_encontrada" and "«Metro Sol»" in r["mensaje"]
