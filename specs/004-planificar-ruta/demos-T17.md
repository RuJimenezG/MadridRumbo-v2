# Demos manuales T17 — Spec 004 (2026-10-16)

> Ejecución única con APIs reales (Nominatim, Google Routes, RAG real con el índice existente, Gemini). Script temporal no versionado, ya borrado.
> **Peticiones:** Google Routes 3 (tope 5) · RAG vía `planificar_ruta` 3 llamadas (todas de zona; ninguna llegó a la de precio) · Nominatim 16 a ≤1/s · Gemini: 3 llamadas del RAG y 6 turnos del grafo (más 3 de diagnóstico). Ningún 429; un 503 `UNAVAILABLE` (alta demanda) en el diagnóstico del supervisor.
> **Veredicto: T17 NO queda cerrada.** Casos 1, 3 y 7 no coinciden con lo esperado. No se ha arreglado nada: queda anotado.

## Resumen

| # | Caso | ¿Coincide? | RF |
|---|---|---|---|
| 1 | Ruta completa Atocha → Puerta del Sol | **No**: origen ambiguo; con otra ruta, el RAG no da zona ni precio | RF-8, RF-19, RF-21 |
| 2 | Hora de llegada mañana 09:30 | **Sí** (ruta + «El primer transporte sale…»); zona/precio sin evidencia (ver caso 1) | RF-39, RF-44 |
| 3 | Título libre «abono joven» | **No verificable**: el RAG no devolvió zona, no se llegó a la pregunta de precio | RF-46, RF-52, RF-53 |
| 4 | Fuera de cobertura (Barcelona) | **Sí** | RF-4, RF-5 |
| 5 | Dirección ambigua | **Sí** (con una pega cosmética) | RF-8 |
| 6 | Nominatim sin red (doble) | **Sí** | RF-40 |
| 7 | Grafo con LLM real | **No**: el supervisor casi siempre cae al fallback; `rutas` no se ejecutó | RF-26, RF-28, RF-29 |

## Caso 1 — Ruta completa (no coincide)

- **Entrada:** `origen="Atocha, Madrid"`, `destino="Puerta del Sol, Madrid"`, salida ahora, billete sencillo.
- **Obtenido:** `ambigua`. Tres candidatos para Atocha: «Atocha, Paseo de la Infanta Isabel…», «Atocha, Arganzuela…» y «Atocha-Cercanías…». Sin llamadas a Google ni RAG.
- **1b:** con la dirección exacta del primer candidato sigue `ambigua` (Atocha / Estación del Arte / Atocha-Cercanías). **1c:** con el texto exacto del candidato «Atocha-Cercanías, …» → `direccion_no_encontrada` (Nominatim no resuelve ese texto largo). Ninguna llegó a Google.
- **Esperado:** ruta, zona y precio. **Valoración:** el comportamiento ambiguo es el de RF-8; lo que no se cumple es el objetivo de la demo «Atocha → Sol con ruta, zona y precio».
- **Ruta completa alternativa (casos 2, 3 y 3b):** la ruta llega siempre, pero el RAG responde «No lo sé, no está en los documentos.» a la pregunta de zona (`¿Qué zona tarifaria corresponde a un trayecto entre Sol y Nuevos Ministerios?` y `… entre Plaza Elíptica y Nuevos Ministerios?`). Resultado: `zona = sin_evidencia`, `precio = omitida`, mensaje «Faltan la zona y el precio: no se pudieron determinar con el corpus.» Es lo que pide RF-52, pero **con el RAG real no se obtuvo ninguna zona ni ningún precio**: la pregunta de zona construida con nombres de parada (RF-19/RF-20) no funciona con este corpus.

## Caso 2 — Hora de llegada (coincide)

- **Entrada:** Sol → Bernabéu, `hora_llegada=2026-10-17T09:30`.
- **Obtenido:** `estado=ok`, cabecera «Llegada: 17/10/2026 09:30 · Título: billete sencillo.», ruta de 20 min (Cercanías C4b Sol → Nuevos Ministerios + tramos a pie), **«El primer transporte sale el 17/10/2026 a las 09:04 desde Sol (Google Routes).»**; `hora_salida = salida_resultante = 2026-10-17T09:04+02:00`, `hora_llegada = 2026-10-17T09:30+02:00` (contrato de T19). 1 llamada a Google.
- **Observación:** muchos tramos «A pie 0 min» en el trayecto (ruido en el mensaje; no es un incumplimiento).

