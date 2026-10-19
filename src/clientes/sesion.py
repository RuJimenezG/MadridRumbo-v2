"""Sesión de chat compartida por el CLI y Streamlit.

Guarda el identificador de la conversación, el último estado del grafo y el historial,
y traslada al grafo lo que decide la persona. No decide nada por su cuenta: `done` y
`hitl_pendiente` se copian tal cual de lo que devuelve el grafo (spec 008, RF-27).
"""
import uuid

from src.clientes.contrato import estado_vacio, normalizar_estado
from src.clientes.planes import ids_de_planes

# Mensaje que ve la persona si el grafo falla; no incluye detalles internos.
MENSAJE_ERROR = "No se pudo completar la acción: el grafo ha fallado. Inténtalo de nuevo."


class SesionChat:
    """Una conversación con el grafo, con su `thread_id`, su estado y su historial."""

    def __init__(self, agente):
        # `agente` es el grafo (real o simulado): debe tener procesar_turno y aprobar_plan.
        self.agente = agente
        self.error: str | None = None
        self._reiniciar()

    def _reiniciar(self) -> None:
        self.thread_id = str(uuid.uuid4())
        self.estado = estado_vacio()
        self.historial: list[dict] = []
        self.error = None

    @property
    def planes(self) -> list:
        """Planes pendientes de decisión, tal como los devolvió el grafo."""
        planes = self.estado["plan"]
        return list(planes) if isinstance(planes, list) else []

    @property
    def puede_decidir(self) -> bool:
        """Aprobar y rechazar solo tienen sentido con un plan pendiente."""
        return bool(self.estado["hitl_pendiente"])

    @property
    def puede_escribir(self) -> bool:
        """Con un plan pendiente hay que decidir antes de escribir otro mensaje."""
        return not self.puede_decidir

    def _registrar_error(self) -> None:
        self.error = MENSAJE_ERROR
        self.historial.append({"rol": "error", "texto": MENSAJE_ERROR})

    def _aplicar(self, nuevo_estado: dict) -> None:
        """Guarda el estado del grafo y añade su respuesta al historial."""
        self.estado = normalizar_estado(nuevo_estado)
        self.error = None
        if self.estado["respuesta"]:
            self.historial.append({"rol": "asistente", "texto": self.estado["respuesta"]})

    def enviar(self, mensaje: str) -> None:
        """Envía un mensaje al grafo. Se ignora si hay un plan pendiente de decisión."""
        if not self.puede_escribir:
            return
        self.historial.append({"rol": "usuario", "texto": mensaje})
        try:
            self._aplicar(self.agente.procesar_turno(self.estado, mensaje, self.thread_id))
        except Exception:  # un fallo del grafo no debe cortar la conversación
            self._registrar_error()

    def decidir(self, aprobado: bool, plan_id: str | None = None) -> None:
        """Traslada al grafo la aprobación o el rechazo del plan.

        Se ignora, sin llamar al grafo, si no hay plan pendiente, si hay varios planes y no se
        indica cuál, o si el identificador no corresponde a ninguno: el grafo respondería con
        un aviso que deja `hitl_pendiente` en falso aunque siga habiendo un plan.
        """
        if not self.puede_decidir:
            return
        ids = ids_de_planes(self.planes)
        if plan_id is None and len(ids) > 1:
            return
        if plan_id is not None and plan_id not in ids:
            return

        # Copia: el identificador elegido solo viaja en esta llamada, no se guarda en la sesión.
        enviado = dict(self.estado)
        if plan_id is not None:
            enviado["plan_id_seleccionado"] = plan_id
        try:
            self._aplicar(self.agente.aprobar_plan(enviado, self.thread_id, aprobado))
        except Exception:
            self._registrar_error()

    def nueva_conversacion(self) -> None:
        """Empieza de cero: nuevo identificador, historial y estado vacíos."""
        self._reiniciar()
