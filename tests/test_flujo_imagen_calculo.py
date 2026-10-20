"""Tests de extracción de importes en nodo_tarifas (spec 005, RF-15 y RF-44).

Usan un LLM y tools falsos: no llaman a ninguna API.
"""
import pytest

import src.tools as tools
from src.agents.tarifas import MARCADOR_REDIRECCION_A_RAG, PROMPT_TARIFAS, nodo_tarifas
from src.estado import crear_estado_inicial
from src.graph import crear_grafo, invocar_grafo, recuperar_estado


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
    """Sustituye a ejecutar_tool: guarda las llamadas y devuelve textos fijos."""

    def __init__(self, resultados):
        self.resultados = resultados
        self.llamadas = []

    def __call__(self, nombre, args, traza):
        self.llamadas.append((nombre, args))
        resultado = self.resultados.get(nombre, "ok")
        traza.append({"tool": nombre, "args": args, "status": "ok", "preview": resultado})
        return resultado


def estado(mensaje=PREGUNTA):
    """Construye el estado mínimo que usa el especialista de tarifas."""
    return {"mensaje": mensaje, "notas": [], "traza": []}


def test_tarifas_extrae_importes_sin_calcular():
    """RF-15 y RF-46: tarifas entrega importes para el posterior nodo auxiliar."""
    llm = LLMFalso([
        {"tool": "describir_imagen", "args": {"pregunta": "precios de los billetes"}},
        {"final": "La imagen muestra los importes 1,50 € y 5,00 €."},
    ])
    ejecutor = EjecutorFalso({"describir_imagen": TEXTO_IMAGEN})

    salida = nodo_tarifas(estado(), llm, ejecutor, tiene_imagen_valida=True)

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["describir_imagen"]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["describir_imagen"]
    assert "1,50" in llm.recibidos[1][-1]["content"]
    assert "1,50" in salida["notas"][-1]


def test_tarifas_con_ejecutor_controlado_solo_llama_a_imagen(monkeypatch):
    """RF-18: la única traza directa de tarifas corresponde a describir_imagen."""
    monkeypatch.setitem(tools.TOOLS_PERMITIDAS, "describir_imagen", lambda **kwargs: TEXTO_IMAGEN)
    llm = LLMFalso([
        {"tool": "describir_imagen", "args": {}},
        {"final": "He encontrado importes en la imagen."},
    ])

    salida = nodo_tarifas(estado(), llm, tools.ejecutar_tool, tiene_imagen_valida=True)

    assert [entrada["tool"] for entrada in salida["traza"]] == ["describir_imagen"]
    assert salida["traza"][0]["status"] == "ok"


def test_prompt_entrega_importes_y_delega_el_calculo_en_auxiliar():
    """RF-46: tarifas no calcula ni consulta RAG; deja esa responsabilidad fuera."""
    for exigencia in ["importes", "imagen", "nodo_auxiliar"]:
        assert exigencia in PROMPT_TARIFAS.lower()
    for tool_prohibida in ["calculadora", "rag_ask"]:
        assert tool_prohibida not in PROMPT_TARIFAS


def test_sin_importes_no_inventa_un_total():
    """RF-19: si la imagen no da importes, tarifas conserva la limitación."""
    def llm(mensajes):
        ultimo = mensajes[-1]["content"]
        if SIN_TEXTO in ultimo:
            return {"final": "No hay importes legibles en la imagen; no se puede calcular el total."}
        return {"tool": "describir_imagen", "args": {}}

    ejecutor = EjecutorFalso({"describir_imagen": SIN_TEXTO})
    salida = nodo_tarifas(estado(), llm, ejecutor, tiene_imagen_valida=True)

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["describir_imagen"]
    assert "no se puede calcular" in salida["notas"][-1]
    assert "precios ni resultados" in PROMPT_TARIFAS.lower()


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("calculadora", {"expresion": "3*1,50+5,00"}),
        ("rag_ask", {"consulta": "tarifas"}),
    ],
)
def test_tarifas_bloquea_calculadora_y_rag(tool, args):
    """RF-44: las dos tools pertenecen a otros nodos y no se ejecutan aquí."""
    llm = LLMFalso([{"tool": tool, "args": args}, {"final": "No disponible."}])
    ejecutor = EjecutorFalso({})

    salida = nodo_tarifas(estado(), llm, ejecutor, tiene_imagen_valida=True)

    assert ejecutor.llamadas == []
    assert salida["traza"][0] == {
        "tool": tool,
        "args": args,
        "status": "bloqueada",
        "preview": f"ERROR: tool no permitida: {tool}",
    }


