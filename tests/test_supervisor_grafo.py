"""Fallback determinista del supervisor multiagente (spec 005, T4)."""
import pytest

from src.supervisor_reglas import (
    MENSAJE_REFORMULACION,
    ORDEN_FALLBACK,
    elegir_roles_por_reglas,
)
from src.supervisor import ROLES_ADMITIDOS, nodo_supervisor


@pytest.mark.parametrize(
    ("mensaje", "roles"),
    [
        ("¿Cómo llego de Atocha a Sol?", ["rutas"]),
        ("¿Cuál es el horario de la línea 1?", ["horarios"]),
        ("¿Qué hora es ahora?", ["auxiliar"]),
        ("Calcula 3 * 2,50", ["auxiliar"]),
        ("Describe esta imagen del cartel de tarifas.", ["tarifas"]),
        ("¿Qué zona tarifaria CRTM cubre mi abono?", ["rag"]),
    ],
)
def test_fallback_reconoce_cada_intencion_admitida(mensaje, roles):
    """RF-7 a RF-10 y RF-57: cada intención llega al rol correcto."""
    assert elegir_roles_por_reglas(mensaje) == roles


def test_hora_actual_no_se_confunde_con_horario_de_transporte():
    """RF-8 y RF-9: la consulta temporal usa auxiliar, no horarios."""
    assert elegir_roles_por_reglas("¿Qué hora es?") == ["auxiliar"]
    assert elegir_roles_por_reglas("¿A qué hora cierra el metro?") == ["horarios"]


def test_fallback_ordenado_encadena_roles_y_documentacion_con_hora():
    """RF-42 y RF-45: el orden normal es estable y RAG precede a auxiliar."""
    mensaje = (
        "Consulta el corpus CRTM sobre la zona, el horario de metro, "
        "dime qué hora es, cómo llegar de Atocha a Sol y revisa esta imagen."
    )

    assert elegir_roles_por_reglas(mensaje) == list(ORDEN_FALLBACK)
    assert elegir_roles_por_reglas("¿Qué dice el CRTM sobre tarifas y qué hora es?") == [
        "rag",
        "auxiliar",
    ]


def test_total_de_imagen_respeta_la_dependencia_tarifas_y_auxiliar():
    """RF-46: primero se extraen importes de la imagen y luego se calculan."""
    assert elegir_roles_por_reglas("Calcula el total de esta imagen de tarifas.") == [
        "tarifas",
        "auxiliar",
    ]


def test_fallback_desconocido_pide_reformulacion_con_alcance():
    """RF-6 y RF-11: una consulta no clasificable no deriva a un rol inventado."""
    assert elegir_roles_por_reglas("Háblame de astronomía.") == []
    alcance = MENSAJE_REFORMULACION.lower()
    for termino in ["rutas", "crtm", "hora", "cálculos", "imágenes"]:
        assert termino in alcance


def test_supervisor_convierte_una_decision_valida_en_cola():
    """RF-2 y RF-4: solo los roles permitidos llegan a la cola del grafo."""
    actualizacion = nodo_supervisor(
        {"mensaje": "Consulta documental."},
        modelo=lambda mensajes: {"roles": ["rag"]},
    )

    assert actualizacion["cola_roles"] == ["rag"]
    assert set(ROLES_ADMITIDOS) == {"rag", "horarios", "rutas", "auxiliar", "tarifas"}
    assert "respuesta" not in actualizacion


def test_supervisor_conserva_cadena_y_repeticion_del_modelo():
    """RF-3: una cola válida conserva orden y repeticiones para el mismo turno."""
    actualizacion = nodo_supervisor(
        {"mensaje": "Consulta compuesta."},
        modelo=lambda mensajes: {"roles": ["rag", "rutas", "rag"]},
    )

    assert actualizacion["cola_roles"] == ["rag", "rutas", "rag"]


def test_supervisor_acepta_finish_como_una_cola_vacia():
    """RF-2: una decisión válida sin roles permite que el grafo finalice."""
    actualizacion = nodo_supervisor(
        {"mensaje": "No hace falta ninguna tool."},
        modelo=lambda mensajes: {"roles": []},
    )

    assert actualizacion["cola_roles"] == []
    assert "respuesta" not in actualizacion


@pytest.mark.parametrize(
    "respuesta",
    [
        "no es JSON",
        {"roles": "rutas"},
        {"roles": ["rol_prohibido"]},
    ],
)
def test_supervisor_decision_no_interpretable_o_prohibida_usa_fallback(respuesta):
    """RF-6: las decisiones inseguras no se propagan a una arista del grafo."""
    actualizacion = nodo_supervisor(
        {"mensaje": "¿Cómo llego de Atocha a Sol?"},
        modelo=lambda mensajes: respuesta,
    )

    assert actualizacion["cola_roles"] == ["rutas"]
    assert "fallback" in actualizacion["log"][0].lower()


def test_supervisor_usa_fallback_si_el_modelo_lanza_una_excepcion():
    """RF-6: un fallo del LLM conserva una decisión determinista disponible."""
    def modelo_fallido(mensajes):
        raise RuntimeError("proveedor no disponible")

    actualizacion = nodo_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=modelo_fallido,
    )

    assert actualizacion["cola_roles"] == ["auxiliar"]
    assert "fallback" in actualizacion["log"][0].lower()
