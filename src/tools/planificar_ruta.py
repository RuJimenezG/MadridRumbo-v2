"""Tool planificar_ruta (spec 004): ruta en transporte público CRTM con zona y precio del RAG.

De momento solo contiene las funciones puras del ámbito de cobertura, la hora de salida, el título y el cliente Nominatim.
"""
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
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


# Instante (time.monotonic) de la última petición a Nominatim, para respetar su límite de 1 petición/s.
_ultima_peticion_nominatim = None


def _http_json(url: str, *, headers: dict | None = None, body: dict | None = None, timeout: float = 10):
    """Hace una petición HTTP (GET, o POST con cuerpo JSON) y devuelve el JSON de la respuesta.

    Es el único punto que sale a la red: los tests lo sustituyen. Lanza la excepción de
    urllib ante cualquier error (conexión, timeout, error HTTP, JSON inválido).
    """
    datos = json.dumps(body).encode("utf-8") if body is not None else None
    peticion = urllib.request.Request(url, data=datos, headers=headers or {})
    if datos is not None:
        peticion.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        return json.loads(respuesta.read().decode("utf-8"))


def geocodificar(direccion: str) -> dict:
    """Busca una dirección en Nominatim y devuelve `{"estado", "candidatos"}`.

    `estado` es "ok" (aunque no haya candidatos) o "geocodificacion_fallida" si Nominatim
    falla por error, timeout, error HTTP, límite de peticiones o respuesta inválida (RF-40).
    No lanza esas excepciones: la orquestación decide qué hacer con el fallo.
    """
    global _ultima_peticion_nominatim
    # Política de uso de Nominatim: se espera lo que falte hasta cumplir el intervalo mínimo.
    if _ultima_peticion_nominatim is not None:
        falta = config.NOMINATIM_INTERVALO_S - (time.monotonic() - _ultima_peticion_nominatim)
        if falta > 0:
            time.sleep(falta)

    parametros = {
        "q": direccion,
        "format": "jsonv2",
        "countrycodes": config.NOMINATIM_PAIS,
        "viewbox": viewbox_nominatim(),
        "bounded": 1,
        "addressdetails": 1,
        "limit": config.NOMINATIM_LIMIT,
        "accept-language": "es",
    }
    try:
        respuesta = _http_json(
            f"{config.NOMINATIM_URL}?{urlencode(parametros)}",
            headers={"User-Agent": config.NOMINATIM_USER_AGENT},
            timeout=config.NOMINATIM_TIMEOUT_S,
        )
    except (OSError, ValueError):  # URLError, HTTPError y timeout son OSError; JSON inválido, ValueError
        respuesta = None
    _ultima_peticion_nominatim = time.monotonic()

    # Ante un error Nominatim a veces responde un dict en lugar de una lista de resultados.
    if not isinstance(respuesta, list):
        return {"estado": "geocodificacion_fallida", "candidatos": []}
    candidatos = []
    for r in respuesta:
        try:
            lugar = r.get("address", {})
            candidatos.append({
                "direccion": r["display_name"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "municipio": next((lugar[k] for k in ("city", "town", "village", "municipality") if k in lugar), None),
            })
        except (KeyError, TypeError, ValueError, AttributeError):
            continue  # un resultado mal formado se descarta sin tumbar la consulta
    return {"estado": "ok", "candidatos": candidatos}
