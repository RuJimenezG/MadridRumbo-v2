"""Alternativa en bici con BiciMAD (spec 009): cliente de la EMT con HTTP propio.

No importa nada de `planificar_ruta.py` (evita la dependencia circular; deuda: dos clientes HTTP y dos haversine).
La `description` del login contiene el usuario y el token: nunca se registra, se devuelve ni entra en un error.
"""
import json
import logging
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request

import config

logger = logging.getLogger(__name__)

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


def _post_json(url, headers=None, body=None, timeout=10):
    """POST con cuerpo JSON que devuelve `(status_http, cuerpo_json)`; el cuerpo es None si un error HTTP no trae JSON.

    Lanza OSError (red, timeout) o ValueError (JSON inválido en una respuesta 200).
    """
    peticion = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers or {}, method="POST")
    peticion.add_header("Content-Type", "application/json")
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
    # "00": token nuevo. "01" («Token extend into control-cache»): la EMT devuelve el token que ya estaba vigente.
    if estado != 200 or not isinstance(cuerpo, dict) or cuerpo.get("code") not in ("00", "01"):
        return None
    datos = cuerpo["data"][0]
    token = datos["accessToken"]
    if not _credencial(token):
        return None
    caducidad = datos.get("tokenSecExpiration")
    if not (_numero(caducidad) and caducidad > 0):
        caducidad = config.EMT_TOKEN_CADUCIDAD_DEFECTO_S
    _token = (token, time.monotonic() + float(caducidad))
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


def tramo_google(modo: str, origen: dict, destino: dict) -> dict:
    """Tramo a pie (`WALK`) o en bici (`BICYCLE`) con Google Routes: una llamada, sin reintentos (RF-8, RF-9, RF-12).

    Devuelve `{"estado": "ok", "duracion_min": int, "aviso": str}` (el aviso de Google si llega y, si no,
    `BICI_AVISO_GOOGLE`) o `{"estado": "no_disponible"}`. Nunca lanza ni incluye detalles del error ni la clave.
    """
    fallo = {"estado": "no_disponible"}
    try:
        clave = config.GOOGLE_ROUTES_API_KEY
        if not _credencial(clave):
            return fallo

        def punto(lugar: dict) -> dict:
            return {"location": {"latLng": {"latitude": lugar["lat"], "longitude": lugar["lon"]}}}

        cuerpo = {"origin": punto(origen), "destination": punto(destino), "travelMode": modo, "languageCode": "es"}
        estado, respuesta = _post_json(
            config.GOOGLE_ROUTES_URL,
            {"X-Goog-Api-Key": clave, "X-Goog-FieldMask": config.GOOGLE_FIELD_MASK_BICI},
            cuerpo, config.GOOGLE_TIMEOUT_S)
        if estado != 200 or not isinstance(respuesta, dict):
            return fallo
        primera = respuesta["routes"][0]
        duracion = primera["duration"]
        if not isinstance(duracion, str) or not re.fullmatch(r"\d+(\.\d+)?s", duracion):
            return fallo
        avisos = primera.get("warnings")
        textos = [a.strip() for a in avisos if isinstance(a, str) and a.strip()] if isinstance(avisos, list) else []
        return {"estado": "ok", "duracion_min": round(float(duracion[:-1]) / 60),
                "aviso": " ".join(textos) or config.BICI_AVISO_GOOGLE}
    except Exception:  # noqa: BLE001 - sin detalles: la excepción puede contener datos sensibles
        return fallo


FRASES_NO_OFRECIDA = {   # RF-4: solo en R3 y R4
    "sin_bicis_origen": "No hay estaciones de BiciMAD con bicis cerca del origen.",
    "sin_huecos_destino": "No hay estaciones de BiciMAD con huecos libres cerca del destino.",
    "misma_estacion": "No hay una alternativa en bici con estaciones de origen y destino distintas.",
}
FRASE_NO_DISPONIBLE = "La alternativa en bici (BiciMAD) no está disponible ahora."   # RF-13, RF-14, RF-15


