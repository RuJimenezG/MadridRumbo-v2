# Validación — Spec 010

> Fecha: 2026-10-21 · `python -m pytest`: **1142 passed**, sin red ni LLM (todo con dobles). No se hizo ninguna llamada real a ningún servicio en esta spec; los diagnósticos reales previos (Nominatim, ruta Sol → Bernabéu) están en la conversación, no en tests.
> **Veredicto: Sí con dobles; la verificación real queda pendiente de autorización** (ver «Qué no se ha comprobado»).

## RF por RF

| RF | Resultado | Evidencia (tests) |
|---|---|---|
| RF-1, RF-2, RF-3 | Sí | `test_normalizacion_lugares.py` (prefijos con mayúsculas y tildes, «Metro» solo, sin cambios en textos sin prefijo, sin «Madrid» ni llamadas extra, mensajes con el texto original) |
| RF-4, RF-5 | Sí | `test_bloques_ruta.py::test_ambigua_lleva_las_opciones_en_bloques`, `test_direccion_no_encontrada_y_fuera_cobertura_en_bloques`, `test_sin_bloques_no_hay_clave` |
| RF-6, RF-7, RF-8 | Sí | `test_bici_ok_lleva_su_parrafo_y_el_clima`, `test_motivo_de_cada_causa_en_bloques` (R1, R2, mal tiempo, sin bicis, sin huecos, misma estación, EMT, Google), `test_mensaje_y_campos_existentes_no_cambian` |
| RF-9, RF-10, RF-11, RF-12 | Sí | `test_clima_caido_ofrece_bici_con_aviso`, `test_clima_caido_sin_less_walking`, `test_mal_tiempo_sigue_sin_bici`, `test_hora_pedida_sin_clima_y_con_motivo`, `test_log_de_clima_solo_tipo_y_reason`; `test_bicimad.py::test_sin_dato_de_clima_sigue_el_flujo_normal` |
| RF-13 a RF-16 | Sí | `test_sintetizador_bloques.py` (opciones, bici, motivo y clima visibles aunque el modelo los omita; sin duplicados, también con el aviso dentro del bloque; resultado ilegible; bloques mal formados; respaldo intacto) y `test_sintetizador_avisos.py` |
| RF-17, RF-18 | Sí | `test_precio_titulo.py` (el `titulo` entra en la pregunta de precio, 2 llamadas al RAG; reglas del prompt) y `test_especialista_rutas.py::test_prompt_sin_lista_de_titulos` (sin tocar) |
| RF-19, RF-20 | Sí | `test_capa2_lugares.py` (alternativo que resuelve, ≤ 4 llamadas a Nominatim, sin resolver, no verificado, fallo de Nominatim, vacío) |
| RF-21 | Sí | `test_capa2_lugares.py::test_probable_*`, `test_opcion_usada_va_en_bloques`, `test_la_opcion_usada_acompana_a_un_error_del_otro_extremo` |
| RF-22, RF-23, RF-24 | **Parcial** | `test_prompt_capa2.py` comprueba que el prompt **contiene** las reglas y que los argumentos llegan a la tool. Que el LLM real **las cumpla** no se ha comprobado (depende del modelo). |
| RF-25, RF-26 | Sí | `test_ok_lleva_zona_y_precio_en_bloques`, `test_sin_zona_ni_precio_no_hay_bloque_de_tarifa`, `test_ruta_no_calculada_lleva_su_mensaje_en_bloques` |
| RF-27 | Sí | `test_bici_no_disponible_lleva_su_causa_y_su_frase` (5 causas), `test_las_frases_de_no_disponible_se_distinguen`, `test_causa_solo_cuando_no_esta_disponible` |
| RF-29 | Sí | `test_catalogo_roles.py::test_ficha_y_regla_incluyen_el_titulo_concreto`, y los dos tests de la línea de exclusión actualizados |
| RF-30 | Sí con dobles | `test_supervisor_ruta_con_extremos.py` (casos pedidos, nunca quita roles, LLM, fallback y nodo). Con el LLM real no se ha comprobado. |
| RF-31 | Sí | `test_especialista_rutas.py`: `test_de_x_al_y_y_hasta_no_dan_aviso_de_destino`, `test_de_x_al_y_llega_a_la_herramienta`, `test_sin_destino_sigue_el_aviso`, `test_sin_origen_y_sin_nada_siguen_el_aviso`, `test_se_parte_por_la_primera_aparicion_del_separador` |
| RF-32 | Parcial | `test_prompt_rutas_pide_la_tool_tambien_para_ir_en_bici` y `test_ir_en_bici_llega_a_la_herramienta_con_origen_y_destino` (LLM falso): el prompt lleva la regla y la tool se ejecuta; que el LLM real no rechace «en bici» no se ha comprobado. |
| RF-33 | Sí | `test_sintetizador_turnos.py` (seis casos del sintetizador y el grafo en dos turnos) |
| RF-34 | Sí | `test_candidatos_madrid.py` |
| RF-35 | Sí con dobles | `test_tls_open_meteo.py` (contexto con `cafile=certifi.where()` y verificación activa, respaldo sin `certifi`, bundle ilegible, `clima_origen` lo pide, la EMT no, y ningún `CERT_NONE` ni `_create_unverified_context` en `src/`). Con el cliente nuevo no se ha llamado aún a Open-Meteo. |
| RF-36, RF-37, RF-38 | Sí con dobles | `test_precio_dos_intentos.py` y los tests de tarifa ajustados (ver `plan.md`). Medido con el RAG real, pero la ruta completa con el cambio no se ha ejecutado contra el RAG. |
| RF-39 | Sí con dobles | `test_sintetizador_contexto.py` (el contexto del LLM no lleva los textos de los bloques ni en `resultado` ni en `notas`, y sí la `nota`; la respuesta los lleva una vez; sin bloques el contexto no cambia; ilegibles y otras tools intactos; el respaldo usa el contexto completo; el grafo en dos turnos). Que el LLM real deje de parafrasear no se ha comprobado. |
| RF-40 | Sí con dobles | `test_sintetizador_contexto.py` (solo el turno actual; sin marca se incluye; sin historial no se filtra). **Límite:** `notas` y `traza` no llevan marca de turno y el LLM las sigue viendo enteras. |
| RF-41 | Parcial | `test_prompt_seguimiento.py`: el prompt lleva la regla (sin ejemplos de títulos), y la regla y el historial llegan al LLM falso, que pide la tool con los mismos argumentos. Que el LLM real los reutilice no se ha comprobado. |
| RF-42, RF-43 | Sí con dobles | `test_sintetizador_aprobacion.py` (tras aprobar: contexto con la nota y sin los textos de los bloques, respuesta del modelo sin bloques ni avisos, respaldo de siempre; sin aprobación nada cambia aunque `plan_aprobado` siga puesto; el turno siguiente a la aprobación vuelve a lo normal; con varios planes sigue exigiendo elegir). Los dos tests de HITL existentes (`test_grafo_hitl.py::test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido` y `test_clientes_grafo_real.py::test_varios_planes_exigen_elegir_y_se_aprueba_solo_el_elegido`) pasan sin cambios. Que el LLM real confirme brevemente no se ha comprobado. |
| RF-28 | **Parcial** | `test_catalogo_roles.py::test_ficha_de_rutas_incluye_zona_y_precio_y_las_preguntas_de_seguimiento`: la ficha lo dice y llega al prompt del supervisor, pero **no garantiza** el enrutado (ver «Dudas»). |

