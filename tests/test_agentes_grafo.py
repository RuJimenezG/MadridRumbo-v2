"""Especialistas del grafo multiagente probados con dobles sin red (spec 005)."""
import config

from src.agents.base import crear_ejecutor_transversal
from src.agents.rag import PROMPT_RAG, nodo_rag
from src.agents.auxiliar import PROMPT_AUXILIAR, nodo_auxiliar
from tests.dobles_grafo import EjecutorFalso, LLMFalso


def _estado(mensaje="¿Qué zona CRTM corresponde al abono?"):
    """Construye el mínimo estado que necesita un especialista aislado."""
    return {"mensaje": mensaje, "notas": [], "traza": []}


def test_nodo_rag_consulta_evidencia_y_deja_traza_completa():
    """RF-16 a RF-18: consulta RAG, conserva evidencia y audita la llamada."""
    evidencia = "Fuente: documento CRTM. La zona B1 cubre el municipio indicado."
    llm = LLMFalso([
        {"tool": "rag_ask", "args": {"consulta": "zona del abono"}},
        {"final": "Según el documento CRTM, corresponde la zona B1."},
    ])
    ejecutor = EjecutorFalso({"rag_ask": evidencia})

    salida = nodo_rag(_estado(), llm, ejecutor)

    assert PROMPT_RAG in llm.llamadas[0][0]["content"]
    assert ejecutor.llamadas == [("rag_ask", {"consulta": "zona del abono"})]
    assert salida["notas"][-1].endswith("corresponde la zona B1.")
    assert evidencia in llm.llamadas[1][-1]["content"]
    assert salida["traza"] == [
        {
            "tool": "rag_ask",
            "args": {"consulta": "zona del abono"},
            "status": "ok",
            "preview": evidencia,
        }
    ]


def test_nodo_rag_conserva_la_abstencion_del_corpus():
    """RF-17: si no hay evidencia, la abstención llega intacta a la nota final."""
    abstencion = "No lo sé, no está en los documentos."

    def llm(mensajes):
        if abstencion in mensajes[-1]["content"]:
            return {"final": abstencion}
        return {"tool": "rag_ask", "args": {"consulta": "dato no documentado"}}

    salida = nodo_rag(_estado(), llm, EjecutorFalso({"rag_ask": abstencion}))

    assert abstencion in salida["notas"][-1]
    assert salida["traza"][0]["status"] == "ok"


def test_nodo_rag_conserva_un_error_controlado_de_la_tool():
    """RF-19: el fallo se mantiene en traza y puede comunicarse al sintetizador."""
    error = "ERROR: el índice no está disponible."
    llm = LLMFalso([
        {"tool": "rag_ask", "args": {"consulta": "tarifas"}},
        {"final": "No he podido consultar el corpus en este momento."},
    ])

    salida = nodo_rag(_estado(), llm, EjecutorFalso({"rag_ask": error}))

    assert salida["traza"][0]["status"] == "error"
    assert salida["traza"][0]["preview"] == error
    assert "No he podido" in salida["notas"][-1]


def test_nodo_rag_bloquea_toda_tool_distinta_de_rag_ask():
    """RF-44: ninguna propuesta diferente obtiene ejecución directa desde RAG."""
    llm = LLMFalso([
        {"tool": "hora_actual", "args": {}},
        {"final": "La tool no está disponible para este especialista."},
    ])
    ejecutor = EjecutorFalso({"hora_actual": "12:00"})

    salida = nodo_rag(_estado(), llm, ejecutor)

    assert config.TOOLS_POR_ESPECIALISTA["rag"] == ["rag_ask"]
    assert ejecutor.llamadas == []
    assert salida["traza"] == [
        {
            "tool": "hora_actual",
            "args": {},
            "status": "bloqueada",
            "preview": "ERROR: tool no permitida: hora_actual",
        }
    ]


