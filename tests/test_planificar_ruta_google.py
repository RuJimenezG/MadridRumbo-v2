"""Tests de la petición a Google Routes de planificar_ruta (spec 004, RF-11, RF-12, RF-14 y RF-16). No usan red.

Todo pasa por un doble de `_http_json`; el conftest.py bloquea `urlopen`.
"""
import io
import urllib.error

import pytest

import config
from src.tools import planificar_ruta as pr

CLAVE = "CLAVE-SECRETA-123"
ORIGEN = {"direccion": "Puerta del Sol", "lat": 40.4169, "lon": -3.7035, "municipio": "Madrid"}
DESTINO = {"direccion": "Estadio Santiago Bernabéu", "lat": 40.4531, "lon": -3.6883, "municipio": "Madrid"}
# Respuesta mínima de ejemplo; su interpretación se prueba en T10.
RESPUESTA = {"routes": [{"duration": "1320s", "legs": [{"steps": []}]}]}


class GoogleFalso:
    """Doble de `_http_json`: guarda cada petición y devuelve (o lanza) lo que se le indique."""

    def __init__(self):
        self.respuesta = RESPUESTA
        self.peticiones = []   # (url, cabeceras, cuerpo, timeout)

    def http_json(self, url, *, headers=None, body=None, timeout=10):
        self.peticiones.append((url, headers or {}, body, timeout))
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


@pytest.fixture
def google(monkeypatch):
    falso = GoogleFalso()
    monkeypatch.setattr(pr, "_http_json", falso.http_json)
    monkeypatch.setattr(config, "GOOGLE_ROUTES_API_KEY", CLAVE)
    return falso


def test_calcula_con_coordenadas(google):
    # RF-11: la ruta se pide a Google a partir de las coordenadas de origen y destino, en una sola llamada.
    r = pr.consultar_google(ORIGEN, DESTINO)
    assert r == {"estado": "ok", "respuesta": RESPUESTA}

    assert len(google.peticiones) == 1                      # máximo 1 llamada por consulta
    url, cabeceras, cuerpo, timeout = google.peticiones[0]
    assert url == config.GOOGLE_ROUTES_URL and timeout == config.GOOGLE_TIMEOUT_S
    assert cuerpo["origin"]["location"]["latLng"] == {"latitude": 40.4169, "longitude": -3.7035}
    assert cuerpo["destination"]["location"]["latLng"] == {"latitude": 40.4531, "longitude": -3.6883}
    assert cuerpo["travelMode"] == "TRANSIT"
    assert cuerpo["languageCode"] == "es"
    assert cuerpo["computeAlternativeRoutes"] is False       # las rutas alternativas están fuera de alcance
    assert cabeceras["X-Goog-FieldMask"] == config.GOOGLE_FIELD_MASK


def test_pide_solo_los_modos_de_la_red_crtm(google):
    # RF-12: se piden únicamente los modos configurados (metro, ligero/tranvía, autobús y Cercanías).
    pr.consultar_google(ORIGEN, DESTINO)
    cuerpo = google.peticiones[0][2]
    assert cuerpo["transitPreferences"]["allowedTravelModes"] == config.MODOS_GOOGLE


def test_sin_hora_no_hay_departure_time(google):
    # RF-14: sin hora de salida pedida no se envía departureTime (Google calcula con salida inmediata).
    pr.consultar_google(ORIGEN, DESTINO)
    assert "departureTime" not in google.peticiones[0][2]
    pr.consultar_google(ORIGEN, DESTINO, None)
    assert "departureTime" not in google.peticiones[1][2]


def test_hora_pedida_se_envia_en_rfc3339(google):
    # RF-31: si la persona pidió hora, se envía tal cual la convirtió validar_hora (RFC 3339).
    pr.consultar_google(ORIGEN, DESTINO, "2026-07-15T08:30:00+02:00")
    assert google.peticiones[0][2]["departureTime"] == "2026-07-15T08:30:00+02:00"


def test_clave_solo_en_la_cabecera(google):
    # RNF Secretos: la clave va únicamente en X-Goog-Api-Key; no en la URL ni en el cuerpo ni en el resultado.
    resultado = pr.consultar_google(ORIGEN, DESTINO)
    url, cabeceras, cuerpo, _ = google.peticiones[0]
    assert cabeceras["X-Goog-Api-Key"] == CLAVE
    assert CLAVE not in url and CLAVE not in repr(cuerpo) and CLAVE not in repr(resultado)
    assert [k for k, v in cabeceras.items() if v == CLAVE] == ["X-Goog-Api-Key"]


@pytest.mark.parametrize("clave", [None, "", "   "])
def test_sin_clave_falla_sin_llamar_a_la_red(google, monkeypatch, clave):
    # RF-16: sin clave configurada es un fallo controlado y no se hace ninguna llamada.
    monkeypatch.setattr(config, "GOOGLE_ROUTES_API_KEY", clave)
    assert pr.consultar_google(ORIGEN, DESTINO) == {"estado": "ruta_no_calculada", "respuesta": None}
    assert google.peticiones == []


@pytest.mark.parametrize("fallo", [
    urllib.error.URLError("sin conexión"),
    TimeoutError("timeout"),
    urllib.error.HTTPError(config.GOOGLE_ROUTES_URL, 403, "Forbidden", {}, io.BytesIO(b"")),
    urllib.error.HTTPError(config.GOOGLE_ROUTES_URL, 500, "Server Error", {}, io.BytesIO(b"")),
    ValueError(f"JSON inválido, clave {CLAVE}"),
    ["no", "es", "un", "dict"],
])
def test_google_falla_informa(google, fallo):
    # RF-16: error, falta de conexión, error HTTP o respuesta inválida no lanzan excepción; devuelven un fallo
    # sin el texto del error (podría contener datos sensibles) y sin reintentos.
    google.respuesta = fallo
    resultado = pr.consultar_google(ORIGEN, DESTINO)
    assert resultado == {"estado": "ruta_no_calculada", "respuesta": None}
    assert CLAVE not in repr(resultado)
    assert len(google.peticiones) == 1
