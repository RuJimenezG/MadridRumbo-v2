# Plan técnico — Spec 010 (lugares, bloques literales y precio)

> Basado en `spec.md` (estado: Borrador). No añade comportamiento que no esté en la spec. Implementado: Fase A (T1–T5 y T5b) y Fase B (T6–T7); T8 en `validacion.md`.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/tools/planificar_ruta.py` | Modificar (mínimo) | `normalizar_lugar` (función pura) y su uso en `geocodificar`; `bloques` en las ramas de dirección problemática, en `ruta_no_calculada` (RF-26) y en la rama `ok` (zona y precio, RF-25); el enganche de la bici pasa `clima` también cuando no está disponible; Fase B: parámetros `texto_alternativo_*` y `probable_*`, y los avisos de «qué se usó» también en `bloques` (a través de `salir`). | RF-1 a 8, 10, 19 a 21, 25, 26 |
| `src/tools/bicimad.py` | Modificar | R0 solo rechaza con clima **apto = falso**; `linea_motivo_bici` (pura); log de `URLError` con su `reason`; `causa` y `FRASES_NO_DISPONIBLE` (T5b). | RF-7, 9, 10, 11, 27 |
| `config.py` | Modificar (compartido; junto a las constantes `CLIMA_*`) | `CLIMA_SIN_DATO_AVISO` (texto fijo de RF-10). | RF-10 |
| `src/sintetizador.py` | Modificar (de Rubén y Guzmán) | `_avisos_obligatorios` pasa a devolver también los `bloques`; el nodo los añade sin duplicar (también contra bloques ya añadidos); log del resultado ilegible. | RF-13 a 16 |
| `src/agents/rutas.py` | Modificar (de Rubén y Guzmán) | Texto de `PROMPT_RUTAS` (RF-18; capa 2, RF-22 a 24; «en bici», RF-32) y, en `_aclaracion_formulacion_incompleta`, separadores `a`/`al`/`hasta` y primera aparición (RF-31, T10). | RF-17, 18, 22 a 24, 31, 32 |
| `src/catalogo_roles.py` | Modificar (**de Rubén**; solo texto) | `limites` de la ficha del rol `rutas`: incluye zona y precio (también para un título concreto) y las preguntas de precio de seguimiento van a `rutas`; la regla de exclusión se acota («…sin origen ni destino debe seleccionar rag; con origen y destino selecciona rutas…»). La `responsabilidad` no cambia. | RF-28, 29 |
| `src/supervisor_reglas.py` | Modificar (**de Rubén y José Manuel**) | `completar_rutas_con_extremos(roles, mensaje)`: puramente aditiva, junto a las reglas del fallback; reutiliza `_normalizar` y `_texto_normalizado`. No toca el fallback existente. | RF-30 |
| `src/supervisor.py` | Modificar (**de Rubén**; dos líneas) | Aplica la corrección tras `corregir_tarifas_textuales` (decisión del LLM) y en `_decision_fallback`. | RF-30 |
| `tests/test_supervisor_ruta_con_extremos.py` | **Crear** | T9. | RF-30 |
| `tests/test_normalizacion_lugares.py` | **Crear** | T1. | RF-1 a 3 |
| `tests/test_bloques_ruta.py` | **Crear** | T2 y T3 (`Escenario`, sin red). | RF-4 a 12 |
| `tests/test_sintetizador_bloques.py` | **Crear** | T4 (modelo falso). | RF-13 a 16 |
| `tests/test_precio_titulo.py` | **Crear** | T5. | RF-17, 18 |
| `tests/test_capa2_lugares.py` | **Crear** | T6. | RF-19 a 21 |
| `tests/test_prompt_capa2.py` | **Crear** | T7. | RF-22 a 24 |
| `tests/test_catalogo_roles.py` | Añadir un test (T5b c) | La ficha de `rutas` contiene lo pedido. | RF-28 |
| `tests/test_bicimad.py` y otros | Modificar solo los que el cambio de RF-10 obligue | Los que fijan «sin dato de clima → sin bici» (ver «Tests obsoletos»). | RF-10 |
| `src/tools/bicimad.py` | Modificar (T12) | `_get_json(..., contexto_certifi=False)` y `_contexto_ssl`; `clima_origen` lo pide con `True`. | RF-35 |
| `requirements.txt` | Modificar (T12) | Añade `certifi`. | RF-35 |
| `config.py` | Modificar (T13) | `PREGUNTA_PRECIO` = «¿Cuánto cuesta el {titulo}?» (sin zona) y `PREGUNTA_PRECIO_CON_ZONA` = «Tarifa y precio del {titulo} {zona}». | RF-36, 37 |
| `src/tools/planificar_ruta.py` | Modificar (T13) | `consultar_tarifa`: precio sin zona primero; segundo intento con zona solo tras `sin_evidencia`; ≤ 3 llamadas. | RF-36 a 38 |
| `tests/test_precio_dos_intentos.py` y tests de tarifa existentes | Nuevo y ajustes justificados (T13) | Ver «Tests ajustados en T13». | RF-36 a 38 |
| `src/modelos.py`, `src/graph.py`, `rag/`, corpus, `output/chunks.json`, `src/tools/__init__.py` | **No se tocan** | — | — |

## Contrato

`planificar_ruta` mantiene todos sus campos y estados. Añade `bloques` solo si no está vacío; `mensaje` no cambia.

```text
"bloques": [str, ...]     # textos literales para la persona usuaria, en el orden en que deben mostrarse
```

Contenido de `bloques` por estado:

```text
ambigua | direccion_no_encontrada | fuera_cobertura:
    una frase por extremo con problema (la de _problema_direccion, sin cabecera)
    p. ej. "La dirección de origen «Legazpi» es ambigua. Opciones: 1) …; 2) …. Indica cuál es o concreta más."
