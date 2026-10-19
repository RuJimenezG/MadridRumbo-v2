"""Cliente de terminal del grafo multiagente (spec 005).

Capa fina: muestra lo que devuelve el grafo y traslada lo que escribe la persona.
La entrada (`leer`) y la salida (`escribir`) se inyectan para poder probarlo sin terminal.
"""
import argparse

import config
from src.clientes.presentacion import (
    es_mensaje_vacio,
    es_salida,
    formatear_turno,
    interpretar_decision,
)
from src.clientes.sesion import SesionChat

PROMPT = "Tú> "
PROMPT_DECISION = "¿Apruebas el plan? [s/n]> "
DECISION_NO_VALIDA = "Respuesta no válida: escribe s para aprobar o n para rechazar."
BIENVENIDA = "MadridRumbo: escribe tu consulta sobre transporte en Madrid ('salir' para terminar)."


def _mostrar_turno(sesion: SesionChat, escribir) -> None:
    """Imprime el resultado del último turno, o el aviso de error si el grafo falló."""
    if sesion.error:
        escribir(sesion.error)
    else:
        escribir(formatear_turno(sesion.estado, sesion.thread_id))


def _pedir_decision(sesion: SesionChat, leer, escribir) -> bool:
    """Pregunta si se aprueba el plan hasta recibir una decisión válida.

    Devuelve False si la persona termina el chat sin decidir; en ese caso no se cierra nada.
    """
    while sesion.puede_decidir:
        try:
            texto = leer(PROMPT_DECISION)
        except (EOFError, KeyboardInterrupt):
            escribir("")
            return False
        if es_salida(texto):
            return False
        decision = interpretar_decision(texto)
        if decision is None:
            escribir(DECISION_NO_VALIDA)
            continue
        sesion.decidir(decision)
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
                sesion.decidir(True)
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
