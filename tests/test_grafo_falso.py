"""Tests del grafo simulado de los clientes (spec 008, RF-28).

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
    # Una ruta pausa para HITL y no se da por terminada hasta aprobar.
    estado = GrafoFalso().procesar_turno(estado_vacio(), RUTA, "hilo-1")
    assert estado["hitl_pendiente"] is True
    assert estado["done"] is False
    assert estado["plan"]
    assert RUTA in estado["respuesta"]


def test_el_log_estructurado_y_la_traza_conservan_sus_contratos():
    estado = GrafoFalso().procesar_turno(estado_vacio(), "hola", "hilo-1")
    assert estado["log"]
    assert estado["traza"]
    for entrada in estado["log"]:
        assert set(entrada) == {"paso", "tipo", "nodo", "entrada", "salida", "resultado", "detalle"}
    for paso in estado["traza"]:
        assert {"tool", "args", "status", "preview"} <= set(paso)


def test_aprobar_cierra_la_conversacion():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), RUTA, "hilo-1")
    estado = grafo.aprobar_plan(pendiente, "hilo-1", True)
    assert estado["done"] is True
    assert estado["hitl_pendiente"] is False


def test_rechazar_no_cierra_y_descarta_el_plan():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), RUTA, "hilo-1")
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


# --- Grafo simulado con el formato del grafo real (spec 008, RF-34 y RF-36) ---
# Como el real, solo las rutas pausan para HITL; horarios y RAG cierran directamente.

import config  # noqa: E402
from src.clientes.planes import ids_de_planes, resumir_plan  # noqa: E402

RUTA = config.PEDIDOS_DEMO[1]
VARIAS_RUTAS = "Dame dos rutas alternativas desde la Puerta del Sol hasta la Estación de Atocha"
HORARIOS = config.PEDIDOS_DEMO[0]
FUERA_DE_CORPUS = config.PEDIDOS_DEMO[2]


def con_ruta(mensaje=RUTA):
    return GrafoFalso().procesar_turno(estado_vacio(), mensaje, "hilo-1")


def test_ruta_devuelve_un_plan_con_formato_real():
    estado = con_ruta()
    assert estado["hitl_pendiente"] is True
    assert estado["done"] is False
    assert len(estado["plan"]) == 1
    plan = estado["plan"][0]
    assert plan["id"] == "ruta-1"
    resultado = plan["resultado"]
    assert {"origen", "destino", "ruta"} <= set(resultado)
    assert resultado["ruta"]["tramos"]


def test_el_plan_simulado_se_puede_resumir():
    texto = resumir_plan(con_ruta()["plan"][0])
    assert "ruta-1" in texto and "Origen" in texto and "Destino" in texto


def test_varias_rutas_devuelven_varios_planes():
    estado = con_ruta(VARIAS_RUTAS)
    assert ids_de_planes(estado["plan"]) == ["ruta-1", "ruta-2"]
    assert estado["hitl_pendiente"] is True


def test_horarios_cierra_sin_plan():
    # RF-34: sin ruta no hay pausa; el grafo da la conversación por terminada.
    estado = con_ruta(HORARIOS)
    assert estado["plan"] == []
    assert estado["hitl_pendiente"] is False
    assert estado["done"] is True
    assert any(entrada["nodo"] == "horarios" for entrada in estado["log"])


def test_fuera_de_corpus_cierra_sin_plan():
    estado = con_ruta(FUERA_DE_CORPUS)
    assert estado["plan"] == [] and estado["hitl_pendiente"] is False and estado["done"] is True
    assert any(entrada["nodo"] == "rag" for entrada in estado["log"])


def test_devuelve_solo_las_seis_claves_publicas():
    # Como el grafo real, no filtra claves internas ni las que mandó el cliente.
    grafo = GrafoFalso()
    estado = grafo.procesar_turno({"plan_id_seleccionado": "ruta-1", "interna": 1}, RUTA, "hilo-1")
    assert set(estado) == set(estado_vacio())
    assert set(grafo.aprobar_plan(estado, "hilo-1", False)) == set(estado_vacio())


def test_aprobar_el_plan_elegido():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), VARIAS_RUTAS, "hilo-1")
    estado = grafo.aprobar_plan({**pendiente, "plan_id_seleccionado": "ruta-2"}, "hilo-1", True)
    assert estado["done"] is True
    assert estado["hitl_pendiente"] is False
    assert estado["plan"] == []


def test_un_solo_plan_se_aprueba_sin_indicar_cual():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), RUTA, "hilo-1")
    assert grafo.aprobar_plan(pendiente, "hilo-1", True)["done"] is True


def test_rechazar_un_plan_deja_los_demas_pendientes():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), VARIAS_RUTAS, "hilo-1")
    estado = grafo.aprobar_plan({**pendiente, "plan_id_seleccionado": "ruta-1"}, "hilo-1", False)
    assert ids_de_planes(estado["plan"]) == ["ruta-2"]
    assert estado["hitl_pendiente"] is True
    assert estado["done"] is False


def test_rechazar_el_unico_plan_no_deja_ninguno():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), RUTA, "hilo-1")
    estado = grafo.aprobar_plan(pendiente, "hilo-1", False)
    assert estado["plan"] == [] and estado["hitl_pendiente"] is False and estado["done"] is False


def test_varios_planes_sin_indicar_cual_da_un_aviso():
    # Como el real: aviso controlado y `hitl_pendiente` en False aunque quede un plan pendiente.
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), VARIAS_RUTAS, "hilo-1")
    estado = grafo.aprobar_plan(pendiente, "hilo-1", True)
    assert "identificador" in estado["respuesta"].lower()
    assert estado["done"] is False and estado["hitl_pendiente"] is False


def test_plan_inexistente_da_un_aviso():
    grafo = GrafoFalso()
    pendiente = grafo.procesar_turno(estado_vacio(), VARIAS_RUTAS, "hilo-1")
    estado = grafo.aprobar_plan({**pendiente, "plan_id_seleccionado": "ruta-9"}, "hilo-1", True)
    assert "identificador" in estado["respuesta"].lower() and estado["done"] is False


def test_aprobar_sin_plan_pendiente():
    estado = GrafoFalso().aprobar_plan(estado_vacio(), "hilo-1", True)
    assert "no existe un plan pendiente" in estado["respuesta"].lower()
    assert estado["done"] is False and estado["hitl_pendiente"] is False
