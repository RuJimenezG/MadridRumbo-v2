# Plan técnico — Spec 003 (Planificar ruta en transporte público)

> Basado en `spec.md` (estado: Aprobada, con RF-40 y RF-41 añadidos por `/sdd-cambio`). No añade comportamiento que no esté en la spec.

## Dependencias y supuestos

- **Código de otra rama.** `ejecutar_especialista` (`src/agents/base.py`), `ejecutar_tool` y `TOOLS_PERMITIDAS` (`src/tools/__init__.py`), la tool `hora_actual`, `config.ZONA_HORARIA`, `config.MAX_STEPS_ESPECIALISTA` y `config.TOOLS_POR_ESPECIALISTA` **existen en `origin/feature/tools-auxiliar-multimodal` y llegan a `develop` con el merge del PR de José Manuel**. Este plan se ha escrito leyendo esa rama; en la rama actual `src/` está vacío. Hasta ese merge no se puede implementar contra ellas.
- **Persistencia (RF-28).** `ejecutar_especialista` solo recibe `estado["mensaje"]`. Combinar el dato que faltaba con lo dicho antes depende de que el grafo (otra spec) componga ese mensaje. Aquí solo se garantiza que el especialista no vuelve a pedir lo que el mensaje ya contiene.
- **Duda abierta de la spec (hora actual).** No bloquea. Diseño: una única función `ahora()` (ver Decisiones) que es la fuente de la hora para la herramienta y para el prompt. Sustituirla no toca nada más.
- **Sin dependencias nuevas.** HTTP con `urllib` (stdlib), `zoneinfo`, `json`, `math`. No se usa `langgraph`.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `config.py` | Modificar | Constantes nuevas (ver "Configuración"). | RF-2, 12, 34, 35, 36; RNF |
| `src/reloj.py` | Crear | `ahora() -> datetime` en `ZONA_HORARIA`; única fuente de la hora. | RF-14, 32, 34 |
| `src/tools/planificar_ruta.py` | Crear | Lógica completa de la herramienta: validación de hora/título, geocodificación, ámbito, Google Routes, consulta al RAG, mensajes. Más `planificar_ruta_texto()` (serializa a JSON). | RF-1 a 24, 31 a 41 |
| `src/tools/__init__.py` | Modificar | Registrar `"planificar_ruta": planificar_ruta_texto` en `TOOLS_PERMITIDAS`. **Archivo compartido con otro PR** (ver Riesgos). | RF-25, 30 |
| `src/agents/rutas.py` | Crear | `construir_prompt(ahora_dt)` y `nodo_rutas(estado, llm, ejecutar)` sobre `ejecutar_especialista("rutas", ...)`. | RF-25 a 29, 31, 35 |
| `config.py` (`TOOLS_POR_ESPECIALISTA`) | Modificar | Añadir `"rutas": ["planificar_ruta"]`. El RAG no se expone al especialista: lo llama la herramienta (RF-19). | RF-25 |
| `tests/test_planificar_ruta_*.py`, `tests/test_especialista_rutas.py` | Crear | Ver Estrategia de tests. | todos |
| `.env.example` | Modificar | Añadir los nombres `GOOGLE_ROUTES_API_KEY` y `NOMINATIM_CONTACTO`, sin valores. | RNF Secretos |
| `.env` (local, no versionado) | Manual | Cada persona rellena sus valores; no se versiona ni se lee. | RNF Secretos |

No se modifican `rag/` ni `app.py`.

### Configuración nueva en `config.py` (un solo punto, RF-2)

