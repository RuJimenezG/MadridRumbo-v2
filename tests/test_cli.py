"""Tests del chat interactivo del CLI (spec 005, RF-1 a RF-5 y RF-28). No usan API.

La entrada y la salida del CLI se inyectan: `leer` devuelve líneas de una lista y
`escribir` acumula lo que se imprimiría.
"""
from src.clientes.cli import ejecutar_cli
from src.clientes.grafo_falso import GrafoFalso
from src.clientes.sesion import MENSAJE_ERROR


class GrafoSinPlan:
    """Grafo de pruebas que responde con un eco y nunca pide aprobación (el HITL va en otros tests)."""

    def __init__(self, fallar_primera=False):
        self.llamadas = []
        self.fallar_primera = fallar_primera

    def procesar_turno(self, estado, mensaje, thread_id):
        self.llamadas.append(("procesar_turno", thread_id, mensaje))
        if self.fallar_primera and len(self.llamadas) == 1:
            raise RuntimeError("fallo simulado")
        return {
            "respuesta": f"Eco: {mensaje}",
            "log": ["[supervisor] -> eco"],
            "hitl_pendiente": False,
            "done": False,
        }

    def aprobar_plan(self, estado, thread_id, aprobado):
        raise AssertionError("estos tests no deberían aprobar ni rechazar")


class Entrada:
    """Sustituye a `input`: devuelve las líneas en orden y lanza EOFError cuando se acaban."""

    def __init__(self, lineas):
        self.lineas = list(lineas)
        self.prompts = []  # lo que el CLI ha preguntado, en orden

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.lineas:
            raise EOFError
        return self.lineas.pop(0)


def ejecutar(lineas, agente=None, argumentos=None, aviso=None):
    """Lanza el CLI con esas entradas y devuelve (código de salida, texto impreso, grafo)."""
    agente = agente or GrafoSinPlan()
    salida = []
    codigo = ejecutar_cli(argumentos or [], agente, Entrada(lineas), salida.append, aviso)
    return codigo, "\n".join(salida), agente


def test_chat_interactivo_responde():
    # RF-1: la persona escribe y ve la respuesta del asistente.
    codigo, texto, _ = ejecutar(["hola", "salir"])
    assert codigo == 0
    assert "Eco: hola" in texto


def test_mismo_thread_id_en_todo_el_chat():
    # RF-2: todos los mensajes llevan el mismo identificador, que además se muestra.
    _, texto, grafo = ejecutar(["uno", "dos", "tres", "salir"])
    hilos = {hilo for _, hilo, _ in grafo.llamadas}
    assert len(grafo.llamadas) == 3
    assert len(hilos) == 1
    assert hilos.pop() in texto


def test_mensaje_vacio_no_llama_al_grafo():
    # RF-3
    _, _, grafo = ejecutar(["", "   ", "salir"])
    assert grafo.llamadas == []


def test_salir_termina():
    # RF-4
    codigo, _, grafo = ejecutar(["salir", "esto no se lee"])
    assert codigo == 0
    assert grafo.llamadas == []


def test_fin_de_entrada_termina_sin_error():
    # RF-4: Ctrl+D (fin de entrada) también termina.
    codigo, _, _ = ejecutar(["hola"])
    assert codigo == 0


def test_ctrl_c_termina_sin_error():
    # RF-4: Ctrl+C termina sin error ni traza.
    def leer(prompt=""):
        raise KeyboardInterrupt

    salida = []
    codigo = ejecutar_cli([], GrafoSinPlan(), leer, salida.append, None)
    assert codigo == 0


def test_fallo_del_grafo_no_corta_el_chat():
    # RF-5: se avisa en español, no se muestran detalles internos y el chat sigue.
    codigo, texto, grafo = ejecutar(["uno", "dos", "salir"], GrafoSinPlan(fallar_primera=True))
    assert codigo == 0
    assert MENSAJE_ERROR in texto
    assert "fallo simulado" not in texto
    assert "Eco: dos" in texto
    assert len(grafo.llamadas) == 2


