"""Grafo simulado que cumple el contrato de `contrato.py`.

Sirve para probar los clientes sin API y para el modo simulado (spec 005, RF-28),
mientras no esté el grafo real. No decide nada de verdad: siempre propone un plan,
pausa para HITL y solo cierra la conversación cuando se aprueba.
"""
from src.clientes.contrato import normalizar_estado
from src.supervisor_reglas import elegir_rol_por_palabras

# Tools que "usa" cada rol simulado, para que la traza se parezca a la real.
TOOLS_POR_ROL = {
    "horarios": ["hora_actual", "rag_ask"],
    "tarifas": ["describir_imagen", "calculadora"],
    "rag": ["rag_ask"],
}


def _elegir_rol(mensaje: str) -> str:
    """Reutiliza el fallback real del supervisor y añade un caso para tarifas."""
    if elegir_rol_por_palabras(mensaje) == "horarios":
        return "horarios"
    minusculas = mensaje.lower()
    if "imagen" in minusculas or "billete" in minusculas:
        return "tarifas"
    return "rag"


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
        nuevo = normalizar_estado(estado)
        nuevo.update({
            "respuesta": f"[Simulado] Respuesta a: {mensaje}",
            "plan": [f"Responder a la consulta con el especialista {rol}"],
            "log": [f"[supervisor] -> {rol}", f"[{rol}] nota lista", "[sintetizar] plan listo"],
            "traza": [
                {"tool": tool, "args": {}, "status": "ok", "preview": "(simulado)"}
                for tool in TOOLS_POR_ROL[rol]
            ],
            "hitl_pendiente": True,
            "done": False,
        })
        return nuevo

    def aprobar_plan(self, estado: dict, thread_id: str, aprobado: bool) -> dict:
        self.llamadas.append(("aprobar_plan", thread_id, aprobado))
        if self.fallar:
            raise RuntimeError("fallo simulado del grafo")

        nuevo = normalizar_estado(estado)
        nuevo["hitl_pendiente"] = False
        if aprobado:
            nuevo["respuesta"] = "[Simulado] Plan aprobado y aplicado."
            nuevo["done"] = True
        else:
            nuevo["respuesta"] = "[Simulado] Plan rechazado. Escribe otro mensaje para continuar."
            nuevo["plan"] = []
            nuevo["done"] = False
        return nuevo