| Constante | Valor inicial | Nota |
|---|---|---|
| `AMBITO_COBERTURA` | `(39.88, -4.58, 41.17, -3.05)` = (lat_min, lon_min, lat_max, lon_max) | **A VERIFICAR.** Caja aproximada de la Comunidad de Madrid; comprobar sobre el mapa antes de implementar. |
| `NOMINATIM_URL`, `NOMINATIM_PAIS` (`"es"`), `NOMINATIM_LIMIT` (10), `NOMINATIM_TIMEOUT_S`, `NOMINATIM_INTERVALO_S` (1.0) | | Uso responsable (RNF). |
| `NOMINATIM_USER_AGENT` | `"MadridRumbo/1.0"` + contacto leído de `os.getenv("NOMINATIM_CONTACTO")` | El contacto no se escribe en el código. |
| `MAX_CANDIDATOS_MOSTRAR` | 3 | RF-8. |
| `RADIO_MISMA_UBICACION_M` | 100 | RF-10 y deduplicado de candidatos. |
| `GOOGLE_ROUTES_URL`, `GOOGLE_ROUTES_API_KEY = os.getenv(...)`, `GOOGLE_TIMEOUT_S` | | RF-11, RNF Secretos. |
| `GOOGLE_FIELD_MASK` | campos mínimos (duración, tramos, `transitDetails`) | **A VERIFICAR** contra respuesta real. |
| `MODOS_GOOGLE` | `["SUBWAY", "LIGHT_RAIL", "BUS", "TRAIN"]` | RF-12. |
| `TIPOS_VEHICULO_ACEPTADOS` | tipos de `transitDetails.transitLine.vehicle.type` aceptados (metro, metro ligero, tranvía, autobús, Cercanías) | **A VERIFICAR con una respuesta real** si Google distingue Cercanías de larga distancia/alta velocidad; si lo hace, estos últimos quedan excluidos. |
| `ANTELACION_MAX_DIAS` | 7 | RF-34. Valor a confirmar. |
| `TITULOS_TRANSPORTE`, `TITULO_POR_DEFECTO` | `("billete sencillo", "billete de 10 viajes")`, `"billete sencillo"` | RF-19, 35, 36. |
| `PREGUNTA_ZONA`, `PREGUNTA_PRECIO` | plantillas con `{origen}`, `{destino}`, `{titulo}` | RF-19. |
| `FRASE_ABSTENCION` | `"No lo sé, no está en los documentos."` | Ver Riesgos. |

## Contrato

### Herramienta (función Python)

```text
planificar_ruta(origen: str, destino: str,
                hora_salida: str | None = None,   # ISO 8601, p. ej. "2026-10-15T08:30"
                hora_llegada: str | None = None,  # solo para rechazarla (RF-39)
                titulo: str | None = None) -> dict
```

Devuelve siempre un `dict` y nunca lanza excepciones. `estado` es la primera clave.

```text
{
  "estado": "ok" | "faltan_datos" | "hora_llegada_no_admitida" | "hora_no_interpretable"
          | "hora_pasada" | "hora_demasiado_lejana" | "geocodificacion_fallida"   # RF-40
          | "direccion_no_encontrada" | "fuera_cobertura" | "ambigua"
          | "misma_ubicacion" | "ruta_no_calculada" | "sin_ruta"
          | "error_interno",       # fallo inesperado: mensaje en español, sin excepción
  "mensaje": str,                  # español, fijado por Python; incluye siempre hora de salida y título (RF-38)
  "hora_salida": str,              # la considerada (por defecto, la actual)
  "titulo": str,                   # el considerado
  "origen": {"direccion": str} | None,    # dirección identificada (RF-7)
  "destino": {"direccion": str} | None,
  "candidatos": {"origen": [...], "destino": [...]},   # solo si ambigua, máx. MAX_CANDIDATOS_MOSTRAR
  "ruta": {"duracion_min": int, "tramos": [...], "fuente": "Google Routes"} | None,
  "zona":   {"estado": "ok"|"sin_evidencia"|"error"|"omitida", "texto": str|None, "fuente": "RAG"},
  "precio": {"estado": "ok"|"sin_evidencia"|"error"|"omitida", "texto": str|None, "fuente": "RAG"}
}
```

`error_interno`: cualquier excepción no prevista dentro de `planificar_ruta` se captura en un único `try/except` externo y se convierte en este estado, con un `mensaje` en español ("Ocurrió un error inesperado y no se pudo planificar la ruta") que lleva igualmente la cabecera de hora y título. No se lanza excepción y no se incluye el detalle técnico ni datos sensibles en el mensaje. No cubre los fallos esperados, que tienen su estado propio (RF-16, RF-40, RF-41).
`estado = "ok"` significa "se entregó la ruta"; `zona` y `precio` pueden venir parciales (RF-21, 22, 36, 37, 41). Cada tramo: `{"modo": "A pie"|<tipo>, "linea": str|None, "desde": str|None, "hasta": str|None, "duracion_min": int}`.

