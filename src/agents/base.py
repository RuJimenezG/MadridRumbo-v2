"""Mini-bucle común y ejecutor compartido de los especialistas.

El modelo propone una tool, pero Python aplica la allowlist y el límite local.
El ejecutor transversal se inyecta desde el grafo para que todos los nodos usen
la misma vía de auditoría; los límites globales se aplicarán sobre esa vía.
"""
from __future__ import annotations

from typing import Any, Callable

import config


EjecutorTool = Callable[[str, dict[str, Any], list[dict[str, Any]]], str]


def crear_ejecutor_transversal(ejecutar: EjecutorTool) -> EjecutorTool:
    """Envuelve un ejecutor inyectado sin alterar la traza ni el límite local."""
    def ejecutar_compartido(nombre: str, args: dict[str, Any], traza: list[dict[str, Any]]) -> str:
        argumentos = dict(args) if isinstance(args, dict) else {}
        return ejecutar(nombre, argumentos, traza)

    return ejecutar_compartido


def crear_ejecutor_acotado(ejecutar: EjecutorTool, tools_usadas: object = 0) -> EjecutorTool:
    """Aplica el presupuesto global a una secuencia de llamadas de un especialista."""
    usadas = tools_usadas if isinstance(tools_usadas, int) and tools_usadas >= 0 else 0

    def ejecutar_acotado(nombre: str, args: dict[str, Any], traza: list[dict[str, Any]]) -> str:
        nonlocal usadas
        if usadas >= config.MAX_CICLOS_TOOLS:
            return "ERROR: se alcanzó el máximo de tools permitido para este turno."
        usadas += 1
        argumentos = dict(args) if isinstance(args, dict) else {}
        return ejecutar(nombre, argumentos, traza)

    return ejecutar_acotado


def ejecutar_especialista(
    nombre: str,
    prompt: str,
    estado: dict[str, Any],
    llm: Callable[[list[dict[str, str]]], Any],
    ejecutar: EjecutorTool,
) -> dict[str, Any]:
    """Ejecuta un especialista y devuelve notas y traza conservando su máximo local."""
    notas = list(estado.get("notas", []))
    traza = list(estado.get("traza", []))
    permitidas = config.TOOLS_POR_ESPECIALISTA[nombre]
    mensajes = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": estado["mensaje"]},
    ]
    obtenido = []

    def terminar(texto: str) -> dict[str, Any]:
        return {"notas": notas + [f"[{nombre}] {texto}"], "traza": traza}

    for _ in range(config.MAX_STEPS_ESPECIALISTA):
        try:
            respuesta = llm(mensajes)
        except Exception as exc:
            return terminar(f"ERROR: el modelo no respondió ({exc}).")

        if not isinstance(respuesta, dict):
            return terminar("ERROR: respuesta del modelo no interpretable.")
        if isinstance(respuesta.get("final"), str):
            return terminar(respuesta["final"])
        tool = respuesta.get("tool")
        if not isinstance(tool, str):
            return terminar("ERROR: respuesta del modelo no interpretable.")

        args = respuesta.get("args") if isinstance(respuesta.get("args"), dict) else {}
        if tool not in permitidas:
            aviso = f"ERROR: tool no permitida: {tool}"
            traza.append({"tool": tool, "args": args, "status": "bloqueada", "preview": aviso})
            mensajes.append({"role": "tool", "content": aviso})
            continue

        resultado = ejecutar(tool, args, traza)
        obtenido.append(f"{tool}: {resultado}")
        mensajes.append({"role": "tool", "content": f"{tool}: {resultado}"})

    detalle = " | ".join(obtenido) if obtenido else "sin datos"
    return terminar(f"Se alcanzó el límite de pasos. Datos obtenidos: {detalle}")
