"""Tests de T2 (spec 009): configuración de BiciMAD y cliente de la EMT. Sin red: dobles de `_get_json`.

Interfaz que fijan estos tests (a implementar después):
- `config`: `BICI_*`, `EMT_LOGIN_URL`, `EMT_ESTACIONES_URL`, `EMT_TIMEOUT_S`, `EMT_CLIENT_ID`, `EMT_PASS_KEY` (de `os.getenv`),
  `GOOGLE_FIELD_MASK_BICI` y `BICI_AVISO_GOOGLE`.
- `src/tools/bicimad.py` (cliente HTTP propio, sin importar nada de `planificar_ruta.py`):
  - `_get_json(url, headers=None, timeout=10) -> (status_http, cuerpo_json)`; lanza OSError (red, timeout) o ValueError (JSON inválido).
  - `emt_estaciones() -> {"estado": "ok" | "no_disponible", "estaciones": [{id, nombre, lat, lon, bicis, huecos, activa}]}`.
    Nunca lanza; el token vive en `_token` (con caducidad por `time.monotonic`) y se reutiliza.
Datos reales de la EMT: ver `specs/009-alternativa-bicimad/verificacion-emt.md`.
"""
import ast
import json
import importlib
import re
import time
from pathlib import Path

import pytest

import config
from src.tools import bicimad, planificar_ruta as pr
from tests.dobles_ruta import ATOCHA, BARCELONA, BERNABEU, METEO_APTO, METEO_LLUVIA, SOL, Escenario

RAIZ = Path(__file__).resolve().parent.parent

# Valores ficticios: ninguna credencial real interviene en los tests.
ID_FALSO, CLAVE_FALSA, TOKEN_FALSO, USUARIO_FALSO = "ID-FALSO", "CLAVE-FALSA", "TOKEN-FALSO", "USUARIO-FALSO"
SECRETOS = (ID_FALSO, CLAVE_FALSA, TOKEN_FALSO, USUARIO_FALSO)


@pytest.fixture
def bici():
    return importlib.import_module("src.tools.bicimad")


# --- Configuración y secretos (RNF Configuración, RNF Secretos) ---

def test_constantes_bici_valores_iniciales():
    assert config.BICI_DISTANCIA_MIN_M == 1000
    assert config.BICI_DISTANCIA_MAX_M == 6000
    assert config.BICI_ESTACION_RADIO_MAX_M == 500
    assert config.BICI_MIN_BICIS == 1
    assert config.BICI_MIN_HUECOS == 1


def test_urls_y_timeout_de_la_emt():
    assert config.EMT_LOGIN_URL == "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/"
    assert config.EMT_ESTACIONES_URL == "https://openapi.emtmadrid.es/v1/transport/bicimad/stations/"
    assert isinstance(config.EMT_TIMEOUT_S, (int, float)) and config.EMT_TIMEOUT_S > 0


def test_mascara_de_google_para_bici_y_a_pie_y_aviso():
    mascara = config.GOOGLE_FIELD_MASK_BICI
    assert "routes.duration" in mascara and "routes.distanceMeters" in mascara
    assert "transitDetails" not in mascara            # no es la máscara de transporte público
    assert isinstance(config.BICI_AVISO_GOOGLE, str) and "beta" in config.BICI_AVISO_GOOGLE.lower()


