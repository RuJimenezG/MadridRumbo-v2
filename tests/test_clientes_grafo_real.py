"""Los clientes contra el grafo real de `src/agent.py` (spec 008, RF-26 y RF-30 a RF-35).

Se construye el grafo real con `crear_grafo` y se inyectan el supervisor, los especialistas y el
sintetizador, así que no se llama a ningún LLM, tool ni red. Solo cambia lo que habría detrás:
el contrato (`procesar_turno` y `aprobar_plan`) y su máquina de estados son los de verdad.
"""
import pytest

import src.agent as agent
from src.clientes.cargar import cargar_agente
from src.clientes.cli import ejecutar_cli
from src.clientes.contrato import estado_vacio
from src.clientes.planes import ids_de_planes
from src.clientes.presentacion import datos_depuracion, formatear_turno, pasos_del_turno
from src.clientes.sesion import SesionChat
from src.graph import crear_grafo
from tests.test_cli import Entrada

RUTA_OK = {
    "estado": "ok",
    "origen": {"direccion": "Atocha"},
    "destino": {"direccion": "Sol"},
    "ruta": {"duracion_min": 12, "tramos": [{"modo": "SUBWAY", "linea": "1"}]},
}
ALTERNATIVA = {**RUTA_OK, "ruta": {"duracion_min": 20, "tramos": [{"modo": "BUS", "linea": "27"}]}}
PEDIDO_RUTA = "Dame una ruta de Atocha a Sol."


def _resultado_rutas(*rutas):
    """Resultados de `planificar_ruta` con la forma que espera el normalizador de planes del grafo."""
    return {
        "resultados": [
            {
                "especialista": "rutas",
                "tool": "planificar_ruta",
                "status": "ok",
                "resultado": ruta,
                "args": {"origen": "Atocha", "destino": "Sol"},
            }
            for ruta in rutas
        ]
    }


def _nota(rol, texto):
    return {"notas": [f"[{rol}] {texto}"], "traza": [], "resultados": []}


def _sintetizar(contexto):
    """Usa la nota de aprobación si existe; si no, un texto fijo."""
    for nota in contexto["notas"]:
        if "Plan aprobado" in nota:
            return nota
    return "Respuesta del sintetizador."


def _especialistas_sin_api():
    """Un especialista falso por rol, para que ningún camino llegue a un LLM real."""
    return {
        "rag": lambda estado: _nota("rag", "No lo sé, no está en los documentos."),
        "horarios": lambda estado: _nota("horarios", "El metro cierra a la 1:30."),
        "auxiliar": lambda estado: _nota("auxiliar", "Son las 18:00."),
        "tarifas": lambda estado: _nota("tarifas", "Sin imagen."),
    }


@pytest.fixture
def contadores():
    return {"supervisor": 0, "rutas": 0}


