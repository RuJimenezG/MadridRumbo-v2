"""Tests de la carga del grafo para los clientes (spec 005, RF-28 y RF-29). No usan API."""
import sys
import types

import pytest

import config
from src.clientes.cargar import GrafoNoDisponible, cargar_agente
from src.clientes.grafo_falso import GrafoFalso

ENTORNO_SIMULADO = {config.VARIABLE_MODO_SIMULADO: config.VALOR_MODO_SIMULADO}


def grafo_real_falso():
    """Módulo que cumple el contrato, como lo haría el grafo real."""
    modulo = types.ModuleType(config.MODULO_GRAFO_REAL)
    modulo.procesar_turno = lambda estado, mensaje, thread_id: estado
    modulo.aprobar_plan = lambda estado, thread_id, aprobado: estado
    return modulo


@pytest.fixture
def sin_grafo_real(monkeypatch):
    """Hace que importar el grafo real falle, exista o no el archivo en el repositorio."""
    monkeypatch.setitem(sys.modules, config.MODULO_GRAFO_REAL, None)


def test_modo_simulado_usa_grafo_falso(sin_grafo_real):
    # RF-28: con la variable activada se usa el simulado y se avisa.
    agente, aviso = cargar_agente(ENTORNO_SIMULADO)
    assert isinstance(agente, GrafoFalso)
    assert "simulado" in aviso.lower()


def test_modo_simulado_tiene_prioridad_sobre_el_grafo_real(monkeypatch):
    monkeypatch.setitem(sys.modules, config.MODULO_GRAFO_REAL, grafo_real_falso())
    agente, _ = cargar_agente(ENTORNO_SIMULADO)
    assert isinstance(agente, GrafoFalso)


def test_usa_el_grafo_real_si_existe(monkeypatch):
    # Sin la variable, y con el grafo real disponible, se usa el real y no hay aviso.
    real = grafo_real_falso()
    monkeypatch.setitem(sys.modules, config.MODULO_GRAFO_REAL, real)
    agente, aviso = cargar_agente({})
    assert agente is real
    assert aviso is None


def test_sin_grafo_real_da_error_claro(sin_grafo_real):
    # RF-29: sin grafo real y sin la variable, error en español que explica cómo activar el simulado.
    with pytest.raises(GrafoNoDisponible) as error:
        cargar_agente({})
    mensaje = str(error.value)
    assert config.VARIABLE_MODO_SIMULADO in mensaje
    assert config.VALOR_MODO_SIMULADO in mensaje
    assert "grafo" in mensaje.lower()


def test_otro_valor_de_la_variable_no_activa_el_simulado(sin_grafo_real):
    with pytest.raises(GrafoNoDisponible):
        cargar_agente({config.VARIABLE_MODO_SIMULADO: "otro"})


def test_modulo_que_no_cumple_el_contrato(monkeypatch):
    # Un módulo sin aprobar_plan no es un grafo válido para los clientes.
    incompleto = types.ModuleType(config.MODULO_GRAFO_REAL)
    incompleto.procesar_turno = lambda estado, mensaje, thread_id: estado
    monkeypatch.setitem(sys.modules, config.MODULO_GRAFO_REAL, incompleto)
    with pytest.raises(GrafoNoDisponible) as error:
        cargar_agente({})
    assert "aprobar_plan" in str(error.value)