def test_credenciales_solo_del_entorno_y_env_example():
    codigo = (RAIZ / "config.py").read_text(encoding="utf-8")
    assert 'os.getenv("EMT_CLIENT_ID")' in codigo and 'os.getenv("EMT_PASS_KEY")' in codigo
    # Ningún valor con forma de credencial (UUID o 128 hex) escrito en el código.
    for ruta in (RAIZ / "config.py", RAIZ / "src" / "tools" / "bicimad.py"):
        if ruta.exists():
            texto = ruta.read_text(encoding="utf-8")
            assert not re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", texto)
            assert not re.search(r"\b[0-9a-fA-F]{64,}\b", texto)
    # .env.example conserva los nombres sin valor.
    lineas = (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "EMT_CLIENT_ID=" in [l.strip() for l in lineas]
    assert "EMT_PASS_KEY=" in [l.strip() for l in lineas]


def test_bicimad_no_importa_planificar_ruta(bici):
    arbol = ast.parse(Path(bici.__file__).read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom):
            assert "planificar_ruta" not in (nodo.module or "") and all(a.name != "planificar_ruta" for a in nodo.names)
        elif isinstance(nodo, ast.Import):
            assert all("planificar_ruta" not in a.name for a in nodo.names)


# --- Cliente de la EMT: doble de red ---

def login_ok(caducidad=86400, descripcion=None):
    descripcion = descripcion or f"Register user: {USUARIO_FALSO} with token: {TOKEN_FALSO}  Data recovered OK"
    return 200, {"code": "00", "description": descripcion, "datetime": "2026-10-20T13:00:00", "data": [
        {"accessToken": TOKEN_FALSO, "username": USUARIO_FALSO, "tokenSecExpiration": caducidad, "apiCounter": 1}]}


def estacion(id_=1409, activate=1, no_available=0, virtual=False, bicis=2, huecos=22, coords=(-3.7021354, 40.4285212)):
    return {"id": id_, "number": "5", "name": "5 - Fuencarral", "address": "Calle Fuencarral, 106",
            "geometry": {"type": "Point", "coordinates": list(coords)}, "activate": activate,
            "no_available": no_available, "virtualDelete": virtual, "dock_bikes": bicis, "free_bases": huecos,
            "total_bases": 27, "geofenced_capacity": 20, "light": 0, "reservations_count": 0,
            "tipo_estacionPBSC": "FIXED", "image": ""}


def estaciones_ok(*lista):
    return 200, {"code": "00", "description": f"{len(lista)} bases recovered", "datetime": "x", "data": list(lista)}


class Red:
    """Doble de `_get_json`: una respuesta (o excepción) por llamada, en orden, y registro de las llamadas."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def __call__(self, url, headers=None, timeout=10):
        self.llamadas.append((url, dict(headers or {}), timeout))
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


@pytest.fixture
def emt(bici, monkeypatch):
    """Módulo con credenciales falsas, sin token guardado y con la red sustituida por `Red(...)`."""
    monkeypatch.setattr(config, "EMT_CLIENT_ID", ID_FALSO, raising=False)
    monkeypatch.setattr(config, "EMT_PASS_KEY", CLAVE_FALSA, raising=False)
    monkeypatch.setattr(bici, "_token", None, raising=False)

    def con(*respuestas):
        red = Red(*respuestas)
        monkeypatch.setattr(bici, "_get_json", red)
        return red
    return types_namespace(bici, con)


def types_namespace(bici, con):
    class E:
        pass
    e = E()
    e.bici, e.con = bici, con
    return e


FALLO = {"estado": "no_disponible", "estaciones": []}


# --- Éxito: forma, coordenadas, estado ---

def test_login_y_estaciones_rutas_cabeceras_y_dos_llamadas(emt):
    red = emt.con(login_ok(), estaciones_ok(estacion()))
    r = emt.bici.emt_estaciones()
    assert r["estado"] == "ok" and len(red.llamadas) == 2
    (url1, cab1, t1), (url2, cab2, t2) = red.llamadas
    assert url1 == config.EMT_LOGIN_URL and cab1 == {"X-ClientId": ID_FALSO, "passKey": CLAVE_FALSA}
    assert url2 == config.EMT_ESTACIONES_URL and cab2 == {"accessToken": TOKEN_FALSO}
    assert t1 == t2 == config.EMT_TIMEOUT_S


def test_coordenadas_lon_lat_se_convierten_a_lat_lon(emt):
    emt.con(login_ok(), estaciones_ok(estacion(coords=(-3.7021354, 40.4285212))))
    e = emt.bici.emt_estaciones()["estaciones"][0]
    assert e["lat"] == 40.4285212 and e["lon"] == -3.7021354


def test_normaliza_los_campos_de_la_estacion(emt):
    emt.con(login_ok(), estaciones_ok(estacion(id_=1409, bicis=2, huecos=22)))
    e = emt.bici.emt_estaciones()["estaciones"][0]
    assert e == {"id": 1409, "nombre": "5 - Fuencarral", "lat": 40.4285212, "lon": -3.7021354,
                 "bicis": 2, "huecos": 22, "activa": True}


@pytest.mark.parametrize("activate, no_available, virtual, activa", [
    (1, 0, False, True),
    (0, 0, False, False),     # activate distinto de 1
    (1, 1, False, False),     # no_available distinto de 0
    (1, 0, True, False),      # borrada virtualmente
    (2, 0, False, False),     # solo activate == 1 cuenta
])
def test_estacion_activa_segun_activate_no_available_y_virtual_delete(emt, activate, no_available, virtual, activa):
    emt.con(login_ok(), estaciones_ok(estacion(activate=activate, no_available=no_available, virtual=virtual)))
    assert emt.bici.emt_estaciones()["estaciones"][0]["activa"] is activa


def test_estacion_mal_formada_se_descarta_sin_tumbar_la_lista(emt):
    rota = {"id": 7, "name": "sin coordenadas ni campos"}
    emt.con(login_ok(), estaciones_ok(rota, estacion(id_=1)))
    r = emt.bici.emt_estaciones()
    assert r["estado"] == "ok" and [e["id"] for e in r["estaciones"]] == [1]


# --- Token ---

def test_token_reutilizado_en_la_segunda_consulta(emt):
    red = emt.con(login_ok(), estaciones_ok(estacion()), estaciones_ok(estacion()))
    emt.bici.emt_estaciones()
    emt.bici.emt_estaciones()
    assert [u for u, _, _ in red.llamadas] == [config.EMT_LOGIN_URL, config.EMT_ESTACIONES_URL, config.EMT_ESTACIONES_URL]


def test_token_caducado_vuelve_a_hacer_login(emt, monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: ahora[0])
    red = emt.con(login_ok(caducidad=86400), estaciones_ok(estacion()), login_ok(), estaciones_ok(estacion()))
    emt.bici.emt_estaciones()
    ahora[0] += 86400 + 1
    emt.bici.emt_estaciones()
    assert [u for u, _, _ in red.llamadas].count(config.EMT_LOGIN_URL) == 2


# --- Fallos controlados: sin excepción, sin datos sensibles, sin reintentos ---

@pytest.mark.parametrize("credencial", ["EMT_CLIENT_ID", "EMT_PASS_KEY"])
@pytest.mark.parametrize("valor", [None, "", "   "])
def test_credenciales_ausentes_no_llaman(emt, monkeypatch, credencial, valor):
    red = emt.con()
    monkeypatch.setattr(config, credencial, valor, raising=False)
    assert emt.bici.emt_estaciones() == FALLO and red.llamadas == []


DESCRIPCION_CON_SECRETOS = f"Register user: {USUARIO_FALSO} with token: {TOKEN_FALSO}  fallo"

FALLOS_LOGIN = [
    (403, {"code": "84", "description": "", "datetime": "x", "data": []}),
    (403, {"code": "84", "description": DESCRIPCION_CON_SECRETOS, "datetime": "x", "data": []}),
    (500, {"code": "00", "description": DESCRIPCION_CON_SECRETOS, "datetime": "x", "data": []}),
    (200, {"code": "01", "description": DESCRIPCION_CON_SECRETOS, "datetime": "x", "data": []}),
    (200, {"code": "00", "description": DESCRIPCION_CON_SECRETOS, "datetime": "x", "data": []}),         # sin token
    (200, {"code": "00", "description": DESCRIPCION_CON_SECRETOS, "datetime": "x", "data": [{}]}),
    (200, ["no", "es", "un", "objeto"]),
    TimeoutError(f"timeout con {CLAVE_FALSA} {TOKEN_FALSO}"),
    OSError(f"sin red {ID_FALSO}"),
    ValueError(f"JSON inválido {CLAVE_FALSA}"),
]

FALLOS_ESTACIONES = [
    (401, {"code": "80", "description": "token", "datetime": "x", "data": []}),
    (429, {"code": "98", "description": "límite", "datetime": "x", "data": []}),
    (200, {"code": "90", "description": "error", "datetime": "x", "data": []}),
    (200, {"code": "00", "description": "ok", "datetime": "x", "data": "no es una lista"}),
    (200, {"code": "00", "description": "ok", "datetime": "x"}),
    (200, "texto"),
    TimeoutError(f"timeout {TOKEN_FALSO}"),
    ValueError("JSON inválido"),
]


@pytest.mark.parametrize("fallo", FALLOS_LOGIN)
def test_fallo_de_login_no_disponible_sin_excepcion_ni_reintento(emt, fallo):
    red = emt.con(fallo)
    assert emt.bici.emt_estaciones() == FALLO
    assert len(red.llamadas) == 1                        # sin reintentos y sin pedir estaciones


@pytest.mark.parametrize("fallo", FALLOS_ESTACIONES)
def test_fallo_de_estaciones_no_disponible_sin_excepcion_ni_reintento(emt, fallo):
    red = emt.con(login_ok(), fallo)
    assert emt.bici.emt_estaciones() == FALLO
    assert len(red.llamadas) == 2


@pytest.mark.parametrize("fallo", FALLOS_LOGIN)
def test_login_fallido_no_filtra_description_ni_secretos(emt, fallo, caplog, capsys):
    emt.con(fallo)
    with caplog.at_level("DEBUG"):
        r = emt.bici.emt_estaciones()
    visible = repr(r) + caplog.text + "".join(capsys.readouterr())
    assert not any(s in visible for s in SECRETOS)
    assert set(r) == {"estado", "estaciones"}


@pytest.mark.parametrize("respuestas", [
    (login_ok(), estaciones_ok(estacion())),
    (login_ok(), TimeoutError(f"timeout {TOKEN_FALSO} {CLAVE_FALSA}")),
    (login_ok(), (401, {"code": "80", "description": DESCRIPCION_CON_SECRETOS, "data": []})),
])
def test_description_del_login_y_token_nunca_salen(emt, respuestas, caplog, capsys):
    emt.con(*respuestas)
    with caplog.at_level("DEBUG"):
        r = emt.bici.emt_estaciones()
    visible = repr(r) + caplog.text + "".join(capsys.readouterr())
    assert not any(s in visible for s in SECRETOS)
    assert set(r) == {"estado", "estaciones"}
    assert all(set(e) == {"id", "nombre", "lat", "lon", "bicis", "huecos", "activa"} for e in r["estaciones"])


def test_haversine_propio(bici):
    assert bici.distancia_m(40.4169, -3.7035, 40.4169, -3.7035) == 0
    assert 1000 < bici.distancia_m(40.4169, -3.7035, 40.4065, -3.6895) < 3000


# --- T3: regla de oferta (R1, R2) y elección de estaciones (R3, R4): funciones puras ---

ORIGEN = {"lat": 40.4169, "lon": -3.7035}
DESTINO = {"lat": 40.4439, "lon": -3.7035}          # unos 3 km al norte


def punto_a(metros_al_norte):
    return {"lat": ORIGEN["lat"] + metros_al_norte / 111_195, "lon": ORIGEN["lon"]}


def est(id_, lugar, desplazamiento_lat_m=0, bicis=5, huecos=5, activa=True):
    """Estación a `desplazamiento_lat_m` metros al norte de `lugar`."""
    return {"id": id_, "nombre": f"E{id_}", "lat": lugar["lat"] + desplazamiento_lat_m / 111_195, "lon": lugar["lon"],
            "bicis": bicis, "huecos": huecos, "activa": activa}


def test_regla_hora_pedida_no_ofrece(bici):
    assert bici.rechazo_oferta(ORIGEN, DESTINO, hora_pedida=True) == "R1"
    assert bici.rechazo_oferta(ORIGEN, DESTINO, hora_pedida=False) is None
    # R1 va antes que R2: con hora pedida y distancia fuera de rango sigue siendo R1.
    assert bici.rechazo_oferta(ORIGEN, punto_a(100), hora_pedida=True) == "R1"


def test_regla_distancia_en_los_bordes(bici, monkeypatch):
    for metros, esperado in [(900, "R2"), (1100, None), (5900, None), (6100, "R2")]:
        assert bici.rechazo_oferta(ORIGEN, punto_a(metros), hora_pedida=False) == esperado
    # Bordes exactos (inclusivos): la distancia justo igual al mínimo o al máximo se ofrece.
    d = bici.distancia_m(ORIGEN["lat"], ORIGEN["lon"], DESTINO["lat"], DESTINO["lon"])
    monkeypatch.setattr(config, "BICI_DISTANCIA_MIN_M", d)
    assert bici.rechazo_oferta(ORIGEN, DESTINO, hora_pedida=False) is None
    monkeypatch.setattr(config, "BICI_DISTANCIA_MIN_M", d + 0.001)
    assert bici.rechazo_oferta(ORIGEN, DESTINO, hora_pedida=False) == "R2"
    monkeypatch.setattr(config, "BICI_DISTANCIA_MIN_M", 1000)
    monkeypatch.setattr(config, "BICI_DISTANCIA_MAX_M", d)
    assert bici.rechazo_oferta(ORIGEN, DESTINO, hora_pedida=False) is None
    monkeypatch.setattr(config, "BICI_DISTANCIA_MAX_M", d - 0.001)
    assert bici.rechazo_oferta(ORIGEN, DESTINO, hora_pedida=False) == "R2"


def test_estacion_con_bicis_y_con_huecos(bici, monkeypatch):
    estaciones = [
        est(1, ORIGEN, 100, bicis=0, huecos=9),      # la más cercana al origen, sin bicis: se salta
        est(2, ORIGEN, 200, bicis=4, huecos=0),      # con bicis (origen); sin huecos (no vale de destino)
        est(3, DESTINO, 100, bicis=9, huecos=0),     # la más cercana al destino, llena: se salta
        est(4, DESTINO, 300, bicis=0, huecos=6),     # con huecos
    ]
    r = bici.elegir_estaciones(estaciones, ORIGEN, DESTINO)
    assert r["estado"] == "ok"
    assert r["origen"]["id"] == 2 and r["destino"]["id"] == 4
    assert r["origen"]["distancia_m"] == 200 and r["destino"]["distancia_m"] == 300
    # Los mínimos son los de config.
    monkeypatch.setattr(config, "BICI_MIN_BICIS", 5)
    assert bici.elegir_estaciones(estaciones, ORIGEN, DESTINO) == {"estado": "no_ofrecida", "motivo": "sin_bicis_origen"}
    monkeypatch.setattr(config, "BICI_MIN_BICIS", 1)
    monkeypatch.setattr(config, "BICI_MIN_HUECOS", 7)
    assert bici.elegir_estaciones(estaciones, ORIGEN, DESTINO) == {"estado": "no_ofrecida", "motivo": "sin_huecos_destino"}


def test_la_mas_cercana_gana_aunque_este_despues_en_la_lista(bici):
    estaciones = [est(1, ORIGEN, 400), est(2, ORIGEN, 50), est(3, DESTINO, 400), est(4, DESTINO, 50)]
    r = bici.elegir_estaciones(estaciones, ORIGEN, DESTINO)
    assert (r["origen"]["id"], r["destino"]["id"]) == (2, 4)


def test_inactiva_y_radio(bici, monkeypatch):
    destino_ok = est(9, DESTINO, 50)
    # Una inactiva más cercana se descarta y se usa la siguiente activa.
    r = bici.elegir_estaciones([est(1, ORIGEN, 50, activa=False), est(2, ORIGEN, 300), destino_ok], ORIGEN, DESTINO)
    assert r["origen"]["id"] == 2
    # Solo hay una a más de BICI_ESTACION_RADIO_MAX_M: no vale, aunque tenga bicis.
    lejos = est(3, ORIGEN, 600)
    assert bici.elegir_estaciones([lejos, destino_ok], ORIGEN, DESTINO) == {"estado": "no_ofrecida", "motivo": "sin_bicis_origen"}
    assert bici.elegir_estaciones([est(4, ORIGEN, 50), est(5, DESTINO, 600)], ORIGEN, DESTINO) == \
        {"estado": "no_ofrecida", "motivo": "sin_huecos_destino"}
    # El radio es inclusivo.
    d = bici.distancia_m(ORIGEN["lat"], ORIGEN["lon"], lejos["lat"], lejos["lon"])
    monkeypatch.setattr(config, "BICI_ESTACION_RADIO_MAX_M", d)
    assert bici.elegir_estaciones([lejos, destino_ok], ORIGEN, DESTINO)["origen"]["id"] == 3
    # Sin estaciones.
    assert bici.elegir_estaciones([], ORIGEN, DESTINO) == {"estado": "no_ofrecida", "motivo": "sin_bicis_origen"}


def test_misma_estacion_no_se_ofrece(bici, monkeypatch):
    monkeypatch.setattr(config, "BICI_ESTACION_RADIO_MAX_M", 10_000)     # una sola estación sirve a los dos extremos
    r = bici.elegir_estaciones([est(1, ORIGEN, 1500, bicis=3, huecos=3)], ORIGEN, DESTINO)
    assert r == {"estado": "no_ofrecida", "motivo": "misma_estacion"}


# --- T5: cliente de Google Routes para bici y a pie ---

CLAVE_GOOGLE = "CLAVE-GOOGLE-FALSA"
A = {"lat": 40.4169, "lon": -3.7035}
B = {"lat": 40.4285, "lon": -3.7021}


class RedPost:
    """Doble de `_post_json`: una respuesta (o excepción) por llamada y registro de las llamadas."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def __call__(self, url, headers=None, body=None, timeout=10):
        self.llamadas.append({"url": url, "headers": dict(headers or {}), "body": body, "timeout": timeout})
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


@pytest.fixture
def google(bici, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_ROUTES_API_KEY", CLAVE_GOOGLE)

    def con(*respuestas):
        red = RedPost(*respuestas)
        monkeypatch.setattr(bici, "_post_json", red)
        return red
    return types_namespace(bici, con)


def ruta(duracion="660s", **extra):
    return 200, {"routes": [{"duration": duracion, "distanceMeters": 2300, **extra}]}


def test_mascara_incluye_los_avisos():
    assert "routes.warnings" in config.GOOGLE_FIELD_MASK_BICI


def test_tramo_bici_una_llamada_con_bicycle(google):
    red = google.con(ruta("660s"))
    r = google.bici.tramo_google("BICYCLE", A, B)
    assert r["estado"] == "ok" and r["duracion_min"] == 11
    assert len(red.llamadas) == 1
    llamada = red.llamadas[0]
    assert llamada["url"] == config.GOOGLE_ROUTES_URL and llamada["timeout"] == config.GOOGLE_TIMEOUT_S
    assert llamada["body"]["travelMode"] == "BICYCLE"
    assert llamada["body"]["origin"] == {"location": {"latLng": {"latitude": A["lat"], "longitude": A["lon"]}}}
    assert llamada["body"]["destination"] == {"location": {"latLng": {"latitude": B["lat"], "longitude": B["lon"]}}}
    # Máscara propia (no la de transporte público) y clave solo en la cabecera.
    assert llamada["headers"] == {"X-Goog-Api-Key": CLAVE_GOOGLE, "X-Goog-FieldMask": config.GOOGLE_FIELD_MASK_BICI}
    assert CLAVE_GOOGLE not in json.dumps(llamada["body"]) and CLAVE_GOOGLE not in llamada["url"]


def test_tramos_a_pie_con_walk(google):
    red = google.con(ruta("185s"), ruta("90s"))
    assert google.bici.tramo_google("WALK", A, B)["duracion_min"] == 3
    assert google.bici.tramo_google("WALK", B, A)["duracion_min"] == 2
    assert [l["body"]["travelMode"] for l in red.llamadas] == ["WALK", "WALK"]
    assert red.llamadas[1]["body"]["origin"]["location"]["latLng"]["latitude"] == B["lat"]


def test_aviso_de_google_o_texto_fijo(google):
    google.con(ruta(warnings=["Aviso de Google uno.", "Aviso de Google dos."]),
               ruta(), ruta(warnings=[]), ruta(warnings=[None, "", 7]))
    assert google.bici.tramo_google("WALK", A, B)["aviso"] == "Aviso de Google uno. Aviso de Google dos."
    for _ in range(3):
        assert google.bici.tramo_google("WALK", A, B)["aviso"] == config.BICI_AVISO_GOOGLE


FALLOS_GOOGLE = [
    (403, {"error": {"message": f"clave {CLAVE_GOOGLE} rechazada"}}),
    (500, None),
    (200, {}),                                              # sin rutas
    (200, {"routes": []}),
    (200, {"routes": [{}]}),                                # sin duración
    (200, {"routes": [{"duration": "abc"}]}),
    (200, {"routes": [{"duration": 660}]}),
    (200, ["no", "es", "un", "objeto"]),
    TimeoutError(f"timeout con {CLAVE_GOOGLE}"),
    OSError(f"sin red {CLAVE_GOOGLE}"),
    ValueError(f"JSON inválido {CLAVE_GOOGLE}"),
]


@pytest.mark.parametrize("fallo", FALLOS_GOOGLE)
def test_google_falla_no_disponible(google, fallo, caplog, capsys):
    red = google.con(fallo)
    with caplog.at_level("DEBUG"):
        r = google.bici.tramo_google("BICYCLE", A, B)
    assert r == {"estado": "no_disponible"} and len(red.llamadas) == 1       # sin excepción ni reintento
    assert CLAVE_GOOGLE not in repr(r) + caplog.text + "".join(capsys.readouterr())


@pytest.mark.parametrize("clave", [None, "", "   "])
def test_google_sin_clave_no_llama(google, monkeypatch, clave):
    red = google.con()
    monkeypatch.setattr(config, "GOOGLE_ROUTES_API_KEY", clave)
    assert google.bici.tramo_google("BICYCLE", A, B) == {"estado": "no_disponible"} and red.llamadas == []


# Clima ya consultado (T13) que recibe `alternativa_bici` (T14): apto, no apto y sin dato.
CLIMA_APTO = {"estado": "ok", "temperatura_c": 16.1, "precipitacion_mm": 0.0, "codigo": 3, "viento_kmh": 11.2,
              "apto": True, "motivos": [], "fuente": "Open-Meteo", "licencia": "CC BY 4.0"}
CLIMA_LLUVIA = {**CLIMA_APTO, "precipitacion_mm": 1.4, "codigo": 61, "apto": False, "motivos": ["lluvia"]}
CLIMA_SIN_DATO = {"estado": "no_disponible"}

# --- T6: orquestador `alternativa_bici` y texto del párrafo ---

class Orquesta:
    """Dobles de `emt_estaciones` y `tramo_google` del módulo, con registro de llamadas."""

    def __init__(self, bici, monkeypatch, estaciones=None, tramos=None):
        self.emt_llamadas = 0
        self.google = []                        # (modo, origen, destino)
        self.estaciones = estaciones if estaciones is not None else {"estado": "ok", "estaciones": [
            est(1, ORIGEN, 120, bicis=6, huecos=2), est(2, DESTINO, 80, bicis=1, huecos=9)]}
        self.tramos = list(tramos if tramos is not None else [
            {"estado": "ok", "duracion_min": 11, "aviso": config.BICI_AVISO_GOOGLE},   # bici
            {"estado": "ok", "duracion_min": 4, "aviso": config.BICI_AVISO_GOOGLE},    # a pie: origen → estación
            {"estado": "ok", "duracion_min": 3, "aviso": config.BICI_AVISO_GOOGLE}])   # a pie: estación → destino
        monkeypatch.setattr(bici, "emt_estaciones", self._emt)
        monkeypatch.setattr(bici, "tramo_google", self._google)

    def _emt(self):
        self.emt_llamadas += 1
        if isinstance(self.estaciones, Exception):
            raise self.estaciones
        return self.estaciones

    def _google(self, modo, origen, destino):
        self.google.append((modo, origen, destino))
        respuesta = self.tramos.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


@pytest.fixture
def orq(bici, monkeypatch):
    def crear(**kw):
        o = Orquesta(bici, monkeypatch, **kw)
        o.bici = bici
        return o
    return crear


def test_alternativa_caso_feliz_tres_tramos(orq):
    o = orq()
    bici, texto = o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert bici["estado"] == "ok" and bici["motivo"] is None
    assert [t["modo"] for t in bici["tramos"]] == ["A pie", "Bici", "A pie"]
    assert [t["duracion_min"] for t in bici["tramos"]] == [4, 11, 3]
    assert bici["origen_estacion"] == {"nombre": "E1", "bicis": 6, "distancia_m": 120}
    assert bici["destino_estacion"] == {"nombre": "E2", "huecos": 9, "distancia_m": 80}
    # Orden de las llamadas: EMT una vez, Google bici, pie, pie; la bici va entre las dos estaciones.
    assert o.emt_llamadas == 1 and [g[0] for g in o.google] == ["BICYCLE", "WALK", "WALK"]
    assert (o.google[0][1]["id"], o.google[0][2]["id"]) == (1, 2)
    assert o.google[1][1] == ORIGEN and o.google[1][2]["id"] == 1
    assert o.google[2][1]["id"] == 2 and o.google[2][2] == DESTINO
    assert texto.startswith("Alternativa en bici (BiciMAD): ")


@pytest.mark.parametrize("hora_pedida, destino", [(True, DESTINO), (False, punto_a(500)), (False, punto_a(8000))])
def test_r1_r2_no_llaman_a_nada(orq, hora_pedida, destino):
    o = orq()
    bici, texto = o.bici.alternativa_bici(ORIGEN, destino, hora_pedida=hora_pedida, clima=CLIMA_APTO)
    assert bici["estado"] == "no_ofrecida" and o.emt_llamadas == 0 and o.google == []


def test_r3_r4_no_llaman_a_google(orq, monkeypatch):
    casos = [
        {"estado": "ok", "estaciones": []},                                        # sin bicis en el origen
        {"estado": "ok", "estaciones": [est(1, ORIGEN, 50, bicis=3, huecos=0)]},   # sin huecos en el destino
    ]
    for estaciones in casos:
        o = orq(estaciones=estaciones)
        assert o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)[0]["estado"] == "no_ofrecida"
        assert o.emt_llamadas == 1 and o.google == []
    monkeypatch.setattr(config, "BICI_ESTACION_RADIO_MAX_M", 10_000)               # R4: la misma estación
    o = orq(estaciones={"estado": "ok", "estaciones": [est(1, ORIGEN, 1500, bicis=3, huecos=3)]})
    assert o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)[0]["estado"] == "no_ofrecida"
    assert o.emt_llamadas == 1 and o.google == []


