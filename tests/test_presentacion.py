"""Tests de presentación y contrato de los clientes (spec 008, RF-3, RF-4, RF-10, RF-15, RF-16, RF-24 y RF-26).

Son funciones puras: no usan grafo, red ni API.
"""
import pytest

from src.clientes.contrato import estado_vacio, normalizar_estado
from src.clientes.presentacion import (
    datos_depuracion,
    es_mensaje_vacio,
    es_salida,
    formatear_turno,
    interpretar_decision,
)

ESTADO = {
    "respuesta": "El metro cierra a la 1:30.",
    "plan": ["Informar del horario", "Citar la fuente"],
    "log": [],
    "traza": [
        {"tool": "hora_actual", "args": {}, "status": "ok", "preview": "Hoy es jueves"},
        {"tool": "rag_ask", "args": {"consulta": "horario"}, "status": "error", "preview": "ERROR"},
    ],
    "hitl_pendiente": True,
    "done": False,
}


REGISTRO_ESTRUCTURADO = [
    {
        "paso": 1,
        "tipo": "nodo",
        "nodo": "supervisor",
        "entrada": {"mensaje": "¿Cuál es la tarifa?"},
        "salida": {"roles": ["rag"]},
        "resultado": "completado",
        "detalle": None,
    },
    {
        "paso": 2,
        "tipo": "tool",
        "nodo": "rag_ask",
        "entrada": {"consulta": "tarifa"},
        "salida": {"texto": "La tarifa es 1,50 €."},
        "resultado": "completado",
        "detalle": None,
    },
    {
        "paso": 3,
        "tipo": "control",
        "nodo": "fachada",
        "entrada": None,
        "salida": None,
        "resultado": "rechazado",
        "detalle": {"categoria": "plan_pendiente", "resumen": "Aprueba o rechaza el plan."},
    },
    {
        "paso": 4,
        "tipo": "nodo",
        "nodo": "supervisor",
        "entrada": {"mensaje": "Consulta ambigua"},
        "salida": None,
        "resultado": "fallido",
        "detalle": {"categoria": "json_invalido", "resumen": "Se aplicó el fallback del Supervisor."},
    },
]

DIAGNOSTICO_ESTRUCTURADO = {
    "paso": 9,
    "tipo": "nodo",
    "nodo": "supervisor",
    "entrada": {"mensaje": "Consulta ambigua"},
    "salida": None,
    "resultado": "fallido",
    "detalle": {"categoria": "json_invalido", "resumen": "Se aplicó el fallback del Supervisor."},
}

# Los consumidores reciben exclusivamente el contrato estructurado del registro.
ESTADO["log"] = [REGISTRO_ESTRUCTURADO[0], REGISTRO_ESTRUCTURADO[1]]


# --- Contrato ---

def test_estado_vacio():
    # El estado inicial no tiene respuesta, plan ni trazas y no está pendiente ni terminado.
    assert estado_vacio() == {
        "respuesta": "", "plan": [], "log": [], "traza": [], "hitl_pendiente": False, "done": False,
    }


def test_normalizar_rellena_claves_ausentes():
    # El grafo real puede devolver menos claves: las que faltan toman su valor por defecto.
    estado = normalizar_estado({"respuesta": "hola"})
    assert estado["respuesta"] == "hola"
    assert estado["plan"] == [] and estado["traza"] == [] and estado["log"] == []
    assert estado["hitl_pendiente"] is False and estado["done"] is False


def test_normalizar_conserva_claves_desconocidas_y_no_modifica_la_entrada():
    original = {"respuesta": "hola", "extra": 1}
    estado = normalizar_estado(original)
    assert estado["extra"] == 1
    assert "plan" not in original  # no se modifica el diccionario recibido


def test_normalizar_none():
    assert normalizar_estado(None) == estado_vacio()


# --- Formato del turno (RF-15, RF-16) ---

