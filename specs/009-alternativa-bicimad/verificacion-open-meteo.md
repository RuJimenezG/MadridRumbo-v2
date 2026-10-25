# Verificación de Open-Meteo (T12, spec 009) — COMPLETA

> 2026-10-20 · Peticiones reales gastadas: **1**, sin reintentos. Sin clave.

- **Petición:** `GET https://api.open-meteo.com/v1/forecast?latitude=40.4169&longitude=-3.7035&current=temperature_2m,precipitation,weather_code,wind_speed_10m&timezone=Europe%2FMadrid` (Puerta del Sol).
- **Respuesta:** HTTP 200, `application/json; charset=utf-8`.
- **Estructura:** `latitude`, `longitude` (ajustadas a la rejilla del modelo: 40.417583, -3.739399), `elevation`, `utc_offset_seconds`, `timezone`, `current_units` y `current`.
- **`current_units`:** `temperature_2m` "°C", `precipitation` "mm", `weather_code` "wmo code", `wind_speed_10m` "km/h" (confirma km/h por defecto).
- **`current` (respuesta real):** `{"time": "2026-10-20T13:00", "interval": 900, "temperature_2m": 16.1, "precipitation": 0.00, "weather_code": 3, "wind_speed_10m": 11.2}`. `time` va en hora local, sin desfase; `interval` = 900 s.
- **Periodo de `precipitation`:** se atribuye al intervalo de 15 minutos (`interval` = 900); no confirmado en la documentación.
- **Licencia y límites:** verificado en open-meteo.com: gratuito sin clave para uso no comercial hasta 10.000 llamadas/día, atribución CC BY 4.0. La atribución irá también en el `README`, por si el sintetizador la omite.
- **Diferencias con lo supuesto:** ninguna en los nombres de variables; solo se ha visto el código 3 (nublado), así que la lista de códigos WMO de lluvia, nieve y tormenta sigue siendo la de la documentación.