def test_motivo_solo_en_r3_r4(orq, monkeypatch):
    # R1 y R2: sin motivo y sin párrafo (RF-4).
    o = orq()
    for hora, destino in [(True, DESTINO), (False, punto_a(500))]:
        assert o.bici.alternativa_bici(ORIGEN, destino, hora_pedida=hora, clima=CLIMA_APTO) == (
            {"estado": "no_ofrecida", "motivo": None}, "")
    # R3 y R4: frase breve, que es también el texto que se añade al mensaje.
    esperadas = [
        ({"estado": "ok", "estaciones": []}, "No hay estaciones de BiciMAD con bicis cerca del origen."),
        ({"estado": "ok", "estaciones": [est(1, ORIGEN, 50)]},
         "No hay estaciones de BiciMAD con huecos libres cerca del destino."),
    ]
    for estaciones, frase in esperadas:
        bici, texto = orq(estaciones=estaciones).bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
        assert bici == {"estado": "no_ofrecida", "motivo": frase} and texto == frase
    monkeypatch.setattr(config, "BICI_ESTACION_RADIO_MAX_M", 10_000)
    bici, texto = orq(estaciones={"estado": "ok", "estaciones": [est(1, ORIGEN, 1500)]}).bici.alternativa_bici(
        ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert bici["estado"] == "no_ofrecida" and bici["motivo"] and texto == bici["motivo"]
    assert "distintas" in texto


def test_total_es_la_suma_y_etiqueta_fuentes(orq):
    bici, texto = orq().bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert bici["duracion_min"] == 4 + 11 + 3 == 18
    assert bici["fuentes"] == {"estaciones": "EMT BiciMAD", "tiempos": "Google Routes"}
    assert "18 min en total (Google Routes)" in texto and "EMT BiciMAD" in texto


def test_mensaje_indica_estaciones_y_disponibilidad(orq):
    bici, texto = orq().bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert "«E1»" in texto and "6 bicis" in texto and "«E2»" in texto and "9 huecos libres" in texto
    assert "al consultar" in texto and "puede haber cambiado" in texto
    assert bici["aviso"] == config.BICI_AVISO_GOOGLE and texto.endswith(f"Aviso: {config.BICI_AVISO_GOOGLE}")
    # Singular cuando solo hay una.
    una = {"estado": "ok", "estaciones": [est(1, ORIGEN, 120, bicis=1, huecos=2), est(2, DESTINO, 80, bicis=1, huecos=1)]}
    _, texto = orq(estaciones=una).bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert "1 bici " in texto and "1 hueco libre" in texto


def test_aviso_distinto_de_google_se_conserva_sin_repetir(orq):
    def ok(m, a):
        return {"estado": "ok", "duracion_min": m, "aviso": a}
    bici, _ = orq(tramos=[ok(11, "Aviso A"), ok(4, "Aviso A"), ok(3, "Aviso B")]).bici.alternativa_bici(
        ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert bici["aviso"] == "Aviso A Aviso B"


@pytest.mark.parametrize("falla_en", [0, 1, 2])
def test_si_falla_un_tramo_no_hay_alternativa_parcial(orq, falla_en):
    ok = {"estado": "ok", "duracion_min": 5, "aviso": config.BICI_AVISO_GOOGLE}
    tramos = [ok, ok, ok]
    tramos[falla_en] = {"estado": "no_disponible"}
    o = orq(tramos=tramos)
    bici, texto = o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert bici["estado"] == "no_disponible" and bici["motivo"] == texto
    assert not {"tramos", "duracion_min", "origen_estacion", "destino_estacion", "aviso"} & set(bici)
    assert len(o.google) == falla_en + 1                    # se corta al primer fallo


def test_emt_no_disponible_no_llama_a_google(orq):
    o = orq(estaciones={"estado": "no_disponible", "estaciones": []})
    bici, texto = o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)
    assert bici["estado"] == "no_disponible" and o.google == [] and o.emt_llamadas == 1
    assert texto == "La alternativa en bici (BiciMAD) no está disponible ahora."


@pytest.mark.parametrize("donde", ["emt", "google"])
def test_error_inesperado_no_rompe_la_ruta(orq, caplog, donde):
    o = orq(estaciones=KeyError("DATO-SENSIBLE")) if donde == "emt" else orq(tramos=[ValueError("DATO-SENSIBLE")])
    with caplog.at_level("DEBUG"):
        bici, texto = o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)    # no lanza
    assert bici["estado"] == "no_disponible" and texto == "La alternativa en bici (BiciMAD) no está disponible ahora."
    assert "DATO-SENSIBLE" not in repr((bici, texto)) + caplog.text
    assert caplog.records                                                           # queda registrado en el log interno


