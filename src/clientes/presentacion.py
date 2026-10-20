"""Funciones puras que comparten el CLI y Streamlit para mostrar y entender lo que ocurre.

Aquí no hay lógica del grafo: solo se da formato a lo que devuelve y se interpretan
las entradas de la persona usuaria.
"""
import config
from src.clientes.contrato import normalizar_estado
from src.clientes.planes import es_entrada_tecnica_supervisor, resumir_plan

# Longitud máxima del extracto de cada tool al mostrar la traza.
PREVIEW_MAX = 80


def _si_no(valor: bool) -> str:
    return "sí" if valor else "no"


def _log_visible(log: list, ocultar_tecnicas: bool) -> list:
    """El log del grafo; la web quita los diagnósticos técnicos del supervisor (RF-35)."""
    if not ocultar_tecnicas:
        return list(log)
    return [entrada for entrada in log if not es_entrada_tecnica_supervisor(entrada)]


def formatear_turno(estado: dict, thread_id: str, ocultar_tecnicas: bool = False) -> str:
    """Texto de un turno: respuesta, planes, especialistas, tools y banderas.

    `ocultar_tecnicas` quita del registro los diagnósticos del supervisor: el CLI los muestra
    (los consulta el cliente técnico) y la web no.
    """
    estado = normalizar_estado(estado)
    lineas = [estado["respuesta"]]

    planes = estado["plan"] if isinstance(estado["plan"], list) else []
    if planes:
        lineas += ["", "Plan propuesto:" if len(planes) == 1 else "Planes propuestos:"]
        for numero, plan in enumerate(planes):
            if numero:
                lineas.append("")
            lineas += resumir_plan(plan).split("\n")
    log = _log_visible(estado["log"], ocultar_tecnicas)
    if log:
        lineas += ["", "Especialistas:"] + [f"  {entrada}" for entrada in log]
    if estado["traza"]:
        lineas += ["", "Tools:"]
        for paso in estado["traza"]:
            extracto = str(paso.get("preview", ""))[:PREVIEW_MAX]
            lineas.append(f"  - {paso.get('tool', '?')} [{paso.get('status', '?')}] {extracto}".rstrip())

    lineas += [
        "",
        f"Conversación: {thread_id}",
        f"Plan pendiente: {_si_no(estado['hitl_pendiente'])}",
        f"Terminada: {_si_no(estado['done'])}",
    ]
    return "\n".join(lineas)


def datos_depuracion(estado: dict, thread_id: str, ocultar_tecnicas: bool = False) -> dict:
    """Datos del panel de depuración: especialistas, tools, conversación y banderas."""
    estado = normalizar_estado(estado)
    return {
        "thread_id": thread_id,
        "log": _log_visible(estado["log"], ocultar_tecnicas),
        "traza": estado["traza"],
        "hitl_pendiente": estado["hitl_pendiente"],
        "done": estado["done"],
    }


def es_mensaje_vacio(texto: str | None) -> bool:
    """True si el mensaje está vacío o solo tiene espacios."""
    return not texto or not texto.strip()


def es_salida(texto: str) -> bool:
    """True si la persona quiere terminar el chat."""
    return texto.strip().lower() in config.PALABRAS_SALIR


def interpretar_decision(texto: str) -> bool | None:
    """True si aprueba, False si rechaza y None si no se entiende (hay que volver a preguntar)."""
    limpio = texto.strip().lower()
    if limpio in config.PALABRAS_APROBAR:
        return True
    if limpio in config.PALABRAS_RECHAZAR:
        return False
    return None
