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
    assert config.TITULO_POR_DEFECTO == "billete sencillo" and not hasattr(config, "TITULOS_TRANSPORTE")
    assert config.TITULO_LONGITUD_MAX == 60 >= len(config.TITULO_POR_DEFECTO)
    assert set(config.MODOS_GOOGLE) == {"SUBWAY", "LIGHT_RAIL", "BUS", "TRAIN"}
    assert config.TIPOS_VEHICULO_ACEPTADOS
    # Las plantillas de pregunta al RAG aceptan los datos de la ruta.
    config.PREGUNTA_ZONA.format(origen="A", destino="B")
    config.PREGUNTA_PRECIO.format(titulo="billete sencillo", zona="Zona A")


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


def test_maximo_2_nominatim_y_1_google(monkeypatch):
    # RNF Coste: una consulta hace como mucho 2 llamadas a Nominatim y 1 a Google (y 2 al RAG: zona y precio),
    # sea cual sea el camino: éxito, Google caído, sin ruta, ambigua, título no disponible o Nominatim caído.
    from src.tools import planificar_ruta as pr
    from tests.dobles_ruta import ATOCHA, BERNABEU, SOL, Escenario

    casos = [
        ({}, {}),
        ({"google": TimeoutError("t")}, {}),
        ({"google": {}}, {}),
        ({"nominatim": [[SOL, ATOCHA], [BERNABEU]]}, {}),
        ({}, {"titulo": "abono"}),
        ({"nominatim": [TimeoutError("t")]}, {}),
    ]
    for cambios, args in casos:
        esc = Escenario(monkeypatch)
        for k, v in cambios.items():
            setattr(esc, k, v)
        pr.planificar_ruta("Sol", "Bernabéu", **args)
        assert esc.cuantas("nominatim") <= 2 and esc.cuantas("google") <= 1 and esc.cuantas("rag") <= 2, cambios
    esc = Escenario(monkeypatch)
    pr.planificar_ruta("Sol", "Bernabéu")
    assert (esc.cuantas("nominatim"), esc.cuantas("google"), esc.cuantas("rag")) == (2, 1, 2)


# --- T13: error_interno (RF-42) y mensajes en español ---
import logging
import re

from tests.dobles_ruta import Escenario as _Escenario

SECRETO = "CLAVE-SECRETA-XYZ"
TEXTO_EXCEPCION = f"fallo interno con clave {SECRETO} en C:/datos/privado.json"


@pytest.fixture
def esc(monkeypatch):
    return _Escenario(monkeypatch)


def _fallar(*_args, **_kwargs):
    raise RuntimeError(TEXTO_EXCEPCION)


# Punto donde revienta la herramienta → llamadas externas que pueden haberse hecho ya (nominatim, google, rag).
PUNTOS_DE_FALLO = {
    "geocodificar": (0, 0, 0),
    "clasificar_candidatos": (1, 0, 0),   # falla al clasificar el origen, antes de geocodificar el destino
    "consultar_google": (2, 0, 0),
    "interpretar_respuesta_google": (2, 1, 0),
    "consultar_tarifa": (2, 1, 0),
}


@pytest.mark.parametrize("punto", PUNTOS_DE_FALLO)
def test_error_inesperado_da_error_interno(esc, monkeypatch, punto):
    # RF-42: cualquier excepción inesperada → error_interno, sin lanzar, con cabecera y mensaje genérico en español.
    from src.tools import planificar_ruta as pr

    monkeypatch.setattr(pr, punto, _fallar)
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo="billete de 10 viajes")
    assert list(r)[0] == "estado" and r["estado"] == "error_interno"
    assert r["mensaje"].startswith("Salida: ahora (15/10/2026 08:12) · Título: billete de 10 viajes. ")
    assert "Ocurrió un error inesperado" in r["mensaje"]
    assert r["ruta"] is None and r["origen"] is None
    # Ni el texto de la excepción, ni la clave, ni rutas o nombres internos llegan a la persona.
    texto = repr(r)
    for prohibido in (SECRETO, TEXTO_EXCEPCION, "privado.json", "RuntimeError", "Traceback", "CLAVE-DE-TEST"):
        assert prohibido not in texto
    # Tras el error no se hace ninguna llamada posterior: solo las que ya se habían hecho.
    asumidas = PUNTOS_DE_FALLO[punto]
    assert (esc.cuantas("nominatim"), esc.cuantas("google"), esc.cuantas("rag")) == asumidas