## Caso 3 — Título libre «abono joven» (no verificable)

- **Entradas:** Sol → Bernabéu y Plaza Elíptica → Bernabéu, `titulo="abono joven"`.
- **Obtenido:** `ok`, `titulo="abono joven"` en cabecera, una sola llamada al RAG (zona) en cada ruta; zona `sin_evidencia`, precio `omitida`; mensaje «Faltan la zona y el precio…».
- **Qué quedó sin comprobar (objetivo de T17 para RF-53):** la respuesta del RAG a la plantilla actual de `PREGUNTA_PRECIO` («¿Cuál es el precio del {titulo} en la zona indicada a continuación? {zona}») y si una zona entera cabe en `ZONA_LONGITUD_MAX = 200`: nunca hubo texto de zona (longitud 0). **Pendiente.**

## Caso 4 — Fuera de cobertura (coincide)

- **Entrada:** Sol → «Carrer de Pelai, Barcelona». **Obtenido:** `fuera_cobertura`, «La dirección de destino «Carrer de Pelai, Barcelona» está fuera de la cobertura de MadridRumbo.», 0 Google, 0 RAG. Confirma la corrección de T16 (sin `bounded=1`).

## Caso 5 — Ambigua (coincide, con una pega)

- **Entrada:** «Calle Mayor, Madrid» → Sol. **Obtenido:** `ambigua`, tres opciones, sin Google ni RAG.
- **Pega:** las opciones 2 y 3 tienen el mismo texto («Calle Mayor, Barrio de los Austrias, Sol…»): puntos a más de `RADIO_MISMA_UBICACION_M` con el mismo nombre. Cosmético.

## Caso 6 — Nominatim sin red (coincide)

- **Doble** que lanza `URLError` en Nominatim (no se cortó la red). **Obtenido:** `geocodificacion_fallida`, «No he podido localizar las direcciones ahora mismo. Inténtalo de nuevo más tarde.», 0 Google, 0 RAG.

## Caso 7 — Grafo con LLM real (no coincide)

Sesión única (`src.agent.procesar_turno`, un `thread_id` nuevo por frase). `planificar_ruta` **no se llamó en ninguna**.

| Frase | Supervisor | Resultado |
|---|---|---|
| «quiero ir a Sol» | fallback determinista | Respuesta genérica «No hay información disponible…». No se pide el origen (RF-26 no demostrado). En el diagnóstico, el modelo devolvió **503 UNAVAILABLE**. |
| «¿cuánto cuesta el abono joven?» | decisión válida → **auxiliar** | Intentó `describir_imagen` (error) y respondió que no hay importes legibles. Enrutado al especialista equivocado (se esperaba tarifas/RAG). `planificar_ruta` no llamada (RF-29 OK en eso). |
| «salgo mañana a las 8» | fallback determinista | Sin especialista; respuesta genérica. |
| «voy a comprar un abono» | fallback determinista | Enruta a `rag_ask` («No se encontró la información…»). No es ruta: `planificar_ruta` no llamada (correcto). |
| «salgo mañana a las 8 de la Puerta del Sol al Estadio Santiago Bernabéu» | fallback determinista | Sin `rutas`; respuesta genérica. |

- **Causa observada del fallback (diagnóstico de la última frase):** el modelo devolvió `{'roles': ['rutas', 'horarios']}` con **comillas simples** (no es JSON válido), `_parsear_objeto` lo rechaza y el supervisor cae al fallback. Con comillas válidas la decisión habría sido correcta. Otra vez, el fallo fue un 503 de Gemini.
- **Consecuencia:** el especialista `rutas` con LLM real (faltan datos RF-26, dato aportado después RF-28, hora relativa RF-50/50b) **no se ha podido comprobar**. Lo que sí se ve: el supervisor real depende de que el modelo devuelva JSON estricto.

## Qué queda abierto (sin arreglar)

1. Zona del RAG: la pregunta construida con paradas devuelve siempre abstención con este corpus → ruta sin zona ni precio (caso 1/3). Afecta a RF-19, RF-20, RF-46, RF-53.
2. Supervisor con LLM real: parseo de JSON con comillas simples y 503 → fallback; `rutas` sin ejecutar.
3. Enrutado de «¿cuánto cuesta el abono joven?» al especialista auxiliar.
4. Atocha como origen siempre ambiguo (RF-8 correcto, pero la demo pedida no se puede hacer con ese nombre).