## Tests existentes modificados (justificación en `plan.md`)

`test_bicimad.py`: `test_no_apto_o_sin_dato_…` (renombrado), `test_campo_bici_solo_en_ok_y_campos_existentes_intactos`, `test_emt_no_disponible_no_llama_a_google`, `test_fallo_de_la_emt_deja_la_ruta_intacta_con_aviso` y `test_fallo_de_google_en_la_bici_deja_la_ruta_intacta_con_aviso`. Ningún otro test existente se tocó.

## Qué no se ha comprobado

- Ninguna ruta real tras los cambios: la bici con el clima caído, los bloques en el texto final de Streamlit/CLI y el comportamiento del LLM del sintetizador con los bloques añadidos.
- El comportamiento real del LLM de rutas con las reglas de la capa 2 (RF-22 a RF-24): si elige solo entre candidatos, si pregunta con confianza baja y si propone un único alternativo.
- Que el supervisor real enrute «¿y cuánto cuesta?» a `rutas`.

## Dudas

1. **La ficha de `rutas` no bastaba para el supervisor (diagnóstico previo a T9; RF-29 y RF-30 lo cubren para ruta con precio, no para el seguimiento sin extremos).** Leído `supervisor.py`, `catalogo_roles.py` y `supervisor_reglas.py`:
   - `instrucciones_para_supervisor()` sigue diciendo «Una consulta textual de tarifa sin imagen debe seleccionar rag», que contradice el nuevo límite de la ficha. El LLM del supervisor puede decidir cualquiera de las dos.
   - `corregir_tarifas_textuales` solo cambia `tarifas` por `rag`; no corrige hacia `rutas`, y `es_consulta_tarifaria_textual` trata «cuesta» como término tarifario.
   - El fallback por palabras (`supervisor_reglas.py`): «¿y cuánto cuesta?» no contiene ningún término de ruta ni de `PALABRAS_RAG`, así que da cola vacía y el mensaje de reformulación. Y «¿cuánto cuesta ir de A a B?» da `rutas` (por «ir de»), pero con «tarifa», «billete» o «abono» añade también `rag`, duplicado.
   - Aunque el supervisor elija `rag`, el especialista RAG solo recibe el mensaje del turno, sin historial ni zona de la ruta anterior.
   - Para cerrarlo hace falta cambiar la regla de exclusión de `instrucciones_para_supervisor` (mismo archivo de Rubén) y el fallback de `supervisor_reglas.py`, que no se ha tocado. Es la mejora futura 5 de abajo.