def test_mensajes_de_bici_en_espanol(orq):
    textos = [orq().bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)[1]]
    textos.append(orq(estaciones={"estado": "ok", "estaciones": []}).bici.alternativa_bici(ORIGEN, DESTINO, False, CLIMA_APTO)[1])
    textos.append(orq(estaciones={"estado": "no_disponible", "estaciones": []}).bici.alternativa_bici(
        ORIGEN, DESTINO, False, CLIMA_APTO)[1])
    for texto in textos:
        assert "BiciMAD" in texto
        assert not re.search(r"\b(bikes?|stations?|docks?|available|minutes?|walk|cycling)\b", texto, re.I)
    assert "estación" in textos[0] and "A pie" in textos[0] and "minutos" not in textos[0]


# --- T13: clima con Open-Meteo (apto_exterior pura y clima_origen). Campos reales: verificacion-open-meteo.md ---

def test_constantes_del_clima():
    assert config.OPEN_METEO_URL == "https://api.open-meteo.com/v1/forecast"
    assert config.OPEN_METEO_TIMEOUT_S > 0
    assert (config.CLIMA_TEMP_MIN_C, config.CLIMA_TEMP_MAX_C) == (5, 32)
    assert config.CLIMA_VIENTO_MAX_KMH == 30 and config.CLIMA_PRECIPITACION_MAX_MM == 0
    assert config.CLIMA_ATRIBUCION == "Datos meteorológicos de Open-Meteo.com (CC BY 4.0)"
    # Códigos WMO no aptos: llovizna y lluvia, nieve y tormenta (documentación de Open-Meteo).
    esperados = set(range(51, 58)) | set(range(61, 68)) | set(range(80, 83)) | set(range(71, 78)) \
        | {85, 86} | set(range(95, 100))
    assert set(config.CLIMA_CODIGOS_NO_APTOS) == esperados


