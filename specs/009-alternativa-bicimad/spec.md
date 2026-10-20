# Spec 009 — Alternativa en bici con BiciMAD en `planificar_ruta`

> Estado: **Aprobada** (2026-10-19, con las decisiones de «Dudas abiertas») · Fecha: 2026-10-19 · Renumerada de 008 a 009 el 2026-10-20 (la 008 ya es `008-clientes-cli-streamlit`)
> **Ampliación 2026-10-20: clima (RF-20 a RF-29). PENDIENTE DE APROBACIÓN.** El resto de la spec no cambia salvo RF-2, RF-3, RF-4, RF-16 y RF-17, marcados con *(clima)*.

## Contexto y objetivo

`planificar_ruta` (spec 004) calcula hoy una ruta en transporte público con Google Routes y le añade zona y precio del RAG. En trayectos cortos o medios por el centro de Madrid, ir en BiciMAD puede ser una alternativa razonable, pero el sistema no la considera. Queremos que, cuando proceda según una **regla determinista en Python** (no la decide el LLM), la respuesta incluya **junto a** la ruta en transporte público —sin sustituirla— una alternativa en bici: caminar hasta la estación de BiciMAD más cercana al origen que tenga bicis, pedalear hasta la estación más cercana al destino que tenga huecos libres y caminar hasta el destino.

Además, la alternativa solo se ofrece con buen tiempo: una función interna del mismo módulo consulta **Open-Meteo** (tiempo actual del origen). Con mal tiempo no se ofrece bici y la ruta en transporte público se pide a Google con menos tramos a pie.

Los datos de estaciones y disponibilidad salen de la **API de la EMT** (bloque BICIMAD); el tramo en bici, y los tramos a pie, de **Google Routes**. No se añaden archivos de datos al repositorio y no se toca `rag/` ni el corpus.

## Usuarios / actores

- Persona usuaria que pregunta por una ruta en Madrid (CLI o Streamlit, mismo grafo).
- Especialista `rutas` (de Rubén), que ya conserva el JSON de la herramienta tal cual; no cambia (ver Dudas abiertas).

## Historias de usuario

- H1: Como persona que se mueve por Madrid quiero ver una alternativa en BiciMAD cuando tenga sentido, para elegir entre bici y transporte público.
- H2: Como persona usuaria quiero saber de dónde cojo y dónde dejo la bici, y cuántas bicis y huecos hay, para no llegar a una estación vacía o llena.
- H3: Como persona usuaria quiero que, si BiciMAD no está disponible, la ruta en transporte público llegue igual.

## Requisitos funcionales (criterios de aceptación en EARS)

### Cuándo se ofrece

- RF-1: CUANDO `planificar_ruta` entrega una ruta en transporte público con estado `ok` y se cumple la regla de oferta (RF-2), EL SISTEMA añade a la respuesta una alternativa en bici con BiciMAD, junto a la ruta en transporte público y sin modificarla, sustituirla ni cambiar su estado.
- RF-2: EL SISTEMA decide en Python, de forma determinista y sin intervención del LLM, si ofrece la alternativa. **Regla propuesta (pendiente de aprobación):** se ofrece solo si se cumplen **todas**:
  - R1. La persona **no** ha pedido hora de salida ni de llegada (la disponibilidad de bicis es la de ahora).
  - R2. La distancia en línea recta entre el origen y el destino está entre `BICI_DISTANCIA_MIN_M` (valor inicial 1 000 m: por debajo es mejor ir a pie) y `BICI_DISTANCIA_MAX_M` (valor inicial 6 000 m).
  - R3. Existe una estación de origen con bicis y una estación de destino con huecos libres, ambas a no más de `BICI_ESTACION_RADIO_MAX_M` (valor inicial 500 m) del punto correspondiente (RF-6).
  - R4. La estación de origen y la de destino son distintas.
  - R0 *(clima)*. El tiempo actual del origen es apto para exterior (RF-21). Sin dato de clima no se cumple (RF-25).