def test_formato_incluye_respuesta_log_traza():
    # RF-15: respuesta, especialistas que actuaron y tools con su estado.
    texto = formatear_turno(ESTADO, "hilo-1")
    assert "El metro cierra a la 1:30." in texto
    assert "Paso 1 · nodo · supervisor [completado]" in texto
    assert "Paso 2 · tool · rag_ask [completado]" in texto
    assert "hora_actual" in texto and "rag_ask" in texto
    assert "ok" in texto and "error" in texto


def test_formato_incluye_thread_id_y_banderas():
    # RF-16: identificador de conversación y banderas de plan pendiente y terminada.
    texto = formatear_turno(ESTADO, "hilo-1")
    assert "hilo-1" in texto
    assert "Plan pendiente: sí" in texto
    assert "Terminada: no" in texto
    terminado = formatear_turno({**ESTADO, "hitl_pendiente": False, "done": True}, "hilo-1")
    assert "Plan pendiente: no" in terminado and "Terminada: sí" in terminado


def test_formato_muestra_el_plan_cuando_hay():
    texto = formatear_turno(ESTADO, "hilo-1")
    assert "Informar del horario" in texto and "Citar la fuente" in texto


def test_formato_con_estado_parcial_no_falla():
    # Un grafo que solo devuelve la respuesta no rompe la presentación.
    texto = formatear_turno({"respuesta": "hola"}, "hilo-2")
    assert "hola" in texto and "hilo-2" in texto
    assert "Plan pendiente: no" in texto


def test_formato_muestra_el_registro_estructurado_completo_y_ordenado():
    """RF-23: CLI recibe todas las clases de entrada con sus siete campos."""
    texto = formatear_turno({"respuesta": "Resultado", "log": REGISTRO_ESTRUCTURADO}, "hilo-registro")

    assert "Registro de depuración:" in texto
    for paso, tipo, nodo, resultado in (
        (1, "nodo", "supervisor", "completado"),
        (2, "tool", "rag_ask", "completado"),
        (3, "control", "fachada", "rechazado"),
        (4, "nodo", "supervisor", "fallido"),
    ):
        assert f"Paso {paso} · {tipo} · {nodo} [{resultado}]" in texto
    assert 'entrada: {"mensaje": "¿Cuál es la tarifa?"}' in texto
    assert 'salida: {"texto": "La tarifa es 1,50 €."}' in texto
    assert "detalle: null" in texto
    assert '"categoria": "plan_pendiente"' in texto
    assert '"categoria": "json_invalido"' in texto
    assert texto.index("Paso 1") < texto.index("Paso 2") < texto.index("Paso 3") < texto.index("Paso 4")


# --- Entradas de la persona (RF-3, RF-4, RF-10) ---

@pytest.mark.parametrize("texto", ["", "   ", "\n", "\t "])
def test_es_mensaje_vacio(texto):
    # RF-3
    assert es_mensaje_vacio(texto) is True


def test_mensaje_con_texto_no_es_vacio():
    assert es_mensaje_vacio("hola") is False


@pytest.mark.parametrize("texto", ["salir", "SALIR", "  Salir  ", "exit", "quit"])
def test_es_salida(texto):
    # RF-4
    assert es_salida(texto) is True


def test_no_es_salida():
    assert es_salida("¿hasta qué hora hay metro?") is False


@pytest.mark.parametrize("texto", ["s", "S", "sí", "si", " Sí ", "aprobar", "a"])
def test_interpretar_decision_aprobar(texto):
    # RF-10
    assert interpretar_decision(texto) is True


@pytest.mark.parametrize("texto", ["n", "N", "no", " NO ", "rechazar", "r"])
def test_interpretar_decision_rechazar(texto):
    assert interpretar_decision(texto) is False


@pytest.mark.parametrize("texto", ["", "quizá", "x", "1", "siii"])
def test_interpretar_decision_invalida(texto):
    # RF-10: lo que no se reconoce devuelve None y el cliente vuelve a preguntar.
    assert interpretar_decision(texto) is None


# --- Depuración (RF-24) ---

def test_datos_depuracion():
    # RF-24: registro de especialistas, trazas, identificador y banderas.
    datos = datos_depuracion(ESTADO, "hilo-1")
    assert datos["thread_id"] == "hilo-1"
    assert datos["log"] == ESTADO["log"]
    assert datos["traza"] == ESTADO["traza"]
    assert datos["hitl_pendiente"] is True and datos["done"] is False