def test_nodo_auxiliar_usa_hora_actual_y_deja_su_traza():
    """RF-9, RF-13 y RF-18: la consulta temporal obtiene la hora mediante su tool."""
    hora = "Hoy es miércoles 15/10/2026, son las 17:58 (laborable, hora de Madrid)."
    llm = LLMFalso([
        {"tool": "hora_actual", "args": {}},
        {"final": "Son las 17:58 en Madrid."},
    ])
    ejecutor = EjecutorFalso({"hora_actual": hora})

    salida = nodo_auxiliar(_estado("¿Qué hora es?"), llm, ejecutor)

    assert PROMPT_AUXILIAR in llm.llamadas[0][0]["content"]
    assert ejecutor.llamadas == [("hora_actual", {})]
    assert hora in llm.llamadas[1][-1]["content"]
    assert salida["traza"][0] == {
        "tool": "hora_actual",
        "args": {},
        "status": "ok",
        "preview": hora,
    }


def test_nodo_auxiliar_usa_calculadora_para_una_operacion_valida():
    """RF-14: el resultado aritmético procede de calculadora, no de una estimación."""
    llm = LLMFalso([
        {"tool": "calculadora", "args": {"expresion": "3 * 2,50"}},
        {"final": "El total calculado es 7,50."},
    ])
    ejecutor = EjecutorFalso({"calculadora": "7,50"})

    salida = nodo_auxiliar(_estado("Calcula 3 por 2,50."), llm, ejecutor)

    assert ejecutor.llamadas == [("calculadora", {"expresion": "3 * 2,50"})]
    assert salida["traza"][0]["tool"] == "calculadora"
    assert salida["traza"][0]["status"] == "ok"
    assert salida["traza"][0]["preview"] == "7,50"


def test_nodo_auxiliar_conserva_el_error_de_calculadora():
    """RF-19: un cálculo inválido se conserva para que el sintetizador lo explique."""
    error = "ERROR: división entre cero"
    llm = LLMFalso([
        {"tool": "calculadora", "args": {"expresion": "1 / 0"}},
        {"final": "No puedo calcular esa operación porque divide entre cero."},
    ])

    salida = nodo_auxiliar(_estado("Calcula 1 / 0."), llm, EjecutorFalso({"calculadora": error}))

    assert salida["traza"][0]["status"] == "error"
    assert salida["traza"][0]["preview"] == error
    assert "divide entre cero" in salida["notas"][-1]


def test_nodo_auxiliar_bloquea_una_tool_que_no_es_hora_ni_calculadora():
    """RF-43: auxiliar no puede ejecutar RAG ni ninguna tercera tool directa."""
    llm = LLMFalso([
        {"tool": "rag_ask", "args": {"consulta": "tarifas"}},
        {"final": "No puedo consultar documentos desde este especialista."},
    ])
    ejecutor = EjecutorFalso({"rag_ask": "dato que no debe usarse"})

    salida = nodo_auxiliar(_estado(), llm, ejecutor)

    assert config.TOOLS_POR_ESPECIALISTA["auxiliar"] == ["hora_actual", "calculadora"]
    assert ejecutor.llamadas == []
    assert salida["traza"][0] == {
        "tool": "rag_ask",
        "args": {"consulta": "tarifas"},
        "status": "bloqueada",
        "preview": "ERROR: tool no permitida: rag_ask",
    }


def test_ejecutor_transversal_conserva_el_limite_local_del_especialista(monkeypatch):
    """RF-18 y RF-19: el ejecutor compartido no evita el máximo local de pasos."""
    monkeypatch.setattr(config, "MAX_STEPS_ESPECIALISTA", 1)
    ejecutor_real = EjecutorFalso({"rag_ask": "Evidencia."})
    ejecutor_compartido = crear_ejecutor_transversal(ejecutor_real)
    llm = LLMFalso([
        {"tool": "rag_ask", "args": {"consulta": "primera"}},
        {"tool": "rag_ask", "args": {"consulta": "segunda"}},
    ])

    salida = nodo_rag(_estado(), llm, ejecutor_compartido)

    assert ejecutor_real.llamadas == [("rag_ask", {"consulta": "primera"})]
    assert len(salida["traza"]) == 1
    assert "límite" in salida["notas"][-1]