ok (con hora pedida):
    [ línea de motivo de la bici ]                       # R1
ok (sin hora pedida):
    [ zona y precio (solo si el RAG los dio),
      línea del clima  |  CLIMA_SIN_DATO_AVISO,
      párrafo de bici  |  línea de motivo,
      avisos de «qué se usó» (opción elegida, elección automática, texto alternativo) ]
ruta_no_calculada:
    [ texto del fallo, con su zona y precio si los hay ]
cualquier estado con avisos de «qué se usó»: se añaden al final de `bloques`
```

`bici` en `no_disponible` gana `causa`:

```text
{"estado": "no_disponible", "motivo": FRASES_NO_DISPONIBLE[causa], "causa": "sin_credenciales" | "emt" | "google" | "interno"}
```

Capa 2 (Fase B): `planificar_ruta(..., texto_alternativo_origen?, texto_alternativo_destino?, probable_origen?, probable_destino?)`;
ver «Lógica clave».

Línea de motivo de la bici (`bicimad.linea_motivo_bici`), solo si la bici no es `ok`:

| Caso | Texto |
|---|---|
| R1, hora pedida | «La alternativa en bici no se ofrece con hora de salida o de llegada pedida: la disponibilidad de bicis es la de ahora.» |
| R2, distancia | «La alternativa en bici no se ofrece: la distancia entre origen y destino queda fuera del rango de 1 a 6 km.» (valores de `config`) |
| R0, mal tiempo | «La alternativa en bici no se ofrece con mal tiempo (…motivos…).» |
| Sin bicis / sin huecos / misma estación | `bici["motivo"]` (frase existente de `FRASES_NO_OFRECIDA`) |
| No disponible | `bici["motivo"]`: una frase por `causa` (`FRASES_NO_DISPONIBLE`: sin credenciales, EMT, Google; `interno` conserva la genérica) |

Los textos van en `bicimad.py` junto a `FRASES_NO_OFRECIDA`; el de RF-10 va en `config.py`.

`PROMPT_RUTAS` conserva el contrato de salida (`{"tool": …}` o `{"final": …}`) y añade las reglas de RF-18.

## Lógica clave

```text
# T1 — normalizar_lugar(texto) -> str       (planificar_ruta.py, pura)
PREFIJOS = r"^\s*(?:estaci[oó]n\s+de\s+metro|estaci[oó]n\s+de|parada\s+de|metro)\b[\s,:\-]*"   # IGNORECASE
resto = re.sub(PREFIJOS, "", texto, count=1, flags=I)
return resto if resto.strip() else texto
# geocodificar(direccion): "q": normalizar_lugar(direccion)   (único sitio; los dos extremos pasan por aquí)

