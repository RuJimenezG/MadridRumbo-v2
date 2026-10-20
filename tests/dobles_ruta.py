"""Escenario con dobles para probar `planificar_ruta` de principio a fin (spec 004). Sin red, RAG ni LLM.

Sustituye `_http_json` (Nominatim y Google), `rag.responder`, `ahora`, `time.sleep` y `time.monotonic`,
y anota el orden de las llamadas externas para comprobar la secuencia y los límites de coste.
"""
import sys
import types
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from src.tools import bicimad, planificar_ruta as pr

# Hora fija de las consultas: jueves 15/10/2026 08:12 en Madrid.
AHORA = datetime(2026, 10, 15, 8, 12, tzinfo=ZoneInfo("Europe/Madrid"))

# Resultados de Nominatim (jsonv2 con addressdetails), reducidos a lo que usa el cliente.
def nominatim(nombre, lat, lon, municipio="Madrid", iso="ES-MD"):
    # ISO3166-2-lvl4 es el código de comunidad autónoma (T22, RF-55); su presencia en Nominatim real está por comprobar.
    return {"display_name": nombre, "lat": str(lat), "lon": str(lon),
            "address": {"city": municipio, "ISO3166-2-lvl4": iso}}

SOL = nominatim("Puerta del Sol, Madrid", 40.4169, -3.7035)
BERNABEU = nominatim("Estadio Santiago Bernabéu, Madrid", 40.4531, -3.6883)
ATOCHA = nominatim("Estación de Atocha, Madrid", 40.4065, -3.6895)
RETIRO = nominatim("Parque del Retiro, Madrid", 40.4153, -3.6845)
BARCELONA = nominatim("Calle Mayor, Barcelona", 41.3874, 2.1686, "Barcelona", "ES-CT")

RESPUESTA_GOOGLE = {"routes": [{"duration": "1320s", "legs": [{"steps": [
    {"travelMode": "WALK", "staticDuration": "180s"},
    {"travelMode": "TRANSIT", "staticDuration": "900s", "transitDetails": {
        "stopDetails": {"departureStop": {"name": "Sol"}, "arrivalStop": {"name": "Plaza de Castilla"}},
        "transitLine": {"nameShort": "1", "vehicle": {"type": "SUBWAY"}}}},
]}]}]}

# Respuesta real de Open-Meteo (T12) reducida a lo que usa el cliente: nublado, 16,1 °C, 11,2 km/h (apto para exterior).
METEO_APTO = {"current": {"time": "2026-10-20T13:00", "interval": 900, "temperature_2m": 16.1,
                          "precipitation": 0.0, "weather_code": 3, "wind_speed_10m": 11.2}}
METEO_LLUVIA = {"current": {**METEO_APTO["current"], "precipitation": 1.4, "weather_code": 61}}

# EMT BiciMAD (T1, 2026-10-20), reducida a lo que usa el cliente. Una estación con bicis junto a Sol y otra con huecos
# junto al Bernabéu (la EMT da las coordenadas como [longitud, latitud]).
EMT_LOGIN_OK = (200, {"code": "00", "description": "doble", "datetime": "x", "data": [
    {"accessToken": "TOKEN-DOBLE", "tokenSecExpiration": 86400}]})


def estacion_emt(id_, nombre, lat, lon, bicis, huecos):
    return {"id": id_, "name": nombre, "geometry": {"type": "Point", "coordinates": [lon, lat]}, "activate": 1,
            "no_available": 0, "virtualDelete": False, "dock_bikes": bicis, "free_bases": huecos}


EMT_ESTACIONES_OK = (200, {"code": "00", "description": "2 bases recovered", "datetime": "x", "data": [
    estacion_emt(1, "1 - Sol", 40.4172, -3.7030, 6, 2), estacion_emt(2, "2 - Bernabeu", 40.4528, -3.6880, 1, 9)]})
# Google bici y a pie: en bici 11 min, a pie 4 y 3 (total 18).
TRAMOS_BICI_OK = [(200, {"routes": [{"duration": f"{m * 60}s"}]}) for m in (11, 4, 3)]

ZONA = "Zona A según la tabla tarifaria."
PRECIO = "El billete sencillo cuesta 1,50 €."


# La función real, guardada al importar: otro Escenario puede haber dejado ya la versión desactivada en el módulo.
ALTERNATIVA_REAL = bicimad.alternativa_bici


