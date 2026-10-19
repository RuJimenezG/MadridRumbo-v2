"""Tests de SesionChat, la lógica que comparten el CLI y Streamlit (spec 005).

Cubre RF-2, RF-5, RF-8, RF-9, RF-18 a RF-23, RF-22b, RF-25 y RF-27 con un grafo simulado: no usan API.
"""
from src.clientes.contrato import estado_vacio
from src.clientes.grafo_falso import GrafoFalso
from src.clientes.sesion import MENSAJE_ERROR, SesionChat


def sesion_nueva():
    grafo = GrafoFalso()
    return SesionChat(grafo), grafo


def test_estado_inicial():
    sesion, _ = sesion_nueva()
    assert sesion.estado == estado_vacio()
    assert sesion.historial == []
    assert sesion.puede_escribir is True
    assert sesion.puede_decidir is False


def test_thread_id_estable():
    # RF-2 y RF-18: el mismo identificador durante toda la conversación; otra sesión, otro identificador.
    sesion, grafo = sesion_nueva()
    inicial = sesion.thread_id
    sesion.enviar("hola")
    sesion.decidir(False)
    sesion.enviar("otra vez")
    assert sesion.thread_id == inicial
    assert {hilo for _, hilo, _ in grafo.llamadas} == {inicial}
    assert SesionChat(GrafoFalso()).thread_id != inicial


def test_enviar_actualiza_estado_e_historial():
    sesion, _ = sesion_nueva()
    sesion.enviar("¿Hasta qué hora hay metro?")
    assert sesion.estado["respuesta"].startswith("[Simulado]")
    assert sesion.historial[0] == {"rol": "usuario", "texto": "¿Hasta qué hora hay metro?"}
    assert sesion.historial[1]["rol"] == "asistente"
    assert sesion.historial[1]["texto"] == sesion.estado["respuesta"]


def test_plan_pendiente_activa_decision():
    # RF-19: con plan pendiente se puede decidir.
    sesion, _ = sesion_nueva()
    sesion.enviar("hola")
    assert sesion.estado["hitl_pendiente"] is True
    assert sesion.puede_decidir is True


def test_decidir_solo_con_plan_pendiente():
    # RF-22: sin plan pendiente no se decide y no se llama al grafo.
    sesion, grafo = sesion_nueva()
    assert sesion.puede_decidir is False
    sesion.decidir(True)
    assert grafo.llamadas == []


def test_no_se_puede_escribir_con_plan_pendiente():
    # RF-22b: con plan pendiente no se escribe; si se intenta, tampoco se llama al grafo.
    sesion, grafo = sesion_nueva()
    sesion.enviar("hola")
    assert sesion.puede_escribir is False
    llamadas = len(grafo.llamadas)
    sesion.enviar("otro mensaje")
    assert len(grafo.llamadas) == llamadas


def test_aprobar_transmite_al_grafo():
    # RF-8 y RF-20: la aprobación llega al grafo con el mismo identificador.
    sesion, grafo = sesion_nueva()
    sesion.enviar("hola")
    sesion.decidir(True)
    assert grafo.llamadas[-1] == ("aprobar_plan", sesion.thread_id, True)
    assert sesion.estado["done"] is True
    assert sesion.estado["hitl_pendiente"] is False
    assert sesion.puede_decidir is False
    assert "aprobado" in sesion.historial[-1]["texto"].lower()


def test_rechazar_descarta_plan():
    # RF-9 y RF-21: el rechazo descarta el plan, no cierra y permite escribir otro mensaje.
    sesion, grafo = sesion_nueva()
    sesion.enviar("hola")
    sesion.decidir(False)
    assert grafo.llamadas[-1] == ("aprobar_plan", sesion.thread_id, False)
    assert sesion.estado["plan"] == []
    assert sesion.estado["done"] is False
    assert sesion.puede_escribir is True
    sesion.enviar("mejor esto otro")
    assert grafo.llamadas[-1][0] == "procesar_turno"
    assert sesion.estado["hitl_pendiente"] is True


def test_nueva_conversacion():
    # RF-23: nuevo identificador, historial y estado vacíos, incluso con un plan pendiente.
    sesion, _ = sesion_nueva()
    sesion.enviar("hola")
    anterior = sesion.thread_id
    sesion.nueva_conversacion()
    assert sesion.thread_id != anterior
    assert sesion.historial == []
    assert sesion.estado == estado_vacio()
    assert sesion.puede_escribir is True and sesion.puede_decidir is False


def test_error_conserva_historial():
    # RF-5 y RF-25: si el grafo falla, el historial anterior y el estado se conservan y se avisa en español.
    sesion, grafo = sesion_nueva()
    sesion.enviar("primero")
    sesion.decidir(False)
    antes_historial = list(sesion.historial)
    antes_estado = dict(sesion.estado)

    grafo.fallar = True
    sesion.enviar("segundo")

    assert sesion.historial[: len(antes_historial)] == antes_historial
    assert sesion.historial[-1] == {"rol": "error", "texto": MENSAJE_ERROR}
    assert sesion.estado == antes_estado
    assert sesion.error == MENSAJE_ERROR
    # No se filtran detalles internos y la sesión sigue funcionando.
    assert "fallo simulado" not in MENSAJE_ERROR
    grafo.fallar = False
    sesion.enviar("tercero")
    assert sesion.error is None
    assert sesion.estado["hitl_pendiente"] is True


def test_error_al_decidir_conserva_el_plan_pendiente():
    sesion, grafo = sesion_nueva()
    sesion.enviar("hola")
    grafo.fallar = True
    sesion.decidir(True)
    assert sesion.estado["hitl_pendiente"] is True
    assert sesion.estado["done"] is False
    assert sesion.historial[-1]["rol"] == "error"


def test_done_lo_decide_el_grafo():
    # RF-27: aunque se apruebe, la sesión no da la conversación por terminada si el grafo no lo dice.
    class GrafoQueNoCierra(GrafoFalso):
        def aprobar_plan(self, estado, thread_id, aprobado):
            nuevo = super().aprobar_plan(estado, thread_id, aprobado)
            nuevo["done"] = False
            return nuevo

    sesion = SesionChat(GrafoQueNoCierra())
    sesion.enviar("hola")
    sesion.decidir(True)
    assert sesion.estado["done"] is False