# T2/T3 — en _planificar_ruta
ramas de dirección problemática:  bloques = [_problema_direccion(rol, …) for rol in problemas]      # y las de RF-55
rama ok:
    bloques = []
    if clima is not None:                                    # solo sin hora pedida
        bloques.append(texto_clima(clima) or config.CLIMA_SIN_DATO_AVISO)
    bici, texto_bici = alternativa_bici(lugar_o, lugar_d, clima is None, clima)    # clima puede ser no_disponible
    bloques.append(texto_bici or linea_motivo_bici(bici, lugar_o, lugar_d, clima))
    extra["bloques"] = [b for b in bloques if b]

# T3 — bicimad.alternativa_bici, regla R0
sin_dato = isinstance(clima, dict) and clima.get("estado") == "no_disponible"
mal_tiempo = ok and apto is not True
if mal_tiempo or (clima no es un dict válido ni no_disponible): return no_ofrecida
# con sin_dato la regla R0 no se aplica

# T6 — capa 2, dentro del bucle de extremos de _planificar_ruta (después de clasificar y de aplicar `opcion_*`)
si clasificadas[rol] no es ok y hay texto_alternativo_<rol> (str no vacío):
    geo = geocodificar(alternativo)                      # +1 llamada a Nominatim (≤ 4 en total); normalizar_lugar incluido
    si geo falla: salir("geocodificacion_fallida")
    alt = clasificar_candidatos(geo)
    si alt es ok y verificar_candidato(alt.elegido): clasificadas[rol] = alt; avisos += «se usó «alternativo»: dirección. …»
    # si no: se mantiene el error original, sin más intentos
opcion_<rol> con probable_<rol> is True: el aviso empieza por «Elección automática: para el <rol> …»
salir(): avisos → texto (como siempre) y también al final de `bloques`

