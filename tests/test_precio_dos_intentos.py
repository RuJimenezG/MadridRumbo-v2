"""Spec 010, T13 (RF-36 a RF-38): el precio se pregunta primero sin zona y, solo si el RAG se abstiene, con zona.

Sin RAG ni red: `consultar_rag` se sustituye por un guion de respuestas. Medición real en `validacion.md`: con zona
el RAG se abstiene («¿Cuánto cuesta el abono joven en la zona A?») y sin ella responde.
"""
import pytest

import config
from src.tools import planificar_ruta as pr

ABST = config.FRASE_ABSTENCION
ZONA = "Zona A"
PRECIO = "El abono joven cuesta 20,00 € (10,00 € con descuento)."
ZONA_Q = config.PREGUNTA_ZONA.format(origen="Madrid", destino="Madrid")
PRECIO_Q = "¿Cuánto cuesta el abono joven?"
PRECIO_ZONA_Q = "Tarifa y precio del abono joven Zona A"


class Rag:
    """Respuestas en orden (texto o excepción); guarda las preguntas recibidas."""

    def __init__(self, monkeypatch, *respuestas):
        self.respuestas = list(respuestas)
        self.preguntas = []
        monkeypatch.setattr(pr, "consultar_rag", self)

    def __call__(self, pregunta):
        self.preguntas.append(pregunta)
        r = self.respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def tarifa(titulo="abono joven"):
    return pr.consultar_tarifa("Madrid", "Madrid", titulo)


def test_las_formulaciones_de_config():
    assert config.PREGUNTA_PRECIO.format(titulo="abono joven") == PRECIO_Q
    assert config.PREGUNTA_PRECIO_CON_ZONA.format(titulo="abono joven", zona="Zona A") == PRECIO_ZONA_Q
    assert "zona" not in config.PREGUNTA_PRECIO.lower()                    # el primer intento no condiciona a una zona


def test_la_pregunta_de_precio_va_sin_zona_y_basta_con_dos_llamadas(monkeypatch):
    rag = Rag(monkeypatch, ZONA, PRECIO)
    t = tarifa()
    assert rag.preguntas == [ZONA_Q, PRECIO_Q]                              # sin tercera llamada
    assert t["zona"]["estado"] == t["precio"]["estado"] == "ok" and t["precio"]["texto"] == PRECIO


def test_segundo_intento_con_zona_solo_tras_la_abstencion(monkeypatch):
    rag = Rag(monkeypatch, ZONA, ABST, PRECIO)
    t = tarifa()
    assert rag.preguntas == [ZONA_Q, PRECIO_Q, PRECIO_ZONA_Q]
    assert t["precio"] == {"estado": "ok", "texto": PRECIO, "fuente": "RAG"}


def test_si_ambos_se_abstienen_sin_evidencia_y_tres_llamadas(monkeypatch):
    rag = Rag(monkeypatch, ZONA, ABST, ABST)
    t = tarifa()
    assert len(rag.preguntas) == 3
    assert t["precio"] == {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}


def test_sin_zona_disponible_no_hay_segundo_intento(monkeypatch):
    for zona in (ABST, RuntimeError("x")):
        rag = Rag(monkeypatch, zona, ABST)
        t = tarifa()
        assert len(rag.preguntas) == 2 and t["precio"]["estado"] == "sin_evidencia"     # solo zona y precio sin zona
        assert t["zona"]["estado"] in ("sin_evidencia", "error")


def test_la_zona_demasiado_larga_no_se_usa_en_el_segundo_intento(monkeypatch):
    rag = Rag(monkeypatch, "z" * (config.ZONA_LONGITUD_MAX + 1), ABST)
    t = tarifa()
    assert len(rag.preguntas) == 2 and t["precio"]["estado"] == "sin_evidencia"
    justo = Rag(monkeypatch, "z" * config.ZONA_LONGITUD_MAX, ABST, PRECIO)          # justo en el límite sí se usa
    assert tarifa()["precio"]["estado"] == "ok" and len(justo.preguntas) == 3


def test_la_zona_se_sanea_antes_de_entrar_en_el_segundo_intento(monkeypatch):
    rag = Rag(monkeypatch, "  Zona A\n(ver tabla)\r\n", ABST, PRECIO)
    tarifa()
    assert rag.preguntas[2] == "Tarifa y precio del abono joven Zona A (ver tabla)"


def test_un_error_en_el_primer_intento_no_provoca_el_segundo(monkeypatch):
    rag = Rag(monkeypatch, ZONA, ConnectionError("Gemini"))
    t = tarifa()
    assert len(rag.preguntas) == 2 and t["precio"] == {"estado": "error", "texto": None, "fuente": "RAG"}


def test_un_error_en_el_segundo_intento_deja_el_precio_en_error(monkeypatch):
    rag = Rag(monkeypatch, ZONA, ABST, ConnectionError("Gemini"))
    assert tarifa()["precio"]["estado"] == "error" and len(rag.preguntas) == 3


def test_el_precio_se_consulta_aunque_la_zona_falle(monkeypatch):
    rag = Rag(monkeypatch, ABST, PRECIO)
    t = tarifa()
    assert t["zona"]["estado"] == "sin_evidencia" and t["precio"]["estado"] == "ok"
    assert rag.preguntas == [ZONA_Q, PRECIO_Q]


def test_titulo_no_interpretable_no_consulta_el_precio(monkeypatch):
    rag = Rag(monkeypatch, ZONA)
    t = tarifa("x" * (config.TITULO_LONGITUD_MAX + 1))
    assert len(rag.preguntas) == 1 and t["precio"]["estado"] == "omitida"


@pytest.mark.parametrize("respuestas", [(ZONA, PRECIO), (ZONA, ABST, ABST), (ABST, ABST), (RuntimeError("x"), PRECIO),
                                        (ZONA, ABST, PRECIO), (ZONA, ConnectionError("x"))])
def test_nunca_mas_de_tres_llamadas(monkeypatch, respuestas):
    rag = Rag(monkeypatch, *respuestas)
    tarifa()
    assert len(rag.preguntas) <= 3


def test_sin_municipios_no_se_consulta_nada(monkeypatch):
    rag = Rag(monkeypatch)
    assert pr.consultar_tarifa(None, "Madrid")["precio"]["estado"] == "omitida" and rag.preguntas == []


def test_en_la_ruta_completa_el_precio_sin_zona_llega_al_mensaje(monkeypatch):
    from tests.dobles_ruta import Escenario
    esc = Escenario(monkeypatch)
    esc.rag = {"zona tarifaria": ZONA, "cuesta": PRECIO}
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo="abono joven")
    assert r["estado"] == "ok" and r["precio"]["estado"] == "ok" and PRECIO in r["mensaje"]
    assert esc.preguntas[1] == PRECIO_Q and esc.cuantas("rag") == 2