2. **`sin_ruta`** («no hay ruta disponible…») no se fuerza en `bloques`; no se pidió.
3. **`causa` tiene un cuarto valor, `interno`**, para el error inesperado (RF-27 pedía tres).
4. **Los tests de `causa` fijan credenciales de prueba** con `monkeypatch`; sin ello el resultado dependería del `.env` local. Un test existente más (`test_emt_no_disponible_no_llama_a_google`) también.
5. **Orden de los avisos en `bloques`**: van siempre al final, tras bici o motivo, y tras zona y precio; no hay orden relativo entre «opción usada» y «texto alternativo».
6. **Normalización**: «Parada de metro X» pierde solo «Parada de» (una pasada) y «Metro de Madrid» pierde «Metro».

## Supervisor (T9)

Diagnóstico real previo (10 llamadas solo al supervisor, ficha actual frente a anterior): consultas 2 y 5 pasan de `[rutas, rag]` a `[rutas]` con la ficha de RF-28; la consulta 1 («…y cuánto cuesta el abono joven») sigue en `[rutas, rag]`; la 3 y la 4 no cambian; `corregir_tarifas_textuales` y el fallback no intervinieron. T9 acota la regla de exclusión (RF-29) y añade la corrección determinista (RF-30). **No se ha repetido la medición con el LLM real** (sin autorización); con RF-30, una respuesta `[rag]` a la consulta 1 ya no puede quedarse sin `rutas`. Riesgo: heurística con falsos positivos posibles (ver spec); `DecisionSupervisor` no registra la corrección.

## Rutas: «de X al Y» y «en bici» (T10)

Antes: «¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu?» daba «Falta indicar el destino» sin llamar a ninguna tool (el atajo solo reconocía «a» y la última aparición), y «en bici desde Cibeles hasta Plaza de España» lo rechazaba el LLM de rutas por el alcance «transporte público» del prompt (no hay ese texto en el código). Ahora el atajo acepta `a`/`al`/`hasta` por la primera aparición y el prompt manda pedir la tool también para bici. No se ha repetido con el LLM real.

