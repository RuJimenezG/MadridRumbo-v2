"""Tests del especialista de rutas (spec 005, T10). No usan API ni red."""
import json

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
