"""Contrato público de ``src.agent`` sin proveedores ni tools reales."""
from __future__ import annotations

from copy import deepcopy
from inspect import signature

import pytest

import config
import src.agent as agent
import src.modelos as modelos
from src.graph import crear_grafo, recuperar_estado
from tests.dobles_grafo import EjecutorFalso, LLMFalso


CLAVES_PUBLICAS = {"respuesta", "plan", "log", "traza", "hitl_pendiente", "done"}


@pytest.fixture
def grafo_falso(monkeypatch):
    """Inyecta un grafo persistente de salida conocida en la fachada perezosa."""
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": []},
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    return grafo


def _comprobar_contrato(resultado):
    """Verifica la forma estable que consumirán los futuros clientes."""
    assert set(resultado) == CLAVES_PUBLICAS
    assert isinstance(resultado["respuesta"], str)
    assert isinstance(resultado["plan"], list)
    assert isinstance(resultado["log"], list)
    assert isinstance(resultado["traza"], list)
    assert isinstance(resultado["hitl_pendiente"], bool)
    assert isinstance(resultado["done"], bool)
    assert all(
        set(entrada) == {"paso", "tipo", "nodo", "entrada", "salida", "resultado", "detalle"}
        for entrada in resultado["log"]
    )
    assert all(set(entrada) == {"tool", "args", "status", "preview"} for entrada in resultado["traza"])


def _comprobar_control(resultado, categoria):
    """RF-12: los rechazos previos al grafo tienen una única forma pública."""
    _comprobar_contrato(resultado)
    assert resultado["log"] == [
        {
            "paso": 1,
            "tipo": "control",
            "nodo": "fachada",
            "entrada": None,
            "salida": None,
            "resultado": "rechazado",
            "detalle": {"categoria": categoria, "resumen": resultado["respuesta"]},
        }
    ]


def _capturar_contextos_de_fachada(monkeypatch):
    """Sustituye el grafo por una invocación controlada y registra su contexto efímero."""
    grafo = object()
    contextos = []

    monkeypatch.setattr(agent, "_obtener_grafo", lambda: grafo)
    monkeypatch.setattr(agent, "recuperar_estado", lambda recibido, hilo: {})

    def invocar(recibido, estado, hilo, *, contexto, sesion):
        assert recibido is grafo
        contextos.append(dict(contexto))
        return {
            "respuesta": "Resumen controlado.",
            "planes_pendientes": [],
            "log": [],
            "traza": [],
            "hitl_pendiente": False,
            "done": True,
        }

    monkeypatch.setattr(agent, "invocar_grafo", invocar)
    return contextos


def test_fachada_expone_las_dos_firmas_y_las_seis_claves(grafo_falso):
    """RF-23 a RF-28: ambas operaciones tienen el contrato público acordado."""
    assert list(signature(agent.procesar_turno).parameters) == ["estado", "mensaje", "thread_id"]
    assert list(signature(agent.aprobar_plan).parameters) == ["estado", "thread_id", "aprobado"]

    resultado_turno = agent.procesar_turno({}, "Consulta de prueba.", "contrato-turno")
    resultado_aprobacion = agent.aprobar_plan({}, "contrato-turno", True)

    _comprobar_contrato(resultado_turno)
    _comprobar_contrato(resultado_aprobacion)
    assert "No existe un plan pendiente" in resultado_aprobacion["respuesta"]


def test_procesar_turno_inicializa_el_contexto_sin_imagen_valida(monkeypatch):
    """RF-8 y RF-17: la fachada no hereda ni acepta contexto visual público."""
    grafo = object()
    contextos = []

    monkeypatch.setattr(agent, "_obtener_grafo", lambda: grafo)
    monkeypatch.setattr(agent, "recuperar_estado", lambda recibido, hilo: {})

    def invocar(recibido, estado, hilo, *, contexto, sesion):
        assert recibido is grafo
        contextos.append(dict(contexto))
        return {
            "respuesta": "Resumen controlado.",
            "planes_pendientes": [],
            "log": [],
            "traza": [],
            "hitl_pendiente": False,
            "done": True,
        }

    monkeypatch.setattr(agent, "invocar_grafo", invocar)

    resultado = agent.procesar_turno(
        {"imagen_valida": True},
        "¿Cuánto cuesta el Combinado Metro?",
        "hilo-contexto-inicial",
    )

    _comprobar_contrato(resultado)
    assert contextos == [
        {
            "diagnostico_supervisor": None,
            "correcciones_tarifas": 0,
            "correcciones_rutas_tarifarias": 0,
            "imagen_valida": False,
        }
    ]
    assert "imagen_valida" not in resultado