def test_apto_exterior_cada_causa_y_los_bordes(bici):
    def apto(temp=16.1, lluvia=0.0, codigo=3, viento=11.2):
        return bici.apto_exterior(temp, lluvia, codigo, viento)

    assert apto() == (True, [])                                     # caso real de T12: nublado, 16,1 °C, 11,2 km/h
    # Bordes inclusivos: justo en el umbral es apto.
    assert apto(temp=5)[0] and apto(temp=32)[0] and apto(viento=30)[0] and apto(lluvia=0)[0]
    assert apto(temp=4.9) == (False, ["temperatura baja"])
    assert apto(temp=32.1) == (False, ["temperatura alta"])
    assert apto(viento=30.1) == (False, ["viento fuerte"])
    assert apto(lluvia=0.1) == (False, ["precipitación"])           # con código de cielo despejado
    for codigo in (0, 1, 2, 3, 45, 48):
        assert apto(codigo=codigo)[0]
    for codigo, motivo in [(51, "lluvia"), (57, "lluvia"), (61, "lluvia"), (67, "lluvia"), (80, "lluvia"), (82, "lluvia"),
                           (71, "nieve"), (77, "nieve"), (85, "nieve"), (86, "nieve"),
                           (95, "tormenta"), (96, "tormenta"), (99, "tormenta")]:
        assert apto(codigo=codigo) == (False, [motivo])
    for codigo in (58, 68, 78, 83, 87, 94):                         # fuera de los intervalos no aptos
        assert apto(codigo=codigo)[0]
    # Varias causas a la vez, sin repetir motivos (lluvia con precipitación).
    assert apto(temp=2, lluvia=1.2, codigo=61, viento=40) == (
        False, ["temperatura baja", "lluvia", "viento fuerte"])
    # Los umbrales son los de config.
    assert apto(temp=40)[0] is False