def test_tarifas_sin_imagen_no_inicia_llm_ni_vision_y_pide_redireccion():
    """RF-12: la defensa local evita cualquier llamada visual sin contexto válido."""
    llm = LLMFalso([AssertionError("el LLM visual no debe ejecutarse")])
    ejecutor = EjecutorFalso({"describir_imagen": TEXTO_IMAGEN})

    salida = nodo_tarifas(estado("Describe este cartel."), llm, ejecutor)

    assert salida[MARCADOR_REDIRECCION_A_RAG] is True
    assert llm.recibidos == []
    assert ejecutor.llamadas == []
    assert salida["traza"] == []


def test_contexto_de_imagen_demo_valida_llega_a_tarifas_y_vision_sin_persistirla():
    """RF-11 y RF-22: una señal válida conserva la única tool visual permitida."""
    llm = LLMFalso([
        {"tool": "describir_imagen", "args": {"pregunta": "precios"}},
        {"final": "La imagen muestra los precios solicitados."},
    ])
    ejecutor = EjecutorFalso({"describir_imagen": TEXTO_IMAGEN})
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["tarifas"]},
        modelos_especialistas={"tarifas": llm},
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    contexto_demo = {
        "diagnostico_supervisor": None,
        "correcciones_tarifas": 0,
        # La fachada ya seleccionó explícitamente una demo configurada válida.
        "imagen_valida": True,
    }

    salida = invocar_grafo(
        grafo,
        crear_estado_inicial("¿Cuánto cuesta el Combinado Metro?"),
        "imagen-demo-explicita",
        contexto=contexto_demo,
    )
    snapshot = recuperar_estado(grafo, "imagen-demo-explicita")

    assert ejecutor.llamadas == [("describir_imagen", {"pregunta": "precios"})]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["describir_imagen"]
    assert contexto_demo["diagnostico_supervisor"]["categoria"] == "sin_fallback"
    assert contexto_demo["correcciones_tarifas"] == 0
    assert "imagen_valida" not in salida
    assert "imagen_valida" not in snapshot


def test_imagen_valida_no_se_hereda_en_el_turno_posterior_del_mismo_hilo():
    """RF-8, RF-15 y RF-17: la señal visual vive solo durante una invocación."""
    llamadas = []
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": ["tarifas"]},
        especialistas={
            "tarifas": lambda estado: llamadas.append("tarifas") or {},
            "rag": lambda estado: llamadas.append("rag") or {},
        },
        modelo_sintetizador=lambda contexto: "Resumen controlado.",
    )
    primer_contexto = {
        "diagnostico_supervisor": None,
        "correcciones_tarifas": 0,
        "imagen_valida": True,
    }
    segundo_contexto = {
        "diagnostico_supervisor": None,
        "correcciones_tarifas": 0,
        "imagen_valida": False,
    }

    invocar_grafo(
        grafo,
        crear_estado_inicial("¿Cuánto cuesta el Combinado Metro?"),
        "imagen-efimera",
        contexto=primer_contexto,
    )
    invocar_grafo(
        grafo,
        crear_estado_inicial("¿Cuánto cuesta el Combinado Metro?"),
        "imagen-efimera",
        contexto=segundo_contexto,
    )
    snapshot = recuperar_estado(grafo, "imagen-efimera")

    assert llamadas == ["tarifas", "rag"]
    assert segundo_contexto["correcciones_tarifas"] == 1
    assert "imagen_valida" not in snapshot
