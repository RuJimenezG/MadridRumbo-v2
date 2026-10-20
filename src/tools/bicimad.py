"""Alternativa en bici con BiciMAD (spec 009): cliente de la EMT con HTTP propio.

No importa nada de `planificar_ruta.py` (evita la dependencia circular; deuda: dos clientes HTTP y dos haversine).
La `description` del login contiene el usuario y el token: nunca se registra, se devuelve ni entra en un error.
"""
import json
import math
import time
import urllib.error
import urllib.request

import config

FALLO = {"estado": "no_disponible", "estaciones": []}

# Token de la EMT reutilizado en memoria: (token, instante monotónico de caducidad) o None.
_token = None


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos coordenadas (haversine)."""
    f1, f2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((f2 - f1) / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def _get_json(url, headers=None, timeout=10):
    """GET que devuelve `(status_http, cuerpo_json)`; el cuerpo es None si un error HTTP no trae JSON.

    Lanza OSError (red, timeout) o ValueError (JSON inválido en una respuesta 200).
    """
    peticion = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, None


def _credencial(valor) -> bool:
    return isinstance(valor, str) and bool(valor.strip())


def _obtener_token():
    """Token vigente (el guardado o uno nuevo por login), o None si no se puede obtener."""
    global _token
    if _token is not None and time.monotonic() < _token[1]:
        return _token[0]
    if not (_credencial(config.EMT_CLIENT_ID) and _credencial(config.EMT_PASS_KEY)):
        return None
    estado, cuerpo = _get_json(config.EMT_LOGIN_URL,
                               {"X-ClientId": config.EMT_CLIENT_ID, "passKey": config.EMT_PASS_KEY},
                               config.EMT_TIMEOUT_S)
    if estado != 200 or not isinstance(cuerpo, dict) or cuerpo.get("code") != "00":
        return None
    datos = cuerpo["data"][0]
    token = datos["accessToken"]
    if not _credencial(token):
        return None
    _token = (token, time.monotonic() + float(datos["tokenSecExpiration"]))
    return token


def _normalizar(e: dict) -> dict:
    lon, lat = e["geometry"]["coordinates"][:2]   # la EMT da [longitud, latitud]
    return {
        "id": e["id"], "nombre": e["name"], "lat": float(lat), "lon": float(lon),
        "bicis": e["dock_bikes"], "huecos": e["free_bases"],
        # Supuesto pendiente de contrastar en T10: activa = activate 1, disponible y no borrada.
        "activa": e["activate"] == 1 and e["no_available"] == 0 and not e.get("virtualDelete", False),
    }


def emt_estaciones() -> dict:
    """Estaciones de BiciMAD: `{"estado": "ok" | "no_disponible", "estaciones": [...]}`. Nunca lanza.

    Como mucho 2 peticiones (login si no hay token vigente y lista), sin reintentos. Un fallo no incluye
    detalles: ni el texto de la excepción ni la respuesta de la EMT.
    """
    global _token
    try:
        token = _obtener_token()
        if token is None:
            return dict(FALLO)
        estado, cuerpo = _get_json(config.EMT_ESTACIONES_URL, {"accessToken": token}, config.EMT_TIMEOUT_S)
        if estado != 200 or not isinstance(cuerpo, dict) or cuerpo.get("code") != "00" \
                or not isinstance(cuerpo.get("data"), list):
            _token = None   # un token rechazado no se reutiliza
            return dict(FALLO)
        estaciones = []
        for e in cuerpo["data"]:
            try:
                estaciones.append(_normalizar(e))
            except (KeyError, IndexError, TypeError, ValueError, AttributeError):
                continue    # una estación mal formada se descarta sin tumbar la lista
        return {"estado": "ok", "estaciones": estaciones}
    except Exception:  # noqa: BLE001 - sin detalles: la excepción puede contener datos sensibles
        return dict(FALLO)


def rechazo_oferta(origen: dict, destino: dict, hora_pedida: bool) -> str | None:
    """Regla de oferta R1 y R2 (RF-2): "R1" si hay hora pedida, "R2" si la distancia está fuera de rango, o None."""
    if hora_pedida:
        return "R1"
    d = distancia_m(origen["lat"], origen["lon"], destino["lat"], destino["lon"])
    if not config.BICI_DISTANCIA_MIN_M <= d <= config.BICI_DISTANCIA_MAX_M:
        return "R2"
    return None


def _mas_cercana(estaciones: list, lugar: dict, campo: str, minimo: int) -> dict | None:
    """Estación activa más cercana a `lugar` con al menos `minimo` en `campo` y dentro del radio (RF-6)."""
    mejor = None
    for e in estaciones:
        if not e["activa"] or e[campo] < minimo:
            continue
        d = distancia_m(lugar["lat"], lugar["lon"], e["lat"], e["lon"])
        if d <= config.BICI_ESTACION_RADIO_MAX_M and (mejor is None or d < mejor[0]):
            mejor = (d, e)
    return None if mejor is None else {**mejor[1], "distancia_m": round(mejor[0])}


def elegir_estaciones(estaciones: list, origen: dict, destino: dict) -> dict:
    """Estación de origen (con bicis) y de destino (con huecos): R3 y R4 (RF-2, RF-6).

    Devuelve `{"estado": "ok", "origen": {...}, "destino": {...}}` o
    `{"estado": "no_ofrecida", "motivo": "sin_bicis_origen" | "sin_huecos_destino" | "misma_estacion"}`.
    """
    e_o = _mas_cercana(estaciones, origen, "bicis", config.BICI_MIN_BICIS)
    if e_o is None:
        return {"estado": "no_ofrecida", "motivo": "sin_bicis_origen"}
    e_d = _mas_cercana(estaciones, destino, "huecos", config.BICI_MIN_HUECOS)
    if e_d is None:
        return {"estado": "no_ofrecida", "motivo": "sin_huecos_destino"}
    if e_o["id"] == e_d["id"]:
        return {"estado": "no_ofrecida", "motivo": "misma_estacion"}
    return {"estado": "ok", "origen": e_o, "destino": e_d}