def test_apto_exterior_usa_los_umbrales_de_config(bici, monkeypatch):
    monkeypatch.setattr(config, "CLIMA_TEMP_MAX_C", 40)
    monkeypatch.setattr(config, "CLIMA_VIENTO_MAX_KMH", 50)
    monkeypatch.setattr(config, "CLIMA_PRECIPITACION_MAX_MM", 0.5)
    assert bici.apto_exterior(38, 0.4, 3, 45)[0]
    assert not bici.apto_exterior(41, 0, 3, 0)[0]
    assert not bici.apto_exterior(20, 0.6, 3, 0)[0]


RESPUESTA_METEO = {"latitude": 40.417583, "longitude": -3.739399, "elevation": 666.0,
                   "current_units": {"temperature_2m": "°C", "precipitation": "mm", "weather_code": "wmo code",
                                     "wind_speed_10m": "km/h"},
                   "current": {"time": "2026-10-20T13:00", "interval": 900, "temperature_2m": 16.1,
                               "precipitation": 0.00, "weather_code": 3, "wind_speed_10m": 11.2}}


def con_current(**cambios):
    actual = {**RESPUESTA_METEO["current"], **cambios}
    return 200, {**RESPUESTA_METEO, "current": actual}


@pytest.fixture
def meteo(bici, monkeypatch):
    def con(*respuestas):
        red = Red(*respuestas)
        monkeypatch.setattr(bici, "_get_json", red)
        return red
    return types_namespace(bici, con)


def test_clima_una_llamada_con_las_cuatro_variables(meteo):
    from urllib.parse import parse_qs, urlsplit
    red = meteo.con((200, RESPUESTA_METEO))
    r = meteo.bici.clima_origen(ORIGEN)
    assert r == {"estado": "ok", "temperatura_c": 16.1, "precipitacion_mm": 0.0, "codigo": 3, "viento_kmh": 11.2,
                 "apto": True, "motivos": [], "fuente": "Open-Meteo", "licencia": "CC BY 4.0"}
    assert len(red.llamadas) == 1
    url, cabeceras, timeout = red.llamadas[0]
    partes = urlsplit(url)
    assert f"{partes.scheme}://{partes.netloc}{partes.path}" == config.OPEN_METEO_URL
    consulta = parse_qs(partes.query)
    assert consulta["latitude"] == [str(ORIGEN["lat"])] and consulta["longitude"] == [str(ORIGEN["lon"])]
    assert consulta["current"] == ["temperature_2m,precipitation,weather_code,wind_speed_10m"]
    assert cabeceras == {} and timeout == config.OPEN_METEO_TIMEOUT_S          # sin clave ni credenciales


def test_clima_no_apto_lleva_los_motivos(meteo):
    meteo.con(con_current(weather_code=61, precipitation=1.4, wind_speed_10m=35.0))
    r = meteo.bici.clima_origen(ORIGEN)
    assert r["estado"] == "ok" and r["apto"] is False and r["motivos"] == ["lluvia", "viento fuerte"]
    assert r["precipitacion_mm"] == 1.4 and r["codigo"] == 61


def _sin(clave):
    actual = {k: v for k, v in RESPUESTA_METEO["current"].items() if k != clave}
    return 200, {**RESPUESTA_METEO, "current": actual}


FALLOS_METEO = [
    (429, {"reason": "Too many requests", "error": True}),
    (500, None),
    (200, {}),
    (200, {"current": None}),
    (200, {"current": "no es un objeto"}),
    (200, ["no", "es", "un", "objeto"]),
    _sin("temperature_2m"), _sin("precipitation"), _sin("weather_code"), _sin("wind_speed_10m"),
    con_current(temperature_2m=None),
    con_current(temperature_2m="16.1"),
    con_current(wind_speed_10m=True),
    con_current(weather_code=3.5),
    con_current(precipitation=float("nan")),
    TimeoutError("timeout"),
    OSError("sin red"),
    ValueError("JSON inválido"),
]


@pytest.mark.parametrize("fallo", FALLOS_METEO)
def test_open_meteo_falla_ruta_intacta_y_sin_bici(meteo, fallo):
    red = meteo.con(fallo)
    assert meteo.bici.clima_origen(ORIGEN) == {"estado": "no_disponible"}     # sin excepción, sin datos inventados
    assert len(red.llamadas) == 1                                              # sin reintentos


@pytest.mark.parametrize("origen", [{}, None, {"lat": "x", "lon": None}])
def test_origen_invalido_no_llama_y_no_rompe(meteo, origen):
    red = meteo.con()
    assert meteo.bici.clima_origen(origen) == {"estado": "no_disponible"} and red.llamadas == []


