"""Mini-bucle común y ejecutor compartido de los especialistas.

El modelo propone una tool, pero Python aplica la allowlist y el límite local.
El ejecutor transversal se inyecta desde el grafo para que todos los nodos usen
la misma vía de auditoría; los límites globales se aplicarán sobre esa vía.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator

import config
from src.depuracion import SesionDepuracion


EjecutorTool = Callable[[str, dict[str, Any], list[dict[str, Any]]], str]


# La sesión pertenece a una sola llamada pública; ContextVar evita incluirla en
# EstadoGrafo o en el checkpoint y también aísla ejecuciones anidadas.
_SESION_DEPURACION: ContextVar[SesionDepuracion | None] = ContextVar(
    "sesion_depuracion",
    default=None,
)


@contextmanager
def sesion_depuracion_activa(sesion: SesionDepuracion) -> Iterator[None]:
    """Activa una sesión efímera mientras se ejecuta un recorrido del grafo."""
    token = _SESION_DEPURACION.set(sesion)
    try:
        yield
    finally:
        _SESION_DEPURACION.reset(token)


def _registrar_tool(
    nombre: str,
    argumentos: dict[str, Any],
    salida: Any,
    *,
    fallida: bool,
) -> None:
    """Registra una tool solo si la llamada pública activó la sesión temporal."""
    sesion = _SESION_DEPURACION.get()
    if sesion is None:
        return
    if fallida:
        sesion.registrar(
            "tool",
            nombre,
            argumentos,
            None,
            resultado="fallido",
            detalle={
                "categoria": "tool",
                "resumen": "La herramienta no pudo completarse.",
            },
        )
        return
    sesion.registrar("tool", nombre, argumentos, salida)


def _resultado_fallido(resultado: Any, traza: list[dict[str, Any]], desde: int) -> bool:
    """Detecta el convenio existente de error sin transformar la traza original."""
    if isinstance(resultado, str) and resultado.startswith("ERROR"):
        return True
    return any(
        isinstance(entrada, dict) and entrada.get("status") in {"error", "bloqueada"}
        for entrada in traza[desde:]
    )


def crear_ejecutor_transversal(ejecutar: EjecutorTool) -> EjecutorTool:
    """Envuelve un ejecutor inyectado sin alterar la traza ni el límite local."""
    def ejecutar_compartido(nombre: str, args: dict[str, Any], traza: list[dict[str, Any]]) -> str:
        argumentos = dict(args) if isinstance(args, dict) else {}
        inicio_traza = len(traza)
        try:
            resultado = ejecutar(nombre, argumentos, traza)
        except Exception:
            _registrar_tool(nombre, argumentos, None, fallida=True)
            raise

        _registrar_tool(
            nombre,
            argumentos,
            resultado,
            fallida=_resultado_fallido(resultado, traza, inicio_traza),
        )
        return resultado

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