def test_referencia_literal_de_demo_activa_solo_el_turno_que_la_contiene(monkeypatch, tmp_path):
    """RF-21, RF-22 y RF-24: la demo válida se selecciona de forma efímera."""
    imagenes_dir = tmp_path / "assets"
    imagenes_dir.mkdir()
    (imagenes_dir / "imagen_demo.jpg").write_bytes(b"imagen-demo-de-prueba")
    monkeypatch.setattr(config, "IMAGENES_DIR", imagenes_dir)
    monkeypatch.setattr(config, "IMAGEN_DEMO", "imagen_demo.jpg")
    contextos = _capturar_contextos_de_fachada(monkeypatch)

    primero = agent.procesar_turno(
        {},
        "Analiza assets/imagen_demo.jpg e indica los precios.",
        "hilo-demo-efimera",
    )
    segundo = agent.procesar_turno(
        {},
        "Ahora dime cuánto cuesta el abono.",
        "hilo-demo-efimera",
    )

    _comprobar_contrato(primero)
    _comprobar_contrato(segundo)
    assert [contexto["imagen_valida"] for contexto in contextos] == [True, False]
    assert "imagen_valida" not in primero
    assert "imagen_valida" not in segundo


def test_demo_referenciada_invalida_conserva_el_contexto_textual(monkeypatch, tmp_path):
    """RF-22 y RF-23: una demo inexistente no habilita la ruta visual."""
    monkeypatch.setattr(config, "IMAGENES_DIR", tmp_path / "assets")
    monkeypatch.setattr(config, "IMAGEN_DEMO", "imagen_demo.jpg")
    contextos = _capturar_contextos_de_fachada(monkeypatch)

    resultado = agent.procesar_turno(
        {},
        "Analiza assets/imagen_demo.jpg y dime el precio del abono.",
        "hilo-demo-invalida",
    )

    _comprobar_contrato(resultado)
    assert contextos[0]["imagen_valida"] is False
    assert "imagen_valida" not in resultado


def test_referencia_de_demo_valida_alcanza_tarifas_e_invoca_vision_falsa(monkeypatch, tmp_path):
    """RF-21 y RF-22: la selección pública mantiene el recorrido visual permitido."""
    imagenes_dir = tmp_path / "assets"
    imagenes_dir.mkdir()
    (imagenes_dir / "imagen_demo.jpg").write_bytes(b"imagen-demo-de-prueba")
    monkeypatch.setattr(config, "IMAGENES_DIR", imagenes_dir)
    monkeypatch.setattr(config, "IMAGEN_DEMO", "imagen_demo.jpg")
    mensaje = "Analiza assets/imagen_demo.jpg e indica los precios visibles."
    ejecutor = EjecutorFalso({"describir_imagen": "Precio visible: 1,50 €."})
    modelo_tarifas = LLMFalso(
        [
            {"tool": "describir_imagen", "args": {"pregunta": "precios visibles"}},
            {"final": "La imagen muestra un precio de 1,50 €."},
        ]
    )

    def rag_no_permitido(_mensajes):
        raise AssertionError("RAG no debe ejecutarse cuando la demo válida selecciona tarifas")

    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["tarifas"]},
        modelos_especialistas={"tarifas": modelo_tarifas, "rag": rag_no_permitido},
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    resultado = agent.procesar_turno({}, mensaje, "hilo-demo-vision")

    _comprobar_contrato(resultado)
    assert ejecutor.llamadas == [("describir_imagen", {"pregunta": "precios visibles"})]
    assert [entrada["tool"] for entrada in resultado["traza"]] == ["describir_imagen"]