@pytest.fixture
def grafo_de_ruta(monkeypatch, contadores):
    """Grafo real donde una ruta genera un único plan; al rechazarlo se replanifica con otro."""
    respuestas = [RUTA_OK, ALTERNATIVA, RUTA_OK]

    def supervisor(mensajes):
        contadores["supervisor"] += 1
        return {"roles": ["rutas"]}

    def rutas(estado):
        contadores["rutas"] += 1
        return _resultado_rutas(respuestas.pop(0))

    grafo = crear_grafo(
        modelo_supervisor=supervisor,
        especialistas={**_especialistas_sin_api(), "rutas": rutas},
        modelo_sintetizador=_sintetizar,
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    return grafo


@pytest.fixture
def grafo_de_varias_rutas(monkeypatch):
    """Grafo real donde una consulta genera dos planes a la vez."""
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        especialistas={**_especialistas_sin_api(), "rutas": lambda estado: _resultado_rutas(RUTA_OK, ALTERNATIVA)},
        modelo_sintetizador=_sintetizar,
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    return grafo


@pytest.fixture
def grafo_con_fallback(monkeypatch):
    """Grafo real cuyo supervisor falla: se aplica el fallback y se anota un diagnóstico técnico."""
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: "RESPUESTA_CRUDA_QUE_NO_ES_JSON",
        especialistas=_especialistas_sin_api(),
        modelo_sintetizador=_sintetizar,
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    return grafo


# --- Carga del grafo real (RF-28 y RF-29) ---

def test_cargar_agente_devuelve_el_grafo_real():
    modulo, aviso = cargar_agente({})
    assert modulo is agent
    assert aviso is None


# --- Contrato (RF-26) ---

def test_el_grafo_real_devuelve_las_seis_claves_publicas(grafo_de_ruta):
    sesion = SesionChat(agent)
    sesion.enviar(PEDIDO_RUTA)
    assert set(sesion.estado) == set(estado_vacio())


# --- Un plan: resumen, aprobar y terminar (RF-30 y RF-32) ---

def test_ruta_con_un_plan_se_resume_se_aprueba_y_termina(grafo_de_ruta):
    sesion = SesionChat(agent)
    sesion.enviar(PEDIDO_RUTA)

    assert sesion.puede_decidir and not sesion.puede_escribir
    assert ids_de_planes(sesion.planes) == ["ruta-1"]
    texto = formatear_turno(sesion.estado, sesion.thread_id)
    assert "ruta-1" in texto and "Origen: Atocha" in texto and "Destino: Sol" in texto
    assert "12 min" in texto and "SUBWAY línea 1" in texto

    sesion.decidir(True)  # un único plan: no hace falta indicar cuál
    assert sesion.estado["done"] is True
    assert sesion.estado["hitl_pendiente"] is False
    assert sesion.planes == []
    assert sesion.puede_escribir


# --- Varios planes: elegir (RF-31) ---

def test_varios_planes_exigen_elegir_y_se_aprueba_solo_el_elegido(grafo_de_varias_rutas):
    sesion = SesionChat(agent)
    sesion.enviar("Dame alternativas.")
    assert ids_de_planes(sesion.planes) == ["ruta-1", "ruta-2"]

    antes = dict(sesion.estado)
    sesion.decidir(True)  # sin elegir: el cliente no llama al grafo
    assert sesion.estado == antes and sesion.puede_decidir

    sesion.decidir(True, plan_id="ruta-2")
    assert sesion.estado["done"] is True
    assert "ruta-2" in sesion.estado["respuesta"]


# --- Rechazo: el grafo replanifica y deja otro plan pendiente (RF-9) ---

def test_rechazar_replanifica_y_se_puede_aprobar_el_nuevo_plan(grafo_de_ruta, contadores):
    sesion = SesionChat(agent)
    sesion.enviar(PEDIDO_RUTA)
    sesion.decidir(False)

    assert contadores["rutas"] == 2  # se volvió a planificar en el mismo hilo
    assert sesion.estado["done"] is False
    assert sesion.estado["hitl_pendiente"] is True
    assert ids_de_planes(sesion.planes) == ["ruta-2"]
    assert "20 min" in formatear_turno(sesion.estado, sesion.thread_id)

    sesion.decidir(True)
    assert sesion.estado["done"] is True


def test_mismo_hilo_para_todo_el_recorrido(grafo_de_ruta):
    sesion = SesionChat(agent)
    hilo = sesion.thread_id
    sesion.enviar(PEDIDO_RUTA)
    sesion.decidir(False)
    sesion.decidir(True)
    assert sesion.thread_id == hilo


# --- Sin ruta no hay pausa (RF-34) ---

def test_una_consulta_sin_ruta_cierra_sin_pausa(monkeypatch):
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["horarios"]},
        especialistas=_especialistas_sin_api(),
        modelo_sintetizador=_sintetizar,
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    sesion = SesionChat(agent)
    sesion.enviar("¿Hasta qué hora hay metro hoy?")
    assert sesion.estado["hitl_pendiente"] is False
    assert sesion.estado["done"] is True
    assert sesion.planes == []
    assert sesion.puede_escribir and not sesion.puede_decidir