def test_error_inesperado_en_clima_no_rompe_la_ruta(meteo, monkeypatch, caplog):
    def explota(*args, **kwargs):
        raise RuntimeError("DATO-SENSIBLE")
    monkeypatch.setattr(meteo.bici, "_get_json", explota)
    with caplog.at_level("DEBUG"):
        r = meteo.bici.clima_origen(ORIGEN)
    assert r == {"estado": "no_disponible"}
    assert "DATO-SENSIBLE" not in repr(r) + caplog.text and caplog.records     # registrado sin el texto de la excepción


# --- T14: integración del clima (R0, LESS_WALKING, línea y campo `clima`) ---

@pytest.mark.parametrize("clima", [CLIMA_LLUVIA, CLIMA_SIN_DATO])
def test_no_apto_o_sin_dato_no_ofrece_bici_ni_llama_a_la_emt(orq, clima):
    o = orq()
    assert o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=clima) == (
        {"estado": "no_ofrecida", "motivo": None}, "")                         # el clima ya lo explica su línea
    assert o.emt_llamadas == 0 and o.google == []


def test_apto_aplica_la_regla_de_oferta(orq):
    o = orq()
    assert o.bici.alternativa_bici(ORIGEN, DESTINO, hora_pedida=False, clima=CLIMA_APTO)[0]["estado"] == "ok"
    assert o.emt_llamadas == 1


def test_texto_del_clima(bici):
    assert bici.texto_clima(CLIMA_SIN_DATO) == ""
    apto = bici.texto_clima(CLIMA_APTO)
    assert apto == ("Tiempo en el origen ahora: 16 °C, sin precipitación, viento 11 km/h (apto para exterior). "
                    f"{config.CLIMA_ATRIBUCION}.")
    no_apto = bici.texto_clima({**CLIMA_LLUVIA, "motivos": ["lluvia", "viento fuerte"]})
    assert "precipitación 1.4 mm" in no_apto and "no apto para exterior: lluvia, viento fuerte" in no_apto
    assert "menos tramos a pie" in no_apto and no_apto.endswith(f"{config.CLIMA_ATRIBUCION}.")


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def cuerpo_google(esc):
    assert len(esc.cuerpos_google) == 1
    return esc.cuerpos_google[0]


def test_no_apto_pide_less_walking_sin_llamadas_extra(esc):
    esc.meteo = (200, METEO_LLUVIA)
    r = pr.planificar_ruta("Sol", "Bernabéu")
    prefs = cuerpo_google(esc)["transitPreferences"]
    assert prefs["routingPreference"] == "LESS_WALKING" and prefs["allowedTravelModes"] == config.MODOS_GOOGLE
    assert esc.cuantas("google") == 1 and len(esc.llamadas_meteo) == 1 and r["estado"] == "ok"


def test_consultar_google_sin_preferencia_es_identica(esc):
    origen, destino = {"lat": 40.4169, "lon": -3.7035}, {"lat": 40.4531, "lon": -3.6883}
    pr.consultar_google(origen, destino)
    pr.consultar_google(origen, destino, preferencia_transito=None)
    pr.consultar_google(origen, destino, preferencia_transito="LESS_WALKING")
    sin, none, con = esc.cuerpos_google
    assert sin == none and "routingPreference" not in sin["transitPreferences"]
    assert con["transitPreferences"] == {**sin["transitPreferences"], "routingPreference": "LESS_WALKING"}
    assert {k: v for k, v in con.items() if k != "transitPreferences"} == \
        {k: v for k, v in sin.items() if k != "transitPreferences"}


@pytest.mark.parametrize("meteo", [(200, {}), TimeoutError("t"), (429, {"error": True}), (200, METEO_APTO)])
def test_apto_o_sin_dato_peticion_de_siempre(esc, meteo):
    esc.meteo = meteo
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert "routingPreference" not in cuerpo_google(esc)["transitPreferences"]
    assert r["estado"] == "ok" and r["ruta"]["duracion_min"] == 22          # la ruta llega intacta
    assert len(esc.llamadas_meteo) == 1


def test_linea_de_clima_con_atribucion(esc):
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert "Tiempo en el origen ahora: 16 °C, sin precipitación, viento 11 km/h (apto para exterior)." in r["mensaje"]
    assert r["mensaje"].endswith(f"{config.CLIMA_ATRIBUCION}.")
    esc.nominatim, esc.meteo = [[SOL], [BERNABEU]], (200, METEO_LLUVIA)
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert "no apto para exterior: lluvia" in r["mensaje"] and "menos tramos a pie" in r["mensaje"]
    assert config.CLIMA_ATRIBUCION in r["mensaje"]
    # Sin dato de clima: ni línea ni atribución (RF-25).
    esc.nominatim, esc.meteo = [[SOL], [BERNABEU]], TimeoutError("t")
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert "Tiempo en el origen" not in r["mensaje"] and "Open-Meteo" not in r["mensaje"]


def test_campo_clima_solo_en_ok_sin_hora(esc):
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "ok" and r["clima"] == {
        "estado": "ok", "temperatura_c": 16.1, "precipitacion_mm": 0.0, "codigo": 3, "viento_kmh": 11.2,
        "apto": True, "motivos": [], "fuente": "Open-Meteo", "licencia": "CC BY 4.0"}
    # Sin dato: el campo existe con estado no_disponible.
    esc.nominatim, esc.meteo = [[SOL], [BERNABEU]], TimeoutError("t")
    assert pr.planificar_ruta("Sol", "Bernabéu")["clima"] == {"estado": "no_disponible"}
    # Estados que no son ok: sin campo clima, aunque se haya consultado.
    for google_roto in (TimeoutError("t"), {}):
        esc.nominatim, esc.meteo, esc.google = [[SOL], [BERNABEU]], (200, METEO_APTO), google_roto
        r = pr.planificar_ruta("Sol", "Bernabéu")
        assert r["estado"] != "ok" and "clima" not in r


def test_hora_pedida_no_consulta_el_clima(esc):
    for args in ({"hora_salida": "2026-10-15T09:00"}, {"hora_llegada": "2026-10-15T10:00"}):
        esc.nominatim = [[SOL], [BERNABEU]]
        esc.cuerpos_google.clear()
        r = pr.planificar_ruta("Sol", "Bernabéu", **args)
        assert r["estado"] == "ok" and "clima" not in r and "Tiempo en el origen" not in r["mensaje"]
        assert "routingPreference" not in cuerpo_google(esc)["transitPreferences"]
    assert esc.llamadas_meteo == []


def test_limite_open_meteo_1(esc):
    pr.planificar_ruta("Sol", "Bernabéu")
    assert len(esc.llamadas_meteo) == 1 and esc.cuantas("google") == 1
    # El clima se pide después de geocodificar y antes de Google.
    assert esc.secuencia[:4] == ["nominatim", "nominatim", "meteo", "google"]
    # Sin Google no hay clima: extremo ambiguo y fuera de cobertura.
    for nominatim in ([[SOL, ATOCHA], [BERNABEU]], [[BARCELONA], [BERNABEU]]):
        esc.nominatim, esc.llamadas_meteo[:] = nominatim, []
        assert pr.planificar_ruta("Sol", "Bernabéu")["estado"] in ("ambigua", "fuera_cobertura")
        assert esc.llamadas_meteo == []


