# Validación — Spec 004 (planificar ruta)

> Fecha: 2026-10-19 · Resultado de `pytest`: **524 passed** (sin API) · Validación solo con `pytest`, más lo ya anotado en `demos-T17.md`.
> Los tests se asocian por **comportamiento**, no por el número de RF que citan los comentarios de `tests/test_especialista_rutas.py` (ese archivo cita RF de otra spec).
> Abreviaturas: `geo` = `test_planificar_ruta_geocodificacion.py`, `goo` = `test_planificar_ruta_google.py`, `ht` = `test_planificar_ruta_hora_titulo.py`, `tar` = `test_planificar_ruta_tarifa.py`, `mun` = `test_planificar_ruta_municipio.py`, `rnf` = `test_planificar_ruta_rnf.py`, `esp` = `test_especialista_rutas.py`, `tra` = `test_tool_rutas_traza.py`, `amb` = `test_planificar_ruta_ambito.py`.

## Requisitos funcionales

| RF | Cómo se comprueba | Test | Resultado |
|---|---|---|---|
| RF-1 | Automático | `geo::test_geocodifica_origen_y_destino_con_nominatim` | ✅ |
| RF-2 | Automático | `amb::test_ambito_definido_en_config` | ✅ |
| RF-3 | Automático | `amb::test_sol_dentro_barcelona_fuera_y_borde`, `::test_homonimo_fuera_se_descarta_y_el_de_dentro_se_conserva` | ✅ |
| RF-4 | Automático | `geo::test_solo_fuera_de_ambito_rechaza`, `::test_destino_fuera_del_ambito_da_fuera_cobertura_y_no_no_encontrada` | ✅ |
| RF-5 | Automático | `goo::test_fuera_de_cobertura_no_llama_a_google` | ✅ |
| RF-6 | Automático | `geo::test_sin_resultados_pide_direccion_precisa`, `::test_direccion_no_encontrada_pide_una_mas_precisa` | ✅ |
| RF-7 | Automático | `geo::test_un_candidato_continua_e_indica_direccion` | ✅ |
| RF-8 | Automático | `geo::test_varios_candidatos_limita_y_no_calcula` | ✅ |
| RF-9 | Automático | `geo::test_aclaracion_en_respuesta_sin_pausa` | ✅ |
| RF-10 | Automático | `geo::test_misma_ubicacion_no_calcula`, `::test_misma_ubicacion_no_llama_a_google` | ✅ |
| RF-40 | Automático | `geo::test_nominatim_falla_no_llama_a_google_ni_rag`, `::test_nominatim_falla_se_detiene_sin_google_ni_rag` | ✅ |
| RF-11 | Automático | `goo::test_calcula_con_coordenadas` | ✅ |
| RF-12 | Automático | `goo::test_pide_solo_los_modos_de_la_red_crtm`, `::test_modos_permitidos_y_tipo_no_aceptado`, `::test_modos_aceptados_dan_ruta` | ✅ (limitación conocida: Cercanías y Avant no se distinguen, `HEAVY_RAIL`) |
| RF-13 | Automático | `goo::test_solo_a_pie_es_sin_ruta` | ✅ |
| RF-14 | Automático | `goo::test_sin_hora_no_hay_departure_time`, `ht::test_sin_hora_usa_momento_de_consulta` | ✅ |
| RF-15 | Automático | `goo::test_devuelve_tiempo_y_tramos` | ✅ |
| RF-16 | Automático | `goo::test_google_falla_informa`, `::test_sin_clave_falla_sin_llamar_a_la_red` | ✅ |
| RF-17 | Automático | `goo::test_sin_ruta_no_da_zona_ni_precio`, `::test_sin_ruta_no_da_zona_ni_precio_ni_consulta_al_rag` | ✅ |
| RF-18 | Automático | `goo::test_no_estima_tiempos_ni_trayectos` | ✅ |
| RF-42 | Automático | `rnf::test_error_inesperado_da_error_interno`, `::test_error_interno_se_registra_solo_en_el_log`, `tra::test_error_interno_queda_en_traza` | ✅ |
| RF-19 | Automático (dobles) | `tar::test_consulta_zona_y_precio_sencillo`, `::test_mensaje_etiqueta_google_y_rag` | ✅ con dobles; calidad real en T17 / ver excepciones |
| RF-20 | Automático (dobles) | `tar::test_google_falla_consulta_rag_con_municipios`, `goo::test_google_falla_consulta_rag_con_municipios_de_nominatim`, `mun::test_google_caido_usa_los_mismos_municipios` | ✅ con dobles; calidad real en T17 / ver excepciones |
| RF-21 | Automático (dobles) | `tar::test_rag_sin_evidencia_entrega_ruta`, `::test_rag_sin_evidencia_se_declara_en_el_mensaje` | ✅ con dobles; calidad real en T17 / ver excepciones |
| RF-22 | Automático (dobles) | `tar::test_evidencia_parcial_declara_el_que_falta` | ✅ con dobles; calidad real en T17 / ver excepciones |
| RF-23 | Automático | `tar::test_no_inventa_zona_ni_precio`, `::test_texto_del_rag_sin_modificar` | ✅ |
| RF-24 | Automático | `tar::test_mensaje_etiqueta_google_y_rag`, `::test_la_fuente_es_siempre_rag` | ✅ |
| RF-41 | Automático | `tar::test_rag_con_error_entrega_ruta_sin_zona_ni_precio`, `::test_rag_falla_la_ruta_se_conserva`, `::test_error_del_rag_en_el_precio_no_se_reintenta` | ✅ |
| RF-25 | Automático | `esp::test_config_allowlist_rutas`, `tra::test_registrada_en_la_allowlist` | ✅ |
| RF-26 | Automático (dobles) | `esp::test_rutas_sin_un_extremo_no_invoca_la_tool`, `::test_formulacion_incompleta_pide_aclaracion_antes_de_llm_tool_y_hitl` | ✅ con dobles; el comportamiento real se vio en T17 caso 7, no en pytest |
| RF-27 | Automático (dobles) | `esp::test_rutas_no_asume_un_origen_por_defecto`, `::test_prompt_prohibe_inventar_o_suponer_extremos` *(nuevos, T18)* | ✅ con dobles (el LLM real no se probó para este RF) |
| RF-28 | Automático (dobles) | `esp::test_rutas_combina_un_extremo_aportado_en_el_turno_anterior` | ✅ con dobles; el comportamiento real se vio en T17 caso 7, no en pytest |
| RF-29 | Automático (dobles) | `esp::test_rutas_consulta_que_no_es_de_rutas_no_invoca_la_tool` | ✅ con dobles; el comportamiento real se vio en T17 caso 7, no en pytest |
| RF-30 | Automático | `tra::test_traza_refleja_estado` | ✅ |
| RF-50 | Automático | `esp::test_prompt_lleva_fecha_y_hora_de_ahora`, `::test_prompt_lee_la_hora_en_cada_llamada`, `::test_prompt_sin_lista_de_titulos` | ✅ |
| RF-50b | Automático | `esp::test_prompt_indica_formato_iso_8601_con_hora` | ✅ |
| RF-31 | Automático | `ht::test_hora_rfc3339_con_desplazamiento_de_madrid`, `goo::test_hora_pedida_llega_a_google_en_rfc3339` | ✅ |
| RF-32 | Automático | `ht::test_hora_pasada_no_calcula`, `::test_llegada_rechazada_con_las_mismas_reglas_que_la_salida` | ✅ |
| RF-33 | Automático | `ht::test_hora_no_interpretable_no_calcula`, `::test_hora_no_interpretable_muestra_el_texto_recibido` | ✅ |
| RF-34 | Automático | `ht::test_hora_demasiado_lejana` | ✅ |
| RF-35 | Automático | `tar::test_titulo_libre_consulta_su_precio`, `::test_titulo_libre_de_extremo_a_extremo`, `ht::test_titulo_libre_se_acepta_sin_lista_cerrada` | ✅ |
| RF-36 | — | **Obsoleto** (sustituido por RF-46 a RF-49) | — |
| RF-37 | Automático | `tar::test_sin_precio_del_titulo_no_lo_sustituye`, `::test_titulo_que_el_corpus_no_conoce_se_abstiene` | ✅ |
| RF-38 | Automático | `ht::test_todos_los_estados_incluyen_hora_y_titulo`, `::test_cabecera_de_llegada_indica_la_hora_de_llegada_considerada` | ✅ |
| RF-39 | Automático | `ht::test_hora_llegada_valida_se_acepta`, `goo::test_hora_llegada_usa_arrival_time_sin_departure_time`, `::test_llegada_con_google_sin_ruta_llama_una_sola_vez` | ✅ |
| RF-43 | Automático | `ht::test_salida_y_llegada_a_la_vez_no_calcula`, `::test_salida_y_llegada_a_la_vez_rechaza_sin_llamar_a_nada` | ✅ |
| RF-44 | Automático | `goo::test_llegada_indica_hora_de_salida_resultante` | ✅ |
| RF-45 | Automático | `goo::test_llegada_sin_salida_de_google_no_la_estima`, `::test_salida_de_google_ilegible_se_trata_como_ausente` | ✅ |
| RF-46 | Automático (dobles) | `tar::test_primero_zona_despues_precio_del_titulo`, `mun::test_zona_antes_que_precio_y_maximo_2_llamadas_con_municipios` | ✅ |
| RF-47 | Automático | `ht::test_titulo_sin_saltos_de_linea` | ✅ |
| RF-48 | Automático | `ht::test_titulo_respeta_longitud_maxima`, `::test_titulo_demasiado_largo_no_consulta_el_precio`, `::test_titulo_en_el_limite_no_se_corta` | ✅ |
| RF-51 | Automático | `ht::test_titulo_vacio_aplica_billete_sencillo`, `::test_titulo_vacio_tras_sanear_usa_sencillo_y_lo_indica` | ✅ |
| RF-52 | Automático | `tar::test_zona_sin_evidencia_o_error_no_consulta_precio` | ✅ |
| RF-53 | Automático (dobles) | `tar::test_zona_se_sanea_antes_de_la_pregunta_de_precio`, `::test_zona_dentro_del_limite_se_pasa_entera`, `::test_zona_por_encima_del_limite_no_consulta_el_precio`, `::test_zona_demasiado_larga_se_informa_en_el_mensaje` | ✅ con dobles; calidad real en T17 / ver excepciones |
| RF-49 | Automático | `rnf::test_maximo_2_llamadas_al_rag`, `ht::test_titulo_libre_nunca_supera_dos_llamadas_al_rag` | ✅ |
| RF-54 | Automático | `mun::test_pregunta_de_zona_usa_municipio_de_origen_y_destino`, `::test_google_caido_usa_los_mismos_municipios`, `goo::test_secuencia_nominatim_google_rag` | ✅ |
| RF-55 | Automático | `mun::test_verificar_candidato`, `::test_geocodificar_extrae_region_e_iso`, `::test_extremo_no_verificado_no_entrega_ruta`, `::test_ambos_extremos_no_verificados_se_listan_los_dos`, `::test_la_verificacion_va_despues_de_ambito_y_ambiguedad` | ✅ con dobles; valores reales de state/ISO: ver riesgo pendiente |