def test_panel_depuracion_conserva_el_diagnostico_estructurado_y_el_chat_lo_filtra():
    """RF-24 y RF-25: el panel es completo; el chat solo omite el diagnóstico técnico."""
    from src.clientes.presentacion import pasos_del_turno

    visible = REGISTRO_ESTRUCTURADO[0]
    estado = {"respuesta": "x", "log": [visible, DIAGNOSTICO_ESTRUCTURADO]}

    assert datos_depuracion(estado, "h")['log'] == [visible, DIAGNOSTICO_ESTRUCTURADO]
    assert datos_depuracion(estado, "h", ocultar_tecnicas=True)['log'] == [visible]
    pasos = pasos_del_turno([visible, DIAGNOSTICO_ESTRUCTURADO], [])
    assert pasos == ["Flujo: supervisor"]
    assert "json_invalido" not in "\n".join(pasos)


# --- Mismo formato en CLI y Streamlit (RF-26) ---

def test_cli_usa_el_mismo_formato():
    # RF-26: lo que imprime el CLI es exactamente `formatear_turno`, la misma función que usa Streamlit.
    from src.clientes.cli import ejecutar_cli

    estado_grafo = {
        "respuesta": "Respuesta del grafo",
        "log": [REGISTRO_ESTRUCTURADO[0]],
        "traza": [{"tool": "hora_actual", "args": {}, "status": "ok", "preview": "Hoy es jueves"}],
        "hitl_pendiente": False,
        "done": False,
    }

    class Grafo:
        llamadas = []

        def procesar_turno(self, estado, mensaje, thread_id):
            self.llamadas.append(thread_id)
            return dict(estado_grafo)

    grafo = Grafo()
    entradas = iter(["hola", "salir"])
    salida = []
    ejecutar_cli([], grafo, lambda prompt="": next(entradas), salida.append, None)

    esperado = formatear_turno(estado_grafo, grafo.llamadas[0])
    assert esperado in "\n".join(salida)


# --- Planes de ruta y entradas técnicas del supervisor (spec 008, RF-6, RF-30 y RF-35) ---

def _plan_de_ruta(numero):
    return {
        "id": f"ruta-{numero}",
        "resultado": {
            "estado": "ok",
            "origen": {"direccion": "Puerta del Sol, Madrid"},
            "destino": {"direccion": "Estación de Atocha, Madrid"},
            "ruta": {"duracion_min": 12, "tramos": [{"modo": "A pie", "linea": None, "duracion_min": 3}]},
            "zona": {"estado": "ok", "texto": "Zona A", "fuente": "RAG"},
            "precio": {"estado": "ok", "texto": "1,50 €", "fuente": "RAG"},
        },
    }


LOG_CON_TECNICAS = [
    {
        "paso": 1,
        "tipo": "nodo",
        "nodo": "rutas",
        "entrada": {"mensaje": "ruta"},
        "salida": {"nota": "ruta lista"},
        "resultado": "completado",
        "detalle": None,
    },
    DIAGNOSTICO_ESTRUCTURADO,
    {
        "paso": 3,
        "tipo": "nodo",
        "nodo": "rag",
        "entrada": {"mensaje": "tarifa"},
        "salida": {"nota": "tarifa lista"},
        "resultado": "completado",
        "detalle": None,
    },
    {
        "paso": 4,
        "tipo": "nodo",
        "nodo": "supervisor",
        "entrada": {"mensaje": "tarifa"},
        "salida": None,
        "resultado": "fallido",
        "detalle": {"categoria": "correccion_semantica", "resumen": "Se redirigió a RAG."},
    },
]


def test_formato_muestra_el_resumen_de_cada_plan():
    # RF-6 y RF-30: cada plan con su identificador y un resumen legible, no el diccionario en bruto.
    estado = {"respuesta": "Ruta preparada", "plan": [_plan_de_ruta(1), _plan_de_ruta(2)], "hitl_pendiente": True}
    texto = formatear_turno(estado, "hilo-1")
    assert "ruta-1" in texto and "ruta-2" in texto
    assert texto.count("Origen: Puerta del Sol, Madrid") == 2
    assert "12 min" in texto and "Zona A" in texto and "1,50 €" in texto
    assert "{'id'" not in texto and "'resultado'" not in texto