## Prueba real: bloques repetidos, candidato de Guadalajara y certificados (T11, T12)

- **Bloques de turnos anteriores (RF-33):** corregido. Reaparecían las «Opciones» de una ambigua ya resuelta porque `resultados` acumula toda la conversación.
- **«Puerta del Sol, Galápagos, Guadalajara» como opción 2 (RF-34):** corregido. Entraba por la caja de cobertura; si el usuario elegía `opcion_origen=2`, `verificar_candidato` la rechazaba con «no se pudo verificar que la dirección de origen esté en la Comunidad de Madrid» (turno perdido).
- **Open-Meteo con `CERTIFICATE_VERIFY_FAILED` (T12): corregido (RF-35) tras el diagnóstico.** Reproducido con 2 llamadas reales a Open-Meteo (cliente del proyecto: fallo; contexto con `certifi.where()` y verificación activa: HTTP 200 con las seis claves de `current`). Python 3.14.4 (venv), OpenSSL 3.0.19, `certifi` 2026.7.22 instalado pero fuera de `requirements.txt`; el otro Python del equipo (3.11.9) no tiene `certifi`. Propuesta en `plan.md`.

## Precio de «abono joven» «no disponible» (T13, aplicado)

**Texto exacto que envía `consultar_tarifa`** (`config.py`, con `titulo="abono joven"` y municipios de Madrid):

- Zona: `¿Qué zona tarifaria corresponde a un trayecto entre Madrid y Madrid?`
- Precio: `¿Cuál es el precio del abono joven en la zona indicada a continuación? {texto de la zona}`

**Cómo se interpreta** (`_dato_rag`): el texto del RAG es `ok` salvo que esté vacío o **contenga** la frase `No lo sé, no está en los documentos.` (`FRASE_ABSTENCION`): entonces es `sin_evidencia` y el mensaje dice «Precio (RAG): no se pudo determinar con el corpus.». Además el precio se omite sin consultar si la zona no está, o si su texto supera `ZONA_LONGITUD_MAX` (200).

**6 llamadas reales a `responder` (sin reintentos).** La zona real no se preguntó (límite de 6): la consulta actual usó un texto de zona simulado, «La zona tarifaria es la zona A.».

| Consulta | Resultado |
|---|---|
| La actual de la herramienta (con la zona simulada) | **Abstención** («No lo sé…»), aunque el contexto recuperado menciona «joven» |
| ¿Cuánto cuesta el abono joven? | **Precio**: 20,00 € sin descuento y 10,00 € con descuento (desde el 1/1/2026) |
| Abono Joven zona A precio | Abstención |
| precio abono joven zona A | Abstención |
| tarifa abono joven zona A | **Precio**: tabla completa (20,00 € / 10,00 € y reducciones por discapacidad y familia numerosa) |
| ¿Cuánto cuesta el abono joven en la zona A? | Abstención |

**Conclusión:** el corpus trae el precio del abono joven sin zona. Cuando la pregunta lo condiciona a una zona («en la zona A», «zona A precio»), el generador (prompt «solo con el CONTEXTO») se abstiene; sin zona, o con «tarifa … zona A», responde. El retrieval no es el problema (en las seis, el contexto menciona «joven»).

**Medición del billete sencillo (4 llamadas reales a `responder`, sin reintentos):**

| Consulta | Resultado |
|---|---|
| ¿Cuánto cuesta el billete sencillo? | **Tabla de varios precios** (18 importes): «Según las tablas vigentes para 2026 para Metro Zona A y ML1»: ordinario 1,50 / 1,80 / 2,00 €; discapacidad 1,20 / 1,40 / 1,60 €; familia numerosa general 1,20 / 1,40 / 1,60 €; especial 0,70 / 0,90 / 1,00 €; y las combinaciones con discapacidad. Aclara que varía por modo, origen y destino. |
| ¿Cuánto cuesta el billete sencillo en la zona A? | Abstención |
| Tarifa y precio del billete sencillo zona A | Abstención |
| ¿Cuánto cuesta el billete sencillo en Madrid? | Abstención |

