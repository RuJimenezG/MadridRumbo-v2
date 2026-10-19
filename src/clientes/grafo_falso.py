"""Grafo simulado que cumple el contrato de `contrato.py` y se parece al grafo real.

Sirve para probar los clientes sin API y para el modo simulado (spec 008, RF-28 y RF-36),
cuando no se quiere usar el grafo real. Como el real, solo las rutas pausan para HITL
(con uno o varios planes `{id, resultado}`), horarios y RAG cierran directamente, y las
respuestas solo llevan las seis claves públicas. Sus textos son fijos y llevan `[Simulado]`.
"""
from typing import Any

from src.clientes.planes import ids_de_planes
from src.supervisor_reglas import elegir_rol_por_palabras

# Tools que "usa" cada rol simulado, para que la traza se parezca a la real.
TOOLS_POR_ROL = {
    "horarios": ["hora_actual", "rag_ask"],
    "rutas": ["planificar_ruta"],
    "rag": ["rag_ask"],
}

AVISO_SIN_PLAN = "No existe un plan pendiente en esta conversación."
AVISO_PLAN_A_ELEGIR = "Indica el identificador del plan pendiente que quieres aprobar."


def _es_ruta(mensaje: str) -> bool:
    minusculas = mensaje.lower()
    return (
        "ruta" in minusculas
        or "llegar" in minusculas
        or ("desde" in minusculas and "hasta" in minusculas)
    )


def _pide_varias_rutas(mensaje: str) -> bool:
    minusculas = mensaje.lower()
    return "alternativ" in minusculas or "dos rutas" in minusculas


def _elegir_rol(mensaje: str) -> str:
    """Reutiliza el fallback real del supervisor para horarios y añade el caso de las rutas."""
    if _es_ruta(mensaje):
        return "rutas"
    if elegir_rol_por_palabras(mensaje) == "horarios":
        return "horarios"
    return "rag"


def _plan_de_ruta(numero: int) -> dict[str, Any]:
    """Un plan con la forma que devuelve el grafo real para una ruta."""
    return {
        "id": f"ruta-{numero}",
        "resultado": {
            "estado": "ok",
            "mensaje": "Ruta calculada (simulada).",
            "hora_salida": None,
            "titulo": "billete sencillo",
            "origen": {"direccion": "Puerta del Sol, Madrid"},
            "destino": {"direccion": "Estación de Atocha, Madrid"},
            "ruta": {
                "duracion_min": 12 + 3 * (numero - 1),
                "tramos": [
                    {"modo": "A pie", "linea": None, "desde": None, "hasta": None, "duracion_min": 3},
                    {"modo": "SUBWAY", "linea": "1", "desde": "Sol", "hasta": "Atocha", "duracion_min": 9 + 3 * (numero - 1)},
                ],
                "fuente": "Simulado",
            },
            "zona": {"estado": "ok", "texto": "Zona A (simulada).", "fuente": "RAG"},
            "precio": {"estado": "ok", "texto": "El billete sencillo cuesta 1,50 € (simulado).", "fuente": "RAG"},
        },
    }


def _resultado(respuesta, plan=(), log=(), traza=(), hitl_pendiente=False, done=False) -> dict[str, Any]:
    """Solo las seis claves públicas, como el grafo real."""
    return {
        "respuesta": respuesta,
        "plan": list(plan),
        "log": list(log),
        "traza": list(traza),
        "hitl_pendiente": hitl_pendiente,
        "done": done,
    }


def _aviso(mensaje: str) -> dict[str, Any]:
    """Aviso controlado: como el real, deja `hitl_pendiente` en falso aunque quede un plan."""
    return _resultado(mensaje, log=[mensaje])


class GrafoFalso:
    """Grafo simulado con la misma interfaz que el real: `procesar_turno` y `aprobar_plan`."""

    def __init__(self, fallar: bool = False):
        self.fallar = fallar
        # Cada llamada se guarda como (nombre, thread_id, dato) para comprobarlas en los tests.
        self.llamadas: list[tuple] = []

    def procesar_turno(self, estado: dict, mensaje: str, thread_id: str) -> dict:
        self.llamadas.append(("procesar_turno", thread_id, mensaje))
        if self.fallar:
            raise RuntimeError("fallo simulado del grafo")

        rol = _elegir_rol(mensaje)
        traza = [
            {"tool": tool, "args": {}, "status": "ok", "preview": "(simulado)"}
            for tool in TOOLS_POR_ROL[rol]
        ]
        log = [f"[supervisor] -> {rol}", f"[{rol}] nota lista", "[sintetizador] respuesta lista"]
        respuesta = f"[Simulado] Respuesta a: {mensaje}"

        if rol != "rutas":
            return _resultado(respuesta, log=log, traza=traza, done=True)
        cantidad = 2 if _pide_varias_rutas(mensaje) else 1
        planes = [_plan_de_ruta(numero) for numero in range(1, cantidad + 1)]
        return _resultado(respuesta, plan=planes, log=log, traza=traza, hitl_pendiente=True)

    def aprobar_plan(self, estado: dict, thread_id: str, aprobado: bool) -> dict:
        self.llamadas.append(("aprobar_plan", thread_id, aprobado))
        if self.fallar:
            raise RuntimeError("fallo simulado del grafo")

        planes = estado.get("plan") if isinstance(estado.get("plan"), list) else []
        ids = ids_de_planes(planes)
        if not ids:
            return _aviso(AVISO_SIN_PLAN)

        elegido = estado.get("plan_id_seleccionado")
        if elegido is None and len(ids) == 1:
            elegido = ids[0]
        if elegido not in ids:
            return _aviso(AVISO_PLAN_A_ELEGIR)

        if aprobado:
            return _resultado(
                f"[Simulado] Plan aprobado y aplicado ({elegido}).",
                log=[f"Plan {elegido} aprobado"],
                done=True,
            )
        restantes = [plan for plan in planes if plan.get("id") != elegido]
        return _resultado(
            f"[Simulado] Plan rechazado ({elegido}). Escribe otro mensaje para continuar.",
            plan=restantes,
            log=[f"Plan {elegido} rechazado"],
            hitl_pendiente=bool(restantes),
        )