@pytest.mark.parametrize(
    ("mensaje", "crear_demo"),
    [
        ("Analiza esta imagen y dime los precios.", True),
        ("Analiza assets/imagen_demo.jpg y dime los precios.", False),
    ],
)
def test_consultas_sin_demo_valida_se_mantienen_en_rag_sin_vision(monkeypatch, tmp_path, mensaje, crear_demo):
    """RF-21 a RF-23: una referencia genérica o demo inválida no activa visión."""
    imagenes_dir = tmp_path / "assets"
    imagenes_dir.mkdir()
    if crear_demo:
        (imagenes_dir / "imagen_demo.jpg").write_bytes(b"imagen-demo-de-prueba")
    monkeypatch.setattr(config, "IMAGENES_DIR", imagenes_dir)
    monkeypatch.setattr(config, "IMAGEN_DEMO", "imagen_demo.jpg")
    ejecutor = EjecutorFalso(
        {
            "rag_ask": "Evidencia textual del corpus CRTM.",
            "describir_imagen": "La visión no debe ejecutarse.",
        }
    )
    modelo_rag = LLMFalso(
        [
            {"tool": "rag_ask", "args": {"consulta": mensaje}},
            {"final": "Respuesta anclada al corpus CRTM."},
        ]
    )

    def tarifas_no_permitido(_mensajes):
        raise AssertionError("Tarifas no debe ejecutarse sin una demo válida seleccionada")

    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["tarifas"]},
        modelos_especialistas={"tarifas": tarifas_no_permitido, "rag": modelo_rag},
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    resultado = agent.procesar_turno({}, mensaje, f"hilo-textual-{crear_demo}")

    _comprobar_contrato(resultado)
    assert ejecutor.llamadas == [("rag_ask", {"consulta": mensaje})]
    assert all(entrada["tool"] != "describir_imagen" for entrada in resultado["traza"])


@pytest.mark.parametrize(
    ("estado", "mensaje", "thread_id", "fragmento"),
    [
        ({}, "Consulta válida.", "", "thread_id"),
        ([], "Consulta válida.", "hilo-invalido", "estado"),
        ({}, "   ", "hilo-vacio", "consulta válida"),
    ],
)
def test_validaciones_de_procesar_turno_no_crean_ni_invocan_grafo(
    monkeypatch, estado, mensaje, thread_id, fragmento
):
    """RF-52, RF-54 y RF-55: los controles cortan sin efectos colaterales."""
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: (_ for _ in ()).throw(AssertionError("no debe ejecutarse")))

    resultado = agent.procesar_turno(estado, mensaje, thread_id)

    _comprobar_contrato(resultado)
    assert fragmento.lower() in resultado["respuesta"].lower()
    assert resultado["done"] is False


def test_rechazos_de_fachada_devuelven_un_unico_control_sin_ejecutar_grafo(monkeypatch):
    """RF-12: validaciones, bloqueo, plan ausente y selección inválida son uniformes."""
    monkeypatch.setattr(
        agent,
        "_obtener_grafo",
        lambda: (_ for _ in ()).throw(AssertionError("no debe ejecutarse")),
    )

    _comprobar_control(agent.procesar_turno({}, "consulta", "  "), "validacion")
    _comprobar_control(agent.procesar_turno([], "consulta", "hilo"), "validacion")
    _comprobar_control(agent.procesar_turno({}, "  ", "hilo"), "validacion")

    grafo = object()
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: grafo)
    monkeypatch.setattr(
        agent,
        "invocar_grafo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no debe ejecutarse")),
    )

    pendiente = {
        "hitl_pendiente": True,
        "planes_pendientes": [{"id": "ruta-1", "resultado": {}}],
    }
    monkeypatch.setattr(agent, "recuperar_estado", lambda *_args: pendiente)
    _comprobar_control(agent.procesar_turno({}, "consulta", "hilo"), "plan_pendiente")

    monkeypatch.setattr(agent, "recuperar_estado", lambda *_args: {})
    _comprobar_control(agent.aprobar_plan({}, "hilo", True), "plan_ausente")

    monkeypatch.setattr(agent, "recuperar_estado", lambda *_args: pendiente)
    _comprobar_control(agent.aprobar_plan({"plan_id_seleccionado": "ruta-9"}, "hilo", True), "seleccion_plan")


