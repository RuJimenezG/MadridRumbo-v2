"""Spec 010, T14 (RF-41): regla de seguimiento sobre la misma ruta en `PROMPT_RUTAS`. Sin API ni red."""
import json

from src.agents.rutas import PROMPT_RUTAS, nodo_rutas
from tests.dobles_grafo import EjecutorFalso, LLMFalso
from tests.test_especialista_rutas import RUTA_OK, _estado

PROMPT = " ".join(PROMPT_RUTAS.split())


def test_el_prompt_pide_reutilizar_textos_opciones_y_titulo_del_historial():
    assert "pregunta de seguimiento sobre la misma ruta" in PROMPT
    assert "los mismos textos de origen y destino" in PROMPT
    assert "las mismas opciones elegidas" in PROMPT and "opcion_origen" in PROMPT
    assert "el mismo `titulo` del historial" in PROMPT
    assert "¿y cómo puedo ir en bici?" in PROMPT


def test_el_prompt_sigue_sin_listas_ni_ejemplos_de_titulos():
    for texto in ("billete de 10 viajes", "billete sencillo", "abono", "títulos disponibles", "lista cerrada"):
        assert texto not in PROMPT.lower()


def test_el_seguimiento_llega_a_la_tool_con_los_mismos_argumentos():
    historial = [
        {"role": "user", "content": "¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu con el abono joven?"},
        {"role": "user", "content": "1"},
    ]
    args = {"origen": "Puerta del Sol", "destino": "Estadio Santiago Bernabéu", "opcion_origen": 1,
            "titulo": "abono joven"}
    llm = LLMFalso([{"tool": "planificar_ruta", "args": args}, {"final": "Ruta propuesta."}])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})
    salida = nodo_rutas(_estado("¿Y cómo puedo ir en bici?", historial), llm, ejecutor)
    mensajes = llm.llamadas[0]
    assert "el mismo `titulo` del historial" in " ".join(mensajes[0]["content"].split())      # la regla llega al LLM
    assert [m["content"] for m in mensajes[1:-1]] == [h["content"] for h in historial]      # y el historial también
    assert ejecutor.llamadas == [("planificar_ruta", args)]
    assert salida["notas"][-1].endswith("Ruta propuesta.")
