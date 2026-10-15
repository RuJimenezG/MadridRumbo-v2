"""Persistencia del StateGraph por ``configurable.thread_id``, sin APIs."""
from langgraph.checkpoint.memory import InMemorySaver

from src.graph import crear_grafo, invocar_grafo, recuperar_estado


def _grafo_persistente(checkpointer=None):
    """Crea un grafo determinista cuya síntesis no depende de proveedores."""
    return crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": []},
        modelo_sintetizador=lambda contexto: "Resumen de pruebas.",
        checkpointer=checkpointer,
    )


def test_mismo_thread_id_recupera_historial_y_contexto_entre_turnos():
    """RF-35 y RF-36: el saver retiene la conversación del mismo hilo."""
    grafo = _grafo_persistente()

    invocar_grafo(grafo, {"mensaje": "Primera consulta sobre Metro."}, "hilo-uno")
    invocar_grafo(grafo, {"mensaje": "Segunda consulta del mismo hilo."}, "hilo-uno")
    recuperado = recuperar_estado(grafo, "hilo-uno")

    assert [entrada["content"] for entrada in recuperado["historial"]] == [
        "Primera consulta sobre Metro.",
        "Segunda consulta del mismo hilo.",
    ]
    assert recuperado["mensaje"] == "Segunda consulta del mismo hilo."
    assert recuperado["respuesta"] == "Resumen de pruebas."


def test_thread_nuevo_empieza_vacio_aun_con_estado_de_entrada_minimo():
    """RF-37: un thread desconocido no hereda el checkpoint de otro hilo."""
    grafo = _grafo_persistente()

    assert recuperar_estado(grafo, "hilo-nuevo") == {}

    salida = invocar_grafo(grafo, {"mensaje": "Consulta inicial."}, "hilo-nuevo")

    assert salida["historial"] == [{"role": "user", "content": "Consulta inicial."}]


def test_checkpointer_inyectado_aisla_dos_thread_id():
    """RF-53: dos conversaciones guardadas en el mismo saver no se mezclan."""
    saver = InMemorySaver()
    grafo = _grafo_persistente(checkpointer=saver)

    invocar_grafo(grafo, {"mensaje": "Solo pertenece al hilo A."}, "hilo-a")
    invocar_grafo(grafo, {"mensaje": "Solo pertenece al hilo B."}, "hilo-b")

    estado_a = recuperar_estado(grafo, "hilo-a")
    estado_b = recuperar_estado(grafo, "hilo-b")
    assert [entrada["content"] for entrada in estado_a["historial"]] == ["Solo pertenece al hilo A."]
    assert [entrada["content"] for entrada in estado_b["historial"]] == ["Solo pertenece al hilo B."]
