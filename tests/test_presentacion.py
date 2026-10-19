"""Tests de presentación y contrato de los clientes (spec 005, RF-3, RF-4, RF-10, RF-15, RF-16, RF-24 y RF-26).

Son funciones puras: no usan grafo, red ni API.
"""
import pytest

from src.clientes.contrato import estado_vacio, normalizar_estado
from src.clientes.presentacion import (
    datos_depuracion,
    es_mensaje_vacio,
    es_salida,
    formatear_turno,
    interpretar_decision,
)

ESTADO = {
    "respuesta": "El metro cierra a la 1:30.",
    "plan": ["Informar del horario", "Citar la fuente"],
    "log": ["[supervisor] -> horarios", "[horarios] nota lista"],
    "traza": [
        {"tool": "hora_actual", "args": {}, "status": "ok", "preview": "Hoy es jueves"},
        {"tool": "rag_ask", "args": {"consulta": "horario"}, "status": "error", "preview": "ERROR"},
    ],
    "hitl_pendiente": True,
    "done": False,
}


# --- Contrato ---

def test_estado_vacio():
    # El estado inicial no tiene respuesta, plan ni trazas y no está pendiente ni terminado.
    assert estado_vacio() == {
        "respuesta": "", "plan": [], "log": [], "traza": [], "hitl_pendiente": False, "done": False,
    }


def test_normalizar_rellena_claves_ausentes():
    # El grafo real puede devolver menos claves: las que faltan toman su valor por defecto.
    estado = normalizar_estado({"respuesta": "hola"})
    assert estado["respuesta"] == "hola"
    assert estado["plan"] == [] and estado["traza"] == [] and estado["log"] == []
    assert estado["hitl_pendiente"] is False and estado["done"] is False


def test_normalizar_conserva_claves_desconocidas_y_no_modifica_la_entrada():
    original = {"respuesta": "hola", "extra": 1}
    estado = normalizar_estado(original)
    assert estado["extra"] == 1
    assert "plan" not in original  # no se modifica el diccionario recibido


def test_normalizar_none():
    assert normalizar_estado(None) == estado_vacio()


# --- Formato del turno (RF-15, RF-16) ---

def test_formato_incluye_respuesta_log_traza():
    # RF-15: respuesta, especialistas que actuaron y tools con su estado.
    texto = formatear_turno(ESTADO, "hilo-1")
    assert "El metro cierra a la 1:30." in texto
    assert "[supervisor] -> horarios" in texto and "[horarios] nota lista" in texto
    assert "hora_actual" in texto and "rag_ask" in texto
    assert "ok" in texto and "error" in texto


def test_formato_incluye_thread_id_y_banderas():
    # RF-16: identificador de conversación y banderas de plan pendiente y terminada.
    texto = formatear_turno(ESTADO, "hilo-1")
    assert "hilo-1" in texto
    assert "Plan pendiente: sí" in texto
    assert "Terminada: no" in texto
    terminado = formatear_turno({**ESTADO, "hitl_pendiente": False, "done": True}, "hilo-1")
    assert "Plan pendiente: no" in terminado and "Terminada: sí" in terminado


def test_formato_muestra_el_plan_cuando_hay():
    texto = formatear_turno(ESTADO, "hilo-1")
    assert "Informar del horario" in texto and "Citar la fuente" in texto


def test_formato_con_estado_parcial_no_falla():
    # Un grafo que solo devuelve la respuesta no rompe la presentación.
    texto = formatear_turno({"respuesta": "hola"}, "hilo-2")
    assert "hola" in texto and "hilo-2" in texto
    assert "Plan pendiente: no" in texto


# --- Entradas de la persona (RF-3, RF-4, RF-10) ---

@pytest.mark.parametrize("texto", ["", "   ", "\n", "\t "])
def test_es_mensaje_vacio(texto):
    # RF-3
    assert es_mensaje_vacio(texto) is True


def test_mensaje_con_texto_no_es_vacio():
    assert es_mensaje_vacio("hola") is False


@pytest.mark.parametrize("texto", ["salir", "SALIR", "  Salir  ", "exit", "quit"])
def test_es_salida(texto):
    # RF-4
    assert es_salida(texto) is True


def test_no_es_salida():
    assert es_salida("¿hasta qué hora hay metro?") is False


@pytest.mark.parametrize("texto", ["s", "S", "sí", "si", " Sí ", "aprobar", "a"])
def test_interpretar_decision_aprobar(texto):
    # RF-10
    assert interpretar_decision(texto) is True


@pytest.mark.parametrize("texto", ["n", "N", "no", " NO ", "rechazar", "r"])
def test_interpretar_decision_rechazar(texto):
    assert interpretar_decision(texto) is False


@pytest.mark.parametrize("texto", ["", "quizá", "x", "1", "siii"])
def test_interpretar_decision_invalida(texto):
    # RF-10: lo que no se reconoce devuelve None y el cliente vuelve a preguntar.
    assert interpretar_decision(texto) is None


# --- Depuración (RF-24) ---

def test_datos_depuracion():
    # RF-24: registro de especialistas, trazas, identificador y banderas.
    datos = datos_depuracion(ESTADO, "hilo-1")
    assert datos["thread_id"] == "hilo-1"
    assert datos["log"] == ESTADO["log"]
    assert datos["traza"] == ESTADO["traza"]
    assert datos["hitl_pendiente"] is True and datos["done"] is False


# --- Mismo formato en CLI y Streamlit (RF-26) ---

def test_cli_usa_el_mismo_formato():
    # RF-26: lo que imprime el CLI es exactamente `formatear_turno`, la misma función que usa Streamlit.
    from src.clientes.cli import ejecutar_cli

    estado_grafo = {
        "respuesta": "Respuesta del grafo",
        "log": ["[supervisor] -> horarios"],
        "traza": [{"tool": "hora_actual", "args": {}, "status": "ok", "preview": "Hoy es jueves"}],
        "hitl_pendiente": False,
        "done": False,
    }

    class Grafo:
        llamadas = []

        def procesar_turno(self, estado, mensaje, thread_id):
            self.llamadas.append(thread_id)
            return dict(estado_grafo)

    grafo = Grafo()
    entradas = iter(["hola", "salir"])
    salida = []
    ejecutar_cli([], grafo, lambda prompt="": next(entradas), salida.append, None)

    esperado = formatear_turno(estado_grafo, grafo.llamadas[0])
    assert esperado in "\n".join(salida)
