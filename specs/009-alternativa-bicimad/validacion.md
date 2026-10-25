# Validación — Spec 009

> Fecha: 2026-10-20 · Resultado de `python -m pytest`: **928 passed**, sin red ni LLM. T11 no hizo llamadas reales. Tests en `tests/test_bicimad.py` salvo indicación.
> Las demos reales son de T10 (`demos.md`); el caso feliz procede de la observación de la persona usuaria en Streamlit.

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático + manual | `::test_alternativa_junto_a_la_ruta_sin_cambiar_su_estado`; demo 1 (Streamlit): ruta de 20 min + alternativa de 29 min | ✅ |
| RF-2 | Automático | `::test_regla_hora_pedida_no_ofrece`, `::test_regla_distancia_en_los_bordes`, `::test_apto_aplica_la_regla_de_oferta` | ✅ |
| RF-3 | Automático + manual | `::test_r1_r2_no_llaman_a_nada`, `::test_r3_r4_no_llaman_a_google`; demo 2 (hora pedida): 0 llamadas de EMT y Google bici | ✅ |
| RF-4 | Automático | `::test_motivo_solo_en_r3_r4` | ✅ |
| RF-5 | Automático | `::test_login_y_estaciones_rutas_cabeceras_y_dos_llamadas`, `::test_token_reutilizado_en_la_segunda_consulta` | ✅ |
| RF-6 | Automático + manual | `::test_estacion_con_bicis_y_con_huecos`, `::test_inactiva_y_radio`, `::test_estacion_activa_segun_activate_no_available_y_virtual_delete`; demo 1: estaciones con 19 bicis y 2 huecos | ✅ (el criterio de «activa» es un supuesto, ver Fuera de spec) |
| RF-7 | Automático + manual | `::test_mensaje_indica_estaciones_y_disponibilidad`; demo 1 | ✅ |
| RF-8 | Automático + manual | `::test_tramo_bici_una_llamada_con_bicycle`; prueba aislada de Google (BICYCLE funciona en Madrid) | ✅ |
| RF-9 | Automático + manual | `::test_tramos_a_pie_con_walk`; prueba aislada de Google (WALK) | ✅ |
| RF-10 | Automático + manual | `::test_total_es_la_suma_y_etiqueta_fuentes`; demo 1: 1 + 22 + 6 = 29 min | ✅ |
| RF-11 | Automático | `::test_si_falla_un_tramo_no_hay_alternativa_parcial` | ✅ |
| RF-12 | Automático + manual | `::test_aviso_de_google_o_texto_fijo`; `tests/test_sintetizador_avisos.py::test_avisos_obligatorios_sobreviven_a_la_sintesis`; demo 1: aviso fijo y atribución al final | ✅ en el JSON y en el `mensaje`; **en la síntesis, condicionado a que Rubén apruebe T9** (si no, queda «no garantizado») |
| RF-13 | Automático + manual | `::test_fallo_de_la_emt_deja_la_ruta_intacta_con_aviso`, `::test_fallo_de_login_no_disponible_sin_excepcion_ni_reintento`, `::test_fallo_de_estaciones_no_disponible_sin_excepcion_ni_reintento`, `::test_timeout_en_cualquier_llamada_no_disponible_sin_reintento_ni_fugas`; demo 3 (sin credenciales) y timeout real del login | ✅ |
| RF-14 | Automático | `::test_google_falla_no_disponible` | ✅ |
| RF-15 | Automático | `::test_error_inesperado_no_rompe_la_ruta` | ✅ |
| RF-16 | Automático | `::test_campo_bici_solo_en_ok_y_campos_existentes_intactos` | ✅ |
| RF-17 | Automático | `::test_enganche_unico_en_planificar_ruta` | ✅ |
| RF-18 | Automático | `::test_el_rag_mantiene_sus_dos_llamadas` | ✅ |
| RF-19 | Automático | `::test_mensajes_de_bici_en_espanol` | ✅ |
| RF-20 | Automático + manual | `::test_clima_una_llamada_con_las_cuatro_variables`; demos 1, 3 y 4 con Open-Meteo real | ✅ |
| RF-21 | Automático | `::test_apto_exterior_cada_causa_y_los_bordes` | ✅ |
| RF-22 | Automático + manual | `::test_no_apto_pide_less_walking_sin_llamadas_extra`, `::test_apto_o_sin_dato_peticion_de_siempre`; demo 4: Google aceptó `LESS_WALKING` | ✅ |
| RF-23 | Automático | `::test_no_apto_o_sin_dato_no_ofrece_bici_ni_llama_a_la_emt` | ✅ |
| RF-24 | Automático + manual | `::test_linea_de_clima_con_atribucion`; demos 1 y 4 | ✅ |
| RF-25 | Automático | `::test_open_meteo_falla_ruta_intacta_y_sin_bici`, `::test_error_inesperado_en_clima_no_rompe_la_ruta` | ✅ (no se probó un Open-Meteo caído real) |
| RF-26 | Automático | `::test_campo_clima_solo_en_ok_sin_hora` | ✅ |
| RF-27 | Automático + manual | `::test_hora_pedida_no_consulta_el_clima`; demo 2: 0 llamadas a Open-Meteo | ✅ |
| RF-28 | Automático | `::test_el_rag_mantiene_sus_dos_llamadas` (compartido con RF-18) | ✅ |
| RNF Coste | Automático | `::test_limites_de_llamadas_emt_2_google_4_nominatim_2`, `::test_limite_open_meteo_1` | ✅ en tests; **demo 1 de Streamlit sin contar llamadas** |
| RNF Secretos | Automático | `::test_credenciales_solo_del_entorno_y_env_example`, `::test_credenciales_nunca_en_resultado_ni_log`, `::test_login_01_no_filtra_description_ni_secretos`; `tests/test_planificar_ruta_rnf.py::test_los_tests_no_hacen_peticiones_reales` | ✅ |
| RNF Tiempo | Manual | `config.py`: login 10 s, lista 20 s. No se midió la latencia total de la demo 1 | ⚠️ limitación conocida (25-30 s en el peor caso) |