---

# Diagnóstico de T17 (2026-10-16, sin arreglar nada)

> Peticiones: **Google 0** · Nominatim 9 · consultas al RAG 6 (retrieve + generate; la A4 recibió 503 al generar) · turnos del grafo con LLM real 6 (el supervisor se sustituye por uno fijo `["rutas"]`). Sin 429; se vieron varios **503 UNAVAILABLE** de Gemini (alta demanda). Scripts temporales borrados.

## A. Zona con el RAG real

**Pregunta exacta que envía la herramienta:** `config.PREGUNTA_ZONA` = «¿Qué zona tarifaria corresponde a un trayecto entre {origen} y {destino}?», con `origen` = parada de subida del **primer** tramo de transporte de Google y `destino` = parada de bajada del **último** (si Google falla: municipios de Nominatim). En el caso 2 fue «…entre Sol y Nuevos Ministerios?».

| Variante | Pregunta | Chunks recuperados (top-4) | Respuesta |
|---|---|---|---|
| A1 producción, paradas de Google | «…entre Sol y Nuevos Ministerios?» | CSV 312 (Puerta del Sol, Tribunal…), 2 de `crtm_billetes_tarifas.md` (zonas), CSV 306 (Plaza de Castilla…Sol…) | **No lo sé** |
| A2 producción, municipios | «…entre Madrid y Madrid?» | 4 de `crtm_billetes_tarifas.md` (incl. «La zona A: coincide prácticamente con el término municipal de Madrid») | **«La zona A coincide prácticamente con el término municipal de Madrid.»** |
| A3 dos paradas que sí están en el índice | «…entre Plaza de Castilla y Atocha?» | CSV 311 (Atocha-Renfe, Intercambiador de Plaza de Castilla), CSV 306, 2 de zonas | **No lo sé** |
| A4 una parada, nombre corto | «¿Qué zona tarifaria tiene la parada de metro Sol?» | CSV 312, 306, 311, 307 | 503 al generar (sin respuesta) |
| A5 parada que no está en el índice | «…la parada de metro Nuevos Ministerios?» | CSV 311, 306, 307, 312 (ninguno la contiene) | **No lo sé** |
| A6 una parada, estilo del CSV | «Zona tarifaria de la parada SOL de Metro» | CSV 312, 306, 311, 309 | **«A»** |

**Qué obtiene zona y qué no:** funcionan la consulta por **municipio** (A2) y la de **una sola parada con el nombre del CSV** (A6). Fallan la pregunta exacta de producción con **dos paradas** (A1), incluso con las dos en el índice (A3), y la parada ausente (A5).

**Causas probables:**
1. **El índice solo tiene 40 filas del CSV.** `config.MAX_FILAS_CSV = 40`: de las 22 404 paradas de `Paradas CRTM.csv` (Metro 530, Cercanías 97, Metro Ligero 71, autobuses el resto) solo están indexadas las 40 primeras, todas Metro zona A, en 7 chunks («bloque_csv» de ≤6 paradas, ~350–550 caracteres). Faltan Nuevos Ministerios, Plaza Elíptica, todas las de Cercanías (Atocha-Cercanías, Nuevos Ministerios Cercanías…), Bernabéu, etc.
2. **La zona sí está por parada en el CSV y en cada chunk** (cabecera «Tipo de transporte: Metro / Zona tarifaria: A» y una línea por parada con ID, nombre y descripción), así que una consulta de **una** parada indexada se responde (A6).
3. **La pregunta «trayecto entre X e Y» obliga al modelo a justificar la zona de dos paradas**: si una no está en el contexto (A1, A5) o están en chunks distintos (A3), el prompt de abstención responde «No lo sé».
4. **Los nombres de Google no coinciden con los del CSV** («Sol» frente a «SOL»/«Puerta del Sol», «Plaza de Castilla» frente a «Intercambiador de Plaza de Castilla», «Atocha» frente a «Atocha-Renfe»).
5. Además, las rutas que da Google usan a menudo **Cercanías** (C4b, C10) y no Metro, y las paradas de Cercanías no están indexadas.

