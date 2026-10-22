"""Tests de la consulta al RAG de zona y precio de planificar_ruta (spec 004, RF-19 a RF-23, RF-35 a RF-37 y RF-41).

No usan el RAG, ChromaDB ni Gemini reales: `rag.responder` se sustituye por un módulo falso en `sys.modules`,
así que la importación perezosa de `rag_ask` recibe siempre el doble. El mensaje con etiquetas Google/RAG es de T12.
"""
import sys
import types

import pytest

import config
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import Escenario

ZONA = "Zona A según la tabla tarifaria."
PRECIO = "El billete sencillo cuesta 1,50 €."


class RagFalso:
    """Doble de `rag_ask`: guarda las preguntas y responde según un guion {fragmento de pregunta: respuesta}."""

    def __init__(self):
        self.preguntas = []
        self.guion = {"zona tarifaria": ZONA, "precio": PRECIO}

    def rag_ask(self, pregunta):
        self.preguntas.append(pregunta)
        for clave, respuesta in self.guion.items():
            if clave in pregunta or (clave == "precio" and "cuesta" in pregunta):   # T13: precio sin zona = «¿Cuánto cuesta…?»
                if isinstance(respuesta, Exception):
                    raise respuesta
                return respuesta
        raise AssertionError(f"pregunta inesperada: {pregunta}")


@pytest.fixture
def rag(monkeypatch):
    falso = RagFalso()
    monkeypatch.setitem(sys.modules, "rag.responder", types.SimpleNamespace(rag_ask=falso.rag_ask))
    return falso


def test_consulta_zona_y_precio_sencillo(rag):
    # RF-19: sin título se consulta la zona y el precio del billete sencillo, con las plantillas de config.
    r = pr.consultar_tarifa("Sol", "Plaza de Castilla")
    assert rag.preguntas == [
        config.PREGUNTA_ZONA.format(origen="Sol", destino="Plaza de Castilla"),
        config.PREGUNTA_PRECIO.format(titulo="billete sencillo", zona=ZONA),    # RF-46: el precio se pregunta con la zona
    ]
    assert r == {
        "zona": {"estado": "ok", "texto": ZONA, "fuente": "RAG"},
        "precio": {"estado": "ok", "texto": PRECIO, "fuente": "RAG"},
    }


def test_google_falla_consulta_rag_con_municipios(rag):
    # RF-20: con municipios en lugar de paradas (Google caído) se consulta igual, con las mismas plantillas.
    r = pr.consultar_tarifa("Madrid", "Alcalá de Henares")
    assert "Madrid" in rag.preguntas[0] and "Alcalá de Henares" in rag.preguntas[0]
    assert r["zona"]["estado"] == r["precio"]["estado"] == "ok"


def test_titulo_libre_consulta_su_precio(rag):
    # RF-35: cualquier título (sin lista cerrada) sustituye al billete sencillo en la pregunta de precio.
    for titulo in ("Billete de 10 viajes", "abono joven"):
        rag.preguntas.clear()
        r = pr.consultar_tarifa("Sol", "Atocha", titulo)
        assert rag.preguntas[1] == config.PREGUNTA_PRECIO.format(titulo=titulo, zona=ZONA)
        assert r["precio"]["estado"] == "ok" and len(rag.preguntas) == 2


def test_titulo_demasiado_largo_consulta_solo_la_zona(rag):
    # RF-48: título que supera el máximo → se consulta la zona y el precio se omite sin preguntar.
    r = pr.consultar_tarifa("Sol", "Atocha", "x" * (config.TITULO_LONGITUD_MAX + 1))
    assert len(rag.preguntas) == 1 and "zona tarifaria" in rag.preguntas[0]
    assert r["zona"]["estado"] == "ok"
    assert r["precio"] == {"estado": "omitida", "texto": None, "fuente": "RAG"}