## Requisitos no funcionales

| RNF | Test | Resultado |
|---|---|---|
| Idioma (mensajes en español) | `rnf::test_mensajes_en_espanol` | ✅ |
| Secretos (clave de Google solo del entorno) | `rnf::test_clave_solo_del_entorno`, `goo::test_clave_solo_en_la_cabecera`, `rnf::test_env_example_declara_los_nombres_sin_valor`, `rnf::test_ningun_correo_escrito_en_el_codigo` | ✅ |
| Configuración (límites en un único punto) | `rnf::test_limites_y_listas_de_config` | ✅ |
| Dependencias (sin dependencias nuevas) | `geo::test_http_json_usa_urllib_sin_salir_a_la_red` (HTTP con la librería estándar). No hay test que vigile `requirements.txt` | ✅ parcial |
| Tests (ninguno llama a servicios reales) | `rnf::test_los_tests_no_hacen_peticiones_reales` | ✅ |
| Uso responsable de Nominatim (1 petición/s e identificación) | `rnf::test_intervalo_y_user_agent`, `::test_intervalo_nominatim_respeta_politica_de_uso`, `::test_contacto_nominatim_solo_del_entorno` | ✅ |
| Coste (≤ 2 Nominatim, 1 Google, 2 RAG) | `rnf::test_maximo_2_nominatim_y_1_google`, `::test_maximo_2_llamadas_al_rag` | ✅ |

