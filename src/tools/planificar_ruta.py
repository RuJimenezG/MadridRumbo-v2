"""Tool planificar_ruta (spec 004): ruta en transporte público CRTM con zona y precio del RAG.

De momento solo contiene las funciones puras del ámbito de cobertura, la hora de salida y el título.
"""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import config
from src.reloj import ahora


def dentro_de_ambito(lat: float, lon: float, ambito: tuple | None = None) -> bool:
    """Indica si un punto está dentro de la caja de cobertura (los límites cuentan como dentro)."""
    lat_min, lon_min, lat_max, lon_max = ambito or config.AMBITO_COBERTURA
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def viewbox_nominatim(ambito: tuple | None = None) -> str:
    """Convierte el ámbito (lat_min, lon_min, lat_max, lon_max) al `viewbox` de Nominatim.

    Nominatim espera x1,y1,x2,y2 con la longitud primero: esquina superior izquierda
    (lon_min, lat_max) e inferior derecha (lon_max, lat_min).
    """
    lat_min, lon_min, lat_max, lon_max = ambito or config.AMBITO_COBERTURA
    return f"{lon_min},{lat_max},{lon_max},{lat_min}"


def _parsear_hora(texto) -> datetime | None:
    """Convierte un ISO 8601 con fecha y hora a hora de Madrid, o None si no se puede interpretar."""
    # Se exige hora (HH:MM): una fecha sola o una hora sola no bastan para planificar.
    if not isinstance(texto, str) or not re.search(r"\d{2}:\d{2}", texto):
        return None
    try:
        hora = datetime.fromisoformat(texto.strip())
    except ValueError:
        return None
    zona = ZoneInfo(config.ZONA_HORARIA)
    if hora.tzinfo is not None:
        return hora.astimezone(zona)
    hora = hora.replace(tzinfo=zona)
    # Una hora sin zona que no existe (salto a horario de verano) no cambia al ir a UTC y volver.
    if hora.astimezone(timezone.utc).astimezone(zona).replace(tzinfo=None) != hora.replace(tzinfo=None):
        return None
    return hora


def validar_hora(hora_salida, hora_llegada=None) -> dict:
    """Valida la hora pedida y devuelve `estado`, la hora `considerada` y la hora para Google.

    `estado` es "ok" o el de rechazo: hora_llegada_no_admitida, hora_no_interpretable,
    hora_pasada u hora_demasiado_lejana. Sin hora de salida se considera la actual y
    `salida_rfc3339` es None (Google calcula con salida inmediata).
    """
    actual = ahora()
    resultado = {"estado": "ok", "considerada": actual, "salida_rfc3339": None}

    if hora_llegada and str(hora_llegada).strip():
        return {**resultado, "estado": "hora_llegada_no_admitida"}
    if hora_salida is None or (isinstance(hora_salida, str) and not hora_salida.strip()):
        return resultado

    salida = _parsear_hora(hora_salida)
    if salida is None:
        return {**resultado, "estado": "hora_no_interpretable"}
    # La comparación es a nivel de minuto: pedir "ahora mismo" no cuenta como hora pasada.
    minuto_actual = actual.replace(second=0, microsecond=0)
    if salida < minuto_actual:
        return {**resultado, "estado": "hora_pasada"}
    if salida > minuto_actual + timedelta(days=config.ANTELACION_MAX_DIAS):
        return {**resultado, "estado": "hora_demasiado_lejana"}
    return {
        "estado": "ok",
        "considerada": salida,
        "salida_rfc3339": salida.isoformat(timespec="seconds"),
    }


def resolver_titulo(titulo) -> tuple[str, bool]:
    """Devuelve (título considerado, ¿está en la lista cerrada?).

    Sin título se aplica el predeterminado. Un título de la lista se devuelve con su valor
    canónico; uno que no está se devuelve tal cual lo recibió, marcado como no disponible.
    """
    if titulo is None or not str(titulo).strip():
        return config.TITULO_POR_DEFECTO, True
    recibido = str(titulo).strip()
    # Se ignoran mayúsculas y espacios repetidos al comparar con la lista cerrada.
    normalizado = " ".join(recibido.casefold().split())
    for canonico in config.TITULOS_TRANSPORTE:
        if normalizado == canonico:
            return canonico, True
    return recibido, False


def cabecera(hora: "datetime | str", titulo: str, es_ahora: bool = False) -> str:
    """Primera frase de todo mensaje: hora de salida y título considerados.

    `hora` es un datetime, o el texto recibido si no se pudo interpretar.
    `es_ahora` marca que la persona no pidió hora y se usa la actual.
    """
    if isinstance(hora, str):
        salida = f"«{hora}»"
    elif es_ahora:
        salida = f"ahora ({hora:%d/%m/%Y %H:%M})"
    else:
        salida = f"{hora:%d/%m/%Y %H:%M}"
    return f"Salida: {salida} · Título: {titulo}."
