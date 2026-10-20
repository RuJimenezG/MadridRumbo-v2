# Demos reales de la spec 009 (T10) — PARCIAL

> 2026-10-20, ~13:57 (hora de Madrid). Trayecto de las cuatro demos: «Puerta del Sol, Madrid» → «Estadio Santiago Bernabéu, Madrid» (≈ 4,2 km en línea recta, dentro de R2). Sin reintentos. Sin credenciales, tokens ni cabeceras en este archivo; de la EMT solo se guardó el `code` del login, nunca su `description`.

## Llamadas reales gastadas

| Demo | Nominatim | Open-Meteo | EMT | Google transporte | Google bici | RAG |
|---|---|---|---|---|---|---|
| 1 Caso feliz | 2 | 1 | 1 (login) | 1 | 0 | 2 |
| 2 Hora pedida | 2 | 0 | 0 | 1 | 0 | 2 |
| 3 EMT sin credenciales | 2 | 1 | 0 | 1 | 0 | 2 |
| 4 Mal tiempo (simulado) | 2 | 0 | 0 | 1 | 0 | 2 |
| **Total** | **8** | **2** | **1** | **4** | **0** | **8** |

Previstas como máximo: Nominatim 8, Open-Meteo 2, EMT 2, Google 7, RAG 8. La demo 1 no pasó del login de la EMT, así que **no se gastaron** la lista de estaciones ni las 3 llamadas de Google de bici.

## Resultados

| Demo | Estado | `bici` | Mensaje y observaciones |
|---|---|---|---|
| 1 Caso feliz | `ok` | `no_disponible` | **El login de la EMT devolvió HTTP 200 con `code` "01" (no "00"): sin token.** El sistema hizo lo previsto (RF-13): ruta intacta (20 min, Cercanías C4b), línea de clima con atribución y la frase «La alternativa en bici (BiciMAD) no está disponible ahora.». No se pudo ver la alternativa real. |
| 2 Hora pedida (21/10 09:00) | `ok` | `no_ofrecida`, sin motivo | Sin clima, sin `LESS_WALKING`, sin línea de tiempo ni párrafo de bici; 0 llamadas a Open-Meteo, EMT y Google de bici. Ruta 20 min (C3). |
| 3 EMT sin credenciales | `ok` | `no_disponible` | 0 llamadas a la EMT (no hay credenciales). Ruta intacta (20 min, C4b), línea de clima apta con atribución y la frase de no disponible. |
| 4 Mal tiempo (clima simulado: lluvia 1,4 mm, código 61) | `ok` | `no_ofrecida`, sin motivo | La petición a Google llevó `transitPreferences.routingPreference = "LESS_WALKING"`; sin párrafo de bici. |

Línea de clima real (demos 1 y 3, Open-Meteo: 16,5 °C, 0 mm, código 3, 12,6 km/h): «Tiempo en el origen ahora: 16 °C, sin precipitación, viento 13 km/h (apto para exterior). Datos meteorológicos de Open-Meteo.com (CC BY 4.0).»

Línea con mal tiempo (demo 4): «Tiempo en el origen ahora: 16 °C, precipitación 1.4 mm, viento 10 km/h (no apto para exterior: lluvia; la ruta se pidió con menos tramos a pie). Datos meteorológicos de Open-Meteo.com (CC BY 4.0).»

## ¿`LESS_WALKING` cambia la ruta de transporte?

Sí, en esta muestra (una sola, mismo origen y destino, misma hora):

| | Sin `LESS_WALKING` (demos 1 y 3) | Con `LESS_WALKING` (demo 4) |
|---|---|---|
| Duración total | 20 min | 36 min |
| Transporte | Cercanías C4b, Sol → Nuevos Ministerios, 5 min | Autobús 150, 25 min |
| Andando (suma de tramos) | 15 min | 11 min |

Menos andando, pero 16 min más de viaje. Es una preferencia, no una garantía, y el mensaje solo dice «menos tramos a pie».

## Tiempos de respuesta (s, una muestra)

Nominatim 0,04–0,35; Open-Meteo 0,13–0,46; EMT (login) 0,14; Google transporte 0,18–0,41; RAG 1,9–4,7 por llamada (4,3–4,7 la primera). Total por consulta 7,8–8,8 s, dominado por el RAG. Los tiempos de Google bici y de la lista de estaciones no se pudieron medir.

## Sin contrastar (hay que repetir la demo 1)

1. **Qué significa «estación activa»:** no se obtuvo la lista de estaciones.
2. **`routes.warnings` de Google para bici y a pie:** no se hicieron las llamadas de bici.
3. **Cobertura de `BICYCLE` en Madrid** y coherencia del total de la alternativa (suma de los tres tramos).
4. **Significado del `code` "01" del login de la EMT:** no se guardó su `description` (puede contener el usuario y el token). Esta mañana el mismo login devolvió "00".

## Repetición de la demo 1 (2026-10-20, ~14:10) — tampoco llegó a la lista de estaciones

> Tras corregir el cliente para aceptar el `code` "01" del login. Mismo trayecto, sin hora pedida. Sin reintentos.

**Llamadas reales gastadas:** Nominatim 2, Open-Meteo 1, EMT 1 (login), Google transporte 1, Google bici 0, RAG 2. Autorizadas como máximo: EMT 2 y Google 4. No se gastaron la lista de estaciones ni las 3 llamadas de Google de bici.

**Qué pasó:** el login de la EMT no respondió en 10 s (`EMT_TIMEOUT_S`): `TimeoutError` a los 10,05 s. Es la primera vez que falla así; en las pruebas anteriores respondió en 0,14 s. El sistema se comportó como la spec (RF-13): `bici = no_disponible`, ruta de transporte intacta (20 min, Cercanías C4a; antes C4b/C3, solo cambia la línea concreta) y la frase «La alternativa en bici (BiciMAD) no está disponible ahora.». El tiempo de la consulta subió a 18,0 s por esa espera.

Tiempo real de esta pasada: 16 °C, sin precipitación, 13 km/h (apto), con atribución en el mensaje.

**Qué sigue sin contrastar con datos reales:** si el login "01" trae `data[0].accessToken`; cuántas estaciones tienen `activate` distinto de 1, `no_available` distinto de 0 o `virtualDelete` verdadero, y si la elegida cumple la regla; si Google devuelve `routes.warnings` en bici y a pie; el mensaje final con la bici y la suma de los tres tramos.
