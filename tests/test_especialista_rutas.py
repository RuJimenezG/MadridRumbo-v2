"""Tests del especialista de rutas (spec 005, T10). No usan API ni red."""
import json

import pytest

import config

from src.agents.rutas import PROMPT_RUTAS, nodo_rutas
from tests.dobles_grafo import EjecutorFalso, LLMFalso


RUTA_OK = {
    "estado": "ok",
    "origen": {"direccion": "Estación de Atocha, Madrid"},
    "destino": {"direccion": "Puerta del Sol, Madrid"},
    "ruta": {"duracion_min": 12, "tramos": [{"modo": "SUBWAY", "linea": "1"}]},
}


def _estado(mensaje, historial=None):
    """Construye el estado persistente mínimo necesario para rutas."""
    return {"mensaje": mensaje, "historial": historial or [], "notas": [], "traza": []}


def test_config_allowlist_rutas():
    """RF-12 y RF-59: rutas solo usa la tool exterior; su RAG queda encapsulado."""
    assert config.TOOLS_POR_ESPECIALISTA["rutas"] == ["planificar_ruta"]


def test_rutas_con_origen_y_destino_invoca_una_vez_y_conserva_json():
    """RF-12, RF-17 y RF-18: la llamada exterior deja traza y resultado JSON disponible."""
    resultado_json = json.dumps(RUTA_OK, ensure_ascii=False)
    llm = LLMFalso([
        {
            "tool": "planificar_ruta",
            "args": {"origen": "Atocha", "destino": "Sol"},
        },
        {"final": "Hay una ruta de Atocha a Sol."},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": resultado_json})

    salida = nodo_rutas(_estado("¿Cómo llego de Atocha a Sol?"), llm, ejecutor)

    assert PROMPT_RUTAS in llm.llamadas[0][0]["content"]
    assert ejecutor.llamadas == [("planificar_ruta", {"origen": "Atocha", "destino": "Sol"})]
    assert resultado_json in llm.llamadas[1][-1]["content"]
    assert salida["notas"][-1].endswith("Hay una ruta de Atocha a Sol.")
    assert salida["traza"] == [
        {
            "tool": "planificar_ruta",
            "args": {"origen": "Atocha", "destino": "Sol"},
            "status": "ok",
            "preview": resultado_json[:120],
        }
    ]


def test_rutas_combina_un_extremo_aportado_en_el_turno_anterior():
    """RF-7 y RF-59: el LLM recibe el historial para completar los argumentos de la tool."""
    historial = [
        {"role": "user", "content": "Quiero salir desde Atocha."},
        {"role": "assistant", "content": "¿Cuál es el destino?"},
    ]
    llm = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Atocha", "destino": "Sol"}},
        {"final": "Ruta propuesta."},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})

    salida = nodo_rutas(_estado("Quiero llegar a Sol.", historial), llm, ejecutor)

    assert any("Atocha" in mensaje["content"] for mensaje in llm.llamadas[0])
    assert any("Sol" in mensaje["content"] for mensaje in llm.llamadas[0])
    assert ejecutor.llamadas == [("planificar_ruta", {"origen": "Atocha", "destino": "Sol"})]
    assert salida["notas"][-1].endswith("Ruta propuesta.")


def test_rutas_sin_un_extremo_no_invoca_la_tool():
    """RF-34: una petición incompleta solicita aclaración sin activar la planificación."""
    llm = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Atocha"}},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})

    salida = nodo_rutas(_estado("Quiero salir desde Atocha."), llm, ejecutor)

    assert ejecutor.llamadas == []
    assert salida["traza"] == []
    assert "destino" in salida["notas"][-1].lower()


@pytest.mark.parametrize(
    ("mensaje", "dato_pendiente"),
    [
        ("QUIERO IR DE Átocha.", "destino"),
        ("Necesito, ir de Atocha a...", "destino"),
        ("Voy de.", "origen y el destino"),
    ],
)
def test_formulacion_incompleta_pide_aclaracion_antes_de_llm_tool_y_hitl(
    mensaje, dato_pendiente
):
    """RF-21: una formulación explícita incompleta se detiene antes de planificar."""
    llm = LLMFalso([])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})

    salida = nodo_rutas(_estado(mensaje), llm, ejecutor)

    assert dato_pendiente in salida["notas"][-1].lower()
    assert llm.llamadas == []
    assert ejecutor.llamadas == []
    assert salida["traza"] == []
    assert "resultados" not in salida
    assert salida.get("planes_pendientes", []) == []
    assert salida.get("hitl_pendiente", False) is False