def test_pausa_y_reanudacion_hitl_entregan_logs_nuevos_y_no_persistidos(monkeypatch):
    """RF-13 a RF-15 y RF-27: cada operación termina con su propio registro."""
    ruta = {
        "estado": "ok",
        "origen": {"direccion": "Atocha"},
        "destino": {"direccion": "Sol"},
        "ruta": {"duracion_min": 12, "tramos": []},
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        especialistas={
            "rutas": lambda estado: {
                "resultados": [
                    {
                        "especialista": "rutas",
                        "tool": "planificar_ruta",
                        "status": "ok",
                        "resultado": ruta,
                        "args": {"origen": "Atocha", "destino": "Sol"},
                    }
                ]
            }
        },
        modelo_sintetizador=lambda contexto: "Ruta lista para revisiÃ³n.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    inicial = agent.procesar_turno({}, "De Atocha a Sol.", "hilo-logs-hitl")
    reanudado = agent.aprobar_plan(
        {"plan_id_seleccionado": inicial["plan"][0]["id"]},
        "hilo-logs-hitl",
        True,
    )
    checkpoint = recuperar_estado(grafo, "hilo-logs-hitl")

    _comprobar_contrato(inicial)
    _comprobar_contrato(reanudado)
    assert inicial["hitl_pendiente"] is True
    assert inicial["log"]
    assert reanudado["log"]
    assert [entrada["paso"] for entrada in inicial["log"]] == list(range(1, len(inicial["log"]) + 1))
    assert [entrada["paso"] for entrada in reanudado["log"]] == list(range(1, len(reanudado["log"]) + 1))
    assert "log" not in checkpoint


def test_estado_vacio_recupera_el_checkpoint_en_lugar_de_sustituirlo(grafo_falso):
    """RF-53: una segunda llamada con estado vacío conserva el contexto del hilo."""
    agent.procesar_turno({}, "Primer mensaje persistido.", "hilo-recuperable")
    resultado = agent.procesar_turno({}, "Segundo mensaje persistido.", "hilo-recuperable")
    recuperado = recuperar_estado(grafo_falso, "hilo-recuperable")

    _comprobar_contrato(resultado)
    assert [entrada["content"] for entrada in recuperado["historial"]] == [
        "Primer mensaje persistido.",
        "Segundo mensaje persistido.",
    ]


def test_resultado_del_turno_no_recupera_un_log_desde_el_checkpoint(grafo_falso):
    """RF-1, RF-2 y RF-15: el contrato conserva log, pero el checkpoint no."""
    primero = agent.procesar_turno({}, "Primer turno.", "hilo-diagnostico")
    segundo = agent.procesar_turno({}, "Segundo turno.", "hilo-diagnostico")
    snapshot = recuperar_estado(grafo_falso, "hilo-diagnostico")

    _comprobar_contrato(primero)
    _comprobar_contrato(segundo)
    assert primero["log"] and segundo["log"]
    assert primero["log"][0]["paso"] == 1
    assert segundo["log"][0]["paso"] == 1
    assert primero["log"] != segundo["log"]
    assert "log" not in snapshot
    assert "diagnostico_supervisor" not in snapshot


def test_correccion_semantica_se_expone_solo_en_el_turno_que_la_origina(monkeypatch):
    """RF-14 a RF-19: el indicador es público, seguro y efímero."""
    def supervisor(mensajes):
        return {"roles": ["tarifas"]} if "Combinado Metro" in mensajes[-1]["content"] else {"roles": []}

    grafo = crear_grafo(
        modelo_supervisor=supervisor,
        especialistas={"rag": lambda estado: {}},
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    primero = agent.procesar_turno(
        {},
        "¿Cuánto cuesta el Combinado Metro?",
        "hilo-correccion-semantica",
    )
    segundo = agent.procesar_turno(
        {},
        "Consulta posterior sin tarifas.",
        "hilo-correccion-semantica",
    )
    snapshot = recuperar_estado(grafo, "hilo-correccion-semantica")

    _comprobar_contrato(primero)
    _comprobar_contrato(segundo)
    assert primero["log"] and segundo["log"]
    assert primero["log"][0]["paso"] == segundo["log"][0]["paso"] == 1
    assert "correccion_semantica" not in str(snapshot)
    assert "correcciones_tarifas" not in snapshot
    assert "diagnostico_supervisor" not in snapshot
    assert "correccion_semantica" not in str(snapshot["historial"])
    assert "correccion_semantica" not in str(primero["traza"])


def test_correccion_de_rutas_registra_diagnostico_tecnico_separado(monkeypatch):
    """RF-9 a RF-11: la corrección deja un control seguro y no persistido."""
    respuesta_cruda = "RESPUESTA_CRUDA_DEL_LLM_QUE_NO_DEBE_PERSISTIR"

    class RespuestaDelModelo(dict):
        def __repr__(self):
            return respuesta_cruda

    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: RespuestaDelModelo(roles=["rutas"]),
        especialistas={"rag": lambda estado: {}},
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    resultado = agent.procesar_turno(
        {},
        "Precio del abono A-B2",
        "hilo-correccion-rutas",
    )
    snapshot = recuperar_estado(grafo, "hilo-correccion-rutas")

    _comprobar_contrato(resultado)
    controles = [
        entrada
        for entrada in resultado["log"]
        if entrada["tipo"] == "control"
        and entrada["detalle"].get("categoria") == "correccion_semantica"
    ]
    assert len(controles) == 1
    assert controles[0]["nodo"] == "supervisor"
    assert controles[0]["resultado"] == "rechazado"
    assert controles[0]["detalle"] == {
        "categoria": "correccion_semantica",
        "resumen": "Se redirigió 1 aparición de rutas a rag por una consulta tarifaria entre zonas.",
    }
    assert respuesta_cruda not in str(resultado)
    assert "correcciones_rutas_tarifarias" not in snapshot
    assert "correcciones_rutas_tarifarias" not in str(resultado["traza"])


def test_reanudacion_hitl_no_reutiliza_correccion_semantica(monkeypatch):
    """RF-15 y RF-17: la reanudación no recupera el contexto de otro turno."""
    ruta = {
        "estado": "ok",
        "origen": {"direccion": "Atocha"},
        "destino": {"direccion": "Sol"},
        "ruta": {"duracion_min": 12, "tramos": []},
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["tarifas", "rutas"]},
        especialistas={
            "rag": lambda estado: {},
            "rutas": lambda estado: {
                "resultados": [
                    {
                        "especialista": "rutas",
                        "tool": "planificar_ruta",
                        "status": "ok",
                        "resultado": ruta,
                        "args": {"origen": "Atocha", "destino": "Sol"},
                    }
                ]
            },
        },
        modelo_sintetizador=lambda contexto: "Ruta lista para revisión.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    inicial = agent.procesar_turno(
        {},
        "¿Cuánto cuesta ir de Atocha a Sol con Combinado Metro?",
        "hilo-correccion-hitl",
    )
    reanudado = agent.aprobar_plan(
        {"plan_id_seleccionado": inicial["plan"][0]["id"]},
        "hilo-correccion-hitl",
        True,
    )
    snapshot = recuperar_estado(grafo, "hilo-correccion-hitl")

    assert inicial["log"] and reanudado["log"]
    assert inicial["log"][0]["paso"] == reanudado["log"][0]["paso"] == 1
    assert "correccion_semantica" not in str(snapshot)
    assert "correcciones_tarifas" not in snapshot


def test_fallback_publico_solo_expone_categoria_y_resumen_canonicos(monkeypatch):
    """RF-10 a RF-14: ni el JSON crudo ni datos internos llegan al contrato público."""
    llamadas = []

    def especialista_falso(rol):
        def ejecutar(estado):
            llamadas.append(rol)
            return {}

        return ejecutar

    def crear_cliente_prohibido():
        raise AssertionError("el test no debe crear un cliente Gemini")

    monkeypatch.setattr(modelos, "_crear_cliente_gemini", crear_cliente_prohibido)
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: "RESPUESTA_CRUDA_TOKEN_DE_PRUEBA",
        especialistas={
            rol: especialista_falso(rol)
            for rol in ("rag", "horarios", "rutas", "auxiliar", "tarifas")
        },
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    resultado = agent.procesar_turno({}, "¿Qué hora es?", "hilo-fallback-publico")
    snapshot = recuperar_estado(grafo, "hilo-fallback-publico")

    _comprobar_contrato(resultado)
    assert resultado["log"]
    assert "RESPUESTA_CRUDA_TOKEN_DE_PRUEBA" not in str(resultado)
    assert llamadas == ["auxiliar"]
    assert "log" not in snapshot
    assert "diagnostico_supervisor" not in snapshot


def test_reanudacion_hitl_no_reproyecta_el_diagnostico_del_turno_inicial(monkeypatch):
    """RF-25: aprobar un plan no reutiliza la categoría del Supervisor anterior."""
    ruta = {
        "estado": "ok",
        "origen": {"direccion": "Atocha"},
        "destino": {"direccion": "Sol"},
        "ruta": {"duracion_min": 12, "tramos": []},
    }
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["rutas"]},
        especialistas={
            "rutas": lambda estado: {
                "resultados": [
                    {
                        "especialista": "rutas",
                        "tool": "planificar_ruta",
                        "status": "ok",
                        "resultado": ruta,
                        "args": {"origen": "Atocha", "destino": "Sol"},
                    }
                ]
            }
        },
        modelo_sintetizador=lambda contexto: "Ruta lista para revisión.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    inicial = agent.procesar_turno({}, "De Atocha a Sol.", "hilo-diagnostico-hitl")
    reanudado = agent.aprobar_plan(
        {"plan_id_seleccionado": inicial["plan"][0]["id"]},
        "hilo-diagnostico-hitl",
        True,
    )
    snapshot = recuperar_estado(grafo, "hilo-diagnostico-hitl")

    assert inicial["log"] and reanudado["log"]
    assert inicial["log"][0]["paso"] == reanudado["log"][0]["paso"] == 1
    assert "diagnostico_supervisor" not in snapshot