class Escenario:
    def __init__(self, monkeypatch):
        self.nominatim = [[SOL], [BERNABEU]]     # una respuesta (o excepción) por llamada, en orden
        self.google = RESPUESTA_GOOGLE           # respuesta (o excepción) de Google
        self.rag = {"zona tarifaria": ZONA, "precio": PRECIO}   # {fragmento de pregunta: respuesta o excepción}
        self.orden = []                          # "nominatim" / "google" / "rag", en el orden de las llamadas
        self.preguntas = []                      # preguntas recibidas por el RAG
        self.cuerpos_google = []
        self.emt_login = EMT_LOGIN_OK            # respuesta (o excepción) del login de la EMT (T7)
        self.emt_estaciones = EMT_ESTACIONES_OK  # respuesta (o excepción) de la lista de estaciones
        self.tramos_bici = list(TRAMOS_BICI_OK)  # respuestas (o excepciones) de Google para bici, pie y pie
        self.llamadas_bici = []                  # (url, cabeceras o cuerpo) de las llamadas de bici: EMT y Google
        self.meteo = (200, METEO_APTO)           # respuesta (o excepción) de Open-Meteo (T14); su red es la de bicimad
        self.llamadas_meteo = []                 # URLs pedidas a Open-Meteo
        self.secuencia = []                      # "nominatim" / "meteo" / "google" / "rag" en orden (orden no incluye "meteo")
        monkeypatch.setattr(pr, "_http_json", self._http_json)
        monkeypatch.setattr(bicimad, "_get_json", self._get_json_bici)
        monkeypatch.setattr(bicimad, "_post_json", self._post_json_bici)
        monkeypatch.setattr(bicimad, "_token", None)
        # Por defecto la alternativa en bici está desactivada (no_ofrecida, sin llamadas): `bici_real()` la activa.
        self._monkeypatch = monkeypatch
        monkeypatch.setattr(bicimad, "alternativa_bici",
                            lambda origen, destino, hora_pedida, clima: ({"estado": "no_ofrecida", "motivo": None}, ""))
        monkeypatch.setattr(pr, "ahora", lambda: AHORA)
        monkeypatch.setattr(pr.time, "sleep", lambda s: None)
        monkeypatch.setattr(pr.time, "monotonic", lambda: 1000.0)
        monkeypatch.setattr(pr, "_ultima_peticion_nominatim", None)
        monkeypatch.setattr(config, "GOOGLE_ROUTES_API_KEY", "CLAVE-DE-TEST")
        monkeypatch.setitem(sys.modules, "rag.responder", types.SimpleNamespace(rag_ask=self._rag_ask))

    def cuantas(self, servicio):
        return self.orden.count(servicio)

    def bici_real(self):
        """Activa la alternativa real de `bicimad`; su red (EMT, Google de bici y Open-Meteo) sigue simulada."""
        self._monkeypatch.setattr(bicimad, "alternativa_bici", ALTERNATIVA_REAL)

    def _get_json_bici(self, url, headers=None, timeout=10):
        """GET de bicimad: Open-Meteo, login de la EMT o lista de estaciones."""
        if url.startswith(config.OPEN_METEO_URL):
            self.llamadas_meteo.append(url)
            self.secuencia.append("meteo")
            respuesta = self.meteo
        else:
            assert url in (config.EMT_LOGIN_URL, config.EMT_ESTACIONES_URL), f"URL inesperada: {url}"
            self.llamadas_bici.append((url, headers))
            self.secuencia.append("emt")
            respuesta = self.emt_login if url == config.EMT_LOGIN_URL else self.emt_estaciones
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def _post_json_bici(self, url, headers=None, body=None, timeout=10):
        assert url == config.GOOGLE_ROUTES_URL, f"URL inesperada: {url}"
        self.llamadas_bici.append((url, body))
        self.secuencia.append("google_bici")
        respuesta = self.tramos_bici.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def _http_json(self, url, *, headers=None, body=None, timeout=10):
        if url.startswith(config.NOMINATIM_URL):
            self.orden.append("nominatim")
            self.secuencia.append("nominatim")
            respuesta = self.nominatim.pop(0)
        else:
            assert url == config.GOOGLE_ROUTES_URL, f"URL inesperada: {url}"
            self.orden.append("google")
            self.secuencia.append("google")
            self.cuerpos_google.append(body)
            respuesta = self.google
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def _rag_ask(self, pregunta):
        self.orden.append("rag")
        self.secuencia.append("rag")
        self.preguntas.append(pregunta)
        for clave, respuesta in self.rag.items():
            if clave in pregunta:
                if isinstance(respuesta, Exception):
                    raise respuesta
                return respuesta
        raise AssertionError(f"pregunta inesperada: {pregunta}")
