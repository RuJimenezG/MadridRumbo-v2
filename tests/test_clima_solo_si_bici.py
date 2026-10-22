"""Spec 010, T16 (RF-47 y RF-48): el clima solo se consulta si la bici es posible y su fallo se registra por categoría.

Caso real: «Plaza Castilla → Rivas» mostró «No se pudo comprobar el tiempo…» y después «fuera de rango». Sin red.
"""
import logging
import ssl
import urllib.error

import pytest

import config
from src.tools import bicimad, planificar_ruta as pr
from tests.dobles_ruta import METEO_APTO, METEO_LLUVIA, SOL, Escenario, nominatim

RIVAS = nominatim("Rivas-Vaciamadrid, Comunidad de Madrid", 40.3260, -3.5180, "Rivas-Vaciamadrid")   # ~20 km de Sol
PLAZA_MAYOR = nominatim("Plaza Mayor, Madrid", 40.4155, -3.7074)                                     # ~365 m de Sol
MOTIVO_R2 = "La alternativa en bici no se ofrece: la distancia"


@pytest.fixture
def esc(monkeypatch):
    e = Escenario(monkeypatch)
    e.bici_real()
    return e


@pytest.mark.parametrize("lejos", [RIVAS, PLAZA_MAYOR])
def test_fuera_de_rango_no_consulta_el_clima_ni_avisa(esc, lejos):
    esc.nominatim = [[SOL], [lejos]]
    esc.meteo = OSError("no debería llamarse")
    r = pr.planificar_ruta("Sol", "Lejos")
    assert r["estado"] == "ok" and esc.llamadas_meteo == []
    assert config.CLIMA_SIN_DATO_AVISO not in r["mensaje"] and config.CLIMA_SIN_DATO_AVISO not in r["bloques"]
    assert not any(b.startswith("Tiempo en el origen") for b in r["bloques"]) and "clima" not in r
    assert r["bloques"][-1].startswith(MOTIVO_R2)


def test_fuera_de_rango_sin_less_walking_aunque_llueva(esc):
    esc.nominatim, esc.meteo = [[SOL], [RIVAS]], (200, METEO_LLUVIA)
    pr.planificar_ruta("Sol", "Rivas")
    assert "LESS_WALKING" not in str(esc.cuerpos_google[0])


def test_en_rango_con_clima_caido_el_aviso_sigue_saliendo(esc):
    esc.meteo = OSError("caído")
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert len(esc.llamadas_meteo) == 1 and config.CLIMA_SIN_DATO_AVISO in r["bloques"]
    assert r["bici"]["estado"] == "ok"           # la bici se ofrece sin la comprobación del tiempo


def test_en_rango_con_clima_ok_sigue_la_linea_del_tiempo(esc):
    esc.meteo = (200, METEO_APTO)
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert any(b.startswith("Tiempo en el origen") for b in r["bloques"])


def test_con_hora_pedida_el_motivo_es_la_hora_no_la_distancia(esc):
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_salida="2026-10-15T09:00")
    assert esc.llamadas_meteo == [] and "hora de salida o de llegada" in r["bloques"][-1]


# --- RF-48: categoría de la causa en el log ---

ORIGEN = {"lat": 40.4169, "lon": -3.7035}


@pytest.mark.parametrize("respuesta, categoria", [
    ((503, None), "http_503"),
    ((429, {"error": True}), "http_429"),
    ((200, ["no", "objeto"]), "respuesta_invalida"),
    ((200, {"current": {"temperature_2m": 10}}), "datos_incompletos"),
    (TimeoutError("t"), "timeout"),
    (urllib.error.URLError(TimeoutError("timed out")), "timeout"),
    (urllib.error.URLError(ssl.SSLCertVerificationError("cert caducado")), "tls"),
    (urllib.error.URLError("[Errno 11001] getaddrinfo failed"), "red"),
    (OSError("sin red"), "red"),
    (RuntimeError("secreto-xyz"), "error"),
])
def test_cada_fallo_registra_su_categoria(monkeypatch, caplog, respuesta, categoria):
    def red(url, **kw):
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta
    monkeypatch.setattr(bicimad, "_get_json", red)
    caplog.set_level(logging.DEBUG)
    assert bicimad.clima_origen(ORIGEN) == {"estado": "no_disponible"}
    assert f"causa={categoria}" in caplog.text
    assert "secreto-xyz" not in caplog.text and "latitude" not in caplog.text and "40.4169" not in caplog.text


def test_sin_coordenadas_se_registra_sin_llamar(monkeypatch, caplog):
    monkeypatch.setattr(bicimad, "_get_json", lambda *a, **k: pytest.fail("no debe llamar"))
    caplog.set_level(logging.DEBUG)
    assert bicimad.clima_origen({"lat": None}) == {"estado": "no_disponible"}
    assert "causa=sin_coordenadas" in caplog.text