# --- Bloqueo con plan pendiente (RF-22b) ---

def test_un_mensaje_con_plan_pendiente_no_llega_al_grafo(grafo_de_ruta, contadores):
    sesion = SesionChat(agent)
    sesion.enviar(PEDIDO_RUTA)
    antes = dict(contadores)
    sesion.enviar("Quiero cambiar la ruta.")
    assert contadores == antes
    assert sesion.puede_decidir


# --- CLI de punta a punta con el grafo real ---

def _ejecutar_cli(lineas):
    salida = []
    codigo = ejecutar_cli([], agent, Entrada(lineas), salida.append, None)
    return codigo, "\n".join(salida)


def test_cli_con_el_grafo_real_rechaza_y_aprueba(grafo_de_ruta):
    codigo, texto = _ejecutar_cli([PEDIDO_RUTA, "n", "s", "salir"])
    assert codigo == 0
    assert "12 min" in texto and "20 min" in texto  # el plan original y el replanificado
    assert "Terminada: sí" in texto


def test_cli_con_el_grafo_real_y_varios_planes_pide_elegir(grafo_de_varias_rutas):
    codigo, texto = _ejecutar_cli(["Dame alternativas.", "2", "s", "salir"])
    assert codigo == 0
    assert "Planes propuestos:" in texto
    assert "Terminada: sí" in texto


# --- Registro efímero de depuración (spec 011) ---

def test_los_clientes_reciben_el_log_estructurado_de_la_llamada_actual(grafo_con_fallback):
    """RF-1 y RF-15: el cliente recibe el registro efímero, no uno persistido."""
    sesion = SesionChat(agent)
    sesion.enviar("¿Qué hora es?")
    assert sesion.estado["log"]
    assert all(
        set(entrada) == {"paso", "tipo", "nodo", "entrada", "salida", "resultado", "detalle"}
        for entrada in sesion.estado["log"]
    )

    assert "Paso 1" in formatear_turno(sesion.estado, sesion.thread_id)
    _, texto = _ejecutar_cli(["¿Qué hora es?", "salir"])
    assert "Paso 1" in texto
    assert "Paso 1" in formatear_turno(sesion.estado, sesion.thread_id, ocultar_tecnicas=True)


def test_fallback_real_del_supervisor_llega_a_cli_y_panel_pero_no_al_chat(grafo_con_fallback):
    """RF-23 a RF-25: el diagnóstico procede del contexto del grafo real, no de un doble."""
    resultado = agent.procesar_turno({}, "¿Qué hora es?", "hilo-fallback-estructurado")
    diagnosticos = [
        entrada
        for entrada in resultado["log"]
        if entrada["tipo"] == "control" and entrada["nodo"] == "supervisor"
    ]

    assert len(diagnosticos) == 1
    diagnostico = diagnosticos[0]
    assert diagnostico["resultado"] == "rechazado"
    assert diagnostico["entrada"] is None and diagnostico["salida"] is None
    assert diagnostico["detalle"] == {
        "categoria": "json_invalido",
        "resumen": "La decisión no contiene JSON válido; se aplicó el fallback.",
    }
    posicion = resultado["log"].index(diagnostico)
    assert resultado["log"][posicion - 1]["nodo"] == "supervisor"
    assert resultado["log"][posicion - 1]["resultado"] == "completado"
    assert datos_depuracion(resultado, "hilo-fallback-estructurado")["log"] == resultado["log"]
    assert "json_invalido" not in "\n".join(pasos_del_turno(resultado["log"], resultado["traza"]))

    codigo, texto_cli = _ejecutar_cli(["¿Qué hora es?", "salir"])
    assert codigo == 0
    assert "control · supervisor [rechazado]" in texto_cli
    assert '"categoria": "json_invalido"' in texto_cli