### Capa de registro (allowlist)

`planificar_ruta_texto(**args) -> str` = `json.dumps(planificar_ruta(**args), ensure_ascii=False)`. `ejecutar_tool` hace `str(...)` del resultado y guarda `preview[:120]` en la traza. Como `estado` es la primera clave, el extracto de la traza muestra siempre `{"estado": "fuera_cobertura", ...`. La traza (RF-30) la escribe `ejecutar_tool` y refleja el estado del dict. Ningún secreto entra en `args` ni en el resultado.

### Especialista

`nodo_rutas(estado: dict, llm, ejecutar) -> {"notas": [...], "traza": [...]}`, con la convención de `nodo_horarios`. El prompt se construye en cada llamada y lleva: fecha y hora actuales, lista cerrada de títulos, protocolo JSON `{"tool","args"}` / `{"final"}`, reglas (ver Lógica clave).

### Ejemplo (valores ilustrativos, no reales)

Entrada del LLM: `{"tool":"planificar_ruta","args":{"origen":"Puerta del Sol, Madrid","destino":"Estadio Santiago Bernabéu","hora_salida":"2026-10-15T08:30","titulo":"billete sencillo"}}`

Salida (extracto): `{"estado":"ok","mensaje":"Salida: 15/10/2026 08:30 · Título: billete sencillo. De «Puerta del Sol, Madrid» a «Estadio Santiago Bernabéu»: 22 min (Google Routes). ... Zona (RAG): ... Precio (RAG): ...", ...}`

Fuera de cobertura: `{"estado":"fuera_cobertura","mensaje":"Salida: ahora (15/10/2026 08:12) · Título: billete sencillo. La dirección de origen «Calle Mayor, Barcelona» está fuera de la cobertura de MadridRumbo.","ruta":null,...}`

## Lógica clave

```text
planificar_ruta(origen, destino, hora_salida, hora_llegada, titulo):
  # Todo el cuerpo va dentro de un try/except externo: una excepción inesperada
  # devuelve estado "error_interno" (mensaje en español, con cabecera de hora y título).
  ahora_dt = ahora()                                   # única fuente de hora
  titulo_c = normalizar(titulo) or TITULO_POR_DEFECTO  # RF-19
  # 1) validaciones baratas, sin red
  si falta origen o destino          -> faltan_datos                 # defensivo (RF-26)
  si hora_llegada                    -> hora_llegada_no_admitida     # RF-39
  si hora_salida:
      t = parsear_iso(hora_salida)   -> si falla: hora_no_interpretable      # RF-33
      si t < ahora_dt (a minuto)     -> hora_pasada                  # RF-32
      si t > ahora_dt + ANTELACION   -> hora_demasiado_lejana        # RF-34
      t = t con zona ZONA_HORARIA (si venía sin zona) y formateado RFC 3339 con el
          desplazamiento real de esa fecha (+01:00 invierno, +02:00 verano; usa zoneinfo)
  si no: t = None (Google usa "ahora"), hora_considerada = ahora_dt  # RF-14
  # 2) geocodificación: máx. 2 llamadas, >= 1 s entre ellas
  para extremo en (origen, destino):
      resultados = nominatim(extremo)  # countrycodes=es, viewbox+bounded, addressdetails
      si falla -> geocodificacion_fallida y PARA (sin Google ni RAG)   # RF-40
      cand = deduplicar([r for r in resultados si dentro_de_ambito(r)])# RF-3
      clasificar: 0 resultados -> no_encontrada (RF-6)
                  resultados pero 0 dentro -> fuera (RF-4)
                  1 -> ok (RF-7)
                  >1 -> ambigua con <= MAX_CANDIDATOS_MOSTRAR (RF-8)
  si algún extremo no es ok -> estado por prioridad fuera > no_encontrada > ambigua;
       mensaje lista cada problema; NO se llama a Google (RF-5) ni al RAG
  si distancia(origen, destino) <= RADIO_MISMA_UBICACION_M -> misma_ubicacion  # RF-10
  # 3) ruta
  respuesta = google_routes(coords, MODOS_GOOGLE, t)   # máx. 1 llamada
  si error / sin clave / sin conexión -> ruta_no_calculada (RF-16);
       aun así consulta RAG con los municipios de Nominatim (RF-20)
  si sin rutas, sin tramo de transporte, o algún tramo con tipo fuera de
     TIPOS_VEHICULO_ACEPTADOS -> sin_ruta, zona y precio "omitida" (RF-17, 12, 13)
  ruta = tiempo total + tramos (solo datos de Google; nada estimado, RF-18)
  # 4) zona y precio
  lugares = (parada_subida, parada_bajada) si hay ruta, si no (municipio_o, municipio_d)
  zona   = consultar_rag(PREGUNTA_ZONA.format(lugares))
  si titulo_c en TITULOS: precio = consultar_rag(PREGUNTA_PRECIO.format(lugares, titulo_c))
  si no: precio "omitida" + mensaje con títulos disponibles                 # RF-36
  # consultar_rag: excepción -> estado "error" (RF-41);
  #   FRASE_ABSTENCION en la respuesta -> "sin_evidencia" (RF-21, 22, 37);
  #   si no -> "ok" con el texto del RAG sin tocar (RF-23)
  mensaje = cabecera(hora, titulo) + ruta + [Google]/[RAG] por dato (RF-24)

nodo_rutas(estado, llm, ejecutar):
  prompt = construir_prompt(ahora())      # fecha/hora + títulos + reglas
  return ejecutar_especialista("rutas", prompt, estado, llm, ejecutar)

Reglas del prompt: si falta origen o destino, NO usar ninguna tool y pedir lo que falta
(ambos si faltan ambos), sin asumir ubicaciones (RF-26, 27); si no es consulta de rutas,
no usar tools y decirlo en la nota (RF-29); convertir horas relativas a ISO con la hora
actual del prompt; usar solo títulos canónicos; hora de llegada -> pasarla en
`hora_llegada`; reproducir el `mensaje` de la tool sin cambiarlo (RF-9, 24, 38).
```

