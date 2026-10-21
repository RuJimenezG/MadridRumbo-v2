# Plan técnico — Spec 010 (lugares, bloques literales y precio)

> Basado en `spec.md` (estado: Borrador). No añade comportamiento que no esté en la spec. Implementado: Fase A (T1–T5 y T5b) y Fase B (T6–T7); T8 en `validacion.md`.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/tools/planificar_ruta.py` | Modificar (mínimo) | `normalizar_lugar` (función pura) y su uso en `geocodificar`; `bloques` en las ramas de dirección problemática, en `ruta_no_calculada` (RF-26) y en la rama `ok` (zona y precio, RF-25); el enganche de la bici pasa `clima` también cuando no está disponible; Fase B: parámetros `texto_alternativo_*` y `probable_*`, y los avisos de «qué se usó» también en `bloques` (a través de `salir`). | RF-1 a 8, 10, 19 a 21, 25, 26 |
| `src/tools/bicimad.py` | Modificar | R0 solo rechaza con clima **apto = falso**; `linea_motivo_bici` (pura); log de `URLError` con su `reason`; `causa` y `FRASES_NO_DISPONIBLE` (T5b). | RF-7, 9, 10, 11, 27 |
| `config.py` | Modificar (compartido; junto a las constantes `CLIMA_*`) | `CLIMA_SIN_DATO_AVISO` (texto fijo de RF-10). | RF-10 |
| `src/sintetizador.py` | Modificar (de Rubén y Guzmán) | `_avisos_obligatorios` pasa a devolver también los `bloques`; el nodo los añade sin duplicar (también contra bloques ya añadidos); log del resultado ilegible. | RF-13 a 16 |
| `src/agents/rutas.py` | Modificar (de Rubén y Guzmán) | Solo el texto de `PROMPT_RUTAS` (RF-18; capa 2, RF-22 a 24). Sin cambios de código. | RF-17, 18, 22 a 24 |
| `src/catalogo_roles.py` | Modificar (**de Rubén**; solo texto) | `limites` de la ficha del rol `rutas`: incluye zona y precio y las preguntas de precio de seguimiento van a `rutas`. La `responsabilidad` no cambia. | RF-28 |
| `tests/test_normalizacion_lugares.py` | **Crear** | T1. | RF-1 a 3 |
| `tests/test_bloques_ruta.py` | **Crear** | T2 y T3 (`Escenario`, sin red). | RF-4 a 12 |
| `tests/test_sintetizador_bloques.py` | **Crear** | T4 (modelo falso). | RF-13 a 16 |
| `tests/test_precio_titulo.py` | **Crear** | T5. | RF-17, 18 |
| `tests/test_capa2_lugares.py` | **Crear** | T6. | RF-19 a 21 |
| `tests/test_prompt_capa2.py` | **Crear** | T7. | RF-22 a 24 |
| `tests/test_catalogo_roles.py` | Añadir un test (T5b c) | La ficha de `rutas` contiene lo pedido. | RF-28 |
| `tests/test_bicimad.py` y otros | Modificar solo los que el cambio de RF-10 obligue | Los que fijan «sin dato de clima → sin bici» (ver «Tests obsoletos»). | RF-10 |
| `src/modelos.py`, `src/supervisor_reglas.py`, `src/graph.py`, `rag/`, corpus, `output/chunks.json`, `src/tools/__init__.py` | **No se tocan** | — | — |

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

### Tests obsoletos (se anotan al implementar T3)

Solo dos tests existentes dejaron de cumplirse (los demás que simulan Open-Meteo caído en `Escenario` desactivan la bici y no se ven afectados). Se ajusta únicamente lo que el cambio exige:

| Test | Cambio | Por qué |
|---|---|---|
| `test_bicimad.py::test_no_apto_o_sin_dato_no_ofrece_bici_ni_llama_a_la_emt` (renombrado `test_no_apto_o_sin_consulta_no_ofrece_bici_ni_llama_a_la_emt`) | El caso `CLIMA_SIN_DATO` ya no impide la bici; se sustituye por `None` (sin consulta de clima), que sigue sin ofrecerla. El caso nuevo va en `test_sin_dato_de_clima_sigue_el_flujo_normal`. | RF-10 revisa RF-25 de la spec 009. |
| `test_bicimad.py::test_campo_bici_solo_en_ok_y_campos_existentes_intactos` | El conjunto de claves de un resultado `ok` incluye ahora `bloques`. | RF-4: campo aditivo nuevo. |
| `test_bicimad.py::test_emt_no_disponible_no_llama_a_google` | Fija credenciales de prueba y espera `causa == "emt"` y su frase (antes la frase única). | RF-27: la frase depende de la causa; sin credenciales de prueba dependería del entorno. |
| `test_bicimad.py::test_fallo_de_la_emt_deja_la_ruta_intacta_con_aviso` | Fija credenciales de prueba; el dict `bici` completo ahora lleva `causa` y la frase de la EMT. | RF-27: campo aditivo `causa`; los tests comparaban el dict completo. |
| `test_bicimad.py::test_fallo_de_google_en_la_bici_deja_la_ruta_intacta_con_aviso` | Espera `causa == "google"` y que el `mensaje` termine con su frase. | RF-27. |

## Riesgos

- **Prompt frágil.** RF-18 es una instrucción al LLM: puede no cumplirse. Por eso lo crítico (opciones, bici, clima, motivo) lo fuerza el sintetizador (RF-13), no el prompt.
- **Doble aviso.** Mitigado con el dedupe secuencial (RF-14); la paráfrasis del LLM sigue pudiendo duplicar el contenido sin que el texto coincida (mejora futura: marca estable).
- **Bici sin comprobar el tiempo.** Con Open-Meteo caído puede ofrecerse bici con lluvia. Es una decisión explícita (RF-10); el aviso lo deja claro.
- **Archivos de Rubén.** `sintetizador.py` y `rutas.py` (solo el prompt) se tocan; hay que avisarle. `modelos.py`, `catalogo_roles.py` y `supervisor_reglas.py` no se tocan.
- **Normalización agresiva.** «Metro de Madrid» pierde «Metro»; asumido en «Casos límite».
- **Fase B.** +1 llamada a Nominatim por extremo (≤ 4) y un caso en que se calcula con una elección del LLM (revierte RF-27 de la spec 004); por eso se declara siempre qué se usó (aviso en `mensaje` y en `bloques`).
- **Supervisor.** La ficha de `rutas` no basta por sí sola (ver «Dudas» de `validacion.md`): la instrucción «tarifa sin imagen → rag» y el fallback por palabras siguen pudiendo enviar «¿y cuánto cuesta?» a `rag`.
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

## Fase C (solo documentada, no es parte de esta spec)

El corpus (`output/chunks.json`, de `Paradas CRTM.csv`) trae por parada: tipo de transporte (Metro 89 chunks, Cercanías 20, Metro Ligero 13, autobuses), zona y descripción/dirección (p. ej. «LEGAZPI — Plaza de Legazpi 2», metro, zona A; «CONCHA ESPINA — Calle del Príncipe de Vergara 2», metro, zona A). Idea: consultar esas paradas por nombre y tipo para resolver «Metro X» sin Nominatim por nombre, y geocodificar la **dirección** de la parada. Pendiente: spec propia, evaluación del retrieval con nombres repetidos entre tipos y zonas, y decidir si es una tool o parte de la capa 2.
