"""Spec 010, T15 (RF-42 y RF-43): tras aprobar el plan, el sintetizador (con el LLM) recibe una nota para confirmar
brevemente y no se vuelven a añadir bloques ni avisos. Sin LLM ni red: modelos y especialistas falsos."""
import json

import src.agent as agent
from src.graph import configuracion_hilo, crear_grafo
from src.sintetizador import nodo_sintetizador
from tests.test_sintetizador_avisos import AVISO, BICI_OK, resultado_ruta
from tests.test_sintetizador_bloques import MOTIVO, PARRAFO_BICI

NOTA_APROBACION = "El plan ya se mostró; confirma brevemente la aprobación sin repetir la ruta."
NOTA_BLOQUES = "Zona, precio, clima, bici y opciones se añaden después de forma automática; no los repitas ni los resumas."
CABECERA = "Salida: ahora · Título: billete sencillo."
RESUMEN = "Resumen de la ruta."
CONFIRMACION = "Plan confirmado."


class Modelo:
    """Sintetizador falso: guarda el contexto y responde según la nota que reciba."""

    def __init__(self):
        self.contextos = []

    def __call__(self, contexto):
        self.contextos.append(json.loads(json.dumps(contexto)))
        return CONFIRMACION if contexto.get("nota") == NOTA_APROBACION else RESUMEN


def ruta_ok(**extra):
    mensaje = f"{CABECERA} Ruta de 12 min. {PARRAFO_BICI} {MOTIVO}"
    return {"estado": "ok", "mensaje": mensaje, "origen": {"direccion": "Atocha"}, "destino": {"direccion": "Sol"},
            "ruta": {"duracion_min": 12, "tramos": [{"modo": "SUBWAY", "linea": "1"}]},
            "bici": BICI_OK, "bloques": [PARRAFO_BICI, MOTIVO], **extra}


def resultados(*rutas):
    return {"resultados": [{"especialista": "rutas", "tool": "planificar_ruta", "status": "ok",
                            "resultado": json.dumps(r, ensure_ascii=False), "args": {"origen": "Atocha", "destino": "Sol"}}
                           for r in rutas]}


def montar(monkeypatch, *rutas):
    modelo = Modelo()
    grafo = crear_grafo(modelo_supervisor=lambda m: {"roles": ["rutas"]},
                        especialistas={"rutas": lambda estado: resultados(*rutas)}, modelo_sintetizador=modelo)
    monkeypatch.setattr(agent, "_GRAFO", grafo)
    return grafo, modelo


# --- nodo (unidad) ---

def estado_aprobado():
    return {"notas": ["[rutas] Plan aprobado ruta-1: {}"], "traza": [], "plan_aprobado": {"id": "ruta-1"},
            "resultados": [resultado_ruta(mensaje=f"{CABECERA} {PARRAFO_BICI}", bloques=[PARRAFO_BICI], bici=BICI_OK)]}


def test_tras_aprobar_el_contexto_lleva_la_nota_y_no_los_textos_de_los_bloques():
    modelo = Modelo()
    nodo_sintetizador(estado_aprobado(), modelo, tras_aprobacion=True)
    contexto = modelo.contextos[0]
    assert contexto["nota"] == NOTA_APROBACION
    assert PARRAFO_BICI not in json.dumps(contexto, ensure_ascii=False)
    assert contexto["notas"] == ["[rutas] Plan aprobado ruta-1: {}"]            # la nota del plan aprobado se conserva


def test_tras_aprobar_la_respuesta_es_la_del_modelo_sin_bloques_ni_avisos():
    respuesta = nodo_sintetizador(estado_aprobado(), Modelo(), tras_aprobacion=True)["respuesta"]
    assert respuesta == CONFIRMACION and PARRAFO_BICI not in respuesta and AVISO not in respuesta


def test_sin_aprobacion_nada_cambia_aunque_plan_aprobado_siga_en_el_estado():
    modelo = Modelo()
    respuesta = nodo_sintetizador(estado_aprobado(), modelo)["respuesta"]          # tras_aprobacion por defecto: False
    assert modelo.contextos[0]["nota"] == NOTA_BLOQUES
    assert respuesta == f"{RESUMEN}\n\n{PARRAFO_BICI}"


def test_el_respaldo_tras_aprobar_es_el_de_siempre():
    def roto(contexto):
        raise RuntimeError("caído")

    salida = nodo_sintetizador(estado_aprobado(), roto, tras_aprobacion=True)
    assert salida["respuesta"].startswith("No se ha podido sintetizar la respuesta automáticamente.")
    assert salida["log"] == ["Sintetizador: se ha usado el respaldo determinista."]


# --- grafo completo con HITL ---

def test_en_el_grafo_la_aprobacion_confirma_y_el_turno_siguiente_vuelve_a_lo_normal(monkeypatch):
    grafo, modelo = montar(monkeypatch, ruta_ok())
    inicial = agent.procesar_turno({}, "De Atocha a Sol.", "t15")
    assert inicial["hitl_pendiente"] is True and inicial["respuesta"] == f"{RESUMEN}\n\n{PARRAFO_BICI}\n\n{MOTIVO}"
    assert modelo.contextos[0]["nota"] == NOTA_BLOQUES

    aprobada = agent.aprobar_plan({"plan_id_seleccionado": inicial["plan"][0]["id"]}, "t15", True)
    assert aprobada["done"] is True and aprobada["respuesta"] == CONFIRMACION              # sin bloques ni avisos
    contexto = modelo.contextos[1]
    assert contexto["nota"] == NOTA_APROBACION
    assert PARRAFO_BICI not in json.dumps(contexto, ensure_ascii=False) and MOTIVO not in json.dumps(contexto, ensure_ascii=False)
    assert any(n.startswith("[rutas] Plan aprobado ruta-1") for n in contexto["notas"])

    # Turno siguiente: `plan_aprobado` sigue en el estado, pero la síntesis es la normal (RF-43).
    assert grafo.get_state(configuracion_hilo("t15")).values["plan_aprobado"] is not None
    siguiente = agent.procesar_turno({}, "¿Y otra ruta?", "t15")
    assert modelo.contextos[2]["nota"] == NOTA_BLOQUES
    assert siguiente["respuesta"] == f"{RESUMEN}\n\n{PARRAFO_BICI}\n\n{MOTIVO}"


def test_con_varios_planes_sigue_exigiendo_elegir(monkeypatch):
    alternativa = ruta_ok(ruta={"duracion_min": 20, "tramos": [{"modo": "BUS", "linea": "27"}]})
    grafo, modelo = montar(monkeypatch, ruta_ok(), alternativa)
    inicial = agent.procesar_turno({}, "Dame alternativas.", "t15-varios")
    assert [p["id"] for p in inicial["plan"]] == ["ruta-1", "ruta-2"]
    antes = len(modelo.contextos)

    sin_selector = agent.aprobar_plan({}, "t15-varios", True)
    assert sin_selector["done"] is False and "identificador" in sin_selector["respuesta"].lower()
    assert len(modelo.contextos) == antes                                           # no se sintetizó nada

    aprobada = agent.aprobar_plan({"plan_id_seleccionado": "ruta-2"}, "t15-varios", True)
    assert aprobada["done"] is True and aprobada["respuesta"] == CONFIRMACION
    assert modelo.contextos[-1]["nota"] == NOTA_APROBACION