Nominatim: `GET {URL}/search?q=...&format=jsonv2&countrycodes=es&viewbox=<lon_min>,<lat_max>,<lon_max>,<lat_min>&bounded=1&addressdetails=1&limit=N`. El `viewbox` de Nominatim es `x1,y1,x2,y2` (longitud primero, esquinas superior izquierda e inferior derecha), mientras que `AMBITO_COBERTURA` está en `(lat_min, lon_min, lat_max, lon_max)`: una función `viewbox_nominatim()` hace la conversión en un solo sitio. con `User-Agent` y espera de `NOMINATIM_INTERVALO_S` desde la última petición (reloj monotónico a nivel de módulo). Google: `POST` a `computeRoutes` con `travelMode=TRANSIT`, `transitPreferences.allowedTravelModes=MODOS_GOOGLE`, `languageCode=es`, `departureTime` solo si la persona lo pidió (en RFC 3339 con el desplazamiento de Madrid de esa fecha, teniendo en cuenta el cambio horario), sin rutas alternativas, `X-Goog-FieldMask=GOOGLE_FIELD_MASK`, clave en cabecera `X-Goog-Api-Key`.

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Ámbito = caja rectangular en `config.py`, comprobada por una función pura además del `viewbox` de Nominatim; filtro `countrycodes=es` | Filtro por `address.state`; polígono | Simple, testeable sin red, sin dependencias. Limitación: los bordes pueden incluir trozos de provincias vecinas; lo cubren RF-21 y RF-22 (el RAG se abstiene y se declara el dato como no determinado). Valores a verificar. |
| `hora_salida` y `titulo` los extrae el LLM y Python los valida; `hora_llegada` existe solo para rechazarla | Parsear lenguaje natural en Python; sin `hora_llegada` | Tests deterministas sin LLM; RF-39 comprobable. Lo único dependiente del LLM es "mañana a las 8" → ISO. |
| Fuente única `ahora()` en `src/reloj.py`, usada por la herramienta (RF-14, 32, 34) y por el prompt, que recibe la hora formateada con `hora_actual(ahora())` ya existente | El LLM llama a la tool `hora_actual` en cada consulta | Evita un paso del LLM (y un hueco de `MAX_STEPS_ESPECIALISTA = 3`) y que el LLM la omita. Herramienta y prompt no pueden discrepar. **Alternativa descrita:** si se prefiere `hora_actual` como tool, se añade a `TOOLS_POR_ESPECIALISTA["rutas"]` y se indica en el prompt; la herramienta seguiría usando `ahora()`. Sustituir la fuente = cambiar el cuerpo de `ahora()`. |
| Prompt construido en cada llamada (`construir_prompt`) | Constante como `PROMPT_HORARIOS` | Debe llevar la hora actual. |
| Un único módulo `planificar_ruta.py` con funciones internas pequeñas y puras (`dentro_de_ambito`, `clasificar`, `validar_hora`, `mensaje_*`) | Un paquete por servicio | Menos archivos; las puras se testean sin dobles. Se parte si crece. |
| Salida `dict` con `estado` cerrado y `mensaje` fijado por Python; serialización JSON en una capa fina | Texto libre; excepciones | Mensajes deterministas (RF-18, 23); la traza muestra el estado; coherente con `responder()`. |
| Dos llamadas al RAG (zona y precio) con `rag_ask`, importada de forma perezosa dentro de `consultar_rag` | Una sola llamada; `retrieve()` directo | Permite RF-22 por dato, respeta "RAG como tool" y no cambia su contrato. La importación perezosa evita cargar Chroma al importar y permite el doble de prueba. |
| Preguntas al RAG construidas con paradas de subida/bajada de Google, o con el municipio de Nominatim si Google falla (RF-20) | Texto libre de la dirección | Entidades que el corpus puede reconocer. |
| Ruta sin hora: no se envía `departureTime` y se informa de `ahora()` | Enviar la hora actual explícita | Google rechaza horas pasadas, y la actual lo sería al llegar la petición. |
| Validar primero hora/título/datos (sin red) y luego geocodificar | Geocodificar siempre primero | No gasta Nominatim en peticiones ya inválidas (RNF Coste). |
| Verificación en la respuesta por tipo de vehículo de cada tramo, además de `allowedTravelModes` | Confiar solo en la petición | RF-12 y RF-13 quedan comprobables por nosotros. Un tramo no permitido se informa como "sin ruta" aunque exista alternativa. |
| Duplicados de Nominatim (a menos de `RADIO_MISMA_UBICACION_M`) se unen antes de contar candidatos | Contar tal cual | Evita falsas ambigüedades (edificio + calle). |
| `urllib.request` con una sola función `_http_json()` | `requests` | Sin dependencias nuevas (constitución, 12); un único punto a sustituir en los tests. |
| Cabecera de `mensaje` "Salida: … · Título: …" en todos los estados | Solo en `ok` | RF-38 dice "toda respuesta". Si la hora no se pudo interpretar, se muestra el texto recibido. |

