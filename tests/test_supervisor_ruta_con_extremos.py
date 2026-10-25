"""Spec 010: el supervisor añade `rutas` a la cola si el mensaje tiene forma de ruta con origen y destino. Sin LLM."""
import pytest

from src.supervisor import ErrorProveedorModelo, decidir_decision_supervisor, nodo_supervisor
from src.supervisor_reglas import completar_rutas_con_extremos

CON_ABONO = "Quiero ir desde Concha Espina hasta Legazpi, ¿cuánto cuesta el abono joven?"


def test_ruta_con_precio_y_cola_rag_pasa_a_rutas_y_rag():
    assert completar_rutas_con_extremos(["rag"], CON_ABONO) == (["rutas", "rag"], 1)


def test_cola_que_ya_tiene_rutas_no_cambia():
    assert completar_rutas_con_extremos(["rutas", "rag"], CON_ABONO) == (["rutas", "rag"], 0)
    assert completar_rutas_con_extremos(["rag", "rutas"], CON_ABONO) == (["rag", "rutas"], 0)   # no reordena


@pytest.mark.parametrize("mensaje", [
    "¿Cuánto cuesta el abono joven?",                  # precio sin ruta
    "¿Cómo voy a pagar el abono?",                     # «voy» sin origen ni destino
    "¿Cómo llego?",                                     # verbo de ruta sin extremos
    "Quiero ir a Sol",                                  # solo destino
    "¿Qué dice el CRTM de los abonos de la zona A?",
    "",
    "   ",
    None,
    5,
])
def test_sin_ruta_con_extremos_no_cambia_nada(mensaje):
    assert completar_rutas_con_extremos(["rag"], mensaje) == (["rag"], 0)


@pytest.mark.parametrize("mensaje", [
    "¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu y cuánto cuesta?",
    "¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu y cuánto cuesta el abono joven?",
    "Quiero ir desde Concha Espina hasta Legazpi, ¿cuánto me cuesta?",
    "Necesito llegar de Atocha a Sol, ¿qué billete necesito?",
    "¿Cómo llego desde Legazpi a Sol? ¿Y el precio?",
    "QUIERO IR DE ATOCHA A SOL",
])
def test_formas_de_ruta_con_origen_y_destino(mensaje):
    assert completar_rutas_con_extremos(["rag"], mensaje) == (["rutas", "rag"], 1)


def test_nunca_quita_roles_y_pone_rutas_primero():
    roles, n = completar_rutas_con_extremos(["rag", "horarios", "auxiliar"], CON_ABONO)
    assert roles == ["rutas", "rag", "horarios", "auxiliar"] and n == 1


def test_cola_vacia_con_ruta_pasa_a_rutas():
    assert completar_rutas_con_extremos([], CON_ABONO) == (["rutas"], 1)


def test_no_modifica_la_lista_recibida():
    cola = ["rag"]
    completar_rutas_con_extremos(cola, CON_ABONO)
    assert cola == ["rag"]


# --- integración con el supervisor (modelo doble) ---

def test_decision_del_llm_se_completa_con_rutas():
    decision = decidir_decision_supervisor({"mensaje": CON_ABONO}, modelo=lambda m: {"roles": ["rag"]})
    assert decision.roles == ["rutas", "rag"] and decision.uso_fallback is False


def test_decision_del_llm_sin_ruta_no_cambia():
    decision = decidir_decision_supervisor({"mensaje": "¿Cuánto cuesta el abono joven?"},
                                           modelo=lambda m: {"roles": ["rag"]})
    assert decision.roles == ["rag"]


def test_el_fallback_tambien_se_completa():
    def proveedor_caido(mensajes):
        raise ErrorProveedorModelo("caído")

    decision = decidir_decision_supervisor({"mensaje": CON_ABONO}, modelo=proveedor_caido)
    assert decision.uso_fallback is True and decision.roles == ["rutas", "rag"]


def test_el_nodo_deja_la_cola_corregida():
    actualizacion = nodo_supervisor({"mensaje": CON_ABONO}, modelo=lambda m: {"roles": ["rag"]})
    assert actualizacion["cola_roles"] == ["rutas", "rag"]
