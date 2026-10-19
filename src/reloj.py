"""Fuente única de la hora actual para planificar_ruta y el prompt del especialista de rutas.

Para sustituirla (otra fuente o un reloj fijo) basta con cambiar el cuerpo de `ahora()`.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import config


def ahora() -> datetime:
    """Devuelve el instante actual en la zona horaria configurada."""
    return datetime.now(ZoneInfo(config.ZONA_HORARIA))
