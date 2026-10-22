"""Tests de T5 (spec 010, RF-17 y RF-18): el título pedido llega a la consulta de precio y el prompt de rutas lo explica.

Sin red, RAG ni LLM. No existe `tarifa_solicitada`: el parámetro es el `titulo` que ya tiene la herramienta (spec 004).
"""
import json

import pytest

from src.agents.rutas import PROMPT_RUTAS, construir_prompt
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import AHORA, Escenario

# El prompt se compara sin saltos de línea: las frases pueden partirse al envolver el texto.
PROMPT = " ".join(PROMPT_RUTAS.split())


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def test_titulo_pedido_entra_en_la_consulta_de_precio(esc):
    r = json.loads(pr.planificar_ruta_texto(origen="Sol", destino="Bernabéu", titulo="abono joven"))
    zona, precio = esc.preguntas                                        # como mucho 2 llamadas al RAG: zona y precio
    assert esc.cuantas("rag") == 2 and "abono joven" not in zona and "abono joven" in precio
    assert r["titulo"] == "abono joven" and "Título: abono joven." in r["mensaje"]


def test_sin_titulo_comportamiento_actual(esc):
    r = json.loads(pr.planificar_ruta_texto(origen="Sol", destino="Bernabéu"))
    assert esc.cuantas("rag") == 2 and "billete sencillo" in esc.preguntas[1]
    assert r["titulo"] == "billete sencillo"


def test_no_hay_parametro_tarifa_solicitada():
    import inspect
    assert "tarifa_solicitada" not in inspect.signature(pr.planificar_ruta).parameters


def test_prompt_rutas_explica_el_titulo():
    assert "`titulo`" in PROMPT and "título de transporte" in PROMPT
    assert "abono" not in PROMPT.lower()               # sin lista ni ejemplos de títulos (spec 004, RF-35 y RF-50)


def test_prompt_rutas_copia_las_opciones():
    assert "ambigua" in PROMPT
    assert "copiar literalmente las opciones numeradas del `mensaje` de la tool" in PROMPT


def test_prompt_rutas_no_reescribe_ruta_no_calculada():
    assert "ruta_no_calculada" in PROMPT and "no reescribas el resultado" in PROMPT


def test_prompt_rutas_repite_la_llamada_ante_y_cuanto_cuesta():
    assert "¿y cuánto cuesta?" in PROMPT and "mismos origen y destino del historial" in PROMPT


def test_el_especialista_recibe_las_reglas_en_su_prompt():
    prompt = construir_prompt(AHORA)
    assert PROMPT_RUTAS in prompt and "`titulo`" in prompt