# T4 — sintetizador
extras = bloques de cada resultado (JSON de resultados[].resultado) + avisos obligatorios
texto = respuesta_llm
for e in extras: si e not in texto: añadir "\n\n" + e a la respuesta y a `texto`
```

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Normalizar dentro de `geocodificar` | Normalizar en cada llamada desde `_planificar_ruta` | Un solo punto, los dos extremos y la opción numerada (que geocodifica el mismo texto) quedan cubiertos. |
| `bloques` solo si no está vacío | Campo siempre presente | Los tests de contrato fijan el conjunto de claves por estado; así no cambia ningún estado sin bloques. |
| `mensaje` intacto; los motivos nuevos solo en `bloques` | Añadir las líneas al `mensaje` | Respeta lo pedido y los tests de `mensaje` (`endswith`, exactitud en R0/R1/R2). |
| `linea_motivo_bici` aparte; `bici` no cambia | Añadir `causa` al dict `bici` | Tres tests comparan el dict `bici` completo; el motivo R0/R1/R2 se deduce de los datos que ya tiene el enganche. |
| Una sola frase para EMT y Google caídos | Dos frases (`causa`) | Evita cambiar el contrato de `bici`; queda en «Dudas abiertas». |
| Dedupe secuencial contra el texto acumulado | `a not in respuesta` solo | El bloque de bici ya contiene el aviso de Google y el de clima la atribución; sin esto saldrían dos veces. |
| `interno` como cuarto valor de `causa` | Reutilizar una de las tres | Un error inesperado no es ni la EMT ni Google ni las credenciales; la frase genérica de siempre se conserva. |
| Capa 2 solo si el extremo no se resolvió | Probar el alternativo siempre | Evita llamadas innecesarias a Nominatim; límite ≤ 4. |
| Ficha de `rutas` solo en `limites` | Cambiar su `responsabilidad` | Un test existente fija el texto exacto de la responsabilidad; el límite llega igualmente al prompt del supervisor. |
| Reutilizar `titulo` | Parámetro nuevo `tarifa_solicitada` | Ya existe, ya se sanea y ya entra en la pregunta de precio al RAG (spec 004); falta explicarlo en el prompt. |
| Fase B: parámetros opcionales en la herramienta | Nueva tool de geocodificación | Menos superficie (allowlist y prompts de otros); la tool propia queda como mejora futura. |

## Estrategia de tests

Todos sin red: `tests/dobles_ruta.py::Escenario` para Nominatim, Google, RAG, EMT y Open-Meteo; modelo falso para el sintetizador. Escritos antes que el código y en rojo (T1 a T5).

| RF | Test |
|---|---|
| RF-1, 2, 3 | `test_normalizacion_lugares.py`: cada prefijo (mayúsculas y tildes) llega sin él a Nominatim; «Metro» solo no cambia; textos sin prefijo idénticos; sin «Madrid» añadido; sin llamadas extra; mensajes con el texto original. |
| RF-4 a 8 | `test_bloques_ruta.py`: ambigua → bloque con «Opciones» y `mensaje` igual; `direccion_no_encontrada` y `fuera_cobertura`; ok con bici → párrafo y clima; ok sin bici → línea de motivo por cada causa (R1, R2, R0, sin bicis, sin huecos, misma estación, no disponible); sin bloques no hay clave; orden. |
| RF-9 a 12 | `test_bloques_ruta.py`: clima caído → bici ofrecida y línea de aviso; petición de Google sin `LESS_WALKING`; mal tiempo → sin bici; hora pedida → sin clima; log con `URLError` y `reason` y sin claves. |
| RF-13 a 16 | `test_sintetizador_bloques.py`: ambigua con modelo que omite → opciones visibles; bici ok → bloque; motivo; clima; sin duplicar (incluido el aviso dentro del bloque); resultado ilegible no rompe y se registra; respaldo intacto; `test_sintetizador_avisos.py` sigue verde. |
| RF-17, 18 | `test_precio_titulo.py`: «abono joven» por `planificar_ruta_texto` → la pregunta de precio al RAG la contiene y son 2 llamadas; sin título, comportamiento actual; `PROMPT_RUTAS` contiene las cuatro reglas. |
| RF-19 a 21 | `test_capa2_lugares.py`: alternativo que resuelve, en ambos extremos (4 llamadas), sin resolver (nunca más de 4), no verificado (sin Madrid, ambiguo, fuera de ámbito), fallo de Nominatim, vacío o no texto, normalización de prefijos, `probable_*` y «opción usada» en `bloques`. |
| RF-22 a 24 | `test_prompt_capa2.py`: reglas del prompt, sin listas de títulos, y paso de argumentos del especialista a la tool con dobles. |
| RF-25 a 28 | `test_bloques_ruta.py` (zona y precio, `ruta_no_calculada`, `causa`), `test_catalogo_roles.py` (ficha). |
| RF-29 | `test_catalogo_roles.py::test_ficha_y_regla_incluyen_el_titulo_concreto`. |
| RF-31, 32 | `test_especialista_rutas.py` (nuevos al final): «de X al Y» con y sin «cuánto cuesta», «hasta», «voy de Sol a»/«al» (siguen con aviso), «a las 8», origen que falta; el prompt contiene la regla de bici; con un LLM falso, «ir en bici desde Cibeles hasta Plaza de España» ejecuta la tool con origen y destino. `test_prompt_sin_lista_de_titulos` sin tocar. |
| RF-30 | `test_supervisor_ruta_con_extremos.py`: «Quiero ir desde X hasta Y, ¿cuánto cuesta el abono joven?» con `[rag]` → `[rutas, rag]`; `[rutas, rag]` no cambia; solo precio, «¿Cómo voy a pagar el abono?», vacío y sin ruta no cambian; nunca quita roles; decisión del LLM, fallback y nodo. |

### Tests obsoletos (se anotan al implementar T3)

Solo dos tests existentes dejaron de cumplirse (los demás que simulan Open-Meteo caído en `Escenario` desactivan la bici y no se ven afectados). Se ajusta únicamente lo que el cambio exige:

| Test | Cambio | Por qué |
|---|---|---|
| `test_bicimad.py::test_no_apto_o_sin_dato_no_ofrece_bici_ni_llama_a_la_emt` (renombrado `test_no_apto_o_sin_consulta_no_ofrece_bici_ni_llama_a_la_emt`) | El caso `CLIMA_SIN_DATO` ya no impide la bici; se sustituye por `None` (sin consulta de clima), que sigue sin ofrecerla. El caso nuevo va en `test_sin_dato_de_clima_sigue_el_flujo_normal`. | RF-10 revisa RF-25 de la spec 009. |
| `test_bicimad.py::test_campo_bici_solo_en_ok_y_campos_existentes_intactos` | El conjunto de claves de un resultado `ok` incluye ahora `bloques`. | RF-4: campo aditivo nuevo. |
| `test_bicimad.py::test_emt_no_disponible_no_llama_a_google` | Fija credenciales de prueba y espera `causa == "emt"` y su frase (antes la frase única). | RF-27: la frase depende de la causa; sin credenciales de prueba dependería del entorno. |
| `test_bicimad.py::test_fallo_de_la_emt_deja_la_ruta_intacta_con_aviso` | Fija credenciales de prueba; el dict `bici` completo ahora lleva `causa` y la frase de la EMT. | RF-27: campo aditivo `causa`; los tests comparaban el dict completo. |
| `test_bicimad.py::test_fallo_de_google_en_la_bici_deja_la_ruta_intacta_con_aviso` | Espera `causa == "google"` y que el `mensaje` termine con su frase. | RF-27. |
| `test_catalogo_roles.py::test_instrucciones_reutilizan_catalogo_y_exclusiones_de_tarifas` y `test_supervisor_grafo.py::test_prompt_del_supervisor_se_genera_desde_el_catalogo_de_roles` | Comparaban la línea completa «Una consulta textual de tarifa sin imagen debe seleccionar rag.»; ahora comparan la regla acotada (RF-29). Las otras dos reglas de exclusión no cambian. | RF-29: se cambia el texto de la línea, como se pidió. |

## T11 y T12 (prueba real, 2026-10-21)

| Archivo | Cambio | RF |
|---|---|---|
| `src/graph.py` (de Rubén) | `_envolver_especialista` marca cada resultado con `turno` (importa `turno_actual` del sintetizador). | RF-33 |
| `src/sintetizador.py` (de Rubén y Guzmán) | `turno_actual(estado)` y filtro por turno en `_avisos_obligatorios`. | RF-33 |
| `src/tools/planificar_ruta.py` | `clasificar_candidatos`: si hay candidatos de Madrid verificados, solo ellos (antes de quitar duplicados). | RF-34 |
| `tests/test_sintetizador_turnos.py`, `tests/test_candidatos_madrid.py` | **Nuevos**; ningún test existente modificado. | RF-33, 34 |

**Cómo se distingue un turno de otro en `resultados[]`:** no se distinguía. `historial` solo recibe los mensajes de la persona (`_registrar_mensaje`); `notas`, `traza` y `resultados` se acumulan siempre; `tools_turno` y `turno_contabilizado` se reinician pero no se guardan en cada entrada; `turnos_completados` sube en `registrar_turno`, antes de la pausa del HITL, así que cambia de valor al reanudar y no sirve como marca. El nº de mensajes de la persona en `historial` es estable en todo el turno, también tras el HITL.

**T12 — aplicada (2026-10-21), Open-Meteo y los certificados:**

- `src/tools/bicimad.py`: `_get_json(..., contexto_certifi=False)`; `clima_origen` lo pide con `True`. Con `True` y `certifi` importable: `ssl.create_default_context(cafile=certifi.where())` (verificación siempre activa); si `certifi` no está, contexto por defecto. EMT y Google no cambian (con el bundle de Mozilla podrían dejar de validar su cadena).
- `requirements.txt`: `certifi` (ya instalado de forma transitiva; hay que actualizar antes spec y plan por la constitución, art. 12).
- Tests (sin red): con `urlopen` doble, que `clima_origen` pasa un contexto con `verify_mode == CERT_REQUIRED` y `check_hostname`, construido con `cafile=certifi.where()`; sin `certifi` (simulado con `sys.modules["certifi"] = None`), sin contexto; que el EMT no cambia; que nunca aparece `CERT_NONE` ni `_create_unverified_context` en `src/` (test de código fuente).
- Riesgo: si el bundle de `certifi` queda desfasado, el fallo sería el mismo en otra máquina; la cadena de Open-Meteo no depende del almacén de Windows.

## T14 — contexto del sintetizador y seguimiento

| Archivo | Cambio | RF |
|---|---|---|
| `src/sintetizador.py` (de Rubén y Guzmán) | `contexto_para_modelo(estado)`: contexto anclado con solo los resultados del turno actual, sin los textos de los `bloques` y con la clave `nota` cuando hay bloques; `nodo_sintetizador` se lo pasa al modelo. El respaldo y los avisos siguen usando `contexto_anclado` completo. | RF-39, RF-40 |
| `src/agents/rutas.py` (de Rubén y Guzmán) | Solo el texto de `PROMPT_RUTAS`: regla de seguimiento. | RF-41 |
| `tests/test_sintetizador_contexto.py`, `tests/test_prompt_seguimiento.py` | **Nuevos**. | RF-39 a 41 |
| `src/graph.py` (de Rubén) | Solo el nodo `sintetizador_aprobacion`: pasa `tras_aprobacion=True` a `nodo_sintetizador` (T15). | RF-42, 43 |

**T15 — confirmación tras aprobar (RF-42 y RF-43):** `nodo_sintetizador(estado, modelo, tras_aprobacion=False)`; con `True`, `contexto_para_modelo` pone la `nota` de aprobación en lugar de la de bloques y la respuesta del LLM se devuelve sin añadir bloques ni avisos. Se usa un parámetro del nodo y no `plan_aprobado` porque ese campo nunca se reinicia (queda puesto en los turnos siguientes). Auditoría: no choca con RF-20 (sigue sintetizando el LLM), RF-5, RF-21 ni RF-47 de la spec 005; tensión con RF-31 («devuelve su resultado») asumida (ver la spec). Los tests `test_grafo_hitl.py::test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido` y `test_clientes_grafo_real.py::test_varios_planes_exigen_elegir_y_se_aprueba_solo_el_elegido` usan un sintetizador falso que lee las notas (`[rutas] Plan aprobado ruta-N`), que se conservan: siguen pasando sin cambios. El respaldo tras aprobar es el de siempre (vuelca los resultados; RF-56).

**Auditoría de conflictos previa (T14):** RF-39 y RF-40 no contradicen ningún requisito: el LLM sigue recibiendo los resultados (RF-5) y sigue sintetizando (RF-20); el test `test_el_modelo_recibe_el_mismo_contexto` (spec 009) usa un caso sin bloques (sin `nota`, mismas tres claves) y `test_sintetizador.py` fija el contexto de estados sin resultados de ruta marcados, ambos intactos. RF-41 solo cambia el prompt y respeta `test_prompt_sin_lista_de_titulos`. El punto de la aprobación sí choca (ver la spec).

**Lógica:**

```text
contexto_para_modelo(estado):
    ctx = contexto_anclado(estado)
    ctx.resultados = [r for r in ctx.resultados si r no tiene `turno` o r.turno == turno_actual]
    bloques = los de planificar_ruta (turno actual)
    si bloques:
        en cada resultado de planificar_ruta: JSON sin la clave `bloques` y con cada bloque quitado de `mensaje`
        en cada nota: cada bloque quitado
        ctx.nota = NOTA_BLOQUES
    return ctx