## B. Atocha (solo Nominatim)

«Atocha, Madrid» devuelve **5 resultados crudos**:

| # | Clase | Nombre | Distancia al nº 1 |
|---|---|---|---|
| 1 | railway/station (node) | Atocha, Paseo de la Infanta Isabel | — |
| 2 | railway/stop (node) | Atocha, Paseo de la Infanta Isabel | **2 m** |
| 3 | boundary/administrative (relation) | Atocha, Arganzuela (el barrio) | 924 m |
| 4 | building/train_station (way) | Atocha-Cercanías | 213 m |
| 5 | railway/station (node) | Estación del Arte | 320 m |

- **Sí se deduplica lo que debe:** 1 y 2 están a 2 m y se unen. Los otros cuatro quedan a 213–1237 m entre sí, muy por encima de `RADIO_MISMA_UBICACION_M = 100`: son objetos distintos de OSM (la estación, el **polígono administrativo** del barrio, el edificio de Cercanías y otra estación de metro). El resultado es `ambigua` con 4 candidatos distintos, de los que se muestran 3 (`MAX_CANDIDATOS_MOSTRAR`). No es un fallo del deduplicado; es ambigüedad real de Nominatim (incluido un resultado de tipo barrio que no es una parada).
- **Por qué la dirección completa de un candidato no se encuentra:** el texto largo «Atocha-Cercanías, Paseo de la Infanta Isabel, Pacífico, Retiro, Madrid, Comunidad de Madrid, 28014, España» devuelve **0 resultados**. Nominatim exige que casen todos los términos de una búsqueda libre y el `display_name` no es una consulta re-ejecutable (el edificio figura bajo «Pacífico, Retiro» y la estación homónima bajo «Atocha, Arganzuela»). «Atocha-Cercanías, Madrid» devuelve 2 resultados (siguen ambiguos) y «Estación de Atocha, Madrid» 4 paradas de autobús. Con la dirección larga del primer candidato (1b) vuelve a salir ambigua porque coincide también con Atocha-Cercanías y Estación del Arte.
- **Causa de fondo:** la herramienta pide «indica cuál es», pero lo que la persona escriba se vuelve a geocodificar como texto: no hay forma de elegir un candidato por número ni de reutilizar sus coordenadas.

## C. Especialista `rutas` con LLM real, supervisor fijo `["rutas"]`

| Frase | Salida del LLM | `planificar_ruta` | Resultado |
|---|---|---|---|
| «quiero ir a Sol» | `{"final": "Por favor, indícame desde qué origen deseas partir hacia Sol."}` | no llamada | **Cumple RF-26** (pide el origen). Un primer intento falló con 503 antes de contestar. |
| «quiero ir de la Puerta del Sol al Estadio Santiago Bernabéu» | `{"tool":"planificar_ruta","args":{"origen":"Puerta del Sol","destino":"Estadio Santiago Bernabéu"}}` | llamada 1 vez, argumentos correctos | `ambigua`: «Puerta del Sol» devuelve Madrid, **Galápagos (Guadalajara)** y **Rozas de Puerto Real**; sin Google ni RAG |
| «salgo mañana a las 8 de la Puerta del Sol al Estadio Santiago Bernabéu» | `args` con `"hora_salida": "2026-10-17T08:00"` (**ISO 8601 correcto, RF-50b**) | llamada 1 vez | igual `ambigua`; el mensaje conserva «Salida: 17/10/2026 08:00» |

- **El especialista funciona con LLM real:** pide el dato que falta, llama a la herramienta una sola vez, convierte «mañana a las 8» a ISO 8601 (`2026-10-17T08:00`) y reproduce la aclaración de la herramienta. Con un supervisor fijo el problema del caso 7 desaparece: **la causa estaba en el supervisor** (JSON con comillas simples / 503), no en `rutas`.
- **La ruta completa Sol → Bernabéu no llegó a Google** porque el LLM pasó «Puerta del Sol» sin «, Madrid» y la herramienta lo declara ambiguo (otros «Puerta del Sol» de la provincia de Madrid y de Guadalajara caen dentro de `AMBITO_COBERTURA`). Sin «Madrid» en el texto, una ruta tan típica pide aclaración. No se ha probado si la ambigüedad sería la misma con `bounded=1`.
- **Artefacto de mi primer intento (descartado):** en la primera pasada envolví `planificar_ruta` con una función `(*a, **k)` y `planificar_ruta_texto` filtra argumentos con `inspect.signature`, así que la herramienta recibió `origen=None, destino=None` y devolvió `faltan_datos`. No es un fallo del producto, pero muestra que **`planificar_ruta_texto` depende de la firma de `planificar_ruta`** (un decorador sin `functools.wraps` lo rompe). Repetido con `functools.wraps`, los argumentos llegan bien.
- Los **503 de Gemini** aparecen de forma intermitente en cualquier llamada (supervisor, especialista, sintetizador, generación del RAG): con un 503 el especialista devuelve «ERROR: el modelo no respondió…» y el sintetizador cae a «No se ha podido sintetizar…».

