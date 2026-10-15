"""Escenario con dobles para probar `planificar_ruta` de principio a fin (spec 004). Sin red, RAG ni LLM.

Sustituye `_http_json` (Nominatim y Google), `rag.responder`, `ahora`, `time.sleep` y `time.monotonic`,
y anota el orden de las llamadas externas para comprobar la secuencia y los límites de coste.
"""
import sys
import types
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from src.tools import planificar_ruta as pr

# Hora fija de las consultas: jueves 15/10/2026 08:12 en Madrid.
AHORA = datetime(2026, 10, 15, 8, 12, tzinfo=ZoneInfo("Europe/Madrid"))

# Resultados de Nominatim (jsonv2 con addressdetails), reducidos a lo que usa el cliente.
def nominatim(nombre, lat, lon, municipio="Madrid"):
    return {"display_name": nombre, "lat": str(lat), "lon": str(lon), "address": {"city": municipio}}

SOL = nominatim("Puerta del Sol, Madrid", 40.4169, -3.7035)
BERNABEU = nominatim("Estadio Santiago Bernabéu, Madrid", 40.4531, -3.6883)
ATOCHA = nominatim("Estación de Atocha, Madrid", 40.4065, -3.6895)
RETIRO = nominatim("Parque del Retiro, Madrid", 40.4153, -3.6845)
BARCELONA = nominatim("Calle Mayor, Barcelona", 41.3874, 2.1686, "Barcelona")

RESPUESTA_GOOGLE = {"routes": [{"duration": "1320s", "legs": [{"steps": [
    {"travelMode": "WALK", "staticDuration": "180s"},
    {"travelMode": "TRANSIT", "staticDuration": "900s", "transitDetails": {
        "stopDetails": {"departureStop": {"name": "Sol"}, "arrivalStop": {"name": "Plaza de Castilla"}},
        "transitLine": {"nameShort": "1", "vehicle": {"type": "SUBWAY"}}}},
]}]}]}

ZONA = "Zona A según la tabla tarifaria."
PRECIO = "El billete sencillo cuesta 1,50 €."


class Escenario:
    def __init__(self, monkeypatch):
        self.nominatim = [[SOL], [BERNABEU]]     # una respuesta (o excepción) por llamada, en orden
        self.google = RESPUESTA_GOOGLE           # respuesta (o excepción) de Google
        self.rag = {"zona tarifaria": ZONA, "precio": PRECIO}   # {fragmento de pregunta: respuesta o excepción}
        self.orden = []                          # "nominatim" / "google" / "rag", en el orden de las llamadas
        self.preguntas = []                      # preguntas recibidas por el RAG
        self.cuerpos_google = []
        monkeypatch.setattr(pr, "_http_json", self._http_json)
        monkeypatch.setattr(pr, "ahora", lambda: AHORA)
        monkeypatch.setattr(pr.time, "sleep", lambda s: None)
        monkeypatch.setattr(pr.time, "monotonic", lambda: 1000.0)
        monkeypatch.setattr(pr, "_ultima_peticion_nominatim", None)
        monkeypatch.setattr(config, "GOOGLE_ROUTES_API_KEY", "CLAVE-DE-TEST")
        monkeypatch.setitem(sys.modules, "rag.responder", types.SimpleNamespace(rag_ask=self._rag_ask))

    def cuantas(self, servicio):
        return self.orden.count(servicio)

    def _http_json(self, url, *, headers=None, body=None, timeout=10):
        if url.startswith(config.NOMINATIM_URL):
            self.orden.append("nominatim")
            respuesta = self.nominatim.pop(0)
        else:
            assert url == config.GOOGLE_ROUTES_URL, f"URL inesperada: {url}"
            self.orden.append("google")
            self.cuerpos_google.append(body)
            respuesta = self.google
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def _rag_ask(self, pregunta):
        self.orden.append("rag")
        self.preguntas.append(pregunta)
        for clave, respuesta in self.rag.items():
            if clave in pregunta:
                if isinstance(respuesta, Exception):
                    raise respuesta
                return respuesta
        raise AssertionError(f"pregunta inesperada: {pregunta}")
