# Plan técnico — Spec 009 (alternativa en bici con BiciMAD)

> Basado en `spec.md` (estado: Aprobada; ampliación del clima, RF-20 a RF-28, pendiente de aprobación). No añade comportamiento que no esté en la spec. Sin código todavía.
> La API de la EMT se verificó en T1 (2026-10-20, `verificacion-emt.md`) y la de Open-Meteo en T12 (`verificacion-open-meteo.md`). Normalización de la EMT a `{id, nombre, lat, lon, bicis, huecos, activa}`: `id`←`id`, `nombre`←`name`, `lon, lat`←`geometry.coordinates[0], [1]` (orden lon/lat), `bicis`←`dock_bikes`, `huecos`←`free_bases`, `activa`←`activate == 1 and no_available == 0 and not virtualDelete` (criterio por confirmar).

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/tools/bicimad.py` | **Crear** | Módulo nuevo (incluye las funciones internas del clima `clima_origen` y `apto_exterior`, RF-20 a RF-26): regla de oferta, cliente EMT (login con token reutilizable y lista de estaciones), elección de estaciones, cliente Google BICYCLE/WALK, orquestador `alternativa_bici` y texto del párrafo. Cliente HTTP mínimo **propio**. | RF-1 a 19 |
| `src/tools/planificar_ruta.py` | Modificar (**mínimo**) | *(clima)* (a) Antes de pedir la ruta a Google, sin hora pedida: importación perezosa y una llamada a `clima_origen`; si no es apto, `consultar_google` recibe el parámetro opcional `preferencia_transito="LESS_WALKING"` (RF-22) y, si no, la petición no cambia. (b) Un punto de enganche en la rama `ok` con ruta: importación perezosa de `alternativa_bici`, una llamada y añadir `bici` y su párrafo al resultado. Sin lógica de BiciMAD. | RF-1, 16, 17 |
| `config.py` | Modificar (compartido; añadir al final de la sección de rutas) | *(clima)* `OPEN_METEO_URL`, timeout, `CLIMA_TEMP_MIN_C` (5), `CLIMA_TEMP_MAX_C` (32), `CLIMA_VIENTO_MAX_KMH` (30), `CLIMA_PRECIPITACION_MAX_MM` (0), `CLIMA_CODIGOS_NO_APTOS` (51–57, 61–67, 71–77, 80–82, 85–86, 95–99) y el texto de atribución. Constantes `BICI_*`, URLs y timeouts de la EMT, credenciales leídas con `os.getenv`, máscara de Google para bici y a pie, texto fijo del aviso. | RF-2, 12, RNF |
| `.env.example` | **Sin cambios** | `EMT_CLIENT_ID` y `EMT_PASS_KEY` ya están sin valor; un test nuevo vigila que sigan. | RNF Secretos |
| `tests/test_bicimad.py` | **Crear** | Todos los tests de la spec 009 (dobles de la EMT y de Google, sin red). | todos |
| `src/sintetizador.py` | Modificar **solo si se aprueba la opción A** (T9, bloqueada) | Pie determinista con los avisos obligatorios de los resultados, tras el texto del LLM. Archivo compartido (spec 005): coordinar. | RF-12 |
| `src/agents/rutas.py`, `rag/`, corpus, `src/tools/__init__.py` | **No se tocan** | La tool y la allowlist no cambian; `bicimad.py` y el clima no son tools nuevas; nada de Rubén ni de José. | — |

## Contrato

`planificar_ruta` mantiene todos sus campos y estados. Añade `clima` y `bici` **solo cuando el estado es `ok`** (`clima`, además, solo sin hora pedida):

```text
"clima": {"estado": "ok" | "no_disponible",
  # solo si ok:
  "temperatura_c": float, "precipitacion_mm": float, "codigo": int, "viento_kmh": float,
  "apto": bool, "motivos": [str, ...],      # motivos de no apto, vacío si apto
  "fuente": "Open-Meteo", "licencia": "CC BY 4.0"}