## Estrategia de tests

Todos con `pytest`, sin red ni LLM. **Dobles:** `_http_json` (Nominatim y Google, con respuestas de ejemplo guardadas como dicts en el test; cuenta llamadas), `consultar_rag` / `rag_ask` (devuelve texto, `FRASE_ABSTENCION` o lanza), `ahora` (hora fija, parcheada en `src.tools.planificar_ruta` y `src.agents.rutas`), `time.sleep`/`time.monotonic` (límite de 1 s), un `LLMFalso` y `EjecutorFalso` como en `tests/test_especialista_horarios.py`. Se parchea donde se usa (`docs/tests_sin_api.md`).

- **Ámbito (RF-2, 3):** función pura con Puerta del Sol (dentro), otra ciudad española distinta, p. ej. Barcelona (fuera), y un punto de borde (en el límite exacto de la caja, dentro). Un resultado homónimo fuera junto con otro dentro: se descarta el de fuera. Test del `viewbox`: con una `AMBITO_COBERTURA` de prueba `(1, 2, 3, 4)`, `viewbox_nominatim()` devuelve `"2,3,4,1"` (longitud primero), y la petición a Nominatim lo lleva con `bounded=1`.
- **Geocodificación (RF-1, 4 a 10, 40):** una petición por extremo con `countrycodes`, `viewbox` y `User-Agent`; un candidato continúa y muestra la dirección; varios devuelven `ambigua` con tope; cero resultados; solo fuera; misma ubicación; excepción/timeout/HTTP 429 → `geocodificacion_fallida` sin llamar a Google ni al RAG. RF-9: el resultado es un `dict` con `estado`/`mensaje`, sin pausa ni `interrupt`.
- **Google (RF-5, 11 a 18):** cuerpo con coordenadas y `allowedTravelModes`; no se llama si hay fuera de cobertura; sin hora no hay `departureTime`; ruta feliz con tiempo y tramos; error/sin conexión/sin clave → `ruta_no_calculada`; `{}` o solo tramos a pie o tipo de vehículo no aceptado → `sin_ruta` sin zona ni precio; nada estimado.
- **Zona y precio (RF-19 a 24, 35 a 37, 41):** dos preguntas con paradas de Google; con Google caído, con municipios (RF-20); abstención total y parcial; título de 10 viajes; título fuera de lista (ruta + zona, sin precio, lista de disponibles); RAG que lanza excepción; el texto del RAG se reenvía sin modificar y el `mensaje` etiqueta Google/RAG.
- **Hora y título (RF-14, 31 a 34, 38, 39):** hora válida llega a Google, en RFC 3339 con el desplazamiento correcto: `2026-01-15T08:30` → `...+01:00` y `2026-07-15T08:30` → `...+02:00`, y un día de cambio horario (último domingo de marzo y de octubre) con el desplazamiento que corresponde a esa hora; pasada, no interpretable, lejana y llegada no llaman a nada; el `mensaje` de todos los estados contiene hora y título.
- **Especialista (RF-25 a 29):** `TOOLS_POR_ESPECIALISTA["rutas"] == ["planificar_ruta"]`; el prompt contiene la fecha/hora del `ahora()` parcheado y los títulos; con `LLMFalso` que responde `final` sin pedir tool, `ejecutar` no se llama (RF-26, 27, 29); con un guion de tool y final, se invoca `planificar_ruta` con los argumentos. Esto comprueba el cableado, **no** que el LLM real decida bien (RF-26, 28, 29 y la conversión "mañana a las 8" → ISO).
- **Error interno:** con un doble que lanza una excepción inesperada (p. ej. `KeyError` en el parseo de la respuesta de Google), `planificar_ruta` devuelve `estado == "error_interno"`, no lanza, el mensaje está en español, lleva hora y título y no contiene el texto de la excepción.
- **Error interno en la traza (RF-42):** con el `ejecutar_tool` real y una `planificar_ruta` cuyo doble lanza una excepción inesperada, la traza tiene una entrada cuyo `preview` empieza por `{"estado": "error_interno"` y no contiene el texto de la excepción.
- **Traza (RF-30):** con el `ejecutar_tool` real y una `planificar_ruta` con dobles, la traza tiene una entrada con `preview` que empieza por `{"estado": "..."`.
- **RNF:** ≤ 2 llamadas a Nominatim y ≤ 1 a Google; espera de 1 s entre peticiones a Nominatim; `User-Agent` con el contacto del entorno; la clave no aparece en el resultado, la traza ni el código; `FRASE_ABSTENCION in rag.prompt.PROMPT_TEMPLATE` (se rompe si cambia); mensajes en español.

