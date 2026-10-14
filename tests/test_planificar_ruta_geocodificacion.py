"""Tests del cliente Nominatim de planificar_ruta (spec 004, RF-1 y RF-40). No usan red.

Todo pasa por un doble de `_http_json`; `time.sleep` y `time.monotonic` están parcheados.
"""
import io
import json
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

import pytest

import config
from src.tools import planificar_ruta as pr

# Respuestas de ejemplo de Nominatim (jsonv2 con addressdetails), reducidas a lo que usa el cliente.
SOL = {
    "display_name": "Puerta del Sol, Sol, Centro, Madrid, Comunidad de Madrid, España",
    "lat": "40.4169", "lon": "-3.7035",
    "address": {"city": "Madrid", "state": "Comunidad de Madrid", "country_code": "es"},
}
BERNABEU = {
    "display_name": "Estadio Santiago Bernabéu, Chamartín, Madrid, España",
    "lat": "40.4531", "lon": "-3.6883",
    "address": {"town": "Madrid", "country_code": "es"},
}


class RedFalsa:
    """Dobles de `_http_json`, `time.sleep` y `time.monotonic`; guardan lo que reciben."""

    def __init__(self):
        self.respuestas = []      # cada elemento: dato a devolver o excepción a lanzar
        self.peticiones = []      # (url, cabeceras, timeout)
        self.esperas = []         # segundos pasados a sleep
        self.reloj = 1000.0       # valor actual de monotonic

    def http_json(self, url, *, headers=None, body=None, timeout=10):
        self.peticiones.append((url, headers or {}, timeout))
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def sleep(self, segundos):
        self.esperas.append(segundos)
        self.reloj += segundos

    def monotonic(self):
        return self.reloj


@pytest.fixture
def red(monkeypatch):
    falsa = RedFalsa()
    monkeypatch.setattr(pr, "_http_json", falsa.http_json)
    monkeypatch.setattr(pr.time, "sleep", falsa.sleep)
    monkeypatch.setattr(pr.time, "monotonic", falsa.monotonic)
    monkeypatch.setattr(pr, "_ultima_peticion_nominatim", None)
    return falsa


def parametros(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_geocodifica_origen_y_destino_con_nominatim(red):
    # RF-1: cada dirección en texto libre se convierte a coordenadas con una petición a Nominatim.
    red.respuestas = [[SOL], [BERNABEU]]
    origen = pr.geocodificar("Puerta del Sol, Madrid")
    destino = pr.geocodificar("Estadio Santiago Bernabéu")

    assert origen["estado"] == "ok" and destino["estado"] == "ok"
    assert origen["candidatos"] == [
        {"direccion": SOL["display_name"], "lat": 40.4169, "lon": -3.7035, "municipio": "Madrid"}
    ]
    assert destino["candidatos"][0]["municipio"] == "Madrid"  # sale de address.town

    assert len(red.peticiones) == 2
    url, _, timeout = red.peticiones[0]
    assert url.startswith(config.NOMINATIM_URL + "?")
    p = parametros(url)
    assert p["q"] == "Puerta del Sol, Madrid"
    assert p["countrycodes"] == config.NOMINATIM_PAIS == "es"
    assert p["viewbox"] == pr.viewbox_nominatim() and p["bounded"] == "1"
    assert p["addressdetails"] == "1" and p["format"] == "jsonv2"
    assert p["limit"] == str(config.NOMINATIM_LIMIT)
    assert timeout == config.NOMINATIM_TIMEOUT_S


def test_sin_resultados_no_es_un_fallo(red):
    # Nominatim responde bien pero vacío: no es un fallo (la clasificación como RF-6 llega en T8).
    red.respuestas = [[]]
    assert pr.geocodificar("calle que no existe") == {"estado": "ok", "candidatos": []}


@pytest.mark.parametrize("fallo", [
    urllib.error.URLError("sin conexión"),
    TimeoutError("timeout"),
    urllib.error.HTTPError(config.NOMINATIM_URL, 429, "Too Many Requests", {}, io.BytesIO(b"")),
    urllib.error.HTTPError(config.NOMINATIM_URL, 500, "Server Error", {}, io.BytesIO(b"")),
    ValueError("JSON inválido"),
    {"error": {"code": 400, "message": "Bad request"}},   # Nominatim a veces responde un dict con error
    "texto que no es una lista",
])
def test_nominatim_falla_no_llama_a_google_ni_rag(red, fallo):
    # RF-40: error, timeout, error HTTP, límite de peticiones o respuesta inválida no lanzan excepción:
    # devuelven un resultado de fallo que la orquestación (T12) convierte en geocodificacion_fallida.
    red.respuestas = [fallo]
    resultado = pr.geocodificar("Puerta del Sol")
    assert resultado == {"estado": "geocodificacion_fallida", "candidatos": []}
    assert len(red.peticiones) == 1  # sin reintentos ni otras llamadas


def test_http_json_usa_urllib_sin_salir_a_la_red(monkeypatch):
    # El cliente HTTP real solo construye la petición y lee el JSON; aquí urlopen es un doble.
    vistas = []

    class Respuesta:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"ok": "sí"}).encode("utf-8")

    def urlopen_falso(peticion, timeout=None):
        vistas.append((peticion, timeout))
        return Respuesta()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen_falso)
    assert pr._http_json("https://ejemplo.test/x", headers={"User-Agent": "T/1"}, timeout=7) == {"ok": "sí"}
    peticion, timeout = vistas[0]
    assert peticion.get_method() == "GET" and peticion.get_header("User-agent") == "T/1" and timeout == 7

    pr._http_json("https://ejemplo.test/y", body={"a": 1})
    peticion = vistas[1][0]
    assert peticion.get_method() == "POST" and json.loads(peticion.data) == {"a": 1}
    assert peticion.get_header("Content-type") == "application/json"
