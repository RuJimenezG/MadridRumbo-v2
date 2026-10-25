"""Allowlist de tools y ejecución controlada con traza.

El LLM solo propone un nombre y unos argumentos; aquí se decide si se ejecuta.
Para añadir una tool nueva basta con registrarla en TOOLS_PERMITIDAS.
"""
from src.tools.calculadora import calculadora
from src.tools.describir_imagen import describir_imagen
from src.tools.hora_actual import hora_actual
from src.tools.planificar_ruta import planificar_ruta_texto



def rag_ask(consulta: str) -> str:
    """Tool RAG: delega en rag.responder.rag_ask.

    
    """
    from rag.responder import rag_ask as _rag_ask

    return _rag_ask(consulta)


# Tools que el código permite ejecutar. Cualquier otro nombre se bloquea.
TOOLS_PERMITIDAS = {
    "hora_actual": hora_actual,
    "rag_ask": rag_ask,
    "describir_imagen": describir_imagen,
    "calculadora": calculadora,
    "planificar_ruta": planificar_ruta_texto,
}

# Longitud máxima del extracto del resultado que se guarda en la traza.
PREVIEW_MAX = 120


def ejecutar_tool(nombre: str, args: dict, traza: list) -> str:
    """Ejecuta una tool de la allowlist y añade una entrada a `traza`.

    Devuelve siempre un texto; si la tool no está permitida o falla,
    el texto empieza por "ERROR" y no se lanza ninguna excepción.
    """
    args = args or {}
    if nombre not in TOOLS_PERMITIDAS:
        resultado = f"ERROR: tool no permitida: {nombre}"
        status = "bloqueada"
    else:
        try:
            resultado = str(TOOLS_PERMITIDAS[nombre](**args))
            status = "error" if resultado.startswith("ERROR") else "ok"
        except Exception as exc:  # una tool rota no debe tumbar el grafo
            resultado = f"ERROR: la tool {nombre} falló ({exc})"
            status = "error"

    traza.append(
        {"tool": nombre, "args": args, "status": status, "preview": resultado[:PREVIEW_MAX]}
    )
    return resultado