```

Además añade `bici` (en el resto de estados no existe la clave):

```text
"bici": {
  "estado": "ok" | "no_ofrecida" | "no_disponible",
  "motivo": str | None,          # solo en no_ofrecida por R3/R4 y en no_disponible (frase breve, RF-4/13)
  # solo si estado == "ok":
  "origen_estacion":  {"nombre": str, "bicis": int, "distancia_m": int},
  "destino_estacion": {"nombre": str, "huecos": int, "distancia_m": int},
  "tramos": [{"modo": "A pie"|"Bici"|"A pie", "desde": str, "hasta": str, "duracion_min": int}, ...],   # 3 tramos
  "duracion_min": int,           # suma de los tres
  "aviso": str,                  # RF-12: el de Google si llega, si no BICI_AVISO_GOOGLE
  "fuentes": {"estaciones": "EMT BiciMAD", "tiempos": "Google Routes"}
}
```

- `no_ofrecida` por R1 o R2: sin `motivo` y **sin párrafo** en el `mensaje` (RF-4).
- `no_ofrecida` por R3/R4: `motivo` con la frase de RF-4 y esa frase al final del `mensaje`.
- `no_disponible` (EMT o Google fallan, o error inesperado): `motivo` con la frase de RF-13 y esa frase al final del `mensaje`.
- `ok`: el `mensaje` termina con «Alternativa en bici (BiciMAD): …» con los tres tramos, el total, las estaciones con bicis/huecos «al consultar (pueden haber cambiado)», las fuentes y el aviso.

Ejemplo (valores ilustrativos): «Alternativa en bici (BiciMAD): 18 min en total (Google Routes). A pie 4 min hasta la estación «Puerta del Sol» (EMT BiciMAD: 6 bicis al consultar), en bici 11 min hasta la estación «Plaza de Castilla» (9 huecos libres al consultar) y a pie 3 min hasta el destino. La disponibilidad puede haber cambiado. Aviso: …».

## Lógica clave

```text
# (clima) en planificar_ruta._planificar_ruta, antes de consultar_google, solo si no hay hora pedida:
from src.tools.bicimad import clima_origen                # importación perezosa
clima = clima_origen(lugar_o)                             # <= 1 llamada a Open-Meteo; nunca lanza; {"estado": "no_disponible"} si falla
preferencia = "LESS_WALKING" if clima["estado"] == "ok" and not clima["apto"] else None
google = consultar_google(lugar_o, lugar_d, salida, llegada, preferencia_transito=preferencia)   # misma llamada, un campo más

clima_origen(origen):                                     # try/except local (RF-25)
  GET open-meteo ?latitude&longitude&current=temperature_2m,precipitation,weather_code,wind_speed_10m
  falta alguna variable o error -> {"estado": "no_disponible"}
  apto = not (precipitation > CLIMA_PRECIPITACION_MAX_MM or codigo in CLIMA_CODIGOS_NO_APTOS
              or temp < CLIMA_TEMP_MIN_C or temp > CLIMA_TEMP_MAX_C or viento > CLIMA_VIENTO_MAX_KMH)

# en planificar_ruta._planificar_ruta, rama ok con ruta (tras zona y precio), una sola llamada:
from src.tools.bicimad import alternativa_bici          # importación perezosa: evita la dependencia circular
bici, texto_bici = alternativa_bici(lugar_o, lugar_d, hora_pedida=bool(salida_rfc3339 or llegada_rfc3339), clima=clima)
mensaje += línea_clima + texto_bici ; resultado["clima"] = clima ; resultado["bici"] = bici

alternativa_bici(origen, destino, hora_pedida, clima):              # todo dentro de un try/except local (RF-15)
  si hora_pedida                                  -> no_ofrecida (R1), 0 llamadas
  si clima no ok o no apto                        -> no_ofrecida (R0), 0 llamadas, sin frase propia (RF-23, RF-24)
  d = distancia_m(origen, destino)                # haversine propio de bicimad.py
  si no BICI_DISTANCIA_MIN_M <= d <= MAX_M        -> no_ofrecida (R2), 0 llamadas
  estaciones = emt_estaciones()                   # <= 2 llamadas (login reutilizado + lista)
  si falla                                        -> no_disponible (RF-13)
  e_o = más cercana al origen con activa y bicis >= BICI_MIN_BICIS y distancia <= RADIO
  e_d = más cercana al destino con activa y huecos >= BICI_MIN_HUECOS y distancia <= RADIO
  si falta e_o o e_d, o e_o == e_d                -> no_ofrecida (R3/R4) con motivo, sin Google
  bici  = google(BICYCLE, e_o -> e_d)             # 1 llamada
  pie_1 = google(WALK, origen -> e_o)             # 1 llamada
  pie_2 = google(WALK, e_d -> destino)            # 1 llamada
  si alguna falla o no devuelve duración          -> no_disponible (RF-14), sin alternativa parcial (RF-11)
  aviso = aviso de Google si llega, si no BICI_AVISO_GOOGLE
  devolver ok con tramos, total, estaciones, aviso