# --- T7: gancho de `alternativa_bici` en `planificar_ruta` y campo `bici` (Escenario con la red de bici simulada) ---

CLAVES_BASE = {"estado", "mensaje", "hora_salida", "titulo", "hora_llegada", "salida_resultante", "origen", "destino",
               "ruta", "zona", "precio"}


def ruta_con_bici(esc, **args):
    """Consulta Sol → Bernabéu con la alternativa real (y la red de bici simulada) y la misma sin ella."""
    esc.bici_real()
    return pr.planificar_ruta("Sol", "Bernabéu", **args)


def sin_bici(monkeypatch, **args):
    """La misma consulta con la alternativa desactivada: referencia de lo que no debe cambiar."""
    esc = Escenario(monkeypatch)
    return esc, pr.planificar_ruta("Sol", "Bernabéu", **args)


def test_alternativa_junto_a_la_ruta_sin_cambiar_su_estado(monkeypatch):
    _, base = sin_bici(monkeypatch)
    esc = Escenario(monkeypatch)
    r = ruta_con_bici(esc)
    assert r["estado"] == base["estado"] == "ok"
    assert r["bici"]["estado"] == "ok" and r["bici"]["duracion_min"] == 18
    # La ruta en transporte público no se modifica: mismos campos y el mensaje solo crece al final.
    for campo in CLAVES_BASE - {"mensaje"}:
        assert r[campo] == base[campo]
    assert r["mensaje"].startswith(base["mensaje"]) and r["mensaje"] != base["mensaje"]
    assert "Alternativa en bici (BiciMAD): 18 min en total (Google Routes)." in r["mensaje"]
    assert r["mensaje"].index("Tiempo en el origen") < r["mensaje"].index("Alternativa en bici")   # la bici va la última


def test_campo_bici_solo_en_ok_y_campos_existentes_intactos(monkeypatch):
    esc = Escenario(monkeypatch)
    r = ruta_con_bici(esc)
    assert set(r) == CLAVES_BASE | {"clima", "bici"}                       # solo se añaden clima y bici
    # Estados que no son ok: sin campo bici (y sin llamadas de bici).
    for cambio in ({"google": TimeoutError("t")}, {"google": {}}, {"nominatim": [[SOL, ATOCHA], [BERNABEU]]},
                   {"nominatim": [[BARCELONA], [BERNABEU]]}):
        e = Escenario(monkeypatch)
        e.bici_real()
        for k, v in cambio.items():
            setattr(e, k, v)
        r = pr.planificar_ruta("Sol", "Bernabéu")
        assert r["estado"] != "ok" and "bici" not in r and e.llamadas_bici == []


def test_enganche_unico_en_planificar_ruta():
    import ast
    fuente = (RAIZ / "src" / "tools" / "planificar_ruta.py").read_text(encoding="utf-8")
    assert fuente.count("alternativa_bici(") == 1                          # un único punto de enganche
    for trozo in ("BICYCLE", "emt_estaciones", "elegir_estaciones", "BICI_", "EMT_"):
        assert trozo not in fuente                                         # sin lógica de BiciMAD en este archivo
    arbol = ast.parse(fuente)
    for nodo in arbol.body:                                                 # bicimad solo se importa de forma perezosa
        if isinstance(nodo, ast.ImportFrom):
            assert "bicimad" not in (nodo.module or "") and all(a.name != "bicimad" for a in nodo.names)


def test_el_rag_mantiene_sus_dos_llamadas(monkeypatch):
    esc = Escenario(monkeypatch)
    ruta_con_bici(esc)
    assert esc.cuantas("rag") == 2 and "zona tarifaria" in esc.preguntas[0] and "precio" in esc.preguntas[1]
    assert not any("bici" in p.lower() or "bicimad" in p.lower() for p in esc.preguntas)


def test_limites_de_llamadas_emt_2_google_4_nominatim_2(monkeypatch):
    esc = Escenario(monkeypatch)
    ruta_con_bici(esc)
    assert esc.cuantas("nominatim") == 2 and len(esc.llamadas_meteo) == 1
    assert [u for u, _ in esc.llamadas_bici if "emt" in u] == [config.EMT_LOGIN_URL, config.EMT_ESTACIONES_URL]
    assert esc.cuantas("google") + len([u for u, _ in esc.llamadas_bici if u == config.GOOGLE_ROUTES_URL]) == 4
    assert esc.secuencia.index("meteo") < esc.secuencia.index("google")
    # Segunda consulta en el mismo proceso: el token de la EMT se reutiliza (una llamada menos).
    esc.nominatim = [[SOL], [BERNABEU]]
    esc.llamadas_bici.clear()
    pr.planificar_ruta("Sol", "Bernabéu")
    assert [u for u, _ in esc.llamadas_bici if "emt" in u] == [config.EMT_ESTACIONES_URL]


def test_fallo_de_la_emt_deja_la_ruta_intacta_con_aviso(monkeypatch):
    _, base = sin_bici(monkeypatch)
    for fallo in ((403, {"code": "84", "description": "", "data": []}), TimeoutError("t")):
        esc = Escenario(monkeypatch)
        esc.emt_login = fallo
        r = ruta_con_bici(esc)
        assert r["estado"] == "ok" and r["bici"] == {"estado": "no_disponible", "motivo": bicimad.FRASE_NO_DISPONIBLE}
        assert r["mensaje"].endswith(bicimad.FRASE_NO_DISPONIBLE) and r["mensaje"].startswith(base["mensaje"])
        assert r["ruta"] == base["ruta"] and r["zona"] == base["zona"] and r["precio"] == base["precio"]
        assert [u for u, _ in esc.llamadas_bici if u == config.GOOGLE_ROUTES_URL] == []   # sin Google de bici


@pytest.mark.parametrize("falla_en, llamadas", [(0, 1), (1, 2), (2, 3)])
def test_fallo_de_google_en_la_bici_deja_la_ruta_intacta_con_aviso(monkeypatch, falla_en, llamadas):
    _, base = sin_bici(monkeypatch)
    esc = Escenario(monkeypatch)
    esc.tramos_bici[falla_en] = TimeoutError("t")
    r = ruta_con_bici(esc)
    assert r["estado"] == "ok" and r["bici"]["estado"] == "no_disponible" and "tramos" not in r["bici"]
    assert r["mensaje"].endswith(bicimad.FRASE_NO_DISPONIBLE) and r["ruta"] == base["ruta"]
    assert len([u for u, _ in esc.llamadas_bici if u == config.GOOGLE_ROUTES_URL]) == llamadas


def test_sin_oferta_no_hay_llamadas_de_bici(monkeypatch):
    # R1 (hora pedida) y R0 (mal tiempo): bici no_ofrecida, sin párrafo y sin llamar a la EMT ni a Google de bici.
    esc = Escenario(monkeypatch)
    r = ruta_con_bici(esc, hora_salida="2026-10-15T09:00")
    assert r["bici"] == {"estado": "no_ofrecida", "motivo": None} and "Alternativa en bici" not in r["mensaje"]
    assert esc.llamadas_bici == []
    esc = Escenario(monkeypatch)
    esc.meteo = (200, METEO_LLUVIA)
    r = ruta_con_bici(esc)
    assert r["bici"] == {"estado": "no_ofrecida", "motivo": None} and esc.llamadas_bici == []