def test_el_titulo_del_plan_depende_de_cuantos_hay():
    uno = formatear_turno({"respuesta": "x", "plan": [_plan_de_ruta(1)]}, "h")
    varios = formatear_turno({"respuesta": "x", "plan": [_plan_de_ruta(1), _plan_de_ruta(2)]}, "h")
    assert "Plan propuesto:" in uno and "Planes propuestos:" not in uno
    assert "Planes propuestos:" in varios


def test_un_plan_desconocido_no_rompe_el_formato():
    texto = formatear_turno({"respuesta": "x", "plan": [{"id": "otro-1", "resultado": {"cosa": 1}}]}, "h")
    assert "otro-1" in texto and "cosa: 1" in texto


def test_por_defecto_se_muestran_las_entradas_tecnicas():
    # El CLI muestra todo el registro estructurado, incluidos diagnósticos.
    texto = formatear_turno({"respuesta": "x", "log": LOG_CON_TECNICAS}, "h")
    for entrada in LOG_CON_TECNICAS:
        assert f"Paso {entrada['paso']} · {entrada['tipo']} · {entrada['nodo']} [{entrada['resultado']}]" in texto


def test_ocultar_tecnicas():
    # RF-25: la web oculta diagnósticos y conserva los demás pasos estructurados.
    texto = formatear_turno({"respuesta": "x", "log": LOG_CON_TECNICAS}, "h", ocultar_tecnicas=True)
    assert "json_invalido" not in texto
    assert "correccion_semantica" not in texto
    assert "Paso 1 · nodo · rutas [completado]" in texto
    assert "Paso 3 · nodo · rag [completado]" in texto


def test_ocultar_tecnicas_filtra_el_control_de_correccion_semantica():
    """RF-12: el chat no muestra el control técnico de tarifas entre zonas."""
    control = {
        "paso": 5,
        "tipo": "control",
        "nodo": "supervisor",
        "entrada": None,
        "salida": None,
        "resultado": "rechazado",
        "detalle": {
            "categoria": "correccion_semantica",
            "resumen": "Se redirigió 1 aparición de rutas a rag por una consulta tarifaria entre zonas.",
        },
    }

    texto = formatear_turno({"respuesta": "x", "log": [control]}, "h", ocultar_tecnicas=True)

    assert "Registro de depuración" not in texto
    assert "correccion_semantica" not in texto


def test_si_todo_el_log_es_tecnico_no_queda_la_seccion_de_especialistas():
    solo_tecnicas = [LOG_CON_TECNICAS[1], LOG_CON_TECNICAS[3]]
    texto = formatear_turno({"respuesta": "x", "log": solo_tecnicas}, "h", ocultar_tecnicas=True)
    assert "Registro de depuración" not in texto


def test_la_depuracion_tambien_puede_ocultar_las_tecnicas():
    estado = {"respuesta": "x", "log": LOG_CON_TECNICAS}
    assert datos_depuracion(estado, "h")["log"] == LOG_CON_TECNICAS
    oculto = datos_depuracion(estado, "h", ocultar_tecnicas=True)["log"]
    assert oculto == [LOG_CON_TECNICAS[0], LOG_CON_TECNICAS[2]]


# --- Pasos seguidos (spec 008, RF-39, RF-40 y RF-41) ---

def test_pasos_numeran_las_tools_con_nombre_estado_y_extracto():
    # RF-39: cada tool ejecutada aparece numerada con su nombre, su estado y un extracto.
    from src.clientes.presentacion import pasos_del_turno

    assert pasos_del_turno([], ESTADO["traza"]) == [
        "1. hora_actual [ok] Hoy es jueves",
        "2. rag_ask [error] ERROR",
    ]