```

Orden de las llamadas: EMT primero (barata y decide R3/R4), Google solo si hay estaciones; los tramos de Google se piden en secuencia y se corta al primer fallo.

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Módulo nuevo `src/tools/bicimad.py` con **cliente HTTP propio** (urllib) y sin tocar `_http_json` | Mover `_http_json` a un módulo común | Decisión aprobada: no tocar `planificar_ruta.py` más allá del enganche. **Deuda** anotada: dos clientes HTTP casi iguales; unificarlos al dividir `planificar_ruta.py`. |
| `bicimad.py` lleva su **propio haversine** (`distancia_m`) y no importa nada de `planificar_ruta.py`; `planificar_ruta.py` importa `bicimad` **de forma perezosa** en el enganche | Importar `distancia_m` de `planificar_ruta.py` (dependencia circular) | Decisión consciente (2026-10-20): evita el ciclo a costa de unas líneas duplicadas. Deuda: dos haversine; unificar al dividir `planificar_ruta.py`. |
| Regla de oferta en Python con constantes de `config.py` (R1–R4) | Que decida el LLM | Decisión aprobada. Determinista y testeable. |
| Google WALK para los tramos a pie (3 llamadas de Google en la bici, 4 en total) | Estimación local por distancia | Decisión aprobada: no estimar tiempos (coherente con la spec 004). |
| Token de la EMT reutilizado en memoria del proceso hasta su caducidad; lista de estaciones **sin caché** | Caché de estaciones | La disponibilidad es de ahora; el límite de la EMT (≤ 2) cuenta el login solo cuando no hay token vigente. Sin caché persistente (fuera de alcance). |
| `bici` solo en el estado `ok`; `mensaje` solo se amplía con párrafo si es `ok` o hay frase de RF-4/13 | Campo en todos los estados | Menos tests existentes afectados y sin ruido cuando no hay ruta. |
| Clima como funciones internas de `bicimad.py`, consultado **antes** de Google y solo sin hora pedida (RF-20, RF-27) | Una tool nueva; consultarlo dentro de `alternativa_bici` | Una tool exigiría allowlist y cambios de Rubén. Dentro de `alternativa_bici` llegaría tarde: `LESS_WALKING` debe ir en la petición de transporte público, que es anterior. |
| `LESS_WALKING` como parámetro opcional de `consultar_google` (`transitPreferences.routingPreference`) | Segunda petición a Google; filtrar rutas después | Sin llamadas extra; sin parámetro la petición no cambia (RF-22). |
| Sin dato de clima no se ofrece bici y la ruta no cambia (RF-25) | Suponer buen tiempo | No se inventan datos (coherente con RF-11 y la spec 004). |
| Umbrales, códigos WMO y texto de atribución en `config.py` | Constantes en el módulo | Los ajusta la persona responsable (RF-21). |
| Disponibilidad filtrada al elegir estación (bicis en origen, huecos en destino) | Estación más cercana a secas | Evita mandar a una estación vacía o llena (RF-6). |
| Google con máscara propia para bici y a pie (`routes.duration`, `routes.distanceMeters`, y `routes.warnings` si T1/demo confirman el campo) | Reutilizar `GOOGLE_FIELD_MASK` de transporte | Esa máscara es de `transitDetails`; la facturación depende de los campos. |
| Aviso de beta: el de Google si llega y, si no, texto fijo de `config.py` | Solo texto fijo | Cumple lo que exige Google sin depender de un campo no confirmado. |

## Estrategia de tests

Todos con `pytest`, sin red ni LLM, en `tests/test_bicimad.py`. **Dobles:** funciones de red del propio módulo (`_get_json`/`_post_json`, que se parchean donde se usan), `ahora`/tiempo si hiciera falta, y el `Escenario` de `tests/dobles_ruta.py` para el enganche de extremo a extremo (se reutiliza sin modificarlo). Las respuestas de la EMT en los tests son **dicts mínimos en el propio test** con los campos reales que fije T1 (no se guarda la respuesta completa ni archivos de datos).

- **Config y secretos (RNF):** constantes `BICI_*` definidas; credenciales solo de `os.getenv`; `.env.example` conserva `EMT_CLIENT_ID=` y `EMT_PASS_KEY=` sin valor; ninguna credencial en el resultado ni en el log.
- **Regla (RF-2, 3):** función pura con R1 (hora pedida), R2 (justo en el borde de 1 000 y 6 000 m, dentro y fuera); verifica 0 llamadas.
- **Estaciones (RF-5, 6, 7):** más cercana con bicis (se salta una vacía más cercana), más cercana con huecos (se salta una llena), inactiva descartada, radio máximo, misma estación (R4), ninguna.
- **Cliente EMT (RF-5, 13):** login y lista (≤ 2 llamadas), token reutilizado en la segunda consulta, credenciales ausentes (0 llamadas), 401, 429, timeout y JSON inválido → `no_disponible` sin excepción ni detalle; sin reintentos.
- **Google bici y a pie (RF-8, 9, 11, 12, 14):** cuerpo con `BICYCLE`/`WALK` y coordenadas de las estaciones, clave solo en cabecera, duración leída, aviso de Google si llega y texto fijo si no, error en cualquiera de los tres → `no_disponible` sin alternativa parcial, corte al primer fallo (nº de llamadas).
- **Orquestador (RF-1, 3, 4, 10, 15):** caso feliz con tres tramos, total, fuentes y aviso; `no_ofrecida` con y sin motivo; error inesperado (doble que lanza `KeyError`) → `no_disponible`, nunca excepción.
- **Enganche (RF-1, 16, 17, 18, 19):** de extremo a extremo con `Escenario`: el estado y los campos existentes no cambian, `bici` aparece solo en `ok`, el párrafo va al final del `mensaje` y en español, el RAG hace las mismas 2 llamadas, y límites: Nominatim ≤ 2, Google ≤ 4, EMT ≤ 2.
- **Aviso en la síntesis (RF-12), solo si T9 se aprueba:** el sintetizador con un LLM doble que omite el aviso aun así lo añade.
- **Clima (RF-20 a RF-28):** `apto_exterior` pura con cada causa (lluvia por `precipitation`, códigos de lluvia, llovizna, nieve, tormenta, < 5, > 32, > 30 km/h) y los bordes exactos (5, 32 y 30 son aptos); `clima_origen` con doble de la red (variables pedidas, una llamada, sin clave, falta una variable, error, timeout, 429, JSON inválido → `no_disponible` sin detalles); enganche con `Escenario`: no apto → el cuerpo de Google lleva `LESS_WALKING` y la ruta no cambia, apto o sin dato → el cuerpo es el de siempre, no apto o sin dato → `bici.no_ofrecida` con 0 llamadas a EMT y a Google de bici, hora pedida → 0 llamadas a Open-Meteo, línea de clima y atribución en el `mensaje`, campo `clima`, límites (Open-Meteo ≤ 1, Google transporte 1, total Google ≤ 4).
- **Manual (⚠️, una vez):** T1 (EMT), T12 (Open-Meteo, una llamada) y T10: trayecto que cumple la regla, uno con hora pedida y uno con la EMT sin credenciales.

## Tests existentes que pueden quedar obsoletos (revisar en T7, no antes)

| Test | Motivo |
|---|---|
| Tests que comparan el dict completo del estado `ok` de `planificar_ruta` (`test_planificar_ruta_*`, `test_tool_rutas_traza.py`, `test_integracion_spec005.py`, si los hay) | Aparece la clave `bici`. Se ajustan solo si fallan. |
| Tests con `Escenario` y trayecto Sol → Bernabéu (≈ 3,5 km, dentro de R2) | Con la regla R1–R4 cumplida, el enganche llamaría a la EMT y a Google; hay que parchear `alternativa_bici` o la red de bici en el `Escenario` (cambio en `tests/dobles_ruta.py`, a anotar) para que sigan sin red. |

*(T14, 2026-10-20)* Ningún test existente falló por el campo `clima` ni por la nueva consulta. Sí se cambió el doble `tests/dobles_ruta.py::Escenario`: parchea la red de Open-Meteo (`bicimad._get_json`) con una respuesta real de T12 (apto), registra `llamadas_meteo` y una `secuencia` completa de llamadas (`orden` no incluye Open-Meteo, para no alterar los tests existentes). `LESS_WALKING` va en `transitPreferences.routingPreference` (confirmado en la documentación de Google Routes, 2026-10-20).

*(T7, 2026-10-20)* Ningún test existente falló. `tests/dobles_ruta.py::Escenario` simula también la red de bici (login y estaciones de la EMT, Google de bici y a pie) y **desactiva la alternativa por defecto** (`bici` queda `no_ofrecida` sin llamadas); `Escenario.bici_real()` la activa para los tests de la spec 009. El resultado `ok` de los tests existentes ya lleva `clima` y `bici`.

*(T10, 2026-10-20; segundo intento de la demo 1: timeout del login de la EMT a los 10 s, sin estaciones)* Demos reales parciales (`demos.md`): el login de la EMT devolvió `code` "01" y no se pudo ver la alternativa real. Latencia medida: 7,8–8,8 s por consulta sin bici, dominada por el RAG (1,9–4,7 s por llamada); la alternativa añadirá lista de estaciones y 3 llamadas de Google de bici (sin medir).

## Riesgos

- **Latencia de la EMT (limitación conocida, 2026-10-20):** en T10 el login tardó 5,9 s (normalmente 0,14 s) y la lista de estaciones superó los 10 s. Plazos: login `EMT_TIMEOUT_S` = 10 s y lista `EMT_TIMEOUT_ESTACIONES_S` = 20 s. Con la EMT lenta la consulta puede tardar 25-30 s en el peor caso; si algo agota su plazo, `bici` queda `no_disponible` y la ruta de transporte nunca se pierde. **Mejora futura (no se hace ahora):** paralelizar la bici con el RAG; tampoco hay caché de estaciones.
- **Login de la EMT con dos códigos correctos:** "00" (token nuevo) y "01" (token vigente prorrogado, visto en T10). El cliente acepta ambos si `data[0].accessToken` existe; sin caducidad usa 3600 s (`EMT_TOKEN_CADUCIDAD_DEFECTO_S`). Falta comprobar con datos reales que "01" trae el token.
- **API de la EMT verificada en T1** (login v1 y estaciones). Quedan sin confirmar el significado de `no_available`, los límites de uso (el login devuelve `apiCounter`) y que `description` del login **incluye el token y el usuario**: el cliente nunca debe registrarla ni devolverla.
- **El sintetizador puede descartar el aviso de Google** (LLM; confirmado leyendo el código). Mitigación: T9 (opción A, archivo compartido). Si no se aprueba, RF-12 no se cumple en la respuesta final aunque sí en el JSON.
- **Cobertura y beta de Google BICYCLE/WALK.** Sin confirmar el texto ni el campo del aviso, ni la calidad en Madrid. Se revisa en la demo.
- **Latencia.** Hasta 5 peticiones HTTP secuenciales en la alternativa (2 EMT + 3 Google). Se acepta; paralelizar queda para después.
- **Disponibilidad obsoleta.** Entre la consulta y la llegada a la estación puede cambiar; se avisa en el mensaje.
- **Tests de otros afectados** por el campo `bici` y por la llamada real del enganche (tabla anterior).
- **Archivo compartido.** `config.py` lo tocan otras ramas: añadir al final de la sección de rutas y rebasar.
- **Nombres `EMT_*` ya existentes.** Estaban en `.env.example` antes de esta spec; si otra spec los usa con otro significado, hay que coordinarlo (no hay uso en el código actual).
- **Deuda técnica.** Dos clientes HTTP y dos haversine (`distancia_m` en `planificar_ruta.py` y en `bicimad.py`): se unifican en un módulo común al dividir `planificar_ruta.py`.
- **Clima.** Open-Meteo (verificado en open-meteo.com: gratuito sin clave para uso no comercial hasta 10.000 llamadas/día, atribución CC BY 4.0) es de uso no comercial; si el proyecto pasara a uso comercial hace falta clave de pago. La atribución puede perderse en la síntesis (T9); por eso irá también en el `README`. `LESS_WALKING` en Google puede devolver rutas más largas o con más trasbordos; es una preferencia, no una garantía.
- **Facturación de Google.** Cada alternativa añade 3 llamadas de Routes (BICYCLE/WALK pueden tener otra categoría); revisar en la consola.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Enganche; orquestador | `test_bicimad.py::test_alternativa_junto_a_la_ruta_sin_cambiar_su_estado` |
| RF-2 | Regla R1–R4 | `::test_regla_hora_pedida_no_ofrece`, `::test_regla_distancia_en_los_bordes` |
| RF-3 | Orden de las llamadas | `::test_r1_r2_no_llaman_a_nada`, `::test_r3_r4_no_llaman_a_google` |
| RF-4 | Frases de `no_ofrecida` | `::test_motivo_solo_en_r3_r4` |
| RF-5 | Cliente EMT | `::test_estaciones_una_consulta_y_token_reutilizado` |
| RF-6 | Elección de estaciones | `::test_estacion_con_bicis_y_con_huecos`, `::test_inactiva_y_radio` |
| RF-7 | Texto con disponibilidad | `::test_mensaje_indica_estaciones_y_disponibilidad` |
| RF-8 | Google BICYCLE | `::test_tramo_bici_una_llamada_con_bicycle` |
| RF-9 | Google WALK | `::test_tramos_a_pie_con_walk` |
| RF-10 | Total y fuentes | `::test_total_es_la_suma_y_etiqueta_fuentes` |
| RF-11 | Sin alternativa parcial | `::test_si_falla_un_tramo_no_hay_alternativa_parcial` |
| RF-12 | Aviso | `::test_aviso_de_google_o_texto_fijo`; en la síntesis, `test_sintetizador.py::test_avisos_obligatorios_sobreviven_a_la_sintesis` *(T9, si se aprueba)* |
| RF-13 | Fallo de la EMT | `::test_emt_falla_no_disponible_y_ruta_intacta` |
| RF-14 | Fallo de Google | `::test_google_falla_no_disponible` |
| RF-15 | Error inesperado | `::test_error_inesperado_no_rompe_la_ruta` |
| RF-16 | Contrato aditivo | `::test_campo_bici_solo_en_ok_y_campos_existentes_intactos` |
| RF-17 | Módulo y enganche | `::test_enganche_unico_en_planificar_ruta` (el módulo existe, `planificar_ruta.py` no contiene lógica de BiciMAD) |
| RF-18 | RAG sin cambios | `::test_el_rag_mantiene_sus_dos_llamadas` |
| RF-19 | Español | `::test_mensajes_de_bici_en_espanol` |
| RF-20 | `clima_origen` | `::test_clima_una_llamada_con_las_cuatro_variables`, `::test_sin_hora_pedida_consulta_el_clima_antes_de_google` |
| RF-21 | `apto_exterior` | `::test_apto_exterior_cada_causa_y_los_bordes` |
| RF-22 | `LESS_WALKING` | `::test_no_apto_pide_less_walking_sin_llamadas_extra`, `::test_apto_o_sin_dato_peticion_de_siempre` |
| RF-23 | Regla R0 | `::test_no_apto_o_sin_dato_no_ofrece_bici_ni_llama_a_la_emt` |
| RF-24 | Línea de clima | `::test_linea_de_clima_con_atribucion` |
| RF-25 | Fallo de Open-Meteo | `::test_open_meteo_falla_ruta_intacta_y_sin_bici`, `::test_error_inesperado_en_clima_no_rompe_la_ruta` |
| RF-26 | Contrato aditivo | `::test_campo_clima_solo_en_ok_sin_hora` |
| RF-27 | Hora pedida | `::test_hora_pedida_no_consulta_el_clima` |
| RF-28 | Sin otros usos | `::test_el_rag_mantiene_sus_dos_llamadas` (compartido con RF-18) |
| RNF Coste | Límites | `::test_limites_de_llamadas_emt_2_google_4_nominatim_2`; *(clima)* `::test_limite_open_meteo_1` |
| RNF Secretos | Config | `::test_credenciales_solo_del_entorno_y_env_example` |
