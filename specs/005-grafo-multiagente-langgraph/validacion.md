# Validación final — Spec 005: Grafo multiagente con LangGraph

> Fecha: 2026-10-15  
> Método: pruebas automatizadas sin red, con dobles de LLM, tools y checkpointer.  
> Resultado de la suite: `368 passed in 9.89s` (`python -m pytest`).

## Matriz de trazabilidad

| RF | Evidencia automatizada | Veredicto |
|---|---|---|
| RF-1 | `tests/test_grafo_enrutamiento.py::test_grafo_declara_supervisor_cinco_especialistas_y_sintetizador` | Sí |
| RF-2 | `tests/test_supervisor_grafo.py::test_supervisor_convierte_una_decision_valida_en_cola` y `test_grafo_acepta_finish_sin_ejecutar_especialistas` | Sí |
| RF-3 | `tests/test_grafo_enrutamiento.py::test_grafo_encadena_y_repite_el_mismo_especialista_en_orden` | Sí |
| RF-4 | `tests/test_grafo_enrutamiento.py::test_selector_rechaza_un_rol_sin_arista_declarada` | Sí |
| RF-5 | `tests/test_grafo_enrutamiento.py::test_grafo_recorre_un_especialista_y_luego_sintetiza` | Sí |
| RF-6 | `tests/test_supervisor_grafo.py::test_supervisor_decision_no_interpretable_o_prohibida_usa_fallback` y `test_supervisor_usa_fallback_si_el_modelo_lanza_una_excepcion` | Sí |
| RF-7 | `tests/test_supervisor_grafo.py::test_fallback_reconoce_cada_intencion_admitida` | Sí |
| RF-8 | `tests/test_supervisor_grafo.py::test_fallback_reconoce_cada_intencion_admitida` y `test_hora_actual_no_se_confunde_con_horario_de_transporte` | Sí |
| RF-9 | `tests/test_supervisor_grafo.py::test_fallback_reconoce_cada_intencion_admitida` y `tests/test_agentes_grafo.py::test_nodo_auxiliar_usa_hora_actual_y_deja_su_traza` | Sí |
| RF-10 | `tests/test_supervisor_grafo.py::test_fallback_reconoce_cada_intencion_admitida` | Sí |
| RF-11 | `tests/test_supervisor_grafo.py::test_fallback_desconocido_pide_reformulacion_con_alcance` | Sí |
| RF-12 | `tests/test_especialista_rutas.py::test_rutas_con_origen_y_destino_invoca_una_vez_y_conserva_json` y `tests/test_grafo_hitl.py::test_ruta_valida_persiste_respuesta_y_se_pausa_antes_de_aplicarse` | Sí |
| RF-13 | `tests/test_agentes_grafo.py::test_nodo_auxiliar_usa_hora_actual_y_deja_su_traza` | Sí |
| RF-14 | `tests/test_agentes_grafo.py::test_nodo_auxiliar_usa_calculadora_para_una_operacion_valida` | Sí |
| RF-15 | `tests/test_flujo_imagen_calculo.py::test_tarifas_con_ejecutor_controlado_solo_llama_a_imagen` | Sí |
| RF-16 | `tests/test_agentes_grafo.py::test_nodo_rag_consulta_evidencia_y_deja_traza_completa` | Sí |
| RF-17 | `tests/test_agentes_grafo.py::test_nodo_rag_conserva_la_abstencion_del_corpus` y `test_nodo_rag_conserva_un_error_controlado_de_la_tool` | Sí |
| RF-18 | `tests/test_grafo_enrutamiento.py::test_grafo_encadena_rag_y_auxiliar_con_una_traza_por_tool` | Sí |
| RF-19 | `tests/test_agentes_grafo.py::test_nodo_auxiliar_conserva_el_error_de_calculadora` y `tests/test_sintetizador.py::test_respaldo_conserva_abstencion_y_error_de_los_especialistas` | Sí |
| RF-20 | `tests/test_sintetizador.py::test_sintetizador_devuelve_una_respuesta_sencilla_en_espanol` | Sí |
| RF-21 | `tests/test_sintetizador.py::test_sintetizador_recibe_la_informacion_parcial_y_sus_limitaciones` | Sí |
| RF-22 | `tests/test_sintetizador.py::test_sintetizador_recibe_la_informacion_parcial_y_sus_limitaciones` | Sí |
| RF-23 | `tests/test_agent_contrato.py::test_fachada_expone_las_dos_firmas_y_las_seis_claves` | Sí |
| RF-24 | `tests/test_agent_contrato.py::test_fachada_expone_las_dos_firmas_y_las_seis_claves` | Sí |
| RF-25 | `tests/test_estado_grafo.py::test_proyeccion_publica_tiene_solo_las_seis_claves_y_traza_normalizada` | Sí |
| RF-26 | `tests/test_estado_grafo.py::test_proyeccion_publica_tiene_solo_las_seis_claves_y_traza_normalizada` | Sí |
| RF-27 | `tests/test_estado_grafo.py::test_proyeccion_publica_tiene_solo_las_seis_claves_y_traza_normalizada` | Sí |
| RF-28 | `tests/test_especialista_horarios.py::test_no_decide_done` y `tests/test_grafo_enrutamiento.py::test_grafo_acepta_finish_sin_ejecutar_especialistas` | Sí |
| RF-29 | `tests/test_grafo_hitl.py::test_ruta_valida_persiste_respuesta_y_se_pausa_antes_de_aplicarse` | Sí |
| RF-30 | `tests/test_grafo_hitl.py::test_ruta_valida_persiste_respuesta_y_se_pausa_antes_de_aplicarse` | Sí |
| RF-31 | `tests/test_grafo_hitl.py::test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido` | Sí |
| RF-32 | `tests/test_grafo_hitl.py::test_rechazo_descarta_el_plan_y_replanifica_con_los_args_persistidos` | Sí |
| RF-33 | `tests/test_grafo_hitl.py::test_rechazo_descarta_el_plan_y_replanifica_con_los_args_persistidos` | Sí |
| RF-34 | `tests/test_grafo_hitl.py::test_resultados_de_rutas_no_aplicables_no_interrumpen` | Sí |
| RF-35 | `tests/test_grafo_persistencia.py::test_checkpointer_inyectado_aisla_dos_thread_id` | Sí |
| RF-36 | `tests/test_grafo_persistencia.py::test_mismo_thread_id_recupera_historial_y_contexto_entre_turnos` | Sí |
| RF-37 | `tests/test_grafo_persistencia.py::test_thread_nuevo_empieza_vacio_aun_con_estado_de_entrada_minimo` | Sí |
| RF-38 | `tests/test_config_grafo.py::test_limites_de_conversacion_y_tools` | Sí |
| RF-39 | `tests/test_config_grafo.py::test_limites_de_conversacion_y_tools` | Sí |
| RF-40 | `tests/test_grafo_limites.py::test_limite_turnos_devuelve_resumen_sin_ejecutar_especialistas` | Sí |
| RF-41 | `tests/test_grafo_limites.py::test_limite_turnos_devuelve_resumen_sin_ejecutar_especialistas` | Sí |
| RF-42 | `tests/test_supervisor_grafo.py::test_fallback_ordenado_encadena_roles_y_documentacion_con_hora` | Sí |
| RF-43 | `tests/test_agentes_grafo.py::test_nodo_auxiliar_bloquea_una_tool_que_no_es_hora_ni_calculadora` | Sí |
| RF-44 | `tests/test_agentes_grafo.py::test_nodo_rag_bloquea_toda_tool_distinta_de_rag_ask` y `tests/test_allowlist_multimodal.py::test_tarifas_no_recibe_calculadora_ni_rag_directo` | Sí |
| RF-45 | `tests/test_grafo_enrutamiento.py::test_grafo_encadena_rag_y_auxiliar_con_una_traza_por_tool` | Sí |
| RF-46 | `tests/test_grafo_enrutamiento.py::test_grafo_encadena_tarifas_y_auxiliar_sin_calculadora_en_tarifas` | Sí |
| RF-47 | `tests/test_grafo_hitl.py::test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido` y `test_varios_planes_exigen_un_selector_y_no_reanudan_el_checkpoint` | Sí |
| RF-48 | `tests/test_grafo_hitl.py::test_mensaje_nuevo_con_plan_pendiente_no_ejecuta_nodos_ni_tools` | Sí |
| RF-49 | `tests/test_grafo_hitl.py::test_mensaje_nuevo_con_plan_pendiente_no_ejecuta_nodos_ni_tools` | Sí |
| RF-50 | `tests/test_grafo_limites.py::test_presupuesto_tools_es_compartido_por_los_especialistas` y `test_presupuesto_de_tools_persiste_al_rechazar_un_plan` | Sí |
| RF-51 | `tests/test_agent_contrato.py::test_aprobacion_sin_snapshot_o_plan_no_modifica_el_checkpoint` | Sí |
| RF-52 | `tests/test_agent_contrato.py::test_validaciones_de_procesar_turno_no_crean_ni_invocan_grafo` | Sí |
| RF-53 | `tests/test_agent_contrato.py::test_estado_vacio_recupera_el_checkpoint_en_lugar_de_sustituirlo` y `tests/test_grafo_persistencia.py::test_thread_nuevo_empieza_vacio_aun_con_estado_de_entrada_minimo` | Sí |
| RF-54 | `tests/test_agent_contrato.py::test_validaciones_de_procesar_turno_no_crean_ni_invocan_grafo` | Sí |
| RF-55 | `tests/test_agent_contrato.py::test_validaciones_de_procesar_turno_no_crean_ni_invocan_grafo` | Sí |
| RF-56 | `tests/test_sintetizador.py::test_fallo_del_modelo_devuelve_aviso_y_el_respaldo_disponible` | Sí |
| RF-57 | `tests/test_supervisor_grafo.py::test_fallback_reconoce_cada_intencion_admitida` | Sí |
| RF-58 | `tests/test_especialista_horarios.py::test_prompt_declara_la_excepcion_de_horarios_y_solo_sus_dos_tools` y `test_cualquier_tercera_tool_se_bloquea` | Sí |
| RF-59 | `tests/test_grafo_enrutamiento.py::test_horarios_y_rutas_mantienen_sus_consultas_internas_sin_duplicar_rag` | Sí |

## Escenarios de finalización

- Finalización ordinaria y `finish`: `tests/test_grafo_enrutamiento.py`.
- Pausa HITL, aprobación y rechazo/replanificación: `tests/test_grafo_hitl.py`.
- Límite de turnos y de tools: `tests/test_grafo_limites.py`.
- Flujo integrado RAG → rutas → HITL → aprobación y flujo limitado: `tests/test_integracion_spec005.py`.
- Fallo de síntesis con respaldo: `tests/test_sintetizador.py::test_fallo_del_modelo_devuelve_aviso_y_el_respaldo_disponible`.

## Veredicto final

Todos los requisitos funcionales RF-1 a RF-59 tienen evidencia automatizada y veredicto **Sí**. La suite completa se ejecuta con dobles y sin acceder a LLM, APIs, embeddings ni ChromaDB reales.