def test_rutas_bloquea_una_segunda_planificacion_en_el_mismo_nodo():
    """RF-12: aunque el modelo la proponga de nuevo, solo hay una llamada exterior."""
    llm = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Atocha", "destino": "Sol"}},
        {"tool": "planificar_ruta", "args": {"origen": "Sol", "destino": "Atocha"}},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})

    salida = nodo_rutas(_estado("¿Cómo llego de Atocha a Sol?"), llm, ejecutor)

    assert len(ejecutor.llamadas) == 1
    assert "una sola vez" in salida["notas"][-1].lower()


# --- T15 (spec 004): fecha y hora actuales en el prompt, formato ISO 8601 y consulta que no es de rutas ---

from datetime import datetime
from zoneinfo import ZoneInfo

from src.agents import rutas

MADRID = ZoneInfo("Europe/Madrid")


def _prompt_de(monkeypatch, instante, mensaje="¿Cómo llego de Atocha a Sol mañana?"):
    """Ejecuta el nodo con `ahora()` fijado y devuelve el contenido del mensaje de sistema que recibió el LLM."""
    monkeypatch.setattr(rutas, "ahora", lambda: instante)
    llm = LLMFalso([{"final": "Nota."}])
    nodo_rutas(_estado(mensaje), llm, EjecutorFalso({}))
    return llm.llamadas[0][0]["content"]


def test_prompt_lleva_fecha_y_hora_de_ahora(monkeypatch):
    """RF-50: el prompt lleva la fecha y la hora que da ahora() (src/reloj.py), para entender «mañana»."""
    prompt = _prompt_de(monkeypatch, datetime(2026, 10, 17, 7, 30, tzinfo=MADRID))
    assert "17/10/2026" in prompt and "07:30" in prompt and "sábado" in prompt
    assert PROMPT_RUTAS in prompt           # lo de Rubén sigue entero dentro del prompt


def test_prompt_lee_la_hora_en_cada_llamada(monkeypatch):
    """RF-50: la hora se lee en cada llamada a nodo_rutas, no al importar el módulo (no queda vieja)."""
    primero = _prompt_de(monkeypatch, datetime(2026, 10, 17, 7, 30, tzinfo=MADRID))
    segundo = _prompt_de(monkeypatch, datetime(2026, 12, 3, 18, 45, tzinfo=MADRID))
    assert primero != segundo
    assert "07:30" in primero and "18:45" not in primero
    assert "03/12/2026" in segundo and "18:45" in segundo and "17/10/2026" not in segundo


def test_prompt_indica_formato_iso_8601_con_hora(monkeypatch):
    """RF-50b: las horas se pasan a la herramienta en ISO 8601 con hora, con un ejemplo."""
    prompt = _prompt_de(monkeypatch, datetime(2026, 10, 17, 7, 30, tzinfo=MADRID))
    assert "ISO 8601" in prompt and "2026-10-17T08:00" in prompt
    assert "hora_salida" in prompt and "hora_llegada" in prompt


def test_prompt_sin_lista_de_titulos(monkeypatch):
    """RF-35, RF-50: no hay lista cerrada de títulos en el prompt; el título es texto libre del usuario."""
    prompt = _prompt_de(monkeypatch, datetime(2026, 10, 17, 7, 30, tzinfo=MADRID)).lower()
    for texto in ("billete de 10 viajes", "billete sencillo", "abono", "títulos disponibles", "lista cerrada"):
        assert texto not in prompt


def test_rutas_consulta_que_no_es_de_rutas_no_invoca_la_tool():
    """RF-29: una consulta que no es de rutas no invoca la herramienta y lo dice en la nota."""
    llm = LLMFalso([{"final": "No es una consulta de rutas: no puedo planificar un trayecto con eso."}])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})

    salida = nodo_rutas(_estado("¿Qué tiempo hará mañana en Madrid?"), llm, ejecutor)

    assert ejecutor.llamadas == [] and salida["traza"] == []
    assert "no es una consulta de rutas" in salida["notas"][-1].lower()