## Criterios de finalización
- [x] Todos los RF con test en verde con dobles de la EMT y Google (928 passed).
- [x] RF-20 a RF-28 con test en verde con dobles de Open-Meteo.
- [x] Demo manual: trayecto que cumple la regla (observación en Streamlit), uno con hora pedida y uno con la EMT sin credenciales.
- [x] Atribución de Open-Meteo en el `README` (RNF Dependencias): hecha, apartado `## Créditos`.
- [x] Ampliación del clima (RF-20 a RF-28): aprobada e implementada (T12–T14); la cabecera de `spec.md` ya lo dice.

## Fuera de spec
- **Plazo propio de la lista de estaciones** (`EMT_TIMEOUT_ESTACIONES_S` = 20 s) y **login «01»** aceptado como correcto: se descubrieron en T10 y ya constan en spec y plan.
- **`_avisos_obligatorios` en `src/sintetizador.py`** (T9): archivo de Rubén, pendiente de su confirmación.
- **Supuesto «estación activa»** (`activate == 1`, `no_available == 0`, `virtualDelete` falso): no se contrastaron los recuentos; funcionó con las dos estaciones de la demo.
- Nada más.

## Veredicto
**Parcial.** Todo el comportamiento de la spec está implementado y cubierto por tests, y la demo real del caso feliz, la de hora pedida, la de EMT sin credenciales y la de mal tiempo coinciden con ella. Queda sin cerrar: (1) T9 pendiente de Rubén (RF-12 en la síntesis); (2) «estación activa» sin contrastar con recuentos; (3) la demo 1 se observó sin contar llamadas ni medir la latencia; (4) `LESS_WALKING` solo tiene una muestra (desfavorable: 20 → 36 min); (5) el mensaje de `LESS_WALKING` dice «la ruta se pidió con menos tramos a pie», que describe lo pedido y no lo conseguido: en la única muestra el viaje salió 16 min más largo.
