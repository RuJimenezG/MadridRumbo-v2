# Validación — Spec 010

> Fecha: 2026-10-21 · `python -m pytest`: **1041 passed**, sin red ni LLM (todo con dobles). No se hizo ninguna llamada real a ningún servicio en esta spec; los diagnósticos reales previos (Nominatim, ruta Sol → Bernabéu) están en la conversación, no en tests.
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
| RF-28 | **Parcial** | `test_catalogo_roles.py::test_ficha_de_rutas_incluye_zona_y_precio_y_las_preguntas_de_seguimiento`: la ficha lo dice y llega al prompt del supervisor, pero **no garantiza** el enrutado (ver «Dudas»). |

## Tests existentes modificados (justificación en `plan.md`)

`test_bicimad.py`: `test_no_apto_o_sin_dato_…` (renombrado), `test_campo_bici_solo_en_ok_y_campos_existentes_intactos`, `test_emt_no_disponible_no_llama_a_google`, `test_fallo_de_la_emt_deja_la_ruta_intacta_con_aviso` y `test_fallo_de_google_en_la_bici_deja_la_ruta_intacta_con_aviso`. Ningún otro test existente se tocó.

## Qué no se ha comprobado

- Ninguna ruta real tras los cambios: la bici con el clima caído, los bloques en el texto final de Streamlit/CLI y el comportamiento del LLM del sintetizador con los bloques añadidos.
- El comportamiento real del LLM de rutas con las reglas de la capa 2 (RF-22 a RF-24): si elige solo entre candidatos, si pregunta con confianza baja y si propone un único alternativo.
- Que el supervisor real enrute «¿y cuánto cuesta?» a `rutas`.

## Dudas

1. **La ficha de `rutas` no basta para el supervisor.** Leído `supervisor.py`, `catalogo_roles.py` y `supervisor_reglas.py` (este último sin tocar):
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

## Mejoras futuras (no implementadas)

1. **Fase C — paradas del corpus.** `output/chunks.json` (de `Paradas CRTM.csv`) trae por parada el tipo de transporte, la zona y el nombre con su descripción/dirección: Metro 89 chunks, Cercanías 20, Metro Ligero 13 y autobuses (EMT 816, urbano 1405, interurbano 1405). Evidencia: «Legazpi» aparece en 20 chunks (37 veces; Metro zona A 3, bus EMT/urbano/interurbano zona A) y «Concha Espina» en 11 (22 veces; Metro zona A 2, bus EMT zona A, urbano e interurbano zona B1); p. ej. «LEGAZPI — Plaza de Legazpi 2» y «CONCHA ESPINA — Calle del Príncipe de Vergara 2», ambas Metro zona A. Idea: consultar la parada por nombre y tipo (el nombre se repite entre tipos y zonas, así que el retrieval necesita «Metro») y geocodificar la **dirección** en vez del nombre. Requiere spec propia y evaluar el retrieval.
2. **Tool de geocodificación propia**, para que el LLM elija entre candidatos antes de planificar (toca allowlist, prompts y tests de varios autores).
3. **Salida estructurada del sintetizador**: secciones tipadas (resumen, opciones, bici…) en lugar de texto libre; cambia el contrato de `respuesta`.
4. **Marca estable contra duplicados por paráfrasis**: hoy el dedupe es textual (`a not in texto`); un delimitador o identificador por bloque evitaría repetir lo que el LLM parafraseó.
5. **Cambio en el supervisor** (archivos de Rubén y José Manuel): regla de exclusión de `instrucciones_para_supervisor`, fallback por palabras para el seguimiento de precio y `corregir_tarifas_textuales` para no sumar `rag` cuando ya hay `rutas`; o pasar el historial al especialista RAG.
6. **`sin_ruta` en `bloques`**, si se considera necesario.
