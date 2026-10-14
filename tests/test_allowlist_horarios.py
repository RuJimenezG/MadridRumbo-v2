"""Tests de allowlist y traza de tools (spec 001, RF-6, RF-7 y RF-12). No usan API."""
import src.tools as tools
from src.tools import TOOLS_PERMITIDAS, ejecutar_tool


def test_hora_en_allowlist():
    # RF-6: hora_actual está registrada y se puede ejecutar por nombre.
    assert "hora_actual" in TOOLS_PERMITIDAS
    assert callable(TOOLS_PERMITIDAS["hora_actual"])


def test_traza_ok():
    # RF-7: la traza guarda nombre, argumentos, estado y un extracto del resultado.
    traza = []
    resultado = ejecutar_tool("hora_actual", {}, traza)
    assert not resultado.startswith("ERROR")
    assert len(traza) == 1
    entrada = traza[0]
    assert entrada["tool"] == "hora_actual"
    assert entrada["args"] == {}
    assert entrada["status"] == "ok"
    assert entrada["preview"] == resultado[:120]


def test_tool_no_permitida(monkeypatch):
    # RF-12: una tool que no está en la allowlist no se ejecuta y queda en la traza.
    llamadas = []
    # Se registra una función espía con otro nombre; no debe llamarse nunca.
    monkeypatch.setitem(tools.TOOLS_PERMITIDAS, "espia", lambda **kw: llamadas.append(kw))
    traza = []
    resultado = ejecutar_tool("borrar_todo", {"x": 1}, traza)
    assert resultado.startswith("ERROR: tool no permitida")
    assert llamadas == []
    assert traza[0]["tool"] == "borrar_todo"
    assert traza[0]["status"] == "bloqueada"


def test_tool_con_error(monkeypatch):
    # RF-7: si la tool lanza una excepción, se devuelve ERROR y la traza marca "error".
    def rota(**kwargs):
        raise RuntimeError("fallo simulado")

    monkeypatch.setitem(tools.TOOLS_PERMITIDAS, "rota", rota)
    traza = []
    resultado = ejecutar_tool("rota", {}, traza)
    assert resultado.startswith("ERROR")
    assert traza[0]["status"] == "error"


def test_rag_ask_en_allowlist(monkeypatch):
    # RF-10: el RAG está en la allowlist; se importa de forma perezosa y solo al usarlo.
    import sys
    import types

    assert "rag_ask" in TOOLS_PERMITIDAS
    falso = types.ModuleType("rag.responder")
    falso.rag_ask = lambda consulta: f"respuesta a {consulta}"
    monkeypatch.setitem(sys.modules, "rag.responder", falso)
    assert TOOLS_PERMITIDAS["rag_ask"](consulta="horario") == "respuesta a horario"
