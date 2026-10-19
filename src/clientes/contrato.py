"""Contrato entre los clientes (CLI y Streamlit) y el grafo multiagente.

El grafo devuelve un diccionario de estado. Los clientes solo leen estas claves; las
que falten se rellenan con su valor por defecto y las desconocidas se conservan.
Es una propuesta basada en el enunciado: se ajustará cuando exista el grafo real.

Claves del estado:
- respuesta:       texto para la persona usuaria.
- plan:            viñetas del plan pendiente de aprobar.
- log:             qué especialistas actuaron (p. ej. "[supervisor] -> horarios").
- traza:           entradas {"tool", "args", "status", "preview"} de las tools ejecutadas.
- hitl_pendiente:  hay un plan esperando aprobar o rechazar.
- done:            la conversación ha terminado. Solo lo decide el grafo.
"""


def estado_vacio() -> dict:
    """Estado inicial de una conversación, sin respuesta ni trazas."""
    return {
        "respuesta": "",
        "plan": [],
        "log": [],
        "traza": [],
        "hitl_pendiente": False,
        "done": False,
    }


def normalizar_estado(estado: dict | None) -> dict:
    """Devuelve una copia del estado con todas las claves del contrato presentes."""
    resultado = dict(estado) if estado else {}
    for clave, defecto in estado_vacio().items():
        if resultado.get(clave) is None:
            resultado[clave] = defecto
    return resultado