def test_muestra_el_aviso_del_modo_simulado():
    # RF-28: el aviso se imprime al iniciar, antes de la primera respuesta.
    _, texto, _ = ejecutar(["hola", "salir"], aviso="MODO SIMULADO: prueba")
    assert "MODO SIMULADO: prueba" in texto
    assert texto.index("MODO SIMULADO") < texto.index("Eco: hola")


# --- HITL: aprobar o rechazar el plan (RF-6 a RF-10) ---
# Se usa GrafoFalso, que siempre deja un plan pendiente de decisión.

def ejecutar_hitl(lineas, agente=None):
    """Como `ejecutar`, pero con el grafo simulado y devolviendo también lo que preguntó el CLI."""
    agente = agente or GrafoFalso()
    entrada = Entrada(lineas)
    salida = []
    codigo = ejecutar_cli([], agente, entrada, salida.append, None)
    return codigo, "\n".join(salida), agente, entrada


def llamadas(grafo):
    """Lista de (nombre, dato) de las llamadas al grafo, sin el identificador."""
    return [(nombre, dato) for nombre, _, dato in grafo.llamadas]


def test_plan_pendiente_pregunta_decision():
    # RF-6: se muestra el plan y se pregunta si se aprueba o se rechaza.
    _, texto, _, entrada = ejecutar_hitl(["hola", "s", "salir"])
    assert "Plan propuesto" in texto
    preguntas = [p for p in entrada.prompts if "[s/n]" in p]
    assert len(preguntas) == 1
    assert "aprueba" in preguntas[0].lower()


def test_no_cierra_sin_decision():
    # RF-7: sin una decisión explícita nunca se llama a aprobar_plan.
    for lineas in (["hola"], ["hola", "salir"]):  # fin de entrada y `salir` en la pregunta
        codigo, _, grafo, _ = ejecutar_hitl(lineas)
        assert codigo == 0
        assert [nombre for nombre, _ in llamadas(grafo)] == ["procesar_turno"]


def test_aprobar_muestra_terminada_solo_si_el_grafo_lo_dice():
    # RF-8: la aprobación llega al grafo y «Terminada» depende solo de lo que diga el grafo.
    _, texto, grafo, _ = ejecutar_hitl(["hola", "s", "salir"])
    assert llamadas(grafo)[-1] == ("aprobar_plan", True)
    assert "Terminada: sí" in texto

    class GrafoQueNoCierra(GrafoFalso):
        def aprobar_plan(self, estado, thread_id, aprobado):
            nuevo = super().aprobar_plan(estado, thread_id, aprobado)
            nuevo["done"] = False
            return nuevo

    _, texto, _, _ = ejecutar_hitl(["hola", "s", "salir"], GrafoQueNoCierra())
    assert "Terminada: sí" not in texto


def test_rechazar_permite_seguir():
    # RF-9: tras rechazar, se puede escribir otro mensaje en la misma conversación.
    _, texto, grafo, _ = ejecutar_hitl(["hola", "n", "otra cosa", "s", "salir"])
    assert [nombre for nombre, _ in llamadas(grafo)] == [
        "procesar_turno", "aprobar_plan", "procesar_turno", "aprobar_plan",
    ]
    assert llamadas(grafo)[1] == ("aprobar_plan", False)
    assert len({hilo for _, hilo, _ in grafo.llamadas}) == 1
    assert "Plan rechazado" in texto


def test_decision_invalida_repregunta():
    # RF-10: una respuesta no válida vuelve a preguntar sin llamar al grafo.
    _, texto, grafo, entrada = ejecutar_hitl(["hola", "x", "quizá", "n", "salir"])
    assert len([p for p in entrada.prompts if "[s/n]" in p]) == 3
    assert "Respuesta no válida" in texto
    assert llamadas(grafo) == [("procesar_turno", "hola"), ("aprobar_plan", False)]