## Causa probable de cada fallo de T17

| Fallo | Causa probable |
|---|---|
| Zona sin evidencia con paradas (caso 1/3) | Índice con solo 40 filas del CSV (`MAX_FILAS_CSV`) + pregunta de dos paradas + nombres de Google distintos de los del CSV |
| Atocha siempre ambigua | Nominatim devuelve varios objetos OSM distintos (estación, barrio, edificio Cercanías, estación de metro); no hay forma de elegir uno |
| Dirección larga de un candidato no encontrada | El `display_name` no es una consulta de búsqueda válida para Nominatim |
| Supervisor real cae al fallback (caso 7) | Respuesta del modelo con comillas simples (no JSON) y 503 de Gemini |
| «Puerta del Sol» ambigua con el LLM | El LLM omite «, Madrid» y hay homónimos dentro del ámbito |


---

# Repetición de T17 tras T22 (2026-10-19) — parada en el caso 1

> Peticiones: **Nominatim 2 · Google 0 · RAG 0** · Gemini 0. Sin reintentos. Script temporal borrado. **T17 NO se marca**: los casos 3 y 7 no se ejecutaron por la regla de parada.

| Caso | Entrada | Resultado |
|---|---|---|
| 1 | `Atocha, Madrid` → `Puerta del Sol, Madrid` | **No coincide**: `ambigua` (origen), 3 candidatos como en la primera pasada. Sin Google ni RAG. |
| 3 y 7 | — | No ejecutados |

**Causa:** la terminación «, Madrid» no desambigua Atocha. Nominatim sigue devolviendo objetos distintos de OSM (estación, barrio de Arganzuela, edificio Atocha-Cercanías y Estación del Arte) a más de `RADIO_MISMA_UBICACION_M`. Es el comportamiento de RF-8, no un fallo de T22. Hace falta otro origen para la demo (p. ej. «Plaza de Castilla, Madrid») o decidir cómo elegir un candidato.

**Validación de T22 (valores reales de Nominatim, `address`):** los 6 resultados (5 de «Atocha, Madrid» y 1 de «Puerta del Sol, Madrid») traen `state = "Comunidad de Madrid"`, `ISO3166-2-lvl4 = "ES-MD"` y municipio `Madrid` (`city`). El resultado de Sol es único. Sin comprobar aún: municipio pequeño o sin ciudad, y la pregunta de zona «entre Madrid y Madrid» con el RAG real.


## Segunda repetición (2026-10-19, en una ejecución, sin reintentos) — T17 NO cerrada

> Peticiones: **Nominatim 6 · Google 2 · RAG 4 · Gemini** (supervisor y especialista en 3 turnos, 2 respuestas del RAG que genera Gemini y la síntesis del turno de ruta). Una ejecución anterior se perdió por un error mío al leer la salida y no cuenta aquí. Scripts y salida temporales borrados.
> **Atocha** queda como «ambigua correcta» (RF-8): ya comprobado en la repetición anterior, no se repite.

