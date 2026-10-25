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
from tests.dobles_ruta import (
    ATOCHA as ATOCHA_RAW, BARCELONA as BARCELONA_RAW, BERNABEU as BERNABEU_RAW,
    RETIRO as RETIRO_RAW, SOL as SOL_RAW, Escenario,
)

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
        {"direccion": SOL["display_name"], "lat": 40.4169, "lon": -3.7035, "municipio": "Madrid",
         "region": "Comunidad de Madrid", "iso": None}   # T22: región e ISO para verificar la comunidad (RF-55)
    ]
    assert destino["candidatos"][0]["municipio"] == "Madrid"  # sale de address.town

    assert len(red.peticiones) == 2
    url, _, timeout = red.peticiones[0]
    assert url.startswith(config.NOMINATIM_URL + "?")
    p = parametros(url)
    assert p["q"] == "Puerta del Sol, Madrid"
    assert p["countrycodes"] == config.NOMINATIM_PAIS == "es"
    # RF-4: el viewbox es solo una preferencia (sin bounded=1); el filtro dentro_de_ambito decide qué entra.
    assert p["viewbox"] == pr.viewbox_nominatim() and "bounded" not in p
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


def lugar(nombre, lat, lon):
    """Candidato ya normalizado, como lo devuelve `geocodificar`."""
    return {"direccion": nombre, "lat": lat, "lon": lon, "municipio": "Madrid"}


# Puntos de referencia: cuatro dentro del ámbito y uno claramente fuera.
SOL_C = lugar("Puerta del Sol", 40.4169, -3.7035)
ATOCHA = lugar("Estación de Atocha", 40.4065, -3.6895)
BERNABEU_C = lugar("Estadio Santiago Bernabéu", 40.4531, -3.6883)
RETIRO = lugar("Parque del Retiro", 40.4153, -3.6845)
BARCELONA_C = lugar("Calle Mayor, Barcelona", 41.3874, 2.1686)


def test_sin_resultados_pide_direccion_precisa():
    # RF-6: sin ningún resultado de Nominatim la dirección se clasifica como no encontrada.
    r = pr.clasificar_candidatos([])
    assert r["estado"] == "no_encontrada" and r["elegido"] is None and r["candidatos"] == []


def test_solo_fuera_de_ambito_rechaza():
    # RF-4: con resultados, pero todos fuera del ámbito, la dirección está fuera de cobertura.
    r = pr.clasificar_candidatos([BARCELONA_C])
    assert r["estado"] == "fuera_cobertura" and r["elegido"] is None


def test_un_candidato_continua_e_indica_direccion():
    # RF-7: un único candidato dentro del ámbito se elige sin preguntar, con su dirección identificada.
    r = pr.clasificar_candidatos([SOL_C])
    assert r["estado"] == "ok" and r["elegido"] == SOL_C
    assert r["elegido"]["direccion"] == "Puerta del Sol"
    # RF-3: un homónimo fuera del ámbito se descarta y el de dentro basta para continuar.
    r = pr.clasificar_candidatos([BARCELONA_C, SOL_C])
    assert r["estado"] == "ok" and r["elegido"] == SOL_C


def test_varios_candidatos_limita_y_no_calcula(monkeypatch):
    # RF-8: varios candidatos dentro del ámbito: no se elige ninguno y se muestran como mucho MAX_CANDIDATOS_MOSTRAR.
    cuatro = [SOL_C, ATOCHA, BERNABEU_C, RETIRO]
    r = pr.clasificar_candidatos([BARCELONA_C] + cuatro)
    assert r["estado"] == "ambigua" and r["elegido"] is None
    assert r["candidatos"] == cuatro[:config.MAX_CANDIDATOS_MOSTRAR]
    monkeypatch.setattr(config, "MAX_CANDIDATOS_MOSTRAR", 2)
    assert pr.clasificar_candidatos(cuatro)["candidatos"] == [SOL_C, ATOCHA]


def test_duplicados_cercanos_no_cuentan_como_ambiguedad():
    # Plan, Decisiones: resultados a menos de RADIO_MISMA_UBICACION_M son el mismo lugar (edificio + calle)
    # y se conserva el primero, que es el mejor clasificado por Nominatim.
    cerca = lugar("Puerta del Sol, calle", 40.41715, -3.70350)   # a unos 25 m
    r = pr.clasificar_candidatos([SOL_C, cerca])
    assert r["estado"] == "ok" and r["elegido"] == SOL_C
    # Un lugar a más del radio sí es otro candidato.
    assert pr.clasificar_candidatos([SOL_C, ATOCHA])["estado"] == "ambigua"