**Decisión:** la primera consulta da una tabla utilizable (precios por categoría con el contexto «Metro Zona A y ML1»; el RAG no desambigua qué significan los tres importes por fila, pero lo declara). Con zona o ciudad, **las tres variantes se abstienen**. Se aplicó la estrategia de dos intentos (RF-36 a RF-38).

**Límites de lo aplicado:**
- El segundo intento («Tarifa y precio del {titulo} {zona}») solo funcionó una vez (abono joven, «zona A» corta) y se abstuvo con el billete sencillo: es un respaldo, no una garantía.
- Para el billete sencillo, el precio que se muestra es la tabla del RAG tal cual, con tres importes por categoría que el corpus no desambigua; la persona usuaria verá esa tabla en lugar de un único precio.
- Con la zona simulada de la medición previa; la ruta completa con el cambio no se ha ejecutado contra el RAG real.

**Propuesta original (aplicada con la variante de dos intentos):** (no se toca el corpus ni el RAG)

1. **Opción recomendada:** preguntar el precio sin condicionarlo a la zona, como en la variante que funcionó: `PREGUNTA_PRECIO = "¿Cuánto cuesta el {titulo}?"` en `config.py`. Mantiene las 2 llamadas (zona y precio) y la zona se sigue mostrando; para títulos que sí dependen de la zona, el RAG responderá con lo que traiga el corpus (posible tabla por zonas). Habría que revisar RF-52 y RF-53 de la spec 004 (precio omitido sin zona; límite de longitud de la zona), que dejarían de tener sentido, y eliminar `ZONA_LONGITUD_MAX`.
2. **Alternativa conservadora:** `«Tarifa y precio del {titulo} {zona}»`, parecida a «tarifa abono joven zona A», que sí respondió. Es una sola muestra con una zona corta; con el texto real de la zona podría fallar.
3. **Archivos:** `config.py` (`PREGUNTA_PRECIO` y, en la opción 1, quitar `ZONA_LONGITUD_MAX`), `src/tools/planificar_ruta.py` (`consultar_tarifa`: no pasar la zona a la pregunta de precio en la opción 1), y los tests que comprueban la pregunta de precio y el límite de zona (`test_planificar_ruta_tarifa.py`, y los dobles del RAG, que identifican la pregunta por la palabra «precio» y la de zona por «zona tarifaria»).
4. **Tests nuevos:** el texto de `PREGUNTA_PRECIO` (con el título, sin saltos de línea y sin la zona en la opción 1); con un RAG doble que se abstiene si la pregunta contiene «zona» y responde si no, la herramienta devuelve el precio; con el RAG abstenido sigue dando `sin_evidencia`; como mucho 2 llamadas.
5. **Riesgos:** (a) títulos que dependen de la zona (billete sencillo, abonos por zona) pueden dar un precio sin zona, varios precios o una abstención distinta: **medir antes con 3 o 4 llamadas reales más** (billete sencillo y abono joven, con y sin zona) y con el texto real de la zona; (b) un precio genérico podría confundirse con el de la zona de la ruta.

## Duplicación y seguimiento (T14)

**Aplicado:** contexto del LLM sin los textos de los bloques y con la `nota` (RF-39), solo resultados del turno actual (RF-40) y regla de seguimiento en `PROMPT_RUTAS` (RF-41). RF-20 de la spec 005 queda intacto (el LLM sigue sintetizando).

