"""Spec 010, T12 (RF-35): Open-Meteo verifica el certificado con el bundle de `certifi`; la EMT y Google no cambian. Sin red."""
import io
import json
import ssl
import sys
from pathlib import Path

import pytest

from src.tools import bicimad

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = {"lat": 40.4169, "lon": -3.7035}


class Respuesta(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def urlopen(monkeypatch):
    """Doble de `urlopen` que guarda los argumentos con los que se llama."""
    llamadas = []

    def falso(peticion, timeout=None, **kw):
        llamadas.append(kw)
        return Respuesta(json.dumps({"current": {}}).encode())

    monkeypatch.setattr(bicimad.urllib.request, "urlopen", falso)
    return llamadas


def test_con_certifi_el_contexto_usa_su_bundle_y_verifica(monkeypatch, urlopen):
    certifi = pytest.importorskip("certifi")
    creados = []
    real = ssl.create_default_context

    def espia(*a, **kw):
        ctx = real(*a, **kw)
        creados.append((kw, ctx))
        return ctx

    monkeypatch.setattr(bicimad.ssl, "create_default_context", espia)
    bicimad._get_json("https://ejemplo.test/x", timeout=5, contexto_certifi=True)
    (kw, ctx), = creados
    assert kw == {"cafile": certifi.where()}                       # el bundle de certifi
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname is True
    assert urlopen == [{"context": ctx}]                           # y es el que usa la petición


def test_sin_certifi_se_usa_el_contexto_por_defecto(monkeypatch, urlopen):
    monkeypatch.setitem(sys.modules, "certifi", None)             # `import certifi` falla con ImportError
    assert bicimad._contexto_ssl(True) is None
    bicimad._get_json("https://ejemplo.test/x", contexto_certifi=True)
    assert urlopen == [{}]                                         # sin `context`: el por defecto, que también verifica


def test_con_bundle_ilegible_tambien_se_usa_el_contexto_por_defecto(monkeypatch):
    pytest.importorskip("certifi")

    def roto(*a, **kw):
        raise OSError("bundle ilegible")

    monkeypatch.setattr(bicimad.ssl, "create_default_context", roto)
    assert bicimad._contexto_ssl(True) is None


def test_por_defecto_no_se_pasa_contexto(urlopen):
    bicimad._get_json("https://ejemplo.test/x")                    # EMT: la llamada es la de siempre
    assert urlopen == [{}] and bicimad._contexto_ssl(False) is None


def test_clima_origen_pide_el_bundle_de_certifi(monkeypatch):
    pedidos = []

    def get(url, headers=None, timeout=10, contexto_certifi=False):
        pedidos.append((url, contexto_certifi))
        return 200, {"current": {"temperature_2m": 16.1, "precipitation": 0.0, "weather_code": 3, "wind_speed_10m": 11.2}}

    monkeypatch.setattr(bicimad, "_get_json", get)
    assert bicimad.clima_origen(ORIGEN)["estado"] == "ok"
    assert [c for _, c in pedidos] == [True] and pedidos[0][0].startswith("https://api.open-meteo.com")


def test_la_emt_no_usa_el_bundle_de_certifi(monkeypatch):
    import config
    monkeypatch.setattr(config, "EMT_CLIENT_ID", "ID-DE-TEST")
    monkeypatch.setattr(config, "EMT_PASS_KEY", "CLAVE-DE-TEST")
    monkeypatch.setattr(bicimad, "_token", None)
    pedidos = []

    def get(url, headers=None, timeout=10, **kw):
        pedidos.append((url, kw))
        return 500, None

    monkeypatch.setattr(bicimad, "_get_json", get)
    bicimad.emt_estaciones()
    assert pedidos and all(kw == {} for _, kw in pedidos)         # ni el login ni la lista piden contexto de certifi


def test_nunca_se_desactiva_la_verificacion_de_certificados():
    prohibidos = ("CERT_NONE", "_create_unverified_context", "check_hostname = False", "check_hostname=False",
                  "verify=False", "_create_stdlib_context")
    for ruta in (RAIZ / "src").rglob("*.py"):
        fuente = ruta.read_text(encoding="utf-8")
        for texto in prohibidos:
            assert texto not in fuente, f"{texto} en {ruta.relative_to(RAIZ)}"
