"""Tests de configuración y requisitos no funcionales de planificar_ruta (spec 004). No usan API."""
import importlib
import re

import pytest

import config
from rag.prompt import PROMPT_TEMPLATE


@pytest.fixture
def recargar_config():
    """Permite recargar `config` con otro entorno y la deja como estaba al terminar."""
    yield lambda: importlib.reload(config)
    importlib.reload(config)


def test_clave_solo_del_entorno(monkeypatch, recargar_config):
    # RNF Secretos: la clave de Google Routes se lee del entorno, nunca está escrita en el código.
    monkeypatch.setenv("GOOGLE_ROUTES_API_KEY", "clave-falsa-de-test")
    recargar_config()
    assert config.GOOGLE_ROUTES_API_KEY == "clave-falsa-de-test"
    codigo = open(config.__file__, encoding="utf-8").read()
    assert re.search(r'GOOGLE_ROUTES_API_KEY\s*=\s*os\.getenv\("GOOGLE_ROUTES_API_KEY"\)', codigo)


def test_contacto_nominatim_solo_del_entorno(monkeypatch, recargar_config):
    # RNF Uso de Nominatim: el User-Agent identifica la app y añade el contacto del entorno.
    monkeypatch.setenv("NOMINATIM_CONTACTO", "contacto-falso@example.com")
    recargar_config()
    assert "MadridRumbo" in config.NOMINATIM_USER_AGENT
    assert "contacto-falso@example.com" in config.NOMINATIM_USER_AGENT
    codigo = open(config.__file__, encoding="utf-8").read()
    assert "contacto-falso" not in codigo and "@" not in re.sub(r"#.*", "", codigo)


def test_intervalo_nominatim_respeta_politica_de_uso():
    # RNF Uso de Nominatim: no más de 1 petición por segundo.
    assert config.NOMINATIM_INTERVALO_S >= 1.0


def test_frase_de_abstencion_sigue_en_el_prompt_del_rag():
    # Plan, Riesgos: si alguien cambia la frase en rag/prompt.py, este test avisa.
    assert config.FRASE_ABSTENCION in PROMPT_TEMPLATE


def test_env_example_declara_los_nombres_sin_valor():
    # RNF Secretos: .env.example lista los nombres nuevos y no lleva ningún valor.
    lineas = (config.BASE_DIR / ".env.example").read_text(encoding="utf-8").splitlines()
    for nombre in ("GOOGLE_ROUTES_API_KEY", "NOMINATIM_CONTACTO"):
        assert f"{nombre}=" in [linea.strip() for linea in lineas]


def test_limites_y_listas_de_config():
    # Plan, Configuración: todos los límites y listas viven en config.py.
    assert config.MAX_CANDIDATOS_MOSTRAR >= 1
    assert config.ANTELACION_MAX_DIAS >= 1
    assert config.RADIO_MISMA_UBICACION_M > 0
    assert config.TITULO_POR_DEFECTO in config.TITULOS_TRANSPORTE
    assert set(config.TITULOS_TRANSPORTE) == {"billete sencillo", "billete de 10 viajes"}
    assert set(config.MODOS_GOOGLE) == {"SUBWAY", "LIGHT_RAIL", "BUS", "TRAIN"}
    assert config.TIPOS_VEHICULO_ACEPTADOS
    # Las plantillas de pregunta al RAG aceptan los datos de la ruta.
    config.PREGUNTA_ZONA.format(origen="A", destino="B")
    config.PREGUNTA_PRECIO.format(origen="A", destino="B", titulo="billete sencillo")


def test_intervalo_y_user_agent(monkeypatch):
    # RNF Uso de Nominatim: identificación con el User-Agent de config y al menos 1 s entre peticiones.
    from src.tools import planificar_ruta as pr

    esperas, reloj, cabeceras = [], [1000.0], []

    def sleep(segundos):
        esperas.append(segundos)
        reloj[0] += segundos

    def http_json(url, *, headers=None, body=None, timeout=10):
        cabeceras.append(headers)
        return []

    monkeypatch.setattr(pr, "_http_json", http_json)
    monkeypatch.setattr(pr.time, "sleep", sleep)
    monkeypatch.setattr(pr.time, "monotonic", lambda: reloj[0])
    monkeypatch.setattr(pr, "_ultima_peticion_nominatim", None)
    monkeypatch.setattr(config, "NOMINATIM_USER_AGENT", "MadridRumbo/1.0 (contacto-de-test)")

    pr.geocodificar("a")
    assert esperas == []                       # la primera petición no espera
    reloj[0] += 0.3                            # pasan 0,3 s antes de la siguiente
    pr.geocodificar("b")
    assert len(esperas) == 1 and esperas[0] == pytest.approx(config.NOMINATIM_INTERVALO_S - 0.3)
    reloj[0] += 5                              # pasan 5 s: ya no hace falta esperar
    pr.geocodificar("c")
    assert len(esperas) == 1
    assert all(c["User-Agent"] == "MadridRumbo/1.0 (contacto-de-test)" for c in cabeceras)


def test_ningun_correo_escrito_en_el_codigo():
    # RNF Uso de Nominatim: el contacto sale del entorno; el módulo de la tool no contiene correos.
    from src.tools import planificar_ruta as pr

    codigo = open(pr.__file__, encoding="utf-8").read()
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", codigo)


def test_los_tests_no_hacen_peticiones_reales():
    # Red de seguridad de tests/conftest.py: urlopen sin doble propio falla.
    import urllib.request

    with pytest.raises(AssertionError):
        urllib.request.urlopen("http://ejemplo.test")
