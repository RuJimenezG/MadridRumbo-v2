# Validación — Spec 011

> Fecha: 2026-10-22 · Resultado de `python -m pytest -q --tb=no`: **100 % passed**.
>
> Alcance: validación estática y con dobles, sin LLM, APIs, embeddings ni ChromaDB reales.

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_estado_grafo.py::test_proyeccion_publica_tiene_seis_claves_log_efimero_y_traza_normalizada`; `tests/test_agent_contrato.py::test_fachada_expone_las_dos_firmas_y_las_seis_claves` | ✅ |
| RF-2 | Automático | `tests/test_depuracion.py::test_las_sesiones_son_independientes_y_exponen_una_copia_de_las_entradas`; `tests/test_agent_contrato.py::test_pausa_y_reanudacion_hitl_entregan_logs_nuevos_y_no_persistidos` | ✅ |
| RF-3 | Automático | `tests/test_depuracion.py::test_entrada_completada_tiene_el_esquema_publico_y_detalle_nulo` | ✅ |
| RF-4 | Automático | `tests/test_depuracion.py::test_pasos_son_consecutivos_y_aceptan_los_tipos_y_resultados_permitidos`, `test_rechaza_tipos_de_entrada_no_permitidos` y `test_rechaza_resultados_no_permitidos` | ✅ |
| RF-5 | Automático | `tests/test_depuracion.py::test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos` | ✅ |
| RF-6 | Automático | `tests/test_depuracion.py::test_ejecutor_transversal_registra_tools_en_orden_y_conserva_traza` | ✅ |
| RF-7 | Automático | `tests/test_depuracion.py::test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos` | ✅ |
| RF-8 | Automático | `tests/test_depuracion.py::test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos` | ✅ |
| RF-9 | Automático | `tests/test_depuracion.py::test_ejecutor_transversal_registra_tools_en_orden_y_conserva_traza` | ✅ |
| RF-10 | Automático | `tests/test_depuracion.py::test_una_entrada_completada_exige_detalle_nulo`; `test_fallback_del_supervisor_se_proyecta_como_control_efimero` | ✅ |
| RF-11 | Automático | `tests/test_depuracion.py::test_ejecutor_transversal_registra_el_fallo_si_la_tool_lanza`; `test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos` | ✅ |
| RF-12 | Automático | `tests/test_agent_contrato.py::test_rechazos_de_fachada_devuelven_un_unico_control_sin_ejecutar_grafo` | ✅ |
| RF-13 | Automático | `tests/test_agent_contrato.py::test_pausa_y_reanudacion_hitl_entregan_logs_nuevos_y_no_persistidos` | ✅ |
| RF-14 | Automático | `tests/test_agent_contrato.py::test_pausa_y_reanudacion_hitl_entregan_logs_nuevos_y_no_persistidos` | ✅ |
| RF-15 | Automático | `tests/test_estado_grafo.py::test_estado_inicial_no_contiene_el_log_efimero_y_mantiene_colecciones_aisladas`; `tests/test_agent_contrato.py::test_resultado_del_turno_no_recupera_un_log_desde_el_checkpoint` | ✅ |
| RF-16 | Automático | `tests/test_depuracion.py::test_primitivos_listas_y_diccionarios_se_conservan_cuando_no_son_sensibles`; `test_sesion_registrar_sanea_todas_las_partes_de_la_entrada` | ✅ |
| RF-17 | Automático | `tests/test_depuracion.py::test_sanea_recursivamente_credenciales_sin_distinguir_mayusculas` | ✅ |
| RF-18 | Automático | `tests/test_depuracion.py::test_sanea_recursivamente_credenciales_sin_distinguir_mayusculas` | ✅ |
| RF-19 | Automático | `tests/test_depuracion.py::test_sanea_prompts_y_cuerpos_externos_completos` | ✅ |
| RF-20 | Automático | `tests/test_depuracion.py::test_limite_de_longitud_usa_la_representacion_json_segura` | ✅ |
| RF-21 | Automático | `tests/test_depuracion.py::test_valor_no_json_se_resume_sin_usar_su_representacion_cruda` | ✅ |
| RF-22 | Automático | `tests/test_depuracion.py::test_sanea_recursivamente_credenciales_sin_distinguir_mayusculas`, `test_sanea_prompts_y_cuerpos_externos_completos` y `test_valor_no_json_se_resume_sin_usar_su_representacion_cruda` | ✅ |
| RF-23 | Automático | `tests/test_clientes_grafo_real.py::test_fallback_real_del_supervisor_llega_a_cli_y_panel_pero_no_al_chat` fuerza una decisión inválida en el Supervisor real y comprueba su entrada `control` en la CLI; `tests/test_cli.py::test_cli_muestra_el_registro_estructurado_completo_en_orden` comprueba el formato y orden completos. | ✅ |
| RF-24 | Automático | `tests/test_app_streamlit.py::test_el_panel_muestra_el_fallback_real_del_supervisor_y_el_chat_lo_filtra` ejecuta el grafo real con fallback mediante `AppTest` y verifica que el panel muestra `json_invalido`; `tests/test_clientes_grafo_real.py::test_fallback_real_del_supervisor_llega_a_cli_y_panel_pero_no_al_chat` comprueba el log completo que consume el panel. | ✅ |
| RF-25 | Automático | `tests/test_app_streamlit.py::test_el_panel_muestra_el_fallback_real_del_supervisor_y_el_chat_lo_filtra`; `tests/test_presentacion.py::test_pasos_ocultan_el_diagnostico_del_supervisor_por_defecto` | ✅ |
| RF-26 | Automático | `tests/test_depuracion.py::test_ejecutor_transversal_registra_tools_en_orden_y_conserva_traza`; `tests/test_estado_grafo.py::test_proyeccion_publica_tiene_seis_claves_log_efimero_y_traza_normalizada` | ✅ |
| RF-27 | Automático | `tests/test_depuracion.py::test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos`; `tests/test_agent_contrato.py::test_pausa_y_reanudacion_hitl_entregan_logs_nuevos_y_no_persistidos` | ✅ |

## Criterios de finalización

- [x] Todos los RF cuentan con evidencia automatizada y `python -m pytest` está verde.
- [x] Hay una prueba de orden, campos e instantáneas de entrada/salida con varios nodos y una tool: `tests/test_depuracion.py::test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos`.
- [x] La CLI y el panel de Streamlit muestran el mismo log de una ejecución real, incluido el diagnóstico de fallback del Supervisor, y el chat lo filtra: `tests/test_clientes_grafo_real.py::test_fallback_real_del_supervisor_llega_a_cli_y_panel_pero_no_al_chat` y `tests/test_app_streamlit.py::test_el_panel_muestra_el_fallback_real_del_supervisor_y_el_chat_lo_filtra`.
- [x] Una pausa HITL y la reanudación devuelven registros separados: `tests/test_agent_contrato.py::test_pausa_y_reanudacion_hitl_entregan_logs_nuevos_y_no_persistidos`.
- [x] Secretos, prompts, cuerpos externos, valores no JSON y valores extensos quedan saneados: `tests/test_depuracion.py` (RF-17 a RF-22).
- [x] Entradas inválidas y fallos controlados conservan un registro seguro: `tests/test_agent_contrato.py::test_rechazos_de_fachada_devuelven_un_unico_control_sin_ejecutar_grafo` y `tests/test_depuracion.py::test_ejecutor_transversal_registra_el_fallo_si_la_tool_lanza`.

## Fuera de spec

Nada detectado.

## Veredicto

**Sí.** La implementación satisface los RF-1 a RF-27. En particular, el adaptador proyecta el diagnóstico efímero de un fallback real del Supervisor como una entrada `control` rechazada inmediatamente después del nodo `supervisor`; la CLI y el panel de depuración lo muestran, mientras «Pasos seguidos» lo mantiene oculto. El registro continúa aislado de checkpoints e historial y `traza` conserva su contrato.
