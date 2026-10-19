"""Cliente de terminal del grafo multiagente (spec 008).

Capa fina: muestra lo que devuelve el grafo y traslada lo que escribe la persona.
La entrada (`leer`) y la salida (`escribir`) se inyectan para poder probarlo sin terminal.
"""
import argparse

import config
from src.clientes.planes import ids_de_planes
from src.clientes.presentacion import (
    es_mensaje_vacio,
    es_salida,
    formatear_turno,
    interpretar_decision,
)
from src.clientes.sesion import SesionChat

PROMPT = "Tú> "
PROMPT_DECISION = "¿Apruebas el plan? [s/n]> "
PROMPT_PLAN = "¿Qué plan quieres decidir? [1-{n}]> "
DECISION_NO_VALIDA = "Respuesta no válida: escribe s para aprobar o n para rechazar."
PLAN_NO_VALIDO = "Plan no válido: escribe un número entre 1 y {n}."
BIENVENIDA = "MadridRumbo: escribe tu consulta sobre transporte en Madrid ('salir' para terminar)."


def _mostrar_turno(sesion: SesionChat, escribir) -> None:
    """Imprime el resultado del último turno, o el aviso de error si el grafo falló."""
    if sesion.error:
        escribir(sesion.error)
    else:
        escribir(formatear_turno(sesion.estado, sesion.thread_id))


def _pedir_plan(sesion: SesionChat, leer, escribir) -> tuple[bool, str | None]:
    """Con varios planes pendientes, pregunta cuál se decide (por su número o su identificador).

    Devuelve `(seguir, plan_id)`: `plan_id` es None si solo hay un plan y no hace falta elegir, y
    `seguir` es False si la persona termina el chat sin elegir.
    """
    ids = ids_de_planes(sesion.planes)
    if len(ids) <= 1:
        return True, None
    while True:
        try:
            texto = leer(PROMPT_PLAN.format(n=len(ids)))
        except (EOFError, KeyboardInterrupt):
            escribir("")
            return False, None
        if es_salida(texto):
            return False, None
        elegido = texto.strip()
        if elegido.isdigit() and 1 <= int(elegido) <= len(ids):
            return True, ids[int(elegido) - 1]
        if elegido in ids:
            return True, elegido
        escribir(PLAN_NO_VALIDO.format(n=len(ids)))


def _pedir_aprobacion(leer, escribir) -> bool | None:
    """Pregunta s/n hasta recibir una respuesta válida; None si la persona termina sin decidir."""
    while True:
        try:
            texto = leer(PROMPT_DECISION)
        except (EOFError, KeyboardInterrupt):
            escribir("")
            return None
        if es_salida(texto):
            return None
        decision = interpretar_decision(texto)
        if decision is not None:
            return decision
        escribir(DECISION_NO_VALIDA)


def _pedir_decision(sesion: SesionChat, leer, escribir) -> bool:
    """Mientras haya planes pendientes, pide elegir plan (si hay varios) y aprobarlo o rechazarlo.

    Tras rechazar, el grafo puede dejar otros planes pendientes: se vuelve a preguntar por ellos.
    Devuelve False si la persona termina el chat sin decidir; en ese caso no se cierra nada.
    """
    while sesion.puede_decidir:
        seguir, plan_id = _pedir_plan(sesion, leer, escribir)
        if not seguir:
            return False
        decision = _pedir_aprobacion(leer, escribir)
        if decision is None:
            return False
        sesion.decidir(decision, plan_id)
        _mostrar_turno(sesion, escribir)
    return True


def _chat(sesion: SesionChat, leer, escribir) -> int:
    """Bucle del chat interactivo. Termina con `salir`, Ctrl+D o Ctrl+C."""
    while True:
        try:
            texto = leer(PROMPT)
        except (EOFError, KeyboardInterrupt):
            escribir("")
            return 0
        if es_salida(texto):
            return 0
        if es_mensaje_vacio(texto):
            continue
        sesion.enviar(texto.strip())
        _mostrar_turno(sesion, escribir)
        # Con un plan pendiente hay que decidir antes de seguir (HITL): solo decide la persona.
        if not _pedir_decision(sesion, leer, escribir):
            return 0


def _crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Asistente de transporte público de Madrid. Sin opciones abre el chat interactivo.",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="Muestra esta ayuda y termina.")
    parser.add_argument("--demo", action="store_true", help="Lanza tres pedidos de ejemplo.")
    parser.add_argument(
        "--auto-aprobar",
        action="store_true",
        help="Con --demo, aprueba los planes automáticamente en lugar de preguntar.",
    )
    return parser


def _demo(agente, auto_aprobar: bool, leer, escribir) -> int:
    """Lanza los pedidos de `PEDIDOS_DEMO`, cada uno en su propia conversación."""
    total = len(config.PEDIDOS_DEMO)
    for numero, pedido in enumerate(config.PEDIDOS_DEMO, start=1):
        escribir("")
        escribir(f"=== Pedido {numero}/{total}: {pedido} ===")
        sesion = SesionChat(agente)
        sesion.enviar(pedido)
        _mostrar_turno(sesion, escribir)
        if auto_aprobar:
            if sesion.puede_decidir:
                escribir("Plan aprobado automáticamente (--auto-aprobar).")
                # Con varios planes se aprueba el primero: no hay nadie que elija.
                ids = ids_de_planes(sesion.planes)
                sesion.decidir(True, ids[0] if len(ids) > 1 else None)
                _mostrar_turno(sesion, escribir)
        elif not _pedir_decision(sesion, leer, escribir):
            return 0  # la persona se fue sin decidir: no se sigue ni se cierra nada
    return 0


def ejecutar_cli(argumentos: list[str], agente, leer, escribir, aviso: str | None = None) -> int:
    """Ejecuta el CLI y devuelve el código de salida (0 si todo fue bien)."""
    try:
        opciones = _crear_parser().parse_args(argumentos)
    except SystemExit as salida:  # argparse termina así con --help o con opciones desconocidas
        return salida.code if isinstance(salida.code, int) else 0

    if opciones.auto_aprobar and not opciones.demo:
        escribir("Error: --auto-aprobar solo se puede usar junto con --demo.")
        return 2

    if aviso:
        escribir(aviso)
    if opciones.demo:
        return _demo(agente, opciones.auto_aprobar, leer, escribir)
    escribir(BIENVENIDA)
    return _chat(SesionChat(agente), leer, escribir)