- RF-3: SI no se cumple R0, R1 o R2, ENTONCES EL SISTEMA no llama a la API de la EMT ni a Google para la bici. SI no se cumple R3 o R4, ENTONCES no llama a Google para la bici (solo se habrá llamado a la EMT).
- RF-4: SI se rechaza la alternativa por R3 o R4, ENTONCES EL SISTEMA lo indica en una frase breve («No hay estaciones de BiciMAD con bicis/huecos cerca de …») sin afectar a la ruta en transporte público; si se rechaza por R0, R1 o R2, no dice nada de la bici (el clima ya lo explica su propia línea, RF-24). *(clima)*

### Estaciones y disponibilidad

- RF-5: EL SISTEMA obtiene las estaciones de BiciMAD y su disponibilidad de la API de la EMT, con una sola consulta de la lista de estaciones por petición de ruta, y no guarda copia de los datos en el repositorio.
- RF-6: EL SISTEMA calcula localmente (distancia en línea recta, sin llamadas) la estación más cercana al origen que esté activa y tenga al menos `BICI_MIN_BICIS` bicis disponibles, y la más cercana al destino que esté activa y tenga al menos `BICI_MIN_HUECOS` huecos libres. La estación más cercana sin disponibilidad no se usa.
- RF-7: EL SISTEMA indica de cada estación elegida su nombre y las bicis (la de origen) o los huecos libres (la de destino) que había al consultar, avisando de que la disponibilidad puede haber cambiado.

### Tiempos y trayecto

- RF-8: EL SISTEMA calcula el tramo en bici entre las dos estaciones con Google Routes (`travelMode=BICYCLE`), con una sola llamada.
- RF-9: EL SISTEMA calcula los tramos a pie (origen → estación de origen y estación de destino → destino) con Google Routes (`travelMode=WALK`), una llamada por tramo. *(Decidido: Google, no estimación local.)*
- RF-10: EL SISTEMA muestra el tiempo total de la alternativa (suma de los tres tramos) y el tiempo de cada uno, etiquetando la fuente: BiciMAD (EMT) para estaciones y disponibilidad, Google Routes para tiempos.
- RF-11: EL SISTEMA no estima ni inventa ningún tiempo ni trayecto: si falla cualquiera de los tres tramos, no se muestra la alternativa, ni siquiera parcial.
- RF-12: CUANDO muestra la alternativa, EL SISTEMA incluye siempre el aviso de beta que exige Google para las rutas en bici y a pie: el texto que devuelva Google si la respuesta lo trae y, si no, un texto fijo con el mismo sentido («Las rutas a pie y en bici están en fase beta y pueden carecer de aceras, caminos peatonales o carriles bici claros»). Sin aviso no se muestra la alternativa.

### Fallos

- RF-13: SI la API de la EMT falla (credenciales ausentes, autenticación rechazada, error, timeout, límite de peticiones o respuesta no válida), ENTONCES EL SISTEMA no ofrece la alternativa, entrega la ruta en transporte público con su zona y su precio como si no existiera esta funcionalidad, no reintenta e informa en una frase breve de que la alternativa en bici no está disponible ahora, sin detalles internos ni credenciales.
- RF-14: SI Google falla en cualquiera de las llamadas de la bici (error, falta de conexión, sin ruta o respuesta no válida), ENTONCES EL SISTEMA actúa como en RF-13.
- RF-15: SI ocurre un error inesperado dentro de la alternativa en bici, ENTONCES EL SISTEMA lo captura en el propio módulo, lo registra en el log interno y actúa como en RF-13: nunca produce `error_interno` de la ruta principal.

### Contrato y estructura

- RF-16: EL SISTEMA añade al resultado de `planificar_ruta` un campo **nuevo y aditivo** `bici` (`estado`: `ok` | `no_ofrecida` | `no_disponible`, y, si es `ok`, estaciones, tramos, tiempo total, aviso y fuentes), sin cambiar ni retirar ningún campo existente ni el valor de `estado`; *(clima: añade también `clima`, RF-26)* el `mensaje` añade al final un párrafo «Alternativa en bici (BiciMAD): …» solo si `bici.estado == "ok"` o si hay una frase de RF-4 o RF-13.
- RF-17: EL SISTEMA implementa la alternativa y el clima en un **módulo nuevo** (`src/tools/bicimad.py`); `src/tools/planificar_ruta.py` solo añade dos puntos de enganche *(clima: antes era uno)*: la consulta del clima antes de pedir la ruta a Google y la alternativa en la rama `ok`, más el parámetro opcional de `consultar_google` (RF-22), sin crecer con lógica de BiciMAD ni de clima.
- RF-18: EL SISTEMA no consulta el RAG ni cambia las llamadas al RAG por esta funcionalidad (se mantienen RF-46 y RF-49 de la spec 004).
- RF-19: EL SISTEMA redacta en español todos los mensajes de la alternativa.

