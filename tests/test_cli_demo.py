"""Tests de la demo del CLI: `--demo` y `--auto-aprobar` (spec 008, RF-11 a RF-14). No usan API."""
import config
from src.clientes.cli import ejecutar_cli
from src.clientes.grafo_falso import GrafoFalso
from tests.test_cli import Entrada


def ejecutar(argumentos, lineas=()):
    """Lanza el CLI con el grafo simulado y devuelve (código, texto impreso, grafo, entrada)."""
    grafo = GrafoFalso()
    entrada = Entrada(lineas)
    salida = []
    codigo = ejecutar_cli(argumentos, grafo, entrada, salida.append, None)
    return codigo, "\n".join(salida), grafo, entrada


def decisiones(grafo):
    """Valores de aprobación enviados al grafo, en orden."""
    return [dato for nombre, _, dato in grafo.llamadas if nombre == "aprobar_plan"]


def test_demo_lanza_tres_pedidos():
    # RF-11: los tres pedidos fijos, cada uno en su propia conversación.
    codigo, texto, grafo, _ = ejecutar(["--demo", "--auto-aprobar"])
    assert codigo == 0
    pedidos = [dato for nombre, _, dato in grafo.llamadas if nombre == "procesar_turno"]
    assert pedidos == list(config.PEDIDOS_DEMO)
    hilos = [hilo for nombre, hilo, _ in grafo.llamadas if nombre == "procesar_turno"]
    assert len(set(hilos)) == 3
    for pedido in config.PEDIDOS_DEMO:
        assert pedido in texto


def test_demo_sin_auto_pide_aprobacion():
    # RF-12: sin --auto-aprobar se pide la decisión humana del plan; solo la ruta genera uno.
    codigo, _, grafo, entrada = ejecutar(["--demo"], ["n"])
    assert codigo == 0
    assert len([p for p in entrada.prompts if "[s/n]" in p]) == 1
    assert decisiones(grafo) == [False]


def test_demo_decision_invalida_repregunta():
    _, texto, grafo, _ = ejecutar(["--demo"], ["x", "s"])
    assert "Respuesta no válida" in texto
    assert decisiones(grafo) == [True]


def test_demo_sin_decision_no_aprueba_nada():
    # RF-7: si la persona se va sin decidir, la demo termina sin cerrar ningún plan.
    codigo, _, grafo, _ = ejecutar(["--demo"], [])
    assert codigo == 0
    assert decisiones(grafo) == []
    # Horarios cierra sin pausa; la ruta pausa y, sin decisión, la demo termina sin lanzar el tercer pedido.
    assert len([c for c in grafo.llamadas if c[0] == "procesar_turno"]) == 2


def test_demo_auto_aprueba():
    # RF-13: con --auto-aprobar se aprueba solo, sin preguntar, y se indica en pantalla.
    _, texto, grafo, entrada = ejecutar(["--demo", "--auto-aprobar"])
    assert entrada.prompts == []
    assert decisiones(grafo) == [True]  # solo la ruta genera un plan
    assert texto.count("aprobado automáticamente") == 1


def test_auto_aprobar_sin_demo_da_error():
    # RF-14: error claro y sin iniciar el chat.
    codigo, texto, grafo, entrada = ejecutar(["--auto-aprobar"], ["hola", "salir"])
    assert codigo != 0
    assert "--demo" in texto
    assert grafo.llamadas == []
    assert entrada.prompts == []


def test_demo_auto_aprueba_el_primer_plan_si_hay_varios():
    # RF-13: con --auto-aprobar y varios planes no hay quien elija, así que se aprueba el primero.
    class GrafoConVariasRutas(GrafoFalso):
        def __init__(self):
            super().__init__()
            self.estados_recibidos = []

        def procesar_turno(self, estado, mensaje, thread_id):
            return super().procesar_turno(estado, "Dame dos rutas alternativas desde Sol hasta Atocha", thread_id)

        def aprobar_plan(self, estado, thread_id, aprobado):
            self.estados_recibidos.append(dict(estado))
            return super().aprobar_plan(estado, thread_id, aprobado)

    grafo = GrafoConVariasRutas()
    codigo = ejecutar_cli(["--demo", "--auto-aprobar"], grafo, Entrada([]), [].append, None)
    assert codigo == 0
    assert [e["plan_id_seleccionado"] for e in grafo.estados_recibidos] == ["ruta-1"] * 3