**Confirmación tras aprobar el plan: la versión determinista no se aplicó (conflicto); se aplicó la alternativa con el LLM (T15, RF-42 y RF-43).**
- **Por qué se repite el resumen:** tras `pausa_hitl`, `aceptar_plan` conserva el plan y `sintetizador_aprobacion` (el mismo `nodo_sintetizador` con el LLM) vuelve a sintetizar con los mismos resultados del turno, y añade los bloques otra vez; después `finalizar_turno` marca `done`.
- **Conflictos:** RF-31 de la spec 005 («devuelve su resultado»), su plan («sintetizar el resultado aceptado y fijar done=verdadero»), RF-20 («respuesta sintetizada») y los tests `test_grafo_hitl.py::test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido` y `test_clientes_grafo_real.py::test_varios_planes_exigen_elegir_y_se_aprueba_solo_el_elegido`, que fijan que la respuesta tras aprobar sale del sintetizador.
- **Alternativa aplicada (T15), que respeta RF-20:** en `sintetizador_aprobacion` el LLM recibe la nota «El plan ya se mostró; confirma brevemente la aprobación sin repetir la ruta.» y no se añaden bloques ni avisos. Se identifica por el nodo y no por `plan_aprobado`, que no se reinicia y seguiría puesto en los turnos siguientes. Archivos: `src/sintetizador.py` y `src/graph.py` (una línea del nodo), de Rubén. **Tensión asumida con RF-31 de la spec 005** («devuelve su resultado»): la respuesta no repite la ruta; el plan sigue en `plan_aprobado`.

## Mejoras futuras (no implementadas)

1. **Fase C — paradas del corpus.** `output/chunks.json` (de `Paradas CRTM.csv`) trae por parada el tipo de transporte, la zona y el nombre con su descripción/dirección: Metro 89 chunks, Cercanías 20, Metro Ligero 13 y autobuses (EMT 816, urbano 1405, interurbano 1405). Evidencia: «Legazpi» aparece en 20 chunks (37 veces; Metro zona A 3, bus EMT/urbano/interurbano zona A) y «Concha Espina» en 11 (22 veces; Metro zona A 2, bus EMT zona A, urbano e interurbano zona B1); p. ej. «LEGAZPI — Plaza de Legazpi 2» y «CONCHA ESPINA — Calle del Príncipe de Vergara 2», ambas Metro zona A. Idea: consultar la parada por nombre y tipo (el nombre se repite entre tipos y zonas, así que el retrieval necesita «Metro») y geocodificar la **dirección** en vez del nombre. Requiere spec propia y evaluar el retrieval.
2. **Tool de geocodificación propia**, para que el LLM elija entre candidatos antes de planificar (toca allowlist, prompts y tests de varios autores).
3. **Salida estructurada del sintetizador**: secciones tipadas (resumen, opciones, bici…) en lugar de texto libre; cambia el contrato de `respuesta`.
4. **Marca estable contra duplicados por paráfrasis**: hoy el dedupe es textual (`a not in texto`); un delimitador o identificador por bloque evitaría repetir lo que el LLM parafraseó.
5. **Cambio en el supervisor** (archivos de Rubén y José Manuel): regla de exclusión de `instrucciones_para_supervisor`, fallback por palabras para el seguimiento de precio y `corregir_tarifas_textuales` para no sumar `rag` cuando ya hay `rutas`; o pasar el historial al especialista RAG.
6. **`sin_ruta` en `bloques`**, si se considera necesario.
7. **Modo de viaje solo bici**: una ruta en bici de punta a punta (Google `BICYCLE` entre origen y destino, con o sin estaciones de BiciMAD), con su propia spec: parámetro de modo en `planificar_ruta`, qué precio y zona devuelve (ninguno), reglas de distancia y tiempo, y aviso de Google. Hoy «en bici» solo da la ruta en transporte público más la alternativa en BiciMAD cuando procede (spec 009).
8. **Marca de turno en `notas` y `traza`** para que el LLM del sintetizador tampoco vea las de turnos anteriores (hoy solo se filtran los `resultados`).
9. **Sacar del código el atajo `_aclaracion_formulacion_incompleta`** y dejar a `rutas` (LLM) pedir el extremo que falte, o ampliarlo a «desde … hasta» para que sea coherente con el supervisor.
