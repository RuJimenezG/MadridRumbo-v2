"""Fallback determinista del supervisor multiagente (spec 005, T4)."""
import pytest

from src.supervisor_reglas import (
    MENSAJE_REFORMULACION,
    ORDEN_FALLBACK,
    elegir_roles_por_reglas,
)
from src.modelos import ErrorProveedorModelo, crear_modelo_supervisor
from src.supervisor import ROLES_ADMITIDOS, decidir_decision_supervisor, nodo_supervisor


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


@pytest.mark.parametrize(
    "mensaje",
    [
        "QUIERO IR DE Átocha A Sol, por favor.",
        "Necesito, ir de Atocha a Sol!!!",
        "Voy de Atocha a Sol; dime cómo.",
    ],
)
def test_reglas_reconocen_formulaciones_equivalentes_de_ruta(mensaje):
    assert elegir_roles_por_reglas(mensaje) == ["rutas"]


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


def test_prompt_del_supervisor_exige_json_sin_envoltorios():
    """RF-2 y RF-3: el ejemplo e instrucción no dejan formato ambiguo."""
    mensajes_recibidos = []

    actualizacion = nodo_supervisor(
        {"mensaje": "Consulta documental."},
        modelo=lambda mensajes: mensajes_recibidos.append(mensajes) or {"roles": []},
    )

    instruccion = mensajes_recibidos[0][0]["content"]
    assert actualizacion["cola_roles"] == []
    assert '{"roles": ["auxiliar"]}' in instruccion
    assert "exclusivamente" in instruccion.lower()
    assert "json" in instruccion.lower()
    assert "markdown" in instruccion.lower()
    assert "texto" in instruccion.lower()


def test_adaptador_del_supervisor_conserva_el_texto_para_normalizarlo():
    """RF-5: la normalización estricta ocurre en el Supervisor, no antes."""
    respuesta = '```json\n{"roles": ["rag"]}\n```'
    supervisor = crear_modelo_supervisor(generar=lambda prompt: respuesta)

    assert supervisor("Consulta documental.") == respuesta


@pytest.mark.parametrize(
    "respuesta",
    [
        '{"roles": ["rag"]}',
        ' \n```\n{"roles": ["rag"]}\n```\t ',
        '```json\n{"roles": ["rag"]}\n```',
        '```JSON\n{"roles": ["rag"]}\n```',
    ],
)
def test_supervisor_acepta_json_y_fences_markdown_recuperables(respuesta):
    """RF-5: solo el envoltorio Markdown permitido se retira de forma segura."""
    actualizacion = nodo_supervisor(
        {"mensaje": "Consulta documental."},
        modelo=lambda mensajes: respuesta,
    )

    assert actualizacion["cola_roles"] == ["rag"]
    assert "log" not in actualizacion


@pytest.mark.parametrize(
    "respuesta",
    [
        "{'roles': ['rag']}",
        'La decisión es: {"roles": ["rag"]}',
        '```python\n{"roles": ["rag"]}\n```',
        '```json\n{"roles": ["rag"]}\n```\nTexto adicional',
    ],
)
def test_supervisor_rechaza_json_con_formato_no_recuperable(respuesta):
    """RF-6 y RF-7: no se reparan comillas ni se extraen objetos parciales."""
    actualizacion = nodo_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=lambda mensajes: respuesta,
    )

    assert actualizacion["cola_roles"] == ["auxiliar"]
    assert "log" not in actualizacion


@pytest.mark.parametrize(
    "roles",
    [
        [],
        ["rag", "rag"],
        ["auxiliar"] * 20,
    ],
)
def test_decision_de_roles_valida_conserva_orden_y_sin_fallback(roles):
    """RF-4: lista vacía, repetición y máximo permitido siguen siendo válidos."""
    decision = decidir_decision_supervisor(
        {"mensaje": "Consulta documental."},
        modelo=lambda mensajes: {"roles": roles},
    )

    assert decision.roles == roles
    assert decision.uso_fallback is False
    assert decision.categoria == "sin_fallback"


@pytest.mark.parametrize(
    "respuesta",
    [
        {"roles": ["rag"], "explicacion": "no permitida"},
        {},
        {"roles": "rag"},
        {"roles": ["rag"] * 21},
        {"roles": ["rol_prohibido"]},
    ],
)
def test_roles_fuera_del_contrato_activan_fallback_clasificado(respuesta):
    """RF-9 y RF-12: la forma y allowlist se validan antes de encolar roles."""
    decision = decidir_decision_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=lambda mensajes: respuesta,
    )

    assert decision.roles == ["auxiliar"]
    assert decision.uso_fallback is True
    assert decision.categoria == "roles_invalidos"


@pytest.mark.parametrize(
    "respuesta",
    [
        "{'roles': ['rag']}",
        'Texto adicional: {"roles": ["rag"]}',
    ],
)
def test_json_no_valido_activa_fallback_clasificado(respuesta):
    """RF-6, RF-7 y RF-12: el parseo no se confunde con roles inválidos."""
    decision = decidir_decision_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=lambda mensajes: respuesta,
    )

    assert decision.roles == ["auxiliar"]
    assert decision.uso_fallback is True
    assert decision.categoria == "json_invalido"


@pytest.mark.parametrize(
    "modelo",
    [
        lambda mensajes: (_ for _ in ()).throw(
            ErrorProveedorModelo("TOKEN_DE_PRUEBA_NO_EXPOSABLE")
        ),
        lambda mensajes: (_ for _ in ()).throw(RuntimeError("PROMPT_SECRETO")),
        lambda mensajes: "",
        lambda mensajes: None,
    ],
)
def test_incidencias_de_proveedor_activan_fallback_sin_filtrar_detalles(modelo):
    """RF-8 y RF-14: toda incidencia del proveedor usa un resumen fijo seguro."""
    decision = decidir_decision_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=modelo,
    )

    assert decision.roles == ["auxiliar"]
    assert decision.uso_fallback is True
    assert decision.categoria == "proveedor"
    assert "TOKEN_DE_PRUEBA_NO_EXPOSABLE" not in decision.resumen
    assert "PROMPT_SECRETO" not in decision.resumen


@pytest.mark.parametrize(
    "modelo, categoria",
    [
        (lambda mensajes: {"roles": ["rag"]}, "sin_fallback"),
        (
            lambda mensajes: (_ for _ in ()).throw(ErrorProveedorModelo("sin red")),
            "proveedor",
        ),
    ],
)
def test_nodo_supervisor_deja_diagnostico_solo_en_contexto_efimero(modelo, categoria):
    """RF-10 y RF-11: el nodo no persiste el diagnóstico en su actualización."""
    contexto = {}

    actualizacion = nodo_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=modelo,
        contexto=contexto,
    )

    assert contexto["diagnostico_supervisor"]["categoria"] == categoria
    assert isinstance(contexto["diagnostico_supervisor"]["resumen"], str)
    assert "log" not in actualizacion
    assert "traza" not in actualizacion


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
    assert "log" not in actualizacion


def test_supervisor_usa_fallback_si_el_modelo_lanza_una_excepcion():
    """RF-6: un fallo del LLM conserva una decisión determinista disponible."""
    def modelo_fallido(mensajes):
        raise RuntimeError("proveedor no disponible")

    actualizacion = nodo_supervisor(
        {"mensaje": "¿Qué hora es?"},
        modelo=modelo_fallido,
    )

    assert actualizacion["cola_roles"] == ["auxiliar"]
    assert "log" not in actualizacion
