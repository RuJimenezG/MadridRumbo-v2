# Verificación de la API de la EMT (T1, spec 009) — COMPLETA (intento 3, 2026-10-20)

> 2026-10-19 · Peticiones reales gastadas: **1 de las 2 autorizadas** (login). La consulta de estaciones **no se hizo** porque el login falló. Sin reintentos. Sin credenciales, token ni cabeceras con valores en este archivo.

## Intento 1 — login

- Método y ruta probados (de memoria): `GET https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/`.
- Cabeceras enviadas (solo nombres): `X-ClientId`, `passKey`.
- Respuesta: **HTTP 403**, `Content-Type: application/json`.
- Estructura real del cuerpo (confirmada): objeto con `code` (cadena), `description` (cadena), `datetime` (cadena) y `data` (lista). Es el formato de envoltorio de la API de la EMT.
- `code = "84"`, `description` vacía, sin `accessToken`.

## Qué se sabe y qué no

- **Confirmado:** la ruta del login existe y responde con el envoltorio `code`/`description`/`datetime`/`data`; las credenciales están en el entorno (ambas presentes, sin mostrar su valor).
- **No confirmado:** el significado exacto del código `84` (no hay texto en `description`); si falla por credenciales no válidas o no activadas para esta API, por el nombre de las cabeceras o por el método. No se ha visto ningún token, su caducidad ni la lista de estaciones.
- **Siguen sin verificar:** ruta y método de estaciones, formato de la lista, nombres de los campos (id, nombre, coordenadas, bicis, huecos libres, estado) y límites de uso.

## Siguiente paso (pendiente de decisión)

Comprobar con la persona titular de la cuenta de la EMT que las claves son válidas y están activadas para el entorno de producción de MobilityLabs, y revisar en `apidocs.emtmadrid.es` (con sesión) el login y el significado del código 84. Después, con nueva autorización, repetir T1 desde el principio (2 peticiones).

## Intento 2 — diagnóstico de forma y login v2 (2026-10-19)

- **Forma de las credenciales (sin red, sin mostrar valores):** ambas presentes, sin espacios ni saltos de línea en los extremos ni dentro, sin comillas, sin BOM ni caracteres no ASCII. `EMT_CLIENT_ID`: 36 caracteres con formato UUID. `EMT_PASS_KEY`: 128 caracteres hexadecimales. No hay problema de forma; no se corrigió nada.
- **Petición gastada (1 más; 2 en total contra la EMT):** `GET https://openapi.emtmadrid.es/v2/mobilitylabs/user/login/` con las cabeceras `X-ClientId` y `passKey`.
- **Respuesta:** HTTP 403, JSON con `code = "84"`, `description` vacía, `data = []`. Igual que en la v1: la versión de la ruta no es la causa.
- La consulta de estaciones no se hizo (el login no dio `00`).
- **Conclusión:** con la ruta, el método y las cabeceras de la documentación oficial y credenciales con la forma correcta, la EMT rechaza el login con el código 84. Lo más probable es un problema de la cuenta o de las claves (no activadas, revocadas o de otro entorno), no de formato ni de nuestro código; el significado del código 84 sigue sin confirmar.

## Intento 3 — verificación correcta (2026-10-20)

> **Peticiones reales gastadas: 2** (login y estaciones), sin reintentos; 4 en total con los dos intentos anteriores. Sin credenciales ni token en este archivo. En esta pasada el login, que antes daba 403 con `code` "84", respondió bien con las mismas cabeceras; la causa del fallo anterior no se ha averiguado (se supone un problema de la cuenta, ya resuelto).

### Login

- **Ruta y método:** `GET https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/`.
- **Cabeceras enviadas (solo nombres):** `X-ClientId`, `passKey`.
- **Respuesta:** HTTP 200 (sin cabecera `Content-Type` visible), JSON `{code, description, datetime, data}` con `code` = "00".
- **`data[0]` (solo claves):** `updatedAt`, `username`, `accessToken`, `email`, `idUser`, `tokenSecExpiration`, `apiCounter`, `nameApp`.
- **Caducidad:** `tokenSecExpiration` = 86 400 s (24 h): el token se puede reutilizar en memoria.
- **Atención:** el texto de `description` incluye el nombre de usuario y el token. No debe registrarse, devolverse ni mostrarse.

### Estaciones

- **Ruta y método:** `GET https://openapi.emtmadrid.es/v1/transport/bicimad/stations/`.
- **Cabeceras enviadas (solo nombres):** `accessToken`.
- **Respuesta:** HTTP 200, `code` "00", `description` «678 bases recovered», `data` = lista de 678 objetos (una consulta devuelve todas).
- **Campos de cada estación (nombre exacto: tipo):**

| Dato | Campo | Tipo / nota |
|---|---|---|
| identificador | `id` | int (el `number` es el número de estación, cadena) |
| nombre | `name` | cadena, p. ej. «5 - Fuencarral» |
| dirección | `address` | cadena |
| coordenadas | `geometry.coordinates` | `[longitud, latitud]` (floats; `geometry.type` = "Point") |
| bicis disponibles | `dock_bikes` | int |
| huecos libres | `free_bases` | int |
| total de anclajes | `total_bases` | int |
| estado | `activate` | int (1 en los dos ejemplos) |
| estado | `no_available` | int (0 en los dos ejemplos; significado sin confirmar) |
| estado | `virtualDelete` | bool |
| otros | `geofenced_capacity`, `light`, `reservations_count`, `tipo_estacionPBSC` ("FIXED"), `image` | `image` no siempre presente |

- **Ejemplo de una estación (respuesta real, sin datos sensibles):**

```json
{"id": 1409, "number": "5", "name": "5 - Fuencarral", "address": "Calle Fuencarral, 106",
 "geometry": {"type": "Point", "coordinates": [-3.7021354, 40.4285212]},
 "activate": 1, "no_available": 0, "virtualDelete": false,
 "dock_bikes": 2, "free_bases": 22, "total_bases": 27, "geofenced_capacity": 20,
 "light": 0, "reservations_count": 0, "tipo_estacionPBSC": "FIXED", "image": ""}
```

### Diferencias con lo supuesto y pendiente

- No existe un único campo «activa»: el plan propone `activate == 1 and no_available == 0 and not virtualDelete`. El significado de `no_available` y la distribución de `activate` en las 678 estaciones no se comprobaron (no se guardó la lista).
- Las coordenadas van en orden **longitud, latitud** (al revés que Nominatim y Google en este proyecto).
- Los **huecos libres** son `free_bases` y las **bicis**, `dock_bikes`: ambos datos llegan en la misma consulta (supuesto confirmado).
- Límites de uso: no documentados en la respuesta; el login trae `apiCounter` (sin interpretar). Sin reintentos y como mucho 2 peticiones por consulta (el token se reutiliza 24 h).
- No se vio ningún error nuevo; los de 401, 429 y timeout siguen sin comprobar y se cubren con dobles.
