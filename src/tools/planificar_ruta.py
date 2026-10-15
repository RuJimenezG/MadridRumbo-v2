"""Tool planificar_ruta (spec 004): ruta en transporte público CRTM con zona y precio del RAG.

Contiene las funciones puras (ámbito, hora de salida, título, clasificación de candidatos), los clientes de Nominatim, Google Routes y RAG, y la orquestación `planificar_ruta`.
"""
import json
import logging
import math
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import config
from src.reloj import ahora

# Registro interno: aquí va la excepción completa de los errores inesperados, nunca a la persona.
logger = logging.getLogger(__name__)


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


def distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos coordenadas (fórmula de haversine)."""
    radio_tierra_m = 6_371_000
    f1, f2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((f2 - f1) / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * radio_tierra_m * math.asin(math.sqrt(a))


def misma_ubicacion(a: dict, b: dict) -> bool:
    """Indica si dos candidatos están a menos de RADIO_MISMA_UBICACION_M (RF-10)."""
    return distancia_m(a["lat"], a["lon"], b["lat"], b["lon"]) <= config.RADIO_MISMA_UBICACION_M


def clasificar_candidatos(candidatos: list[dict]) -> dict:
    """Clasifica los resultados de Nominatim de una dirección.

    Devuelve `{"estado", "elegido", "candidatos"}` con `estado`:
    - "no_encontrada": Nominatim no devolvió nada (RF-6).
    - "fuera_cobertura": hay resultados pero ninguno dentro del ámbito (RF-4).
    - "ok": un único candidato dentro del ámbito, en `elegido` (RF-7).
    - "ambigua": varios dentro; `candidatos` lleva como mucho MAX_CANDIDATOS_MOSTRAR (RF-8).
    """
    if not candidatos:
        return {"estado": "no_encontrada", "elegido": None, "candidatos": []}
    dentro = [c for c in candidatos if dentro_de_ambito(c["lat"], c["lon"])]
    if not dentro:
        return {"estado": "fuera_cobertura", "elegido": None, "candidatos": []}
    # Resultados casi en el mismo punto (edificio y calle) son un solo lugar: se queda el primero,
    # que es el mejor clasificado por Nominatim.
    distintos = []
    for c in dentro:
        if not any(misma_ubicacion(c, previo) for previo in distintos):
            distintos.append(c)
    if len(distintos) == 1:
        return {"estado": "ok", "elegido": distintos[0], "candidatos": distintos}
    return {"estado": "ambigua", "elegido": None, "candidatos": distintos[:config.MAX_CANDIDATOS_MOSTRAR]}


def consultar_google(origen: dict, destino: dict, salida_rfc3339: str | None = None) -> dict:
    """Pide a Google Routes una ruta en transporte público y devuelve `{"estado", "respuesta"}`.

    `estado` es "ok" (con el JSON de Google en `respuesta`, que puede venir sin rutas) o
    "ruta_no_calculada" si falta la clave, hay error, falta de conexión o la respuesta no es
    válida (RF-16). Hace como mucho una llamada, sin reintentos ni rutas alternativas.
    El texto de los errores no se propaga: podría contener datos sensibles.
    """
    clave = config.GOOGLE_ROUTES_API_KEY
    if not clave or not clave.strip():
        return {"estado": "ruta_no_calculada", "respuesta": None}

    def punto(lugar: dict) -> dict:
        return {"location": {"latLng": {"latitude": lugar["lat"], "longitude": lugar["lon"]}}}

    cuerpo = {
        "origin": punto(origen),
        "destination": punto(destino),
        "travelMode": "TRANSIT",
        "transitPreferences": {"allowedTravelModes": config.MODOS_GOOGLE},
        "computeAlternativeRoutes": False,
        "languageCode": "es",
    }
    # Sin hora pedida no se envía departureTime: Google calcula con salida inmediata.
    if salida_rfc3339:
        cuerpo["departureTime"] = salida_rfc3339
    try:
        respuesta = _http_json(
            config.GOOGLE_ROUTES_URL,
            headers={"X-Goog-Api-Key": clave, "X-Goog-FieldMask": config.GOOGLE_FIELD_MASK},
            body=cuerpo,
            timeout=config.GOOGLE_TIMEOUT_S,
        )
    except (OSError, ValueError):  # URLError, HTTPError y timeout son OSError; JSON inválido, ValueError
        return {"estado": "ruta_no_calculada", "respuesta": None}
    if not isinstance(respuesta, dict):
        return {"estado": "ruta_no_calculada", "respuesta": None}
    return {"estado": "ok", "respuesta": respuesta}


def _minutos(duracion) -> int | None:
    """Convierte la duración de Google ("1320s") a minutos redondeados, o None si no es válida."""
    if not isinstance(duracion, str) or not re.fullmatch(r"\d+(\.\d+)?s", duracion):
        return None
    return round(float(duracion[:-1]) / 60)


def interpretar_respuesta_google(respuesta: dict) -> dict:
    """Extrae tiempo, tramos y paradas de la respuesta de Google, o `sin_ruta` si no es válida.

    Devuelve `{"estado", "ruta", "parada_subida", "parada_bajada"}`. Es `sin_ruta` (RF-17) si no hay
    ruta, ningún tramo de transporte (solo a pie, RF-13) o algún tramo tiene un tipo de vehículo fuera
    de TIPOS_VEHICULO_ACEPTADOS (RF-12). Nada se estima (RF-18): cualquier duración que falte o
    no se pueda leer descarta la ruta en lugar de rellenarse.
    """
    sin_ruta = {"estado": "sin_ruta", "ruta": None, "parada_subida": None, "parada_bajada": None}
    try:
        ruta = respuesta["routes"][0]
        total = _minutos(ruta["duration"])
        pasos = ruta["legs"][0]["steps"]
        if total is None or not pasos:
            return sin_ruta
        tramos, paradas = [], []
        for paso in pasos:
            minutos = _minutos(paso["staticDuration"])
            if minutos is None:
                return sin_ruta
            if paso["travelMode"] == "WALK":
                tramos.append({"modo": "A pie", "linea": None, "desde": None, "hasta": None, "duracion_min": minutos})
            elif paso["travelMode"] == "TRANSIT":
                detalle = paso["transitDetails"]
                tipo = detalle["transitLine"]["vehicle"]["type"]
                if tipo not in config.TIPOS_VEHICULO_ACEPTADOS:
                    return sin_ruta
                linea = detalle["transitLine"]
                parada = detalle.get("stopDetails", {})
                desde = parada.get("departureStop", {}).get("name")
                hasta = parada.get("arrivalStop", {}).get("name")
                paradas.append((desde, hasta))
                tramos.append({"modo": tipo, "linea": linea.get("nameShort") or linea.get("name"),
                               "desde": desde, "hasta": hasta, "duracion_min": minutos})
            else:
                return sin_ruta  # cualquier otro modo (coche, bici...) queda fuera de alcance
    except (KeyError, IndexError, TypeError, AttributeError):
        return sin_ruta
    if not paradas:
        return sin_ruta
    return {
        "estado": "ok",
        "ruta": {"duracion_min": total, "tramos": tramos, "fuente": "Google Routes"},
        "parada_subida": paradas[0][0],
        "parada_bajada": paradas[-1][1],
    }


def consultar_rag(pregunta: str) -> str:
    """Pregunta al RAG y devuelve su texto. Las excepciones se dejan pasar: las trata `consultar_tarifa`."""
    # Importación perezosa: cargar el RAG arrastra ChromaDB y los clientes del LLM, y así los tests lo sustituyen.
    from rag.responder import rag_ask
    return rag_ask(pregunta)


def _dato_rag(pregunta: str) -> dict:
    """Consulta un dato al RAG y lo clasifica: ok, sin_evidencia (abstención o respuesta inútil) o error."""
    try:
        texto = consultar_rag(pregunta)
    except Exception:  # cualquier fallo del RAG (Chroma, LLM, red) deja el dato sin determinar, sin detalle (RF-41)
        return {"estado": "error", "texto": None, "fuente": "RAG"}
    if not isinstance(texto, str) or not texto.strip() or config.FRASE_ABSTENCION in texto:
        return {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"}
    return {"estado": "ok", "texto": texto, "fuente": "RAG"}  # texto del RAG sin tocar (RF-23)


def consultar_tarifa(origen: str | None, destino: str | None, titulo=None) -> dict:
    """Consulta al RAG la zona y el precio del título y devuelve `{"zona", "precio"}`.

    `origen` y `destino` son las paradas de subida y bajada de Google o, si Google falló, los
    municipios de Nominatim (RF-20). Cada dato es `{"estado", "texto", "fuente": "RAG"}` con estado
    ok, sin_evidencia, error u omitida (sin consulta). Si falta origen o destino no se consulta nada.
    Un título fuera de la lista cerrada consulta solo la zona y omite el precio (RF-36).
    """
    omitida = {"estado": "omitida", "texto": None, "fuente": "RAG"}
    if not (origen and origen.strip() and destino and destino.strip()):
        return {"zona": dict(omitida), "precio": dict(omitida)}
    titulo_considerado, en_lista = resolver_titulo(titulo)
    zona = _dato_rag(config.PREGUNTA_ZONA.format(origen=origen, destino=destino))
    if not en_lista:
        return {"zona": zona, "precio": dict(omitida)}
    precio = _dato_rag(config.PREGUNTA_PRECIO.format(titulo=titulo_considerado, origen=origen, destino=destino))
    return {"zona": zona, "precio": precio}


# Nombre en español del tipo de vehículo de Google para mostrar cada tramo.
_NOMBRE_MODO = {
    "SUBWAY": "Metro", "METRO_RAIL": "Metro", "TRAM": "Metro ligero/tranvía", "LIGHT_RAIL": "Metro ligero/tranvía",
    "BUS": "Autobús", "TROLLEYBUS": "Autobús",
    "COMMUTER_TRAIN": "Cercanías", "HEAVY_RAIL": "Cercanías", "RAIL": "Cercanías", "TRAIN": "Cercanías",
}


def _texto_tramo(tramo: dict) -> str:
    """Una línea por tramo de la ruta: modo, línea, paradas y minutos (solo datos de Google)."""
    if tramo["modo"] == "A pie":
        return f"A pie {tramo['duracion_min']} min"
    texto = _NOMBRE_MODO.get(tramo["modo"], tramo["modo"])
    if tramo["linea"]:
        texto += f" línea {tramo['linea']}"
    if tramo["desde"] and tramo["hasta"]:
        texto += f" de {tramo['desde']} a {tramo['hasta']}"
    return f"{texto} {tramo['duracion_min']} min"


def _texto_dato_rag(nombre: str, dato: dict, titulo_no_disponible: str | None = None) -> str:
    """Frase etiquetada con la fuente (RAG) de la zona o el precio, según su estado."""
    if dato["estado"] == "ok":
        return f"{nombre} (RAG): {dato['texto']}"
    if dato["estado"] == "error":
        return f"{nombre} (RAG): no se pudo consultar."
    if titulo_no_disponible:  # RF-36: el título pedido no está en la lista cerrada
        return titulo_no_disponible
    return f"{nombre} (RAG): no se pudo determinar con el corpus."


def _mensaje_tarifa(tarifa: dict, titulo: str, en_lista: bool) -> str:
    """Zona y precio etiquetados con el RAG, y los títulos disponibles si el pedido no existe (RF-36)."""
    no_disponible = None
    if not en_lista:
        no_disponible = (f"Precio: el título «{titulo}» no está disponible. "
                         f"Títulos disponibles: {', '.join(config.TITULOS_TRANSPORTE)}.")
    return " ".join([_texto_dato_rag("Zona", tarifa["zona"]), _texto_dato_rag("Precio", tarifa["precio"], no_disponible)])


def _respuesta(estado: str, mensaje: str, hora: str, titulo: str, **extra) -> dict:
    """Construye el dict de salida con `estado` como primera clave y todos los campos del contrato."""
    omitida = {"estado": "omitida", "texto": None, "fuente": "RAG"}
    resultado = {
        "estado": estado, "mensaje": mensaje, "hora_salida": hora, "titulo": titulo,
        "origen": None, "destino": None, "ruta": None, "zona": dict(omitida), "precio": dict(omitida),
    }
    resultado.update(extra)
    return resultado


def _problema_direccion(rol: str, texto: str, clasificada: dict) -> str:
    """Frase de un extremo que no se pudo resolver a un único lugar (RF-4, RF-6, RF-8)."""
    if clasificada["estado"] == "fuera_cobertura":
        return f"La dirección de {rol} «{texto}» está fuera de la cobertura de MadridRumbo."
    if clasificada["estado"] == "no_encontrada":
        return f"No he encontrado la dirección de {rol} «{texto}». Indica una más precisa."
    lista = "; ".join(f"{i}) {c['direccion']}" for i, c in enumerate(clasificada["candidatos"], 1))
    return f"La dirección de {rol} «{texto}» es ambigua. Opciones: {lista}. Indica cuál es o concreta más."


def _encabezado(validacion: dict, hora_salida, titulo_considerado: str) -> tuple[str, str]:
    """Devuelve (cabecera, hora para el campo `hora_salida`): la hora pedida, aunque se rechace, o la actual."""
    estado_hora = validacion["estado"]
    if estado_hora == "hora_no_interpretable":
        hora, es_ahora = str(hora_salida), False
    elif estado_hora in ("hora_pasada", "hora_demasiado_lejana"):
        hora, es_ahora = _parsear_hora(hora_salida), False
    else:
        hora, es_ahora = validacion["considerada"], validacion["salida_rfc3339"] is None
    hora_txt = hora if isinstance(hora, str) else hora.isoformat(timespec="minutes")
    return cabecera(hora, titulo_considerado, es_ahora), hora_txt


def planificar_ruta(origen: str, destino: str, hora_salida: str | None = None,
                    hora_llegada: str | None = None, titulo: str | None = None) -> dict:
    """Ruta en transporte público CRTM con zona y precio del RAG. Devuelve siempre un dict con `estado` primero.

    Nunca lanza excepciones: un fallo inesperado (RF-42) se registra en el log interno y se devuelve como
    `error_interno` con un mensaje genérico en español, sin el texto de la excepción ni datos internos.
    """
    try:
        return _planificar_ruta(origen, destino, hora_salida, hora_llegada, titulo)
    except Exception:
        logger.exception("Error inesperado en planificar_ruta")
    # La cabecera se rehace aparte: si el fallo vino de la propia hora o del título, no debe repetirse aquí.
    try:
        titulo_considerado, _ = resolver_titulo(titulo)
        encabezado, hora_txt = _encabezado(validar_hora(hora_salida, hora_llegada), hora_salida, titulo_considerado)
    except Exception:
        titulo_considerado, hora_txt = config.TITULO_POR_DEFECTO, "ahora"
        encabezado = f"Salida: ahora · Título: {titulo_considerado}."
    return _respuesta("error_interno", f"{encabezado} Ocurrió un error inesperado y no se pudo planificar la ruta. "
                                       "Inténtalo de nuevo más tarde.", hora_txt, titulo_considerado)


def _planificar_ruta(origen, destino, hora_salida, hora_llegada, titulo) -> dict:
    """Cuerpo de `planificar_ruta`: validar hora y datos (sin red) → geocodificar → Google Routes → RAG.

    Si un paso falla, los siguientes no se ejecutan. Como mucho 2 llamadas a Nominatim, 1 a Google y 2 al RAG.
    """
    validacion = validar_hora(hora_salida, hora_llegada)
    titulo_considerado, en_lista = resolver_titulo(titulo)
    estado_hora = validacion["estado"]
    encabezado, hora_txt = _encabezado(validacion, hora_salida, titulo_considerado)

    def salir(estado: str, texto: str, **extra) -> dict:
        return _respuesta(estado, f"{encabezado} {texto}", hora_txt, titulo_considerado, **extra)

    # 1) Validaciones baratas, sin red.
    faltan = [rol for rol, valor in (("origen", origen), ("destino", destino))
              if not isinstance(valor, str) or not valor.strip()]
    if faltan:
        return salir("faltan_datos", f"Falta indicar {' y '.join('el ' + f for f in faltan)}.")
    rechazos = {
        "hora_llegada_no_admitida": "Solo se admite hora de salida, no de llegada. Indica a qué hora quieres salir.",
        "hora_no_interpretable": "No he podido interpretar la hora de salida. Indícala de nuevo (por ejemplo, 2026-10-15T08:30).",
        "hora_pasada": "Esa hora de salida ya ha pasado. Indica otra hora.",
        "hora_demasiado_lejana": f"La hora de salida supera la antelación máxima de {config.ANTELACION_MAX_DIAS} días. Indica otra hora.",
    }
    if estado_hora in rechazos:
        return salir(estado_hora, rechazos[estado_hora])

    # 2) Geocodificación: se resuelven los dos extremos (máx. 2 llamadas); un fallo de Nominatim detiene todo.
    clasificadas = {}
    for rol, texto in (("origen", origen), ("destino", destino)):
        geo = geocodificar(texto)
        if geo["estado"] != "ok":
            return salir("geocodificacion_fallida",
                         "No he podido localizar las direcciones ahora mismo. Inténtalo de nuevo más tarde.")
        clasificadas[rol] = clasificar_candidatos(geo["candidatos"])

    problemas = {rol: c for rol, c in clasificadas.items() if c["estado"] != "ok"}
    if problemas:
        # Prioridad del estado: fuera de cobertura > no encontrada > ambigua. El mensaje lista cada problema (RF-5).
        estado = next(e for e in ("fuera_cobertura", "no_encontrada", "ambigua")
                      if any(c["estado"] == e for c in problemas.values()))
        textos = {"origen": origen, "destino": destino}
        candidatos = {rol: [{"direccion": c["direccion"]} for c in clasificadas[rol]["candidatos"]]
                      if clasificadas[rol]["estado"] == "ambigua" else [] for rol in textos}
        extra = {"candidatos": candidatos} if estado == "ambigua" else {}
        mensaje = " ".join(_problema_direccion(rol, textos[rol], c) for rol, c in problemas.items())
        return salir("direccion_no_encontrada" if estado == "no_encontrada" else estado, mensaje, **extra)

    lugar_o, lugar_d = clasificadas["origen"]["elegido"], clasificadas["destino"]["elegido"]
    identificados = {"origen": {"direccion": lugar_o["direccion"]}, "destino": {"direccion": lugar_d["direccion"]}}
    if misma_ubicacion(lugar_o, lugar_d):
        return salir("misma_ubicacion", f"El origen y el destino son la misma ubicación («{lugar_o['direccion']}»). "
                                        "No hay ruta que calcular.", **identificados)

    # 3) Ruta con Google (máx. 1 llamada).
    trayecto = f"De «{lugar_o['direccion']}» a «{lugar_d['direccion']}»"
    google = consultar_google(lugar_o, lugar_d, validacion["salida_rfc3339"])
    if google["estado"] != "ok":
        # RF-16 y RF-20: sin ruta, pero ambos puntos están en el ámbito: se consulta el RAG con los municipios.
        tarifa = consultar_tarifa(lugar_o["municipio"], lugar_d["municipio"], titulo)
        texto = (f"{trayecto}: no se pudo calcular la ruta con Google Routes. Inténtalo de nuevo más tarde. "
                 + _mensaje_tarifa(tarifa, titulo_considerado, en_lista))
        return salir("ruta_no_calculada", texto, **identificados, **tarifa)
    interpretada = interpretar_respuesta_google(google["respuesta"])
    if interpretada["estado"] != "ok":
        return salir("sin_ruta", f"{trayecto}: no hay ruta disponible en transporte público de la red del CRTM. "
                                 "No se indica zona ni precio.", **identificados)

    # 4) Zona y precio con el RAG (máx. 2 llamadas); sus fallos no tumban la ruta (RF-41).
    ruta = interpretada["ruta"]
    tarifa = consultar_tarifa(interpretada["parada_subida"], interpretada["parada_bajada"], titulo)
    trayecto_txt = "; ".join(_texto_tramo(t) for t in ruta["tramos"])
    texto = (f"{trayecto}: {ruta['duracion_min']} min (Google Routes). Trayecto: {trayecto_txt}. "
             + _mensaje_tarifa(tarifa, titulo_considerado, en_lista))
    return salir("ok", texto, **identificados, ruta=ruta, **tarifa)