### Clima (ampliación 2026-10-20)

- RF-20: CUANDO la persona **no** ha pedido hora de salida ni de llegada, EL SISTEMA consulta a **Open-Meteo** el tiempo actual del **origen** (coordenadas del candidato elegido) con una sola llamada, **antes** de pedir la ruta en transporte público a Google. Variables (`current`): `temperature_2m` (°C), `precipitation` (mm), `weather_code` (código WMO) y `wind_speed_10m` (km/h, unidad por defecto). Es una función interna de `src/tools/bicimad.py`: no es una tool, no se registra en la allowlist y no la ve el LLM.
- RF-21: EL SISTEMA decide en Python si el tiempo es **apto para exterior**. **NO es apto** si se cumple alguna de: hay precipitación (`precipitation` > `CLIMA_PRECIPITACION_MAX_MM`, valor inicial 0) o el código WMO es de llovizna o lluvia (51–57, 61–67, 80–82), nieve (71–77, 85–86) o tormenta (95–99); temperatura < `CLIMA_TEMP_MIN_C` (5 °C) o > `CLIMA_TEMP_MAX_C` (32 °C); viento > `CLIMA_VIENTO_MAX_KMH` (30 km/h). Umbrales y lista de códigos son constantes de `config.py`, ajustables por la persona responsable.
- RF-22: SI el tiempo **no** es apto, ENTONCES EL SISTEMA pide la ruta en transporte público a Google con `LESS_WALKING` (en `transitPreferences.routingPreference`), sin ninguna llamada adicional; en cualquier otro caso (apto, sin dato o con hora pedida) la petición es la de siempre.
- RF-23: SI el tiempo es apto, ENTONCES EL SISTEMA aplica la regla de oferta de la bici (RF-2). SI no es apto, ENTONCES no ofrece bici (`bici.estado = "no_ofrecida"`, sin llamadas a la EMT ni a Google para bici).
- RF-24: CUANDO ha obtenido el clima, EL SISTEMA añade al `mensaje` una línea con el tiempo («Tiempo en el origen ahora: 14 °C, sin precipitación, viento 12 km/h.»), indicando, si no es apto, el motivo y que la ruta se pidió con menos tramos a pie, y la atribución «Datos meteorológicos de Open-Meteo.com (CC BY 4.0)».
- RF-25: SI Open-Meteo falla (error, timeout, límite de peticiones, respuesta no válida o falta alguna de las cuatro variables), ENTONCES EL SISTEMA no reintenta, entrega la ruta en transporte público **intacta** (petición de Google y resultado como sin esta funcionalidad), **no ofrece bici** (sin dato de clima no se asume buen tiempo) y no añade línea de clima ni detalles internos; `clima.estado = "no_disponible"`. Un error inesperado en esta función se captura, se registra en el log interno y se trata igual (nunca `error_interno`).
- RF-26: EL SISTEMA añade al resultado el campo **aditivo** `clima` (solo en estado `ok` y sin hora pedida): `estado` (`ok` | `no_disponible`) y, si es `ok`, `temperatura_c`, `precipitacion_mm`, `codigo`, `viento_kmh`, `apto` (bool), `motivos` (lista de textos breves), `fuente` («Open-Meteo»), `licencia` («CC BY 4.0»).
- RF-27: SI la persona ha pedido hora de salida o de llegada, ENTONCES EL SISTEMA no consulta el clima, no aplica `LESS_WALKING` ni añade línea de clima (el tiempo actual no describe esa hora; no hay predicción).
- RF-28: EL SISTEMA no usa el clima en ningún otro cálculo: zona, precio y RAG no cambian (se mantienen RF-18, RF-46 y RF-49 de la spec 004).

## Requisitos no funcionales