def test_titulo_que_el_corpus_no_conoce_se_abstiene(rag):
    # RF-37 con título libre: sin precio en el corpus no se sustituye por el de otro título.
    rag.guion["precio"] = config.FRASE_ABSTENCION
    r = pr.consultar_tarifa("Sol", "Atocha", "abono turístico de 3 meses")
    assert r["precio"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"} and PRECIO not in repr(r)


def test_rag_sin_evidencia_entrega_ruta(rag):
    # RF-21; spec 010 (T13, RF-36): si el RAG se abstiene en la zona y en el precio, no hay texto inventado. Antes el
    # precio ni se consultaba (RF-52); ahora se pregunta igualmente (sin zona) y, abstenido, queda sin_evidencia.
    rag.guion = {"zona tarifaria": config.FRASE_ABSTENCION, "precio": config.FRASE_ABSTENCION}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert r["zona"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    assert r["precio"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    assert len(rag.preguntas) == 2           # sin zona no hay segundo intento


def test_evidencia_parcial_declara_el_que_falta(rag):
    # RF-22: zona sí y precio no: cada dato lleva su propio estado. Spec 010 (T13): el caso inverso (precio sin zona)
    # sí se da ahora, porque el precio se pregunta sin depender de la zona (RF-36); antes daba ("sin_evidencia", "omitida").
    rag.guion["precio"] = config.FRASE_ABSTENCION
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert (r["zona"]["estado"], r["precio"]["estado"]) == ("ok", "sin_evidencia")
    rag.guion = {"zona tarifaria": config.FRASE_ABSTENCION, "precio": PRECIO}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert (r["zona"]["estado"], r["precio"]["estado"]) == ("sin_evidencia", "ok")


def test_sin_precio_del_titulo_no_lo_sustituye(rag):
    # RF-37: sin precio del billete de 10 viajes no se devuelve el del sencillo ni otro texto.
    rag.guion["precio"] = f"{config.FRASE_ABSTENCION}"
    r = pr.consultar_tarifa("Sol", "Atocha", "billete de 10 viajes")
    assert r["precio"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    assert PRECIO not in repr(r)


@pytest.mark.parametrize("respuesta", [f"{config.FRASE_ABSTENCION}", f"  {config.FRASE_ABSTENCION}\n",
                                       f"Con lo que consta: {config.FRASE_ABSTENCION}", "", "   ", None, 42])
def test_no_inventa_zona_ni_precio(rag, respuesta):
    # RF-23; spec 010 (T13): abstención (en cualquier posición del texto), vacío o tipo inesperado → zona y precio
    # sin_evidencia; nunca un valor propio. Antes el precio no se consultaba sin zona (omitida, RF-52); ahora se
    # pregunta sin zona (2 llamadas) y, sin zona disponible, no hay segundo intento.
    rag.guion = {"zona tarifaria": respuesta, "precio": respuesta}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert r["zona"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    assert r["precio"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    assert len(rag.preguntas) == 2


def test_texto_del_rag_sin_modificar(rag):
    # RF-23: lo que el RAG respalda se reenvía tal cual, sin limpiar ni reescribir.
    rag.guion = {"zona tarifaria": "  Zona B1 (ver tabla)\n", "precio": PRECIO}
    assert pr.consultar_tarifa("Sol", "Atocha")["zona"]["texto"] == "  Zona B1 (ver tabla)\n"


def test_rag_con_error_entrega_ruta_sin_zona_ni_precio(rag):
    # RF-41; spec 010 (T13): una excepción del RAG no se propaga (la ruta se conserva). Zona y precio en error, cada
    # uno con su única llamada y sin reintento ni segundo intento; antes el precio ni se consultaba (RF-52).
    rag.guion = {"zona tarifaria": RuntimeError("Chroma caído, clave abc"), "precio": ConnectionError("Gemini")}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert r["zona"] == {"estado": "error", "texto": None, "fuente": "RAG"}
    assert r["precio"] == {"estado": "error", "texto": None, "fuente": "RAG"}
    assert "abc" not in repr(r) and "Gemini" not in repr(r)          # el texto de la excepción no se propaga
    assert len(rag.preguntas) == 2


def test_error_del_rag_en_el_precio_no_se_reintenta(rag):
    # RF-41, RF-49: con la zona bien y el precio en error, 2 llamadas exactas (sin reintentos) y el precio en error.
    rag.guion = {"zona tarifaria": ZONA, "precio": ConnectionError("Gemini")}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert r["zona"]["estado"] == "ok" and r["precio"] == {"estado": "error", "texto": None, "fuente": "RAG"}
    assert len(rag.preguntas) == 2 and "Gemini" not in repr(r)


@pytest.mark.parametrize("origen,destino", [(None, "Atocha"), ("Sol", None), ("", "Atocha"), ("Sol", "  "), (None, None)])
def test_sin_paradas_validas_no_consulta_al_rag(rag, origen, destino):
    # Sin paradas (o municipios) válidas, p. ej. sin_ruta de T10, no se consulta nada y no se inventa nada.
    r = pr.consultar_tarifa(origen, destino)
    assert rag.preguntas == []
    assert r["zona"] == r["precio"] == {"estado": "omitida", "texto": None, "fuente": "RAG"}


def test_la_fuente_es_siempre_rag(rag):
    # RF-24: todos los estados llevan fuente "RAG".
    for guion in ({}, {"zona tarifaria": config.FRASE_ABSTENCION, "precio": RuntimeError("x")}):
        rag.guion = {"zona tarifaria": ZONA, "precio": PRECIO, **guion}
        for titulo in (None, "abono"):
            assert all(d["fuente"] == "RAG" for d in pr.consultar_tarifa("Sol", "Atocha", titulo).values())
    assert pr.consultar_tarifa(None, None)["zona"]["fuente"] == "RAG"


def test_consultar_rag_usa_rag_ask_importado_al_llamar(rag):
    # El RAG real no se carga al importar el módulo: consultar_rag importa `rag_ask` al usarse (aquí, el doble)
    # y devuelve su texto tal cual, dejando pasar las excepciones (las trata consultar_tarifa).
    rag.guion = {"hola": "respuesta del doble"}
    assert pr.consultar_rag("hola mundo") == "respuesta del doble"
    rag.guion = {"hola": RuntimeError("fallo")}
    with pytest.raises(RuntimeError):
        pr.consultar_rag("hola mundo")


# --- T12: mensaje y ruta de extremo a extremo (RF-24, RF-41) ---

@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def test_mensaje_etiqueta_google_y_rag(esc):
    # RF-24: el mensaje distingue qué dato viene de Google (ruta) y cuál del RAG (zona y precio).
    r = pr.planificar_ruta("Sol", "Bernabéu")
    m = r["mensaje"]
    assert r["estado"] == "ok"
    assert "(Google Routes)" in m and "22 min" in m
    assert f"Zona (RAG): {ZONA}" in m and f"Precio (RAG): {PRECIO}" in m
    # Los datos de cada fuente solo aparecen bajo su etiqueta: lo del RAG no se mezcla con la ruta.
    assert m.index("(Google Routes)") < m.index("Zona (RAG)")
    assert r["ruta"]["fuente"] == "Google Routes" and r["zona"]["fuente"] == r["precio"]["fuente"] == "RAG"
    # Se indica la dirección identificada (RF-7) y el trayecto tramo a tramo (RF-15).
    assert "Puerta del Sol, Madrid" in m and "Estadio Santiago Bernabéu, Madrid" in m
    assert "Plaza de Castilla" in m and "A pie" in m


def test_rag_falla_la_ruta_se_conserva(esc):
    # RF-41, de extremo a extremo: el RAG falla → sigue siendo ok, con la ruta y zona/precio en error y sin valores propios.
    esc.rag = {"zona tarifaria": RuntimeError("Chroma caído"), "precio": ConnectionError("Gemini")}
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "ok" and r["ruta"]["duracion_min"] == 22
    # Spec 010 (T13): antes ("error", "omitida") y «Faltan la zona y el precio» (RF-52); ahora el precio también se pregunta.
    assert (r["zona"]["estado"], r["precio"]["estado"]) == ("error", "error")
    assert "Zona (RAG): no se pudo consultar. Precio (RAG): no se pudo consultar." in r["mensaje"]
    assert "22 min" in r["mensaje"] and esc.cuantas("rag") == 2
    assert "Chroma" not in repr(r) and "Gemini" not in repr(r)


def test_rag_sin_evidencia_se_declara_en_el_mensaje(esc):
    # RF-21 y RF-22: dato por dato; solo se declara como no determinado el que falta.
    esc.rag["precio"] = config.FRASE_ABSTENCION
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert f"Zona (RAG): {ZONA}" in r["mensaje"]
    assert "Precio (RAG): no se pudo determinar" in r["mensaje"]
    assert PRECIO not in r["mensaje"]


def test_titulo_libre_de_extremo_a_extremo(esc):
    # RF-35, RF-38: el título pedido (tal cual, sin forma canónica) va al RAG y a la cabecera.
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo="Billete de 10 viajes")
    assert "Billete de 10 viajes" in esc.preguntas[1] and "Título: Billete de 10 viajes." in r["mensaje"]


# --- T21: primero la zona, después el precio del título en esa zona (RF-46, RF-49, RF-52, RF-53) ---

@pytest.mark.parametrize("titulo", [None, "billete sencillo", "abono joven"])
def test_primero_zona_despues_precio_del_titulo(esc, titulo):
    # RF-46; spec 010 (T13, RF-36): para TODOS los títulos (sencillo incluido) la zona se pregunta antes y el precio se
    # pregunta sin zona (con zona el RAG se abstiene): «¿Cuánto cuesta el {titulo}?».
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo=titulo)
    assert r["estado"] == "ok" and esc.orden == ["nominatim", "nominatim", "google", "rag", "rag"]
    assert esc.preguntas[0] == config.PREGUNTA_ZONA.format(origen="Madrid", destino="Madrid")     # T22: municipios
    assert esc.preguntas[1] == config.PREGUNTA_PRECIO.format(titulo=titulo or "billete sencillo", zona=ZONA)
    # La pregunta de precio ya no se construye con origen y destino, y las dos siguen distinguiéndose por fragmento.
    assert "Madrid" not in esc.preguntas[1] and "Plaza de Castilla" not in esc.preguntas[1]
    assert "zona tarifaria" in esc.preguntas[0] and "zona tarifaria" not in esc.preguntas[1]
    assert "cuesta" in esc.preguntas[1] and "cuesta" not in esc.preguntas[0] and "zona" not in esc.preguntas[1].lower()


def test_zona_se_sanea_antes_de_la_pregunta_de_precio(rag):
    # RF-53: los saltos de línea de la zona se quitan en la pregunta; el texto de la zona del resultado no se toca (RF-23).
    rag.guion = {"zona tarifaria": "Zona B1\n(ver\r\ntabla)\n", "precio": PRECIO}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert rag.preguntas[1] == config.PREGUNTA_PRECIO.format(titulo="billete sencillo", zona="Zona B1 (ver tabla)")
    assert "\n" not in rag.preguntas[1] and "\r" not in rag.preguntas[1]
    assert r["zona"]["texto"] == "Zona B1\n(ver\r\ntabla)\n"


def test_zona_dentro_del_limite_se_pasa_entera(rag):
    # RF-53; spec 010 (T13, RF-37): la zona (hasta ZONA_LONGITUD_MAX) se pasa entera, nunca cortada, en el segundo
    # intento (solo tras la abstención del precio sin zona); justo en el límite también. Antes iba en la única pregunta de precio.
    assert config.ZONA_LONGITUD_MAX == 200 and config.ZONA_LONGITUD_MAX != config.TITULO_LONGITUD_MAX
    for zona in ("Zona A", "z" * config.ZONA_LONGITUD_MAX):
        rag.preguntas.clear()
        rag.guion = {"zona tarifaria": zona, "precio": config.FRASE_ABSTENCION}
        r = pr.consultar_tarifa("Sol", "Atocha")
        assert zona in rag.preguntas[2] and len(rag.preguntas) == 3 and r["precio"]["estado"] == "sin_evidencia"


def test_zona_por_encima_del_limite_no_consulta_el_precio(rag):
    # RF-53; spec 010 (T13): si la zona supera ZONA_LONGITUD_MAX (ya sin saltos de línea) no se corta ni se usa en el
    # segundo intento; el precio sin zona se pregunta igualmente (antes no se consultaba el precio).
    zona = "z" * (config.ZONA_LONGITUD_MAX + 1)
    rag.guion = {"zona tarifaria": zona, "precio": PRECIO}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert len(rag.preguntas) == 2
    assert r["zona"] == {"estado": "ok", "texto": zona, "fuente": "RAG"}      # la zona se entrega entera
    assert r["precio"] == {"estado": "ok", "texto": PRECIO, "fuente": "RAG"}
    rag.preguntas.clear()
    rag.guion = {"zona tarifaria": zona, "precio": config.FRASE_ABSTENCION}      # abstenido y con zona demasiado larga
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert len(rag.preguntas) == 2 and r["precio"]["estado"] == "sin_evidencia"     # sin segundo intento
    # Los saltos de línea no cuentan: la misma zona repartida en líneas, ya saneada, cabe justo en el límite.
    rag.preguntas.clear()
    rag.guion = {"zona tarifaria": "z" * 100 + "\n" + "z" * 99, "precio": config.FRASE_ABSTENCION}
    pr.consultar_tarifa("Sol", "Atocha")
    assert len(rag.preguntas) == 3 and "z" * 100 + " " + "z" * 99 in rag.preguntas[2]


def test_zona_demasiado_larga_se_informa_en_el_mensaje(esc):
    # RF-53; spec 010 (T13): ruta y zona entregadas; el precio sin zona se pregunta igualmente. Antes el mensaje decía
    # que no se pudo usar la zona para el precio y no se consultaba; ahora solo falta el segundo intento si hay abstención.
    zona = "z" * (config.ZONA_LONGITUD_MAX + 1)
    esc.rag = {"zona tarifaria": zona, "precio": PRECIO}
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "ok" and r["ruta"]["duracion_min"] == 22 and r["zona"]["texto"] == zona
    assert PRECIO in r["mensaje"] and esc.cuantas("rag") == 2


@pytest.mark.parametrize("respuesta", [config.FRASE_ABSTENCION, "", None, RuntimeError("Chroma caído")])
def test_zona_sin_evidencia_o_error_no_consulta_precio(esc, respuesta):
    # RF-52; spec 010 (T13, RF-36): sin zona (sin evidencia o error) el precio se pregunta igualmente (sin zona) y se
    # entrega si el RAG lo da; antes no había segunda llamada y el mensaje decía «Faltan la zona y el precio».
    esc.rag = {"zona tarifaria": respuesta, "precio": PRECIO}
    r = pr.planificar_ruta("Sol", "Bernabéu")
    assert r["estado"] == "ok" and r["ruta"]["duracion_min"] == 22       # la ruta se entrega igualmente
    assert esc.cuantas("rag") == 2 and "cuesta" not in esc.preguntas[0]
    assert r["zona"]["estado"] in ("sin_evidencia", "error") and r["precio"]["estado"] == "ok"
    assert "Zona (RAG): no se pudo" in r["mensaje"] and f"Precio (RAG): {PRECIO}" in r["mensaje"]
    assert "Chroma" not in repr(r)                                         # nada de detalles internos
