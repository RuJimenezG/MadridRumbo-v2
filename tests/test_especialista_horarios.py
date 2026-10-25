"""Tests del especialista de horarios (spec 001, RF-8 a RF-15).

Usan un LLM y un ejecutor de tools falsos: no llaman a ninguna API.
"""
import config
import pytest
from src.agents.horarios import PROMPT_HORARIOS, nodo_horarios

ABSTENCION = "No lo sé, no está en los documentos."


class LLMFalso:
    """LLM que devuelve respuestas de un guion y recuerda los mensajes recibidos."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.recibidos = []

    def __call__(self, mensajes):
        self.recibidos.append(list(mensajes))
        return self.guion.pop(0)


class EjecutorFalso:
    """Sustituye a ejecutar_tool: guarda las llamadas y devuelve textos fijos."""

    def __init__(self, resultados=None):
        self.resultados = resultados or {}
        self.llamadas = []

    def __call__(self, nombre, args, traza):
        self.llamadas.append(nombre)
        resultado = self.resultados.get(nombre, "ok")
        traza.append(
            {
                "tool": nombre,
                "args": args,
                "status": "error" if str(resultado).startswith("ERROR") else "ok",
                "preview": resultado,
            }
        )
        return resultado


def estado(mensaje="¿hasta qué hora hay metro hoy?"):
    return {"mensaje": mensaje, "notas": [], "traza": []}


def test_prompt_propio():
    # RF-8: el especialista tiene prompt propio y se lo envía al LLM el primero.
    assert isinstance(PROMPT_HORARIOS, str) and PROMPT_HORARIOS.strip()
    llm = LLMFalso([{"final": "Respuesta"}])
    nodo_horarios(estado(), llm, EjecutorFalso())
    assert llm.recibidos[0][0]["content"] == PROMPT_HORARIOS


def test_prompt_declara_la_excepcion_de_horarios_y_solo_sus_dos_tools():
    """RF-58: horarios conserva hora y RAG como excepción explícita del grafo."""
    prompt = PROMPT_HORARIOS.lower()
    assert "únicamente" in prompt
    assert "hora_actual" in prompt
    assert "rag_ask" in prompt


def test_usa_hora_actual():
    # RF-9: si la consulta depende de "ahora/hoy", pide hora_actual antes de la nota.
    llm = LLMFalso([{"tool": "hora_actual", "args": {}}, {"final": "Son las 17:58"}])
    ejecutor = EjecutorFalso({"hora_actual": "Hoy es martes 13/10/2026, son las 17:58"})
    salida = nodo_horarios(estado(), llm, ejecutor)
    assert ejecutor.llamadas == ["hora_actual"]
    assert salida["notas"][-1].startswith("[horarios]")
    # El resultado de la tool vuelve al LLM en el siguiente mensaje.
    assert "17:58" in llm.recibidos[1][-1]["content"]


def test_usa_rag():
    # RF-10: para datos del corpus invoca el RAG como tool.
    llm = LLMFalso([
        {"tool": "hora_actual", "args": {}},
        {"tool": "rag_ask", "args": {"consulta": "horario del metro"}},
        {"final": "El metro cierra a la 1:30"},
    ])
    ejecutor = EjecutorFalso({"rag_ask": "Metro: 6:00 a 1:30"})
    salida = nodo_horarios(estado(), llm, ejecutor)
    assert ejecutor.llamadas == ["hora_actual", "rag_ask"]
    assert len(salida["traza"]) == 2


@pytest.mark.parametrize("tool", ["hora_actual", "rag_ask"])
def test_fallo_de_tool_permitida_queda_controlado_en_la_traza(tool):
    """RF-17 a RF-19: los fallos de ambas dependencias se conservan sin propagarse."""
    error = f"ERROR: fallo simulado de {tool}"
    args = {"consulta": "horario"} if tool == "rag_ask" else {}
    llm = LLMFalso([
        {"tool": tool, "args": args},
        {"final": f"No he podido obtener datos con {tool}."},
    ])

    salida = nodo_horarios(estado(), llm, EjecutorFalso({tool: error}))

    assert salida["traza"] == [
        {"tool": tool, "args": args, "status": "error", "preview": error}
    ]
    assert tool in salida["notas"][-1]


def test_abstencion_sin_evidencia():
    # RF-11: si el RAG se abstiene, la nota lo dice y no inventa horarios.
    def llm(mensajes):
        ultimo = mensajes[-1]["content"]
        if ABSTENCION in ultimo:
            return {"final": "No hay información de ese horario en los documentos."}
        return {"tool": "rag_ask", "args": {"consulta": "horario"}}

    ejecutor = EjecutorFalso({"rag_ask": ABSTENCION})
    salida = nodo_horarios(estado(), llm, ejecutor)
    nota = salida["notas"][-1]
    assert "No hay información" in nota
    assert not any(c.isdigit() for c in nota)


def test_tool_fuera_de_especialista_no_se_ejecuta():
    # RF-12: una tool fuera de la lista del especialista no se ejecuta y queda en la traza.
    llm = LLMFalso([{"tool": "borrar_todo", "args": {}}, {"final": "Listo"}])
    ejecutor = EjecutorFalso()
    salida = nodo_horarios(estado(), llm, ejecutor)
    assert ejecutor.llamadas == []
    assert salida["traza"][0]["tool"] == "borrar_todo"
    assert salida["traza"][0]["status"] == "bloqueada"


@pytest.mark.parametrize("tool", ["calculadora", "describir_imagen", "planificar_ruta"])
def test_cualquier_tercera_tool_se_bloquea(tool):
    """RF-58: ninguna tercera tool se ejecuta desde el especialista de horarios."""
    llm = LLMFalso([{"tool": tool, "args": {}}, {"final": "No disponible."}])
    ejecutor = EjecutorFalso({tool: "resultado que no debe usarse"})

    salida = nodo_horarios(estado(), llm, ejecutor)

    assert ejecutor.llamadas == []
    assert salida["traza"][0]["status"] == "bloqueada"


def test_max_steps(monkeypatch):
    # RF-13: con tope 2, solo se ejecutan 2 tools aunque el LLM pida más.
    monkeypatch.setattr(config, "MAX_STEPS_ESPECIALISTA", 2)
    llm = LLMFalso([{"tool": "hora_actual", "args": {}}] * 10)
    ejecutor = EjecutorFalso({"hora_actual": "17:58"})
    salida = nodo_horarios(estado(), llm, ejecutor)
    assert len(ejecutor.llamadas) == 2
    assert "límite" in salida["notas"][-1]


def test_no_decide_done():
    # RF-14: devuelve nota y traza, nunca decide `done`.
    salida = nodo_horarios(estado(), LLMFalso([{"final": "Respuesta"}]), EjecutorFalso())
    assert set(salida) == {"notas", "traza"}
    assert "done" not in salida


def test_llm_falla():
    # RF-15: si el LLM lanza una excepción, hay nota de error y no se propaga.
    def llm(mensajes):
        raise RuntimeError("sin conexión")

    salida = nodo_horarios(estado(), llm, EjecutorFalso())
    assert "ERROR" in salida["notas"][-1]


def test_respuesta_invalida():
    # RF-15: una respuesta que no es ni tool ni final también da nota de error.
    for basura in ["texto suelto", {}, {"otra": 1}, None]:
        salida = nodo_horarios(estado(), LLMFalso([basura]), EjecutorFalso())
        assert "ERROR" in salida["notas"][-1]