**Comprobación manual (una sola vez, al final; ⚠️ gasta API de Nominatim, Google y Gemini):**
1. Validar con la respuesta real de Google los campos de `GOOGLE_FIELD_MASK` y `TIPOS_VEHICULO_ACEPTADOS` (Cercanías vs. larga distancia).
2. 3 o 4 rutas reales contra el RAG real, con zona y precio, para comprobar que las preguntas devuelven datos útiles. Los dobles no lo demuestran.
3. Demo de consulta completa, de un caso fuera de cobertura y de uno ambiguo (criterios de finalización).
4. Comportamiento real del LLM del especialista: faltan datos, no es de rutas, hora relativa.
5. Revisar en la consola de Google la categoría de facturación de los campos pedidos.
6. Streamlit y CLI no se tocan aquí.

## Riesgos

- **Archivo compartido.** `src/tools/__init__.py` lo toca también otro PR pendiente de merge: coordinar con quien lo mantiene y rebasar tras el merge. `config.py` tiene el mismo riesgo (ambos añaden al final).
- **Contrato de `ejecutar_especialista` / `ejecutar_tool`.** Si cambia, hay que ajustar el especialista y la capa JSON.
- **Frase de abstención** definida solo dentro de `PROMPT_TEMPLATE`, no como constante: punto a **coordinar con quien mantiene el RAG** sin cambiar su contrato. Mitigado con `FRASE_ABSTENCION` y el test que lo vigila.
- **Calidad del RAG.** Zona y precio dependen de que el corpus responda a preguntas por parada o municipio; nada en los tests lo garantiza (validación manual).
- **Cuota de Gemini.** 2 llamadas al RAG por consulta (más las del LLM del especialista) consumen cuota gratuita.
- **Facturación de Google.** La categoría puede depender de los campos de `X-Goog-FieldMask`: revisar en la consola antes de lanzar.
- **Tramo no permitido ⇒ "sin ruta"** aunque exista una alternativa; las alternativas están fuera de alcance. Cercanías y trenes regionales/larga distancia pueden compartir `TRAIN`.
- **Bordes del ámbito.** La caja puede incluir partes de provincias vecinas (cubierto por RF-21 y RF-22). Valores a verificar.
- **Ambigüedad.** Nombres genéricos ("Calle Mayor") pueden generar muchos candidatos y fricción; el deduplicado y el tope lo reducen.
- **Nominatim.** Política de uso (1 req/s, identificación): una consulta no puede superar 2 llamadas. Sin `NOMINATIM_CONTACTO` en `.env` el `User-Agent` va incompleto.
- **RF-28** depende de la spec de persistencia y de cómo el grafo componga `estado["mensaje"]`.
- **Hora.** El cambio de hora, la zona horaria y los minutos: `ahora()` se compara truncada al minuto; la antelación máxima (7 días) es un valor provisional.
- **Duda abierta de la spec** (quién aporta la hora): solucionada de forma sustituible, pero la spec la sigue mostrando como abierta.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Lógica: Nominatim; Contrato | `test_planificar_ruta_geocodificacion.py::test_geocodifica_origen_y_destino_con_nominatim` |
| RF-2 | Configuración `AMBITO_COBERTURA` | `test_planificar_ruta_ambito.py::test_ambito_definido_en_config` |
| RF-3 | `dentro_de_ambito`, Decisiones | `test_planificar_ruta_ambito.py::test_sol_dentro_barcelona_fuera_y_borde` y `::test_viewbox_longitud_primero` |
| RF-4 | Lógica: clasificar | `test_planificar_ruta_geocodificacion.py::test_solo_fuera_de_ambito_rechaza` |
| RF-5 | Lógica: no se llama a Google | `test_planificar_ruta_google.py::test_fuera_de_cobertura_no_llama_a_google` |
| RF-6 | Lógica: no_encontrada | `test_planificar_ruta_geocodificacion.py::test_sin_resultados_pide_direccion_precisa` |
| RF-7 | Lógica: 1 candidato | `test_planificar_ruta_geocodificacion.py::test_un_candidato_continua_e_indica_direccion` |
| RF-8 | Lógica: ambigua | `test_planificar_ruta_geocodificacion.py::test_varios_candidatos_limita_y_no_calcula` |
| RF-9 | Contrato (sin HITL) | `test_planificar_ruta_geocodificacion.py::test_aclaracion_en_respuesta_sin_pausa` |
| RF-10 | Lógica: misma_ubicacion | `test_planificar_ruta_geocodificacion.py::test_misma_ubicacion_no_calcula` |
| RF-11 | Lógica: Google | `test_planificar_ruta_google.py::test_calcula_con_coordenadas` |
| RF-12 | Decisiones: tipos de vehículo | `test_planificar_ruta_google.py::test_modos_permitidos_y_tipo_no_aceptado` |
| RF-13 | Lógica: sin tramo de transporte | `test_planificar_ruta_google.py::test_solo_a_pie_es_sin_ruta` |
| RF-14 | Lógica: sin `departureTime` | `test_planificar_ruta_hora_titulo.py::test_sin_hora_usa_momento_de_consulta` |
| RF-15 | Contrato `ruta` | `test_planificar_ruta_google.py::test_devuelve_tiempo_y_tramos` |
| RF-16 | Lógica: ruta_no_calculada | `test_planificar_ruta_google.py::test_google_falla_informa` |
| RF-17 | Lógica: sin_ruta | `test_planificar_ruta_google.py::test_sin_ruta_no_da_zona_ni_precio` |
| RF-18 | Contrato; Decisiones | `test_planificar_ruta_google.py::test_no_estima_tiempos_ni_trayectos` |
| RF-19 | Lógica: zona y precio | `test_planificar_ruta_tarifa.py::test_consulta_zona_y_precio_sencillo` |
| RF-20 | Lógica: municipios Nominatim | `test_planificar_ruta_tarifa.py::test_google_falla_consulta_rag_con_municipios` |
| RF-21 | Lógica: sin_evidencia | `test_planificar_ruta_tarifa.py::test_rag_sin_evidencia_entrega_ruta` |
| RF-22 | Lógica: por dato | `test_planificar_ruta_tarifa.py::test_evidencia_parcial_declara_el_que_falta` |
| RF-23 | Lógica: texto del RAG intacto | `test_planificar_ruta_tarifa.py::test_no_inventa_zona_ni_precio` |
| RF-24 | Contrato `fuente`; mensaje | `test_planificar_ruta_tarifa.py::test_mensaje_etiqueta_google_y_rag` |
| RF-25 | Archivos: `rutas.py`, allowlist | `test_especialista_rutas.py::test_especialista_registrado_con_su_tool` |
| RF-26 | Prompt; Lógica | `test_especialista_rutas.py::test_falta_dato_no_invoca_tool` + manual |
| RF-27 | Prompt | `test_especialista_rutas.py::test_prompt_prohibe_ubicacion_por_defecto` + manual |
| RF-28 | Dependencias (persistencia) | `test_especialista_rutas.py::test_mensaje_combinado_no_repite_peticion` + manual |
| RF-29 | Prompt | `test_especialista_rutas.py::test_no_es_ruta_no_invoca_tool` + manual |
| RF-30 | Capa de registro; traza | `test_tool_rutas_traza.py::test_traza_refleja_estado` |
| RF-31 | Lógica: `t` a Google en RFC 3339 | `test_planificar_ruta_hora_titulo.py::test_hora_pedida_llega_a_google` y `::test_hora_rfc3339_con_desplazamiento_de_madrid` |
| RF-32 | Lógica: hora_pasada | `test_planificar_ruta_hora_titulo.py::test_hora_pasada_no_calcula` |
| RF-33 | Lógica: no interpretable | `test_planificar_ruta_hora_titulo.py::test_hora_no_interpretable_no_calcula` |
| RF-34 | Lógica: antelación | `test_planificar_ruta_hora_titulo.py::test_hora_demasiado_lejana` |
| RF-35 | Lógica: precio del título | `test_planificar_ruta_tarifa.py::test_billete_10_viajes_consulta_su_precio` |
| RF-36 | Lógica: título fuera de lista | `test_planificar_ruta_tarifa.py::test_titulo_no_disponible_entrega_ruta_y_zona` |
| RF-37 | Lógica: sin_evidencia de título | `test_planificar_ruta_tarifa.py::test_sin_precio_del_titulo_no_lo_sustituye` |
| RF-38 | Cabecera de `mensaje` | `test_planificar_ruta_hora_titulo.py::test_todos_los_estados_incluyen_hora_y_titulo` |
| RF-39 | Lógica: hora_llegada | `test_planificar_ruta_hora_titulo.py::test_hora_llegada_no_calcula` |
| RF-40 | Lógica: geocodificacion_fallida | `test_planificar_ruta_geocodificacion.py::test_nominatim_falla_no_llama_a_google_ni_rag` |
| RF-41 | Lógica: consultar_rag con error | `test_planificar_ruta_tarifa.py::test_rag_con_error_entrega_ruta_sin_zona_ni_precio` |
| RNF Secretos | Configuración; `.env.example` | `test_planificar_ruta_rnf.py::test_clave_solo_del_entorno` |
| RF-42 | Contrato `error_interno`; Capa de registro | `test_planificar_ruta_rnf.py::test_error_inesperado_da_error_interno` y `test_tool_rutas_traza.py::test_error_interno_queda_en_traza` |
| RNF Uso Nominatim | Lógica: Nominatim | `test_planificar_ruta_rnf.py::test_intervalo_y_user_agent` |
| RNF Coste | Lógica | `test_planificar_ruta_rnf.py::test_maximo_2_nominatim_y_1_google` |
| RNF Idioma | Contrato `mensaje` | `test_planificar_ruta_rnf.py::test_mensajes_en_espanol` |