def test_error_interno_se_registra_solo_en_el_log(esc, monkeypatch, caplog):
    # RF-42: la excepción completa (tipo, texto y traza) va al registro interno y solo allí.
    from src.tools import planificar_ruta as pr

    monkeypatch.setattr(pr, "consultar_google", _fallar)
    with caplog.at_level(logging.ERROR, logger=pr.logger.name):
        r = pr.planificar_ruta("Sol", "Bernabéu")
    registros = [x for x in caplog.records if x.name == pr.logger.name]
    assert len(registros) == 1 and registros[0].levelno == logging.ERROR
    tipo, valor, _ = registros[0].exc_info
    assert tipo is RuntimeError and str(valor) == TEXTO_EXCEPCION
    assert TEXTO_EXCEPCION not in r["mensaje"] and TEXTO_EXCEPCION not in repr(r)


def test_error_interno_aunque_falle_el_reloj(monkeypatch):
    # Si lo que falla es la propia fuente de la hora, el error sigue controlado y el mensaje sigue empezando por «Salida:».
    from src.tools import planificar_ruta as pr

    monkeypatch.setattr(pr, "ahora", _fallar)
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "error_interno" and r["mensaje"].startswith("Salida: ")
    assert " · Título: billete sencillo." in r["mensaje"]
    assert TEXTO_EXCEPCION not in repr(r)


def test_error_interno_con_hora_pedida_la_conserva_en_la_cabecera(esc, monkeypatch):
    # La cabecera del error refleja la hora pedida, no una hora inventada.
    from src.tools import planificar_ruta as pr

    monkeypatch.setattr(pr, "geocodificar", _fallar)
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_salida="2026-10-16T09:30")
    assert r["mensaje"].startswith("Salida: 16/10/2026 09:30 · ")


def test_mensajes_en_espanol(esc, monkeypatch):
    # RNF Idioma: todos los mensajes (incluido el de error interno) están en español y sin jerga técnica en inglés.
    from src.tools import planificar_ruta as pr
    from tests.test_planificar_ruta_hora_titulo import ESTADOS

    mensajes = {}
    for estado, (configurar, args) in ESTADOS.items():
        escenario = _Escenario(monkeypatch)
        configurar(escenario)
        mensajes[estado] = pr.planificar_ruta(**{"origen": "Sol", "destino": "Bernabéu", **args})["mensaje"]
    monkeypatch.setattr(pr, "geocodificar", _fallar)
    mensajes["error_interno"] = pr.planificar_ruta("Sol", "Bernabéu")["mensaje"]

    ingles = re.compile(r"\b(the|failed|not found|timeout|exception|route|invalid|unavailable|please)\b", re.I)
    for estado, mensaje in mensajes.items():
        # «Google Routes» es un nombre propio del servicio; se quita antes de buscar palabras en inglés.
        limpio = mensaje.replace("Google Routes", "")
        assert not ingles.search(limpio), f"{estado}: {mensaje}"
        assert re.search(r"\b(de|la|el|no|se|una|que|hora|ruta|dirección|indica|inténtalo)\b", limpio), estado


@pytest.mark.parametrize("cambios, titulo, llamadas", [
    ({}, None, 2),                                                                  # caso normal
    ({}, "x" * 61, 1),                                                              # título largo: solo la zona
    # Spec 010 (T13): el precio se pregunta sin zona aunque la zona falle o sea demasiado larga (antes 1 llamada).
    ({"rag": {"zona tarifaria": RuntimeError("x"), "precio": "p"}}, None, 2),       # zona con error: precio igualmente
    ({"rag": {"zona tarifaria": "z", "precio": RuntimeError("x")}}, None, 2),       # precio con error: sin reintento
    ({"rag": {"zona tarifaria": "z" * 201, "precio": "p"}}, None, 2),               # zona demasiado larga: precio sin zona
    ({"rag": {"zona tarifaria": "z", "precio": config.FRASE_ABSTENCION}}, None, 3),   # abstención: segundo intento con zona
    ({"rag": {"zona tarifaria": "z" * 201, "precio": config.FRASE_ABSTENCION}}, None, 2),   # abstención sin zona usable
    ({"google": TimeoutError("t")}, None, 2),                                       # Google caído: municipios, igual
])
def test_maximo_3_llamadas_al_rag(esc, cambios, titulo, llamadas):
    # RF-49 revisado por la spec 010 (RF-38): como máximo zona, precio y (tras una abstención) precio con zona; sin reintentos.
    from src.tools import planificar_ruta as pr

    for clave, valor in cambios.items():
        setattr(esc, clave, valor)
    pr.planificar_ruta("Sol", "Bernabéu", titulo=titulo)
    assert esc.cuantas("rag") == llamadas <= 3