def test_misma_ubicacion_no_calcula():
    # RF-10: origen y destino a menos de RADIO_MISMA_UBICACION_M se consideran la misma ubicación.
    assert pr.misma_ubicacion(SOL_C, lugar("Sol, otra entrada", 40.4172, -3.7035))   # unos 33 m
    assert not pr.misma_ubicacion(SOL_C, ATOCHA)
    assert pr.distancia_m(40.4169, -3.7035, 40.4169, -3.7035) == 0
    assert 1000 < pr.distancia_m(*SOL_C_COORDS, *ATOCHA_COORDS) < 3000


SOL_C_COORDS = (SOL_C["lat"], SOL_C["lon"])
ATOCHA_COORDS = (ATOCHA["lat"], ATOCHA["lon"])


# --- T12: orquestación (RF-6, RF-8, RF-9, RF-10, RF-40) ---


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def test_aclaracion_en_respuesta_sin_pausa(esc):
    # RF-8 y RF-9: varios candidatos → la aclaración va en la respuesta (un dict normal), sin pausa HITL ni cálculo.
    esc.nominatim = [[SOL_RAW, ATOCHA_RAW, RETIRO_RAW, BERNABEU_RAW], [BERNABEU_RAW]]
    r = pr.planificar_ruta("Madrid centro", "Bernabéu")
    assert isinstance(r, dict) and list(r)[0] == "estado" and r["estado"] == "ambigua"
    assert len(r["candidatos"]["origen"]) == config.MAX_CANDIDATOS_MOSTRAR and r["candidatos"]["destino"] == []
    assert "Puerta del Sol" in r["mensaje"] and "cuál" in r["mensaje"]
    assert esc.orden == ["nominatim", "nominatim"]          # ni Google ni RAG
    assert "interrupt" not in open(pr.__file__, encoding="utf-8").read()


def test_direccion_no_encontrada_pide_una_mas_precisa(esc):
    # RF-6: sin resultados se informa y se pide una dirección más precisa; no se calcula nada.
    esc.nominatim = [[], [BERNABEU_RAW]]
    r = pr.planificar_ruta("calle inexistente", "Bernabéu")
    assert r["estado"] == "direccion_no_encontrada" and "más precisa" in r["mensaje"]
    assert esc.orden == ["nominatim", "nominatim"]


def test_destino_fuera_del_ambito_da_fuera_cobertura_y_no_no_encontrada(esc):
    # RF-4 (y RF-5): un destino que Nominatim sitúa fuera del ámbito se rechaza como fuera de cobertura, no como
    # «no encontrada» (RF-6, que queda para cuando Nominatim no devuelve nada), y sin llamar a Google ni al RAG.
    esc.nominatim = [[SOL_RAW], [BARCELONA_RAW]]
    r = pr.planificar_ruta("Sol", "Calle Mayor, Barcelona")
    assert r["estado"] == "fuera_cobertura" and "destino" in r["mensaje"] and "fuera de la cobertura" in r["mensaje"]
    assert "No he encontrado" not in r["mensaje"] and esc.orden == ["nominatim", "nominatim"]


def test_prioridad_fuera_de_cobertura_sobre_ambigua(esc):
    # Plan: con varios problemas, el estado es fuera > no encontrada > ambigua y el mensaje los lista todos.
    esc.nominatim = [[SOL_RAW, ATOCHA_RAW], [BARCELONA_RAW]]
    r = pr.planificar_ruta("Sol o Atocha", "Calle Mayor, Barcelona")
    assert r["estado"] == "fuera_cobertura"
    assert "destino" in r["mensaje"] and "origen" in r["mensaje"]


def test_misma_ubicacion_no_llama_a_google(esc):
    # RF-10: origen y destino en el mismo sitio → se informa y no se calcula.
    esc.nominatim = [[SOL_RAW], [SOL_RAW]]
    r = pr.planificar_ruta("Sol", "Puerta del Sol")
    assert r["estado"] == "misma_ubicacion" and esc.orden == ["nominatim", "nominatim"]


@pytest.mark.parametrize("fallo", [urllib.error.URLError("sin red"), TimeoutError("t"), {"error": "429"}])
def test_nominatim_falla_se_detiene_sin_google_ni_rag(esc, fallo):
    # RF-40: tras un fallo de Nominatim no hay ninguna llamada más (ni al otro extremo, ni a Google ni al RAG).
    esc.nominatim = [fallo, [BERNABEU_RAW]]
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "geocodificacion_fallida" and "más tarde" in r["mensaje"]
    assert esc.orden == ["nominatim"]
    # El fallo en el destino también detiene el proceso antes de Google y del RAG.
    esc.orden.clear()
    esc.nominatim = [[SOL_RAW], fallo]
    assert pr.planificar_ruta("Sol", "Bernabéu")["estado"] == "geocodificacion_fallida"
    assert esc.orden == ["nominatim", "nominatim"]