def _no_disponible() -> tuple[dict, str]:
    return {"estado": "no_disponible", "motivo": FRASE_NO_DISPONIBLE}, FRASE_NO_DISPONIBLE


def _cuantos(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def alternativa_bici(origen: dict, destino: dict, hora_pedida: bool, clima: dict | None) -> tuple[dict, str]:
    """Alternativa en bici con BiciMAD: devuelve `(bici, texto)`, con el campo `bici` y el párrafo del mensaje.

    `clima` es el tiempo ya consultado (`clima_origen`) o None si no se consultó; sin clima apto no se ofrece (R0).
    Orden: R0, R1 y R2 (sin llamadas) → EMT → R3 y R4 (sin Google) → Google (bici, pie, pie), cortando al primer
    fallo y sin alternativa parcial. Nunca lanza: cualquier fallo es `no_disponible` (RF-13 a RF-15).
    `texto` es "" cuando no hay nada que decir (R1 y R2).
    """
    try:
        if rechazo_oferta(origen, destino, hora_pedida) is not None:
            return {"estado": "no_ofrecida", "motivo": None}, ""
        if not (isinstance(clima, dict) and clima.get("estado") == "ok" and clima.get("apto") is True):
            return {"estado": "no_ofrecida", "motivo": None}, ""    # R0: sin buen tiempo o sin dato no hay bici (RF-23, RF-25)
        estaciones = emt_estaciones()
        if estaciones["estado"] != "ok":
            return _no_disponible()
        elegidas = elegir_estaciones(estaciones["estaciones"], origen, destino)
        if elegidas["estado"] != "ok":
            frase = FRASES_NO_OFRECIDA[elegidas["motivo"]]
            return {"estado": "no_ofrecida", "motivo": frase}, frase
        e_o, e_d = elegidas["origen"], elegidas["destino"]
        bici = tramo_google("BICYCLE", e_o, e_d)
        pie_1 = tramo_google("WALK", origen, e_o) if bici["estado"] == "ok" else None
        pie_2 = tramo_google("WALK", e_d, destino) if pie_1 and pie_1["estado"] == "ok" else None
        if not (pie_2 and pie_2["estado"] == "ok"):
            return _no_disponible()
        tramos = [
            {"modo": "A pie", "desde": "Origen", "hasta": e_o["nombre"], "duracion_min": pie_1["duracion_min"]},
            {"modo": "Bici", "desde": e_o["nombre"], "hasta": e_d["nombre"], "duracion_min": bici["duracion_min"]},
            {"modo": "A pie", "desde": e_d["nombre"], "hasta": "Destino", "duracion_min": pie_2["duracion_min"]},
        ]
        total = sum(t["duracion_min"] for t in tramos)
        aviso = " ".join(dict.fromkeys(t["aviso"] for t in (bici, pie_1, pie_2)))
        resultado = {
            "estado": "ok", "motivo": None,
            "origen_estacion": {"nombre": e_o["nombre"], "bicis": e_o["bicis"], "distancia_m": e_o["distancia_m"]},
            "destino_estacion": {"nombre": e_d["nombre"], "huecos": e_d["huecos"], "distancia_m": e_d["distancia_m"]},
            "tramos": tramos, "duracion_min": total, "aviso": aviso,
            "fuentes": {"estaciones": "EMT BiciMAD", "tiempos": "Google Routes"},
        }
        texto = (
            f"Alternativa en bici (BiciMAD): {total} min en total (Google Routes). "
            f"A pie {tramos[0]['duracion_min']} min hasta la estación «{e_o['nombre']}» "
            f"(EMT BiciMAD: {_cuantos(e_o['bicis'], 'bici', 'bicis')} al consultar), "
            f"en bici {tramos[1]['duracion_min']} min hasta la estación «{e_d['nombre']}» "
            f"({_cuantos(e_d['huecos'], 'hueco libre', 'huecos libres')} al consultar) "
            f"y a pie {tramos[2]['duracion_min']} min hasta el destino. "
            f"La disponibilidad puede haber cambiado. Aviso: {aviso}"
        )
        return resultado, texto
    except Exception as e:  # noqa: BLE001 - nunca rompe la ruta; solo el tipo, la excepción puede llevar datos sensibles
        logger.error("Error inesperado en la alternativa en bici: %s", type(e).__name__)
        return _no_disponible()


# --- Clima (Open-Meteo): funciones internas, no una tool (spec 009, RF-20 a RF-26) ---

def apto_exterior(temperatura_c: float, precipitacion_mm: float, codigo: int, viento_kmh: float) -> tuple[bool, list]:
    """`(apto, motivos)` para ir al aire libre (RF-21). Los umbrales están en `config.py` y son inclusivos."""
    motivos = []
    if temperatura_c < config.CLIMA_TEMP_MIN_C:
        motivos.append("temperatura baja")
    elif temperatura_c > config.CLIMA_TEMP_MAX_C:
        motivos.append("temperatura alta")
    if codigo in config.CLIMA_CODIGOS_NO_APTOS:
        motivos.append(config.CLIMA_CODIGOS_NO_APTOS[codigo])
    elif precipitacion_mm > config.CLIMA_PRECIPITACION_MAX_MM:
        motivos.append("precipitación")
    if viento_kmh > config.CLIMA_VIENTO_MAX_KMH:
        motivos.append("viento fuerte")
    return not motivos, motivos


def _numero(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def clima_origen(origen: dict) -> dict:
    """Tiempo actual del origen con Open-Meteo: una llamada, sin clave ni reintentos (RF-20, RF-25, RF-26).

    Devuelve `{"estado": "ok", temperatura_c, precipitacion_mm, codigo, viento_kmh, apto, motivos, fuente, licencia}`
    o `{"estado": "no_disponible"}` si falla algo o falta alguna de las cuatro variables. Nunca lanza.
    """
    fallo = {"estado": "no_disponible"}
    try:
        if not (isinstance(origen, dict) and _numero(origen.get("lat")) and _numero(origen.get("lon"))):
            return fallo
        consulta = urllib.parse.urlencode({
            "latitude": origen["lat"], "longitude": origen["lon"],
            "current": "temperature_2m,precipitation,weather_code,wind_speed_10m"})
        estado, cuerpo = _get_json(f"{config.OPEN_METEO_URL}?{consulta}", timeout=config.OPEN_METEO_TIMEOUT_S)
        if estado != 200 or not isinstance(cuerpo, dict) or not isinstance(cuerpo.get("current"), dict):
            return fallo
        actual = cuerpo["current"]
        temp, lluvia, codigo, viento = (actual.get(k) for k in
                                        ("temperature_2m", "precipitation", "weather_code", "wind_speed_10m"))
        if not (_numero(temp) and _numero(lluvia) and _numero(viento) and isinstance(codigo, int)
                and not isinstance(codigo, bool)):
            return fallo
        apto, motivos = apto_exterior(temp, lluvia, codigo, viento)
        return {"estado": "ok", "temperatura_c": temp, "precipitacion_mm": lluvia, "codigo": codigo,
                "viento_kmh": viento, "apto": apto, "motivos": motivos, "fuente": "Open-Meteo", "licencia": "CC BY 4.0"}
    except Exception as e:  # noqa: BLE001 - sin detalles: solo el tipo de la excepción
        logger.warning("Open-Meteo no disponible: %s", type(e).__name__)
        return fallo


def texto_clima(clima: dict) -> str:
    """Línea del `mensaje` con el tiempo y la atribución a Open-Meteo (RF-24); "" si no hay dato de clima."""
    if clima.get("estado") != "ok":
        return ""
    lluvia = clima["precipitacion_mm"]
    texto = (f"Tiempo en el origen ahora: {round(clima['temperatura_c'])} °C, "
             f"{'sin precipitación' if lluvia <= 0 else f'precipitación {lluvia:g} mm'}, "
             f"viento {round(clima['viento_kmh'])} km/h ")
    if clima["apto"]:
        texto += "(apto para exterior). "
    else:
        texto += f"(no apto para exterior: {', '.join(clima['motivos'])}; la ruta se pidió con menos tramos a pie). "
    return texto + f"{config.CLIMA_ATRIBUCION}."
