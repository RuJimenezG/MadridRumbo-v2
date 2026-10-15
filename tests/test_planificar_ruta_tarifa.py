"""Tests de la consulta al RAG de zona y precio de planificar_ruta (spec 004, RF-19 a RF-23, RF-35 a RF-37 y RF-41).

No usan el RAG, ChromaDB ni Gemini reales: `rag.responder` se sustituye por un módulo falso en `sys.modules`,
así que la importación perezosa de `rag_ask` recibe siempre el doble. El mensaje con etiquetas Google/RAG es de T12.
"""
import sys
import types

import pytest

import config
from src.tools import planificar_ruta as pr

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
            if clave in pregunta:
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
        config.PREGUNTA_PRECIO.format(titulo="billete sencillo", origen="Sol", destino="Plaza de Castilla"),
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


def test_billete_10_viajes_consulta_su_precio(rag):
    # RF-35: el título de la lista cerrada sustituye al billete sencillo en la pregunta de precio.
    pr.consultar_tarifa("Sol", "Atocha", "Billete de 10  viajes")
    assert rag.preguntas[1] == config.PREGUNTA_PRECIO.format(
        titulo="billete de 10 viajes", origen="Sol", destino="Atocha")


def test_titulo_no_disponible_entrega_ruta_y_zona(rag):
    # RF-36: título fuera de lista → se consulta la zona (no depende del título) y el precio se omite sin preguntar.
    r = pr.consultar_tarifa("Sol", "Atocha", "abono joven")
    assert len(rag.preguntas) == 1 and "zona tarifaria" in rag.preguntas[0]
    assert r["zona"]["estado"] == "ok"
    assert r["precio"] == {"estado": "omitida", "texto": None, "fuente": "RAG"}


def test_rag_sin_evidencia_entrega_ruta(rag):
    # RF-21: si el RAG se abstiene, ambos datos son sin_evidencia y sin texto (nada inventado).
    rag.guion = {"zona tarifaria": config.FRASE_ABSTENCION, "precio": config.FRASE_ABSTENCION}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert r["zona"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    assert r["precio"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}


def test_evidencia_parcial_declara_el_que_falta(rag):
    # RF-22: zona sí y precio no (y al revés): cada dato lleva su propio estado.
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
    # RF-23: abstención (en cualquier posición del texto), vacío o tipo inesperado → sin_evidencia, nunca un valor propio.
    rag.guion = {"zona tarifaria": respuesta, "precio": respuesta}
    r = pr.consultar_tarifa("Sol", "Atocha")
    for dato in r.values():
        assert dato == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}


def test_texto_del_rag_sin_modificar(rag):
    # RF-23: lo que el RAG respalda se reenvía tal cual, sin limpiar ni reescribir.
    rag.guion = {"zona tarifaria": "  Zona B1 (ver tabla)\n", "precio": PRECIO}
    assert pr.consultar_tarifa("Sol", "Atocha")["zona"]["texto"] == "  Zona B1 (ver tabla)\n"


def test_rag_con_error_entrega_ruta_sin_zona_ni_precio(rag):
    # RF-41: una excepción del RAG no se propaga (la ruta se conserva en la orquestación): estado error por dato.
    rag.guion = {"zona tarifaria": RuntimeError("Chroma caído, clave abc"), "precio": ConnectionError("Gemini")}
    r = pr.consultar_tarifa("Sol", "Atocha")
    assert r["zona"] == {"estado": "error", "texto": None, "fuente": "RAG"}
    assert r["precio"] == {"estado": "error", "texto": None, "fuente": "RAG"}
    assert "abc" not in repr(r)          # el texto de la excepción no se propaga
    assert len(rag.preguntas) == 2       # el fallo de la zona no impide intentar el precio


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