## Criterios de finalización

- [x] Todos los RF vigentes tienen test en verde con dobles para Nominatim, Google Routes, RAG y LLM (524 passed).
- [x] Demo manual de una consulta completa con ruta, zona y precio: hecha en T17 (caso 7: Bernabéu → Sol con zona y precio del billete sencillo; caso 2 con hora de llegada). Fuera de pytest.
- [x] Demo manual de un caso fuera de cobertura (caso 4) y de uno ambiguo (caso 5; Atocha y Plaza de Castilla). Fuera de pytest.

## Excepciones de T17 (`demos-T17.md`)

1. **Caso 1 — ambigüedad legítima (RF-8).** Atocha y Plaza de Castilla siguen ambiguas para Nominatim aunque acaben en «, Madrid»; la herramienta pide concretar. Se resuelve en **T23** (pendiente, requiere cambiar el prompt de `src/agents/rutas.py`, de Rubén).
2. **Caso 3 — límite del RAG compartido.** La zona es correcta, pero el precio del abono joven depende de que el RAG recupere su tabla de precios, que hoy no recupera (el billete sencillo sí). A plantear al equipo; no se cambia `rag/` en esta spec.

## Riesgo pendiente

- **state / ISO con municipios pequeños (RF-55).** En 20 de 20 resultados reales de Nominatim (Sol, Atocha, Plaza de Castilla, Bernabéu) `state = "Comunidad de Madrid"`, `ISO3166-2-lvl4 = "ES-MD"` y municipio `Madrid`. No se ha visto un municipio pequeño (p. ej. Alcalá de Henares) ni una dirección sin ciudad; si Nominatim no trae municipio o ISO/state ahí, RF-55 rechazaría rutas válidas. Tampoco se ha repetido «entre X y Y» con dos municipios distintos contra el RAG real.

## Fuera de spec

Nada que la spec no pida. `verificar_candidato` y los campos `region` e `iso` de los candidatos están cubiertos por RF-55.

## Veredicto

**Parcial.** Todos los RF y RNF vigentes tienen test en verde (524), pero: (1) RF-19 a RF-22 y RF-53 solo se verifican con dobles y su calidad real depende del RAG (caso 3 de T17); (2) RF-26, RF-28 y RF-29 se vieron con el LLM real solo en T17 caso 7, no en pytest; (3) el caso 1 de T17 queda a T23; (4) queda el riesgo de state/ISO con municipios pequeños.