def test_pasos_incluyen_el_registro_antes_de_las_tools():
    # RF-39 y RF-42: el flujo de nodos va primero y las tools de la traza después, sin repetir la tool del registro.
    from src.clientes.presentacion import pasos_del_turno

    pasos = pasos_del_turno(ESTADO["log"], ESTADO["traza"])
    assert pasos[0] == "Flujo: supervisor"
    assert pasos[1].startswith("1. hora_actual")
    assert len(pasos) == 3


def test_pasos_ocultan_el_diagnostico_del_supervisor_por_defecto():
    # RF-39 y RF-35: la web no muestra los diagnósticos técnicos; el CLI puede pedirlos.
    from src.clientes.presentacion import pasos_del_turno

    log = [DIAGNOSTICO_ESTRUCTURADO, LOG_CON_TECNICAS[0]]
    assert pasos_del_turno(log, []) == ["Flujo: rutas"]
    assert pasos_del_turno(log, [], ocultar_tecnicas=False) == ["Flujo: supervisor → rutas"]


def test_pasos_vacios_sin_tools_ni_registro_visible():
    # RF-41: sin nada que mostrar no hay pasos, ni siquiera con solo un diagnóstico oculto.
    from src.clientes.presentacion import pasos_del_turno

    assert pasos_del_turno([], []) == []
    assert pasos_del_turno([DIAGNOSTICO_ESTRUCTURADO], []) == []


def test_pasos_recortan_el_extracto_largo():
    # RF-39: el extracto de cada tool tiene la misma longitud máxima que en el CLI.
    from src.clientes.presentacion import PREVIEW_MAX, pasos_del_turno

    largo = "x" * (PREVIEW_MAX + 50)
    (linea,) = pasos_del_turno([], [{"tool": "rag_ask", "args": {}, "status": "ok", "preview": largo}])
    assert linea == f"1. rag_ask [ok] {'x' * PREVIEW_MAX}"


# --- «Pasos seguidos» como resumen del registro estructurado (spec 008, RF-39 y RF-42) ---

def _nodo(paso, nodo, entrada=None, salida=None):
    return {"paso": paso, "tipo": "nodo", "nodo": nodo, "entrada": entrada, "salida": salida,
            "resultado": "completado", "detalle": None}


def test_pasos_muestran_el_flujo_de_nodos_en_orden():
    # RF-42: el flujo recorrido se resume en una línea con los nodos en el orden en que actuaron.
    from src.clientes.presentacion import pasos_del_turno

    log = [_nodo(1, "supervisor"), _nodo(2, "rutas"), _nodo(3, "sintetizador")]
    assert pasos_del_turno(log, []) == ["Flujo: supervisor → rutas → sintetizador"]


def test_pasos_son_un_resumen_sin_entrada_ni_salida():
    # RF-39: el detalle completo (entrada, salida y detalle de cada paso) es solo del panel de depuración.
    from src.clientes.presentacion import pasos_del_turno

    log = [_nodo(1, "rutas", entrada={"mensaje": "texto largo del usuario"}, salida={"nota": "resultado largo"})]
    texto = "\n".join(pasos_del_turno(log, []))
    assert "entrada:" not in texto and "salida:" not in texto and "detalle:" not in texto
    assert "texto largo del usuario" not in texto and "resultado largo" not in texto


def test_pasos_incluyen_los_pasos_de_control_que_no_son_diagnostico_del_supervisor():
    # RF-39: un paso de control de la fachada se muestra resumido en una línea.
    from src.clientes.presentacion import pasos_del_turno

    control = {"paso": 1, "tipo": "control", "nodo": "fachada", "entrada": None, "salida": None,
               "resultado": "rechazado", "detalle": {"categoria": "plan_pendiente", "resumen": "Aprueba o rechaza."}}
    assert pasos_del_turno([control], []) == ["Paso 1 · control · fachada [rechazado]"]


def test_pasos_conservan_las_entradas_heredadas_en_texto():
    # RF-39: un cliente o grafo que aún devuelva textos en el registro no pierde esas líneas.
    from src.clientes.presentacion import pasos_del_turno

    assert pasos_del_turno(["[horarios] nota lista"], []) == ["[horarios] nota lista"]
