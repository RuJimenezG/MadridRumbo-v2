"""Tests de la petición a Google Routes de planificar_ruta (spec 004, RF-11, RF-12, RF-14 y RF-16). No usan red.

Todo pasa por un doble de `_http_json`; el conftest.py bloquea `urlopen`.
"""
import io
import urllib.error

import pytest

import config
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import BARCELONA, BERNABEU, Escenario

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


# --- T10: interpretación de la respuesta de Google (RF-12, RF-13, RF-15, RF-17 y RF-18) ---

def _paso_transito(tipo, linea, desde, hasta, segundos):
    return {
        "travelMode": "TRANSIT", "staticDuration": f"{segundos}s",
        "transitDetails": {
            "stopDetails": {"departureStop": {"name": desde}, "arrivalStop": {"name": hasta}},
            "transitLine": {"nameShort": linea, "vehicle": {"type": tipo}},
        },
    }


def _paso_a_pie(segundos):
    return {"travelMode": "WALK", "staticDuration": f"{segundos}s"}


def _ruta(*pasos, duracion="1320s"):
    return {"routes": [{"duration": duracion, "legs": [{"steps": list(pasos)}]}]}


RUTA_METRO = _ruta(
    _paso_a_pie(180),
    _paso_transito("SUBWAY", "1", "Sol", "Chamartín", 900),
    _paso_transito("BUS", "27", "Chamartín", "Plaza de Castilla", 240),
    _paso_a_pie(60),
)


def test_devuelve_tiempo_y_tramos():
    # RF-15: tiempo total y trayecto tramo a tramo, más las paradas de subida y bajada para el RAG.
    r = pr.interpretar_respuesta_google(RUTA_METRO)
    assert r["estado"] == "ok"
    assert r["parada_subida"] == "Sol" and r["parada_bajada"] == "Plaza de Castilla"
    ruta = r["ruta"]
    assert ruta["duracion_min"] == 22 and ruta["fuente"] == "Google Routes"
    assert ruta["tramos"] == [
        {"modo": "A pie", "linea": None, "desde": None, "hasta": None, "duracion_min": 3},
        {"modo": "SUBWAY", "linea": "1", "desde": "Sol", "hasta": "Chamartín", "duracion_min": 15},
        {"modo": "BUS", "linea": "27", "desde": "Chamartín", "hasta": "Plaza de Castilla", "duracion_min": 4},
        {"modo": "A pie", "linea": None, "desde": None, "hasta": None, "duracion_min": 1},
    ]


@pytest.mark.parametrize("tipo", sorted(config.TIPOS_VEHICULO_ACEPTADOS))
def test_modos_aceptados_dan_ruta(tipo):
    # RF-12: todo tipo de vehículo de la lista configurada es válido.
    assert pr.interpretar_respuesta_google(_ruta(_paso_transito(tipo, "C3", "A", "B", 600)))["estado"] == "ok"


@pytest.mark.parametrize("tipo", ["HIGH_SPEED_TRAIN", "LONG_DISTANCE_TRAIN", "FERRY", "CABLE_CAR", None])
def test_modos_permitidos_y_tipo_no_aceptado(tipo):
    # RF-12: un solo tramo con tipo fuera de lista (o sin tipo) invalida la ruta, aunque los demás valgan.
    r = pr.interpretar_respuesta_google(_ruta(
        _paso_transito("SUBWAY", "1", "Sol", "Atocha", 300),
        _paso_transito(tipo, "AVE", "Atocha", "Sevilla", 9000),
    ))
    assert r == {"estado": "sin_ruta", "ruta": None, "parada_subida": None, "parada_bajada": None}


def test_solo_a_pie_es_sin_ruta():
    # RF-13: caminar solo es un tramo de una ruta en transporte público, nunca la ruta entera.
    assert pr.interpretar_respuesta_google(_ruta(_paso_a_pie(900)))["estado"] == "sin_ruta"


@pytest.mark.parametrize("respuesta", [{}, {"routes": []}, {"routes": [{}]}, {"routes": [{"duration": "60s"}]},
                                       {"routes": ["x"]}, {"routes": [{"duration": "60s", "legs": []}]}])