| Caso | Entrada | Resultado |
|---|---|---|
| 1 | `Plaza de Castilla, Madrid` → `Puerta del Sol, Madrid` | **No coincide**: `ambigua` en el origen (2 candidatos: Plaza de Castilla de Tetuán y de Chamartín). Sin Google ni RAG. |
| 3 | Sol → Bernabéu, `titulo="abono joven"` | **Parcial**: `ok`, ruta de 20 min; pregunta de zona «…entre Madrid y Madrid?» → **zona ok** («la zona A coincide prácticamente con el término municipal de Madrid… zona A»); pregunta de precio construida con esa zona entera (cabe en `ZONA_LONGITUD_MAX`) → **«No lo sé»**, `precio = sin_evidencia`. 2 llamadas al RAG. |
| 7 | grafo con LLM real, 3 turnos | **Sí**: «quiero ir a Puerta del Sol, Madrid» → pide el origen, sin tool (RF-26); «salgo mañana a las 8 desde el Estadio Santiago Bernabéu, Madrid» (mismo hilo) → combina el destino anterior (RF-28), `hora_salida=2026-10-20T08:00` (RF-50b), `estado=ok`, zona A y precio del billete sencillo con aviso de precios contradictorios en el corpus; «voy a comprar un abono» → sin tool (RF-29). El supervisor devolvió decisión estructurada válida en los 3 turnos. |

**Valores reales de Nominatim (T22):** en los 14 resultados recibidos (Plaza de Castilla ×9, Puerta del Sol ×3, Bernabéu ×2) `address.state = "Comunidad de Madrid"`, `address["ISO3166-2-lvl4"] = "ES-MD"` y municipio `Madrid` (`city`). Sumados a la pasada anterior (6 resultados), 20 de 20 coinciden. Siguen sin verse municipios pequeños ni direcciones sin ciudad.

**Por qué no se cierra T17:**
1. **Caso 1:** «Plaza de Castilla, Madrid» también es ambigua para Nominatim (dos plazas homónimas en barrios distintos). RF-8 funciona, pero la demo «ruta completa con dos direcciones» no se puede hacer con nombres de plazas o estaciones genéricos; es lo que cubriría T23.
2. **Caso 3:** la zona ahora sí llega (T22 funciona con el RAG real), pero el precio de «abono joven» no. Causas posibles, sin comprobar: (a) el corpus no tiene ese precio (el caso 7 sí obtuvo el del billete sencillo, con cifras contradictorias en los documentos); (b) la zona devuelta es una frase larga de 170 caracteres y no un identificador, y arrastra «Basándonos en el contexto… Por lo tanto…» a la pregunta de precio. RF-53 pedía comprobar justo esto: con billete sencillo funcionó; con abono joven, no.

## Diagnóstico del precio de «abono joven» (2026-10-19, T24 sin implementar)

> 3 llamadas a `retrieve()` (3 embeddings de Gemini), 0 generaciones, 0 Google, 0 Nominatim. Scripts y salida borrados.

| Pregunta de precio | Chunks top-4 |
|---|---|
| A. abono joven + zona en frase larga (la real del caso 3) | zonas (A, T), descripción del abono 30 días, reglas de zonas, billete turístico. **Ningún chunk con la tabla de precios JOVEN.** |
| B. abono joven + «Zona A» (corta) | 3 chunks de billete turístico + la descripción del abono 30 días. **Tampoco la tabla JOVEN.** |
| C. billete sencillo + zona en frase larga | zonas + 3 chunks «BILLETES SENCILLOS: PRECIOS VIGENTES 2026» (la tabla de precios). |

**Conclusión:** la frase larga de zona no es la causa. Con la zona corta, el abono joven sigue sin recuperar su tabla de precios (que en el corpus es una fila `JOVEN | JOVEN | JOVEN | 20,00 € …` en `bocm-20251231-tarifas_transporte.md` y `bocm-20251231-precios_transporte.md`), mientras que con la frase larga el billete sencillo sí recupera la suya. El fallo es de recuperación del RAG para ese título, no de cómo se pregunta la zona.

## Cierre de T17 (2026-10-19)

T17 se cierra con dos excepciones aceptadas:
1. **Caso 1 — ambigüedad legítima (RF-8).** Atocha y Plaza de Castilla son ambiguas para Nominatim aunque terminen en «, Madrid»; la herramienta pide concretar. Se resuelve en **T23** (pendiente).
2. **Caso 3 — limitación del RAG.** La zona es correcta («zona A»), pero el precio del abono joven depende de que el RAG recupere su tabla de precios, que hoy no recupera (ver el diagnóstico anterior). Limitación conocida del RAG compartido, **a plantear al equipo**. No se implementa T24: la frase larga de zona no era la causa.

Casos 2, 4, 5, 6 y 7 coinciden con la spec. Sin llamadas reales en este cierre.