def test_aprobacion_sin_snapshot_o_plan_no_modifica_el_checkpoint(grafo_falso):
    """RF-51: la aprobación inválida avisa y no escribe ninguna conversación."""
    sin_snapshot = agent.aprobar_plan({}, "hilo-inexistente", True)
    assert recuperar_estado(grafo_falso, "hilo-inexistente") == {}

    agent.procesar_turno({}, "Turno sin ruta.", "hilo-sin-plan")
    antes = deepcopy(recuperar_estado(grafo_falso, "hilo-sin-plan"))
    sin_plan = agent.aprobar_plan({}, "hilo-sin-plan", True)
    despues = recuperar_estado(grafo_falso, "hilo-sin-plan")

    _comprobar_contrato(sin_snapshot)
    _comprobar_contrato(sin_plan)
    assert "No existe un plan pendiente" in sin_snapshot["respuesta"]
    assert "No existe un plan pendiente" in sin_plan["respuesta"]
    assert despues == antes


def test_validacion_de_aprobacion_no_crea_grafo_con_thread_o_estado_invalidos(monkeypatch):
    """RF-51, RF-52 y RF-54: no hay lectura ni escritura tras una entrada inválida."""
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: (_ for _ in ()).throw(AssertionError("no debe ejecutarse")))

    resultado_thread = agent.aprobar_plan({}, "  ", True)
    resultado_estado = agent.aprobar_plan([], "hilo", True)

    _comprobar_contrato(resultado_thread)
    _comprobar_contrato(resultado_estado)
    assert resultado_thread["done"] is False
    assert resultado_estado["done"] is False


def test_aprobacion_sin_grafo_ni_snapshot_no_inicializa_la_fachada(monkeypatch):
    """RF-51: una aprobación aislada no crea un grafo que no puede reanudar."""
    monkeypatch.setattr(agent, "_GRAFO", None)
    monkeypatch.setattr(agent, "_obtener_grafo", lambda: (_ for _ in ()).throw(AssertionError("no debe crearse")))

    resultado = agent.aprobar_plan({}, "hilo-ausente", True)

    _comprobar_contrato(resultado)
    assert "No existe un plan pendiente" in resultado["respuesta"]
