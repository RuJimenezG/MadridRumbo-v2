"""Tests de SesionChat, la lógica que comparten el CLI y Streamlit (spec 008).

Cubre RF-2, RF-5, RF-8, RF-9, RF-18 a RF-23, RF-22b, RF-25 y RF-27 con un grafo simulado: no usan API.
"""
import config
from src.clientes.contrato import estado_vacio
from src.clientes.grafo_falso import GrafoFalso
from src.clientes.sesion import MENSAJE_ERROR, SesionChat


# Pedido de ruta: con el grafo simulado (como con el real) es el único que deja un plan pendiente.
RUTA = config.PEDIDOS_DEMO[1]


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
    sesion.enviar(RUTA)
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
    sesion.enviar(RUTA)
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
    sesion.enviar(RUTA)
    assert sesion.puede_escribir is False
    llamadas = len(grafo.llamadas)
    sesion.enviar("otro mensaje")
    assert len(grafo.llamadas) == llamadas


def test_aprobar_transmite_al_grafo():
    # RF-8 y RF-20: la aprobación llega al grafo con el mismo identificador.
    sesion, grafo = sesion_nueva()
    sesion.enviar(RUTA)
    sesion.decidir(True)
    assert grafo.llamadas[-1] == ("aprobar_plan", sesion.thread_id, True)
    assert sesion.estado["done"] is True
    assert sesion.estado["hitl_pendiente"] is False
    assert sesion.puede_decidir is False
    assert "aprobado" in sesion.historial[-1]["texto"].lower()


def test_rechazar_descarta_plan():
    # RF-9 y RF-21: el rechazo descarta el plan, no cierra y permite escribir otro mensaje.
    sesion, grafo = sesion_nueva()
    sesion.enviar(RUTA)
    sesion.decidir(False)
    assert grafo.llamadas[-1] == ("aprobar_plan", sesion.thread_id, False)
    assert sesion.estado["plan"] == []
    assert sesion.estado["done"] is False
    assert sesion.puede_escribir is True
    sesion.enviar(RUTA)
    assert grafo.llamadas[-1][0] == "procesar_turno"
    assert sesion.estado["hitl_pendiente"] is True


def test_nueva_conversacion():
    # RF-23: nuevo identificador, historial y estado vacíos, incluso con un plan pendiente.
    sesion, _ = sesion_nueva()
    sesion.enviar(RUTA)
    anterior = sesion.thread_id
    sesion.nueva_conversacion()
    assert sesion.thread_id != anterior
    assert sesion.historial == []
    assert sesion.estado == estado_vacio()
    assert sesion.puede_escribir is True and sesion.puede_decidir is False


def test_error_conserva_historial():
    # RF-5 y RF-25: si el grafo falla, el historial anterior y el estado se conservan y se avisa en español.
    sesion, grafo = sesion_nueva()
    sesion.enviar(RUTA)
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
    sesion.enviar(RUTA)
    assert sesion.error is None
    assert sesion.estado["hitl_pendiente"] is True


def test_error_al_decidir_conserva_el_plan_pendiente():
    sesion, grafo = sesion_nueva()
    sesion.enviar(RUTA)
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
    sesion.enviar(RUTA)
    sesion.decidir(True)
    assert sesion.estado["done"] is False


# --- Varios planes y elección del plan (spec 008, RF-31 y RF-32) ---

VARIAS_RUTAS = "Dame dos rutas alternativas desde la Puerta del Sol hasta la Estación de Atocha"


class GrafoEspia(GrafoFalso):
    """Grafo simulado que además guarda el `estado` que recibe `aprobar_plan`."""

    def __init__(self):
        super().__init__()
        self.estados_recibidos = []

    def aprobar_plan(self, estado, thread_id, aprobado):
        self.estados_recibidos.append(dict(estado))
        return super().aprobar_plan(estado, thread_id, aprobado)


def sesion_espia(pedido):
    grafo = GrafoEspia()
    sesion = SesionChat(grafo)
    sesion.enviar(pedido)
    return sesion, grafo


def test_planes_expone_los_planes_pendientes():
    uno, _ = sesion_espia(RUTA)
    varios, _ = sesion_espia(VARIAS_RUTAS)
    assert [plan["id"] for plan in uno.planes] == ["ruta-1"]
    assert [plan["id"] for plan in varios.planes] == ["ruta-1", "ruta-2"]
    assert SesionChat(GrafoFalso()).planes == []


def test_un_plan_se_decide_sin_indicar_cual():
    # RF-32: con un único plan no hace falta elegir y no se envía ningún identificador.
    sesion, grafo = sesion_espia(RUTA)
    sesion.decidir(True)
    assert "plan_id_seleccionado" not in grafo.estados_recibidos[-1]
    assert sesion.estado["done"] is True


def test_con_un_plan_tambien_se_acepta_su_identificador():
    sesion, grafo = sesion_espia(RUTA)
    sesion.decidir(True, plan_id="ruta-1")
    assert grafo.estados_recibidos[-1]["plan_id_seleccionado"] == "ruta-1"
    assert sesion.estado["done"] is True


def test_decidir_con_varios_planes_envia_el_elegido():
    # RF-31: el identificador elegido llega al grafo en el estado.
    sesion, grafo = sesion_espia(VARIAS_RUTAS)
    sesion.decidir(True, plan_id="ruta-2")
    assert grafo.estados_recibidos[-1]["plan_id_seleccionado"] == "ruta-2"
    assert sesion.estado["done"] is True
    assert sesion.estado["hitl_pendiente"] is False


def test_varios_planes_sin_elegir_no_llama_al_grafo():
    # RF-31: sin elección no se llama al grafo y el plan sigue pendiente.
    sesion, grafo = sesion_espia(VARIAS_RUTAS)
    antes = list(grafo.llamadas)
    estado_antes = dict(sesion.estado)
    sesion.decidir(True)
    assert grafo.llamadas == antes
    assert sesion.estado == estado_antes
    assert sesion.puede_decidir is True


def test_plan_inexistente_no_llama_al_grafo():
    sesion, grafo = sesion_espia(VARIAS_RUTAS)
    antes = list(grafo.llamadas)
    sesion.decidir(True, plan_id="ruta-9")
    assert grafo.llamadas == antes
    assert sesion.puede_decidir is True


def test_rechazar_un_plan_deja_los_demas_pendientes():
    sesion, grafo = sesion_espia(VARIAS_RUTAS)
    sesion.decidir(False, plan_id="ruta-1")
    assert [plan["id"] for plan in sesion.planes] == ["ruta-2"]
    assert sesion.puede_decidir is True and sesion.puede_escribir is False
    # Con un único plan restante ya no hace falta elegir.
    sesion.decidir(True)
    assert sesion.estado["done"] is True


def test_el_estado_de_la_sesion_no_se_ensucia_con_el_plan_elegido():
    sesion, grafo = sesion_espia(VARIAS_RUTAS)
    grafo.fallar = True
    sesion.decidir(True, plan_id="ruta-2")
    assert "plan_id_seleccionado" not in sesion.estado
    assert sesion.historial[-1]["rol"] == "error"