- **Coste (límite de llamadas por consulta de ruta).** *(clima)* Open-Meteo ≤ 1 y solo sin hora pedida (RF-20, RF-27); `LESS_WALKING` no añade llamadas a Google. Con la alternativa: Nominatim ≤ 2 y RAG ≤ 2 (sin cambios); API de la EMT ≤ 2 (inicio de sesión, que se reutiliza mientras no caduque, y lista de estaciones); Google ≤ 4 (1 transporte público + 1 bici + 2 a pie). Sin alternativa (RF-3), 0 llamadas adicionales a la EMT o a Google en R1/R2, y como mucho las de la EMT en R3/R4. Sin reintentos.
- **Secretos.** Las credenciales de la EMT se leen solo del entorno (`.env`). Los nombres `EMT_CLIENT_ID` y `EMT_PASS_KEY` **ya figuran sin valor en `.env.example`** (no hay que añadirlos; un test vigila que sigan). No aparecen en el código, el repositorio, el resultado, la traza ni el log. La clave de Google es la ya existente.
- **Configuración.** Distancias mínima y máxima, radio de estación, mínimos de bicis y huecos, URLs, timeouts y texto fijo del aviso viven en `config.py`.
- **Dependencias.** Ninguna nueva (HTTP con la librería estándar, como en la spec 004). *(clima)* Open-Meteo no usa clave; verificado en open-meteo.com: gratuito sin clave para uso no comercial hasta 10.000 llamadas/día, atribución CC BY 4.0 (T12, 2026-10-20). La atribución irá también en el `README`, por si el sintetizador la omite.
- **Tests.** Ninguno llama a la EMT, a Google, al RAG ni al LLM: usan dobles.
- **Idioma.** Español.
- **Tiempo de respuesta.** La alternativa añade hasta 5 llamadas HTTP secuenciales; cada una con timeout propio. **Plazos de la EMT (2026-10-20):** login `EMT_TIMEOUT_S` = 10 s y lista de estaciones `EMT_TIMEOUT_ESTACIONES_S` = 20 s (la lista, de unas 678 estaciones, es la llamada más pesada; en T10 el login tardó 5,9 s y la lista superó los 10 s). **Limitación conocida:** con la EMT lenta la consulta puede tardar 25-30 s en el peor caso (hoy, unos 8 s sin bici); un timeout de la EMT o de Google de bici deja la alternativa en `no_disponible`, pero la ruta de transporte nunca se pierde. Paralelizar la bici con el RAG queda como mejora futura (no se hace ahora; tampoco caché).

## Casos límite

- Hora de salida o de llegada pedida, o trayecto demasiado corto o largo: no se ofrece y no se llama a nada (RF-2, RF-3).
- Estación de origen y de destino la misma, o ninguna con bicis/huecos en el radio: sin Google y con frase breve (RF-3, RF-4).
- La estación más cercana está vacía o llena: se usa la siguiente más cercana con disponibilidad dentro del radio (RF-6).
- EMT sin credenciales, 401, 429, timeout o JSON inválido: RF-13.
- Google sin ruta ciclable o con error en cualquiera de los tres tramos: RF-11, RF-14.
- Ruta en transporte público sin éxito (`sin_ruta`, `ruta_no_calculada`) o dirección no resuelta: no se ofrece bici (fuera de alcance).
- Error inesperado en el módulo: RF-15.
- *(clima)* Lluvia, nieve, tormenta, < 5 °C, > 32 °C o viento > 30 km/h: sin bici, `LESS_WALKING` y línea de clima (RF-21 a RF-24). Justo en el umbral (5 °C, 32 °C, 30 km/h): apto.
- *(clima)* Open-Meteo caído o con una variable ausente: ruta intacta, sin bici y sin línea de clima (RF-25).
- *(clima)* Hora pedida: sin clima (RF-27).

## Fuera de alcance

- Precio o tarifas de BiciMAD (no están en el corpus; no se toca `rag/`).
- Reservar, desbloquear o gestionar bicis; bici propia, patinete o cualquier otro modo.
- Ofrecer la bici cuando la ruta en transporte público falla o no existe.
- Alternativa con hora de salida o de llegada futura (la disponibilidad es la actual).
- Guardar estaciones en el repositorio, caché persistente o actualización periódica en segundo plano.
- Que el LLM o el supervisor decidan si se ofrece la bici.
- Cambiar `rag/`, el corpus o las specs anteriores.
- *(clima)* Predicción por fecha u hora, opción solo a pie, preferir metro sobre autobús, una tool de clima, cambios en la allowlist y cambios en archivos de Rubén (`src/agents/rutas.py`, grafo) o de José.

