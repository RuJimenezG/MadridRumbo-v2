"""Tool auxiliar determinista: fecha y hora actuales en la zona horaria configurada."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def hora_actual(ahora: datetime | None = None) -> str:
    """Devuelve fecha, hora, día de la semana y tipo de día como texto.

    `ahora` solo se usa en tests para fijar el instante; si es None se usa el reloj real.
    Nunca lanza excepciones: ante un fallo devuelve un texto que empieza por "ERROR:".
    """
    try:
        zona = ZoneInfo(config.ZONA_HORARIA)
        if ahora is None:
            ahora = datetime.now(zona)
        elif ahora.tzinfo is None:
            # Sin zona: se interpreta en la zona configurada.
            ahora = ahora.replace(tzinfo=zona)
        else:
            ahora = ahora.astimezone(zona)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return "ERROR: no se pudo obtener la hora (zona horaria no válida)."

    dia = DIAS[ahora.weekday()]
    lugar = config.ZONA_HORARIA.split("/")[-1].replace("_", " ")
    # Solo se distingue laborable / sábado / domingo; los festivos quedan fuera de alcance.
    tipo = "laborable" if ahora.weekday() < 5 else dia
    return (
        f"Hoy es {dia} {ahora:%d/%m/%Y}, son las {ahora:%H:%M} "
        f"({tipo}, hora de {lugar})."
    )
