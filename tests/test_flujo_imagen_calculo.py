"""Tests del flujo imagen -> calculadora en el especialista de tarifas (spec 002, RF-21 a RF-23).

Usan un LLM y tools falsos: no llaman a ninguna API.
"""
import config
import src.tools as tools
from src.agents.tarifas import PROMPT_TARIFAS, nodo_tarifas

TEXTO_IMAGEN = (
    "Billete sencillo EMT: 1,50 € | Billete sencillo TransBus: 1,80 € | "
    "Billete Exprés Aeropuerto: 5,00 € | Metrobús 10 viajes: 7,30 €"
)
SIN_TEXTO = "No hay texto legible en la imagen."
PREGUNTA = "Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?"


class LLMFalso:
    """LLM que devuelve respuestas de un guion y recuerda los mensajes recibidos."""

    def __init__(self, guion):
        self.guion = list(guion)
        self.recibidos = []

    def __call__(self, mensajes):
        self.recibidos.append(list(mensajes))
        return self.guion.pop(0)


class EjecutorFalso:
    """Sustituye a ejecutar_tool: guarda las llamadas (nombre, args) y devuelve textos fijos."""

    def __init__(self, resultados):
        self.resultados = resultados
        self.llamadas = []

    def __call__(self, nombre, args, traza):
        self.llamadas.append((nombre, args))
        resultado = self.resultados.get(nombre, "ok")
        traza.append({"tool": nombre, "args": args, "status": "ok", "preview": resultado})
        return resultado


def estado(mensaje=PREGUNTA):
    return {"mensaje": mensaje, "notas": [], "traza": []}


def test_imagen_luego_calculo():
    # RF-21: primero describir_imagen, después calculadora, en ese orden y con la misma traza.
    llm = LLMFalso([
        {"tool": "describir_imagen", "args": {"pregunta": "precios de los billetes"}},
        {"tool": "calculadora", "args": {"expresion": "3*1,50+5,00"}},
        {"final": "Total: 9,50 €"},
    ])
    ejecutor = EjecutorFalso({"describir_imagen": TEXTO_IMAGEN, "calculadora": "9,50"})
    salida = nodo_tarifas(estado(), llm, ejecutor)
    assert [nombre for nombre, _ in ejecutor.llamadas] == ["describir_imagen", "calculadora"]
    assert [t["tool"] for t in salida["traza"]] == ["describir_imagen", "calculadora"]
    # El resultado de la imagen llega al LLM antes de que pida la calculadora.
    assert "1,50" in llm.recibidos[1][-1]["content"]
    assert "9,50" in llm.recibidos[2][-1]["content"]


def test_flujo_con_tools_reales(monkeypatch):
    # RF-21: con la calculadora real y la allowlist real, el total es exacto.
    monkeypatch.setitem(tools.TOOLS_PERMITIDAS, "describir_imagen", lambda **kwargs: TEXTO_IMAGEN)
    llm = LLMFalso([
        {"tool": "describir_imagen", "args": {}},
        {"tool": "calculadora", "args": {"expresion": "3*1,50+5,00"}},
        {"final": "Total: 9,50 €"},
    ])
    salida = nodo_tarifas(estado(), llm, tools.ejecutar_tool)
    assert salida["traza"][1]["tool"] == "calculadora"
    assert salida["traza"][1]["preview"] == "9,50"
    assert salida["traza"][1]["status"] == "ok"


def test_nota_muestra_importes_y_operacion():
    # RF-22: el prompt exige citar los importes de la imagen y la operación, y la nota llega al grafo.
    for exigencia in ["importes", "imagen", "operación"]:
        assert exigencia in PROMPT_TARIFAS.lower()
    final = "Importes leídos de la imagen: 1,50 € y 5,00 €. Operación: 3*1,50+5,00 = 9,50 €."
    salida = nodo_tarifas(estado(), LLMFalso([{"final": final}]), EjecutorFalso({}))
    assert salida["notas"][-1] == f"[tarifas] {final}"


def test_sin_importes_no_calcula():
    # RF-23: si la imagen no da importes, no se llama a la calculadora y la nota lo indica.
    def llm(mensajes):
        ultimo = mensajes[-1]["content"]
        if SIN_TEXTO in ultimo:
            return {"final": "No hay importes legibles en la imagen; no se puede calcular el total."}
        return {"tool": "describir_imagen", "args": {}}

    ejecutor = EjecutorFalso({"describir_imagen": SIN_TEXTO})
    salida = nodo_tarifas(estado(), llm, ejecutor)
    assert [nombre for nombre, _ in ejecutor.llamadas] == ["describir_imagen"]
    assert "no se puede calcular" in salida["notas"][-1]
    # La regla también está escrita en el prompt del especialista.
    assert "no calcules" in PROMPT_TARIFAS.lower()


def test_tool_ajena_bloqueada():
    # RF-21: el especialista de tarifas no puede usar tools que no le corresponden (p. ej. hora_actual).
    assert "hora_actual" not in config.TOOLS_POR_ESPECIALISTA["tarifas"]
    llm = LLMFalso([{"tool": "hora_actual", "args": {}}, {"final": "Listo"}])
    ejecutor = EjecutorFalso({})
    salida = nodo_tarifas(estado(), llm, ejecutor)
    assert ejecutor.llamadas == []
    assert salida["traza"][0]["status"] == "bloqueada"