@pytest.mark.parametrize("args", [{"destino": "Sol"}, {"origen": "", "destino": "Sol"}, {"origen": None, "destino": "Sol"}])
def test_rutas_no_asume_un_origen_por_defecto(args):
    """RF-27: si falta el origen, la tool no se invoca (no se rellena con una ubicación supuesta) y se pide en la nota."""
    llm = LLMFalso([{"tool": "planificar_ruta", "args": args}])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})

    salida = nodo_rutas(_estado("Quiero llegar a Sol."), llm, ejecutor)

    assert ejecutor.llamadas == [] and salida["traza"] == []
    assert "origen" in salida["notas"][-1].lower()


def test_prompt_prohibe_inventar_o_suponer_extremos():
    """RF-27: el prompt ordena no inventar ni suponer origen o destino."""
    assert "No inventes ni supongas origen o destino" in PROMPT_RUTAS


# --- Spec 010: «de X al Y», «hasta» y «en bici» llegan a la herramienta ---

from src.agents.rutas import _aclaracion_formulacion_incompleta  # noqa: E402

SOL_BERNABEU = "¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu?"


@pytest.mark.parametrize("mensaje", [
    SOL_BERNABEU,
    SOL_BERNABEU[:-1] + " y cuánto cuesta el abono joven?",
    "Quiero ir de Atocha hasta Sol",
    "voy de Sol a Moncloa a las 8",
    "necesito ir de Sol al Retiro",
])
def test_de_x_al_y_y_hasta_no_dan_aviso_de_destino(mensaje):
    assert _aclaracion_formulacion_incompleta(mensaje) is None


@pytest.mark.parametrize("mensaje", [SOL_BERNABEU, SOL_BERNABEU[:-1] + " y cuánto cuesta el abono joven?"])
def test_de_x_al_y_llega_a_la_herramienta(mensaje):
    llm = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Puerta del Sol", "destino": "Estadio Santiago Bernabéu"}},
        {"final": "Ruta propuesta."},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})
    salida = nodo_rutas(_estado(mensaje), llm, ejecutor)
    assert ejecutor.llamadas == [("planificar_ruta", {"origen": "Puerta del Sol", "destino": "Estadio Santiago Bernabéu"})]
    assert salida["notas"][-1].endswith("Ruta propuesta.")


@pytest.mark.parametrize("mensaje", ["voy de Sol a", "voy de Sol al", "Quiero ir de Atocha hasta", "voy de Sol hasta?"])
def test_sin_destino_sigue_el_aviso(mensaje):
    assert _aclaracion_formulacion_incompleta(mensaje) == "Falta indicar el destino para planificar la ruta."


def test_sin_origen_y_sin_nada_siguen_el_aviso():
    assert _aclaracion_formulacion_incompleta("voy de a Sol") == "Falta indicar el origen para planificar la ruta."
    assert _aclaracion_formulacion_incompleta("voy de al Sol") == "Falta indicar el origen para planificar la ruta."
    assert _aclaracion_formulacion_incompleta("quiero ir de") == "Falta indicar el origen y el destino para planificar la ruta."


def test_se_parte_por_la_primera_aparicion_del_separador():
    # «a las 8» no debe tomarse como destino: el destino es «Moncloa a las 8» y el origen «Sol».
    assert _aclaracion_formulacion_incompleta("voy de Sol a Moncloa a las 8") is None
    assert _aclaracion_formulacion_incompleta("voy de Sol a a") is None          # primera «a»: hay origen y destino


def test_prompt_rutas_pide_la_tool_tambien_para_ir_en_bici():
    prompt = " ".join(PROMPT_RUTAS.split())
    assert "pide ir en bici" in prompt and "solicita planificar_ruta igualmente" in prompt
    assert "la alternativa en BiciMAD si procede o el motivo por el que no se ofrece" in prompt
    assert "no rechaces la petición por ser en bici" in prompt


def test_ir_en_bici_llega_a_la_herramienta_con_origen_y_destino():
    mensaje = "Como puedo ir en bici desde Cibeles hasta Plaza de España?"
    assert _aclaracion_formulacion_incompleta(mensaje) is None
    llm = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Cibeles", "destino": "Plaza de España"}},
        {"final": "Ruta en transporte público y alternativa en BiciMAD según la herramienta."},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})
    salida = nodo_rutas(_estado(mensaje), llm, ejecutor)
    assert ejecutor.llamadas == [("planificar_ruta", {"origen": "Cibeles", "destino": "Plaza de España"})]
    assert "rechaces la petición por ser en bici" in llm.llamadas[0][0]["content"]       # el LLM recibe la regla
    assert salida["notas"][-1].startswith("[rutas] Ruta en transporte público")