## Criterios de finalización

- Todos los RF con test en verde (`pytest`) con dobles para la EMT y Google.
- *(clima)* RF-20 a RF-28 con test en verde con dobles de Open-Meteo.
- Demo manual (⚠️ gasta API, una sola vez): un trayecto que cumpla la regla, uno que no (p. ej. con hora pedida) y uno con la EMT sin credenciales o caída.

## Dudas abiertas

### Decisiones cerradas (2026-10-19)

- Regla de oferta R1–R4 aprobada tal como está; los valores (1 000 m, 6 000 m, 500 m, 1 bici, 1 hueco) son constantes de `config.py`. Sin regla R5: se muestran siempre las dos opciones con sus tiempos.
- Tramos a pie con Google WALK (límite de Google 4).
- Enganche mínimo en `src/tools/planificar_ruta.py` y cambios en `config.py`; `.env.example` ya tiene los nombres de la EMT.
- El módulo nuevo (`src/tools/bicimad.py`) lleva su **propio cliente HTTP mínimo** y no toca `_http_json`. **Deuda técnica para la división futura de `planificar_ruta.py`:** hay dos clientes HTTP casi iguales; al dividir el archivo, unificar en un módulo común (junto con `distancia_m`, que `bicimad.py` reutiliza de `planificar_ruta.py`).

### Pendiente

- [VERIFICADO — API de la EMT, T1, 2026-10-20] Ver `verificacion-emt.md`. Login `GET /v1/mobilitylabs/user/login/` con las cabeceras `X-ClientId` y `passKey` → HTTP 200 y `code` "00" (token nuevo) o "01" (la `description` dice «Token extend into control-cache»: la EMT devuelve el token que ya estaba vigente; observado en T10), token en `data[0].accessToken` con caducidad `tokenSecExpiration` = 86 400 s (si falta, el cliente supone `EMT_TOKEN_CADUCIDAD_DEFECTO_S` = 3600 s). Estaciones `GET /v1/transport/bicimad/stations/` con la cabecera `accessToken` → 678 estaciones en `data`. Campos reales: `id`, `name`, `number`, `address`, `geometry.coordinates` (**[longitud, latitud]**), `dock_bikes` (bicis disponibles), `free_bases` (huecos libres), `total_bases`, `activate`, `no_available`, `virtualDelete`. Diferencias con lo supuesto: no hay un campo único «activa» (ver siguiente punto), las coordenadas vienen en orden lon/lat, y la `description` del login **contiene el token y el nombre de usuario** (nunca debe registrarse ni devolverse).
- [PENDIENTE — criterio de «activa»] La estación es `activa` si `activate == 1`, `no_available == 0` y `virtualDelete` es falso; el significado de `no_available` (se supone 1 = no disponible) y la distribución de `activate` no se han comprobado (la verificación no guardó la lista completa). Se confirma en T4 con dobles y en la demo T10.
- [VERIFICACIÓN PENDIENTE — Google] La documentación de Google indica que las rutas a pie, en bici y en dos ruedas están en beta y exige mostrar una advertencia (sentido: pueden faltar aceras, caminos peatonales o carriles bici claros). No se pudo confirmar el texto literal ni si llega en un campo de la respuesta (`routes.warnings`), ni la cobertura de `BICYCLE` en Madrid; de ahí el texto fijo de respaldo en RF-12. Se comprobará con una respuesta real en la demo manual.
- [NECESITA ACLARACIÓN — el sintetizador puede descartar el aviso] Comprobado leyendo `src/sintetizador.py` y `src/modelos.py` (sin modificarlos): el sintetizador es un LLM (Gemini) al que se le pide «Resume en español sencillo únicamente la información disponible» y se le pasa el JSON completo de la herramienta. Por tanto **puede omitir el párrafo de la alternativa o el aviso de beta de Google (RF-12)**; solo el respaldo determinista (cuando falla el LLM) vuelca el JSON entero. Esto incumple RF-12 de cara a la persona usuaria. Opciones: (A) un cambio pequeño en `src/sintetizador.py` (spec 005, archivo compartido; coordinar): tras el texto del LLM, añadir de forma determinista los avisos obligatorios que traigan los resultados (`bici.aviso`); (B) cambiar el prompt del sintetizador en `src/modelos.py` (más frágil: sigue dependiendo del LLM); (C) aceptar el riesgo. Recomendación: **A**. Queda como tarea bloqueada (T9) hasta decidirlo y coordinarlo con quien mantiene el grafo.
### Clima: verificado y pendiente (2026-10-20)