def test_sin_ruta_no_da_zona_ni_precio(respuesta):
    # RF-17: vacío o incompleto → sin_ruta; sin paradas, así que no hay nada con lo que preguntar zona o precio.
    r = pr.interpretar_respuesta_google(respuesta)
    assert r == {"estado": "sin_ruta", "ruta": None, "parada_subida": None, "parada_bajada": None}


def test_no_estima_tiempos_ni_trayectos():
    # RF-18: sin duración total válida no se suma ni se estima a partir de los tramos.
    for duracion in (None, "", "abc"):
        resp = _ruta(_paso_transito("SUBWAY", "1", "Sol", "Atocha", 300), duracion=duracion)
        assert pr.interpretar_respuesta_google(resp)["estado"] == "sin_ruta"
    # Un tramo sin duración propia tampoco se rellena: se descarta la ruta entera.
    paso = _paso_transito("SUBWAY", "1", "Sol", "Atocha", 300)
    del paso["staticDuration"]
    assert pr.interpretar_respuesta_google(_ruta(paso))["estado"] == "sin_ruta"


# --- T12: orquestación (RF-5, RF-11, RF-16, RF-17, RF-20) ---

@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def test_fuera_de_cobertura_no_llama_a_google(esc):
    # RF-5: con el origen fuera de cobertura no se llama a Google ni al RAG (y sí se geocodifican ambos extremos).
    esc.nominatim = [[BARCELONA], [BERNABEU]]
    r = pr.planificar_ruta("Calle Mayor, Barcelona", "Estadio Santiago Bernabéu")
    assert r["estado"] == "fuera_cobertura" and r["ruta"] is None
    assert "origen" in r["mensaje"] and "fuera de la cobertura" in r["mensaje"]
    assert esc.orden == ["nominatim", "nominatim"]


def test_secuencia_nominatim_google_rag(esc):
    # Orden de los pasos: geocodificar origen y destino → Google → RAG (zona y precio).
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "ok"
    assert esc.orden == ["nominatim", "nominatim", "google", "rag", "rag"]
    # RF-11: Google recibe las coordenadas de los candidatos elegidos.
    cuerpo = esc.cuerpos_google[0]
    assert cuerpo["origin"]["location"]["latLng"] == {"latitude": 40.4169, "longitude": -3.7035}
    assert "departureTime" not in cuerpo                  # RF-14: sin hora pedida
    # La ruta y las paradas de Google alimentan al RAG (T10 → T11).
    assert r["ruta"]["duracion_min"] == 22
    assert "Sol" in esc.preguntas[0] and "Plaza de Castilla" in esc.preguntas[0]


def test_hora_pedida_llega_a_google_en_rfc3339(esc):
    pr.planificar_ruta("Sol", "Bernabéu", hora_salida="2026-10-16T08:30")
    assert esc.cuerpos_google[0]["departureTime"] == "2026-10-16T08:30:00+02:00"


@pytest.mark.parametrize("fallo", [urllib.error.URLError("sin red"), TimeoutError("t"), ["lista"]])
def test_google_falla_consulta_rag_con_municipios_de_nominatim(esc, fallo):
    # RF-16 y RF-20: Google falla → ruta_no_calculada, pero se consulta el RAG con los municipios de Nominatim.
    esc.google = fallo
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "ruta_no_calculada" and r["ruta"] is None
    assert esc.orden == ["nominatim", "nominatim", "google", "rag", "rag"]
    assert "Madrid" in esc.preguntas[0]
    assert r["zona"]["estado"] == "ok" and r["precio"]["estado"] == "ok"


@pytest.mark.parametrize("respuesta", [{}, {"routes": []}])
def test_sin_ruta_no_da_zona_ni_precio_ni_consulta_al_rag(esc, respuesta):
    # RF-17: Google responde sin ruta → sin_ruta, zona y precio omitidos y sin consultar al RAG.
    esc.google = respuesta
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "sin_ruta" and r["ruta"] is None
    assert r["zona"]["estado"] == r["precio"]["estado"] == "omitida"
    assert esc.cuantas("rag") == 0
    assert "Zona (RAG)" not in r["mensaje"] and "Precio (RAG)" not in r["mensaje"]
