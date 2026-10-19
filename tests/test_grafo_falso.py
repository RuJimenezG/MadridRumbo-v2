"""Tests del grafo simulado de los clientes (spec 005, RF-28).

El simulado sustituye al grafo real en las pruebas y en el modo simulado, así que debe
cumplir el mismo contrato que `src/clientes/contrato.py`.
"""
import pytest

from src.clientes.contrato import estado_vacio
from src.clientes.grafo_falso import GrafoFalso


def test_cumple_el_contrato():
    # RF-28: devuelve todas las claves del contrato con el tipo esperado.
    grafo = GrafoFalso()
    estado = grafo.procesar_turno(estado_vacio(), "hola", "hilo-1")
    for clave in estado_vacio():
        assert clave in estado
    assert isinstance(estado["respuesta"], str)
    assert isinstance(estado["plan"], list)
    assert isinstance(estado["log"], list)
    assert isinstance(estado["traza"], list)
    assert isinstance(estado["hitl_pendiente"], bool)
    assert isinstance(estado["done"], bool)


def test_procesar_turno_deja_un_plan_pendiente():
    # El simulado siempre pausa para HITL y nunca da la conversación por terminada.
    estado = GrafoFalso().procesar_turno(estado_vacio(), "¿Hasta qué hora hay metro?", "hilo-1")
    assert estado["hitl_pendiente"] is True
    assert estado["done"] is False
    assert estado["plan"]
    assert "¿Hasta qué hora hay metro?" in estado["respuesta"]


def test_el_log_y_la_traza_tienen_formato_de_tools():
    estado = GrafoFalso().procesar_turno(estado_vacio(), "hola", "hilo-1")
    assert estado["log"]
    assert estado["traza"]
    for paso in estado["traza"]:
        assert {"tool", "args", "status", "preview"} <= set(paso)


def test_aprobar_cierra_la_conversacion():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), "hola", "hilo-1")
    estado = grafo.aprobar_plan(pendiente, "hilo-1", True)
    assert estado["done"] is True
    assert estado["hitl_pendiente"] is False


def test_rechazar_no_cierra_y_descarta_el_plan():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), "hola", "hilo-1")
    estado = grafo.aprobar_plan(pendiente, "hilo-1", False)
    assert estado["done"] is False
    assert estado["hitl_pendiente"] is False
    assert estado["plan"] == []


def test_no_modifica_el_estado_recibido():
    grafo = GrafoFalso()
    original = estado_vacio()
    grafo.procesar_turno(original, "hola", "hilo-1")
    assert original == estado_vacio()


def test_registra_las_llamadas_con_su_thread_id():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), "hola", "hilo-7")
    grafo.aprobar_plan(pendiente, "hilo-7", True)
    assert [(nombre, hilo) for nombre, hilo, *_ in grafo.llamadas] == [
        ("procesar_turno", "hilo-7"),
        ("aprobar_plan", "hilo-7"),
    ]


def test_fallo_forzado():
    # Sirve para probar cómo reaccionan los clientes cuando el grafo falla.
    grafo = GrafoFalso(fallar=True)
    with pytest.raises(RuntimeError):
        grafo.procesar_turno(estado_vacio(), "hola", "hilo-1")
    with pytest.raises(RuntimeError):
        grafo.aprobar_plan(estado_vacio(), "hilo-1", True)