- [VERIFICADO en la documentación de Open-Meteo, 2026-10-20] Variables `current`: `temperature_2m`, `precipitation`, `rain`, `snowfall`, `weather_code`, `wind_speed_10m`; viento en km/h por defecto; códigos WMO: llovizna 51–57, lluvia 61–67 y chubascos 80–82, nieve 71–77 y chubascos de nieve 85–86, tormenta 95–99. Se fijan `temperature_2m`, `precipitation`, `weather_code` y `wind_speed_10m`.
- [VERIFICADO — T12, 2026-10-20] Ver `verificacion-open-meteo.md`: `current` trae `time`, `interval` (900 s), `temperature_2m` (°C), `precipitation` (mm), `weather_code` (WMO) y `wind_speed_10m` (km/h). `precipitation` se atribuye al intervalo de 15 minutos (`interval` = 900); no confirmado en la documentación. Las coordenadas se ajustan a la rejilla del modelo (40.4176, -3.7394 para Sol).
- [VERIFICADO] Open-Meteo: verificado en open-meteo.com: gratuito sin clave para uso no comercial hasta 10.000 llamadas/día, atribución CC BY 4.0. La atribución irá también en el `README` además de en el `mensaje` (RF-24), por si el sintetizador la omite.
- [PENDIENTE — T14] En Google Routes `LESS_WALKING` va en `transitPreferences.routingPreference`, no en el `routingPreference` de nivel superior (que es de tráfico). Comprobar en su documentación; los tests no hacen llamadas reales.
- [PENDIENTE — decisión] La atribución de Open-Meteo puede perderse en la síntesis igual que el aviso de Google (RF-12): se propone cubrirla con la misma opción A de T9. Sin T9, queda «en el JSON y en el `mensaje`, no garantizada en la síntesis».
- [VERIFICADO — T10, 2026-10-20, ver `demos.md`] Con datos reales: `LESS_WALKING` en `transitPreferences.routingPreference` es aceptado por Google y cambia la ruta (20 min con Cercanías y 15 min a pie → 36 min con autobús y 11 min a pie); la línea de clima con atribución aparece con tiempo apto y no apto; con hora pedida no hay clima, ni bici, ni llamadas a la EMT ni a Google de bici; sin credenciales de la EMT no hay llamadas a la EMT y la ruta llega intacta con la frase de no disponible (RF-13).
- [CORREGIDO 2026-10-20 — login "01"] El login de la EMT respondió HTTP 200 con `code` "01" (esta mañana, "00") y `bici` quedó `no_disponible` con la ruta intacta (RF-13 comprobado con el servicio real). Un diagnóstico posterior mostró que "01" es un login correcto con el token ya vigente; el cliente ahora lo acepta (con test). **Pendiente de comprobar con datos reales** que `data[0]` de "01" trae `accessToken`; repetir la demo 1 lo confirma. [PENDIENTE — T10, repetir la demo 1; segundo intento 2026-10-20: el login de la EMT agotó los 10 s, `TimeoutError`, y `bici` quedó `no_disponible` con la ruta intacta (RF-13 comprobado otra vez con el servicio real)] Siguen sin contrastar con datos reales: el significado de «estación activa» (`activate`, `no_available`, `virtualDelete`), si Google devuelve `routes.warnings` para bici y a pie, la cobertura de `BICYCLE` en Madrid y el total de la alternativa. Ver `demos.md`. `time` de Open-Meteo viene en UTC si no se pide `timezone` (no se usa).
- [DECISIÓN propuesta] El clima se consulta solo sin hora pedida (RF-27), porque `LESS_WALKING` y la bici dependen del tiempo de ahora.
- [PARA EL PLAN, resuelto; revisado 2026-10-20] `bicimad.py` tiene su propio haversine y no importa `planificar_ruta.py`; `planificar_ruta.py` importa `bicimad` de forma perezosa. Evita la dependencia circular.