```

## T13 — lógica y tests ajustados

```text
consultar_tarifa(origen, destino, titulo):
    sin municipios: zona y precio omitidos
    zona = _dato_rag(PREGUNTA_ZONA)                                     # 1.ª llamada
    título no interpretable: precio omitido
    precio = _dato_rag(PREGUNTA_PRECIO.format(titulo))                  # 2.ª llamada, sin zona
    si precio es sin_evidencia y zona ok y len(zona saneada) <= ZONA_LONGITUD_MAX:
        precio = _dato_rag(PREGUNTA_PRECIO_CON_ZONA.format(titulo, zona))   # 3.ª llamada, solo tras abstención
    # un error (excepción) en la 2.ª no provoca la 3.ª; ambos abstenidos → sin_evidencia
```

**Tests ajustados en T13** (todos por RF-36 a RF-38; ninguno pierde cobertura, cada uno comprueba ahora el criterio nuevo):

| Test | Cambio y motivo |
|---|---|
| Dobles del RAG (`Escenario._rag_ask` en `dobles_ruta.py` y `RagFalso` en `test_planificar_ruta_tarifa.py`) | Identifican como precio las preguntas con «precio» **o** «cuesta»: la nueva pregunta «¿Cuánto cuesta el {titulo}?» no lleva «precio». |
| `test_planificar_ruta_tarifa.py`: `test_rag_sin_evidencia_entrega_ruta`, `test_evidencia_parcial_declara_el_que_falta`, `test_no_inventa_zona_ni_precio`, `test_rag_con_error_entrega_ruta_sin_zona_ni_precio`, `test_rag_falla_la_ruta_se_conserva`, `test_zona_sin_evidencia_o_error_no_consulta_precio` | Fijaban «sin zona no se consulta el precio» (RF-52: precio `omitida`, 1 llamada, «Faltan la zona y el precio»). Ahora el precio se pregunta igualmente (2 llamadas): `sin_evidencia`, `error` u `ok` según el RAG. |
| `test_primero_zona_despues_precio_del_titulo` | La pregunta de precio ya no lleva «precio» ni la zona: se comprueba «cuesta» y que no haya «zona». |
| `test_zona_dentro_del_limite_se_pasa_entera`, `test_zona_por_encima_del_limite_no_consulta_el_precio`, `test_zona_demasiado_larga_se_informa_en_el_mensaje` | La zona entra solo en el segundo intento (tras abstención): 3 llamadas; con zona demasiado larga no hay segundo intento (2 llamadas) y el precio sin zona sí se entrega. El mensaje «no se pudo usar la zona» ya no aparece. |
| `test_planificar_ruta_rnf.py`: `test_maximo_2_llamadas_al_rag` → `test_maximo_3_llamadas_al_rag` | RF-49 pasa de 2 a 3 llamadas; casos nuevos de abstención (3 y 2) y los de zona con error o demasiado larga pasan de 1 a 2. |
| `test_bicimad.py::test_el_rag_mantiene_sus_dos_llamadas`, `test_planificar_ruta_municipio.py` (2 aserciones) | «precio» → «cuesta» en la segunda pregunta; siguen siendo 2 llamadas en el caso normal. |

Código muerto tras T13: en `_mensaje_tarifa`, las ramas «no se pudo usar la zona devuelta» y «Faltan la zona y el precio» ya no se alcanzan desde `consultar_tarifa` (el precio solo se omite con título no interpretable o sin municipios). Se dejan (tienen tests propios) y quedan como limpieza futura.

## Riesgos

- **Prompt frágil.** RF-18 es una instrucción al LLM: puede no cumplirse. Por eso lo crítico (opciones, bici, clima, motivo) lo fuerza el sintetizador (RF-13), no el prompt.
- **Doble aviso.** Mitigado con el dedupe secuencial (RF-14); la paráfrasis del LLM sigue pudiendo duplicar el contenido sin que el texto coincida (mejora futura: marca estable).
- **Bici sin comprobar el tiempo.** Con Open-Meteo caído puede ofrecerse bici con lluvia. Es una decisión explícita (RF-10); el aviso lo deja claro.
- **Archivos de Rubén.** `sintetizador.py` y `rutas.py` (solo el prompt) se tocan; hay que avisarle. `modelos.py`, `catalogo_roles.py` y `supervisor_reglas.py` no se tocan.
- **Primera aparición del separador (T10).** Un origen que contenga como palabra suelta «a», «al» o «hasta» se partiría mal; antes, con la última «a», el fallo era peor (y «al» nunca contaba). Es solo el atajo previo al LLM: si pasa, el LLM decide los extremos.
- **«En bici» (RF-32).** La persona puede esperar una ruta solo en bici y recibir transporte público; la alternativa en BiciMAD depende de las reglas de la spec 009.
- **Normalización agresiva.** «Metro de Madrid» pierde «Metro»; asumido en «Casos límite».
- **Fase B.** +1 llamada a Nominatim por extremo (≤ 4) y un caso en que se calcula con una elección del LLM (revierte RF-27 de la spec 004); por eso se declara siempre qué se usó (aviso en `mensaje` y en `bloques`).
- **Supervisor.** RF-30 es una heurística (verbo + «de/desde X a/hasta Y»): puede añadir `rutas` de más, sin quitar nada. «¿y cuánto cuesta?» de seguimiento sin extremos sigue sin cubrirse. Los archivos de Rubén y José Manuel se tocan solo de forma aditiva.
- **Credenciales en los tests.** Los tests de `causa` fijan credenciales de prueba con `monkeypatch`; sin ello el resultado dependería del `.env` local.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 a 3 | `normalizar_lugar` y `geocodificar` | `test_normalizacion_lugares.py` |
| RF-4 a 8 | `bloques` en `_planificar_ruta`, `linea_motivo_bici` | `test_bloques_ruta.py` |
| RF-9 a 12 | R0 y log en `bicimad.py`, `CLIMA_SIN_DATO_AVISO` | `test_bloques_ruta.py`, `test_bicimad.py` |
| RF-13 a 16 | `_avisos_obligatorios` y `nodo_sintetizador` | `test_sintetizador_bloques.py`, `test_sintetizador_avisos.py` |
| RF-17, 18 | `PROMPT_RUTAS`, `titulo` existente | `test_precio_titulo.py` |
| RF-19 a 21 | Capa 2 en `_planificar_ruta` | `test_capa2_lugares.py` |
| RF-22 a 24 | Capa 2 en `PROMPT_RUTAS` | `test_prompt_capa2.py` |
| RF-25 a 28 | Zona, precio, `causa`, ficha | `test_bloques_ruta.py`, `test_catalogo_roles.py` |
| RF-29, 30 | Regla de exclusión y `completar_rutas_con_extremos` | `test_catalogo_roles.py`, `test_supervisor_ruta_con_extremos.py` |
| RF-31, 32 | `SEPARADORES_DESTINO` y `PROMPT_RUTAS` | `test_especialista_rutas.py` |

## Fase C (solo documentada, no es parte de esta spec)

El corpus (`output/chunks.json`, de `Paradas CRTM.csv`) trae por parada: tipo de transporte (Metro 89 chunks, Cercanías 20, Metro Ligero 13, autobuses), zona y descripción/dirección (p. ej. «LEGAZPI — Plaza de Legazpi 2», metro, zona A; «CONCHA ESPINA — Calle del Príncipe de Vergara 2», metro, zona A). Idea: consultar esas paradas por nombre y tipo para resolver «Metro X» sin Nominatim por nombre, y geocodificar la **dirección** de la parada. Pendiente: spec propia, evaluación del retrieval con nombres repetidos entre tipos y zonas, y decidir si es una tool o parte de la capa 2.
