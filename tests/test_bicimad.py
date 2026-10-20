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
import importlib
import re
import time
from pathlib import Path

import pytest

import config

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
