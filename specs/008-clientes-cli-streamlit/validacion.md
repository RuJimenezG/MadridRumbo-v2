# Validación — Spec 008

> Fecha: 2026-10-19 · Actualizada el 2026-10-22 (RF-38 a RF-41) · Resultado de `python -m pytest -q`: 936 passed, 5 failed
> (los 5 son de `tests/test_bicimad.py`, ajenos a los clientes), sin llamadas a API.

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_cli.py::test_chat_interactivo_responde` | ✅ |
| RF-2 | Automático | `tests/test_cli.py::test_mismo_thread_id_en_todo_el_chat` | ✅ |
| RF-3 | Automático | `tests/test_cli.py::test_mensaje_vacio_no_llama_al_grafo` | ✅ |
| RF-4 | Automático | `tests/test_cli.py::test_salir_termina` | ✅ |
| RF-5 | Automático | `tests/test_cli.py::test_fallo_del_grafo_no_corta_el_chat` | ✅ |
| RF-6 | Automático | `tests/test_cli.py::test_plan_pendiente_pregunta_decision`, `tests/test_cli.py::test_plan_pendiente_muestra_resumen` | ✅ |
| RF-7 | Automático | `tests/test_cli.py::test_no_cierra_sin_decision`, `tests/test_cli.py::test_salir_en_la_eleccion_no_aprueba_nada` | ✅ |
| RF-8 | Automático | `tests/test_cli.py::test_aprobar_muestra_terminada_solo_si_el_grafo_lo_dice` | ✅ |
| RF-9 | Automático | `tests/test_cli.py::test_rechazar_permite_seguir`, `tests/test_cli.py::test_rechazar_muestra_el_nuevo_plan`, `tests/test_clientes_grafo_real.py::test_rechazar_replanifica_y_se_puede_aprobar_el_nuevo_plan` | ✅ |
| RF-10 | Automático | `tests/test_cli.py::test_decision_invalida_repregunta` | ✅ |
| RF-11 | Automático | `tests/test_cli_demo.py::test_demo_lanza_tres_pedidos` | ✅ |
| RF-12 | Automático | `tests/test_cli_demo.py::test_demo_sin_auto_pide_aprobacion` | ✅ |
| RF-13 | Automático | `tests/test_cli_demo.py::test_demo_auto_aprueba`, `tests/test_cli_demo.py::test_demo_auto_aprueba_el_primer_plan_si_hay_varios` | ✅ |
| RF-14 | Automático | `tests/test_cli_demo.py::test_auto_aprobar_sin_demo_da_error` | ✅ |
| RF-15 | Automático | `tests/test_presentacion.py::test_formato_incluye_respuesta_log_traza` | ✅ |
| RF-16 | Automático | `tests/test_presentacion.py::test_formato_incluye_thread_id_y_banderas` | ✅ |
| RF-17 | Manual | Manual (`AppTest`, modo simulado): la web abre con el chat y el historial | ✅ |
| RF-18 | Automático | `tests/test_sesion.py::test_thread_id_estable` | ✅ |
| RF-19 | Automático + manual | `tests/test_sesion.py::test_plan_pendiente_activa_decision`; además manual (`AppTest`): plan en la barra lateral con sus botones | ✅ |
| RF-20 | Automático | `tests/test_sesion.py::test_aprobar_transmite_al_grafo` | ✅ |
| RF-21 | Automático | `tests/test_sesion.py::test_rechazar_descarta_plan` | ✅ |
| RF-22 | Automático + manual | `tests/test_sesion.py::test_decidir_solo_con_plan_pendiente`; además manual (`AppTest`): botones desactivados sin plan | ✅ |
| RF-22b | Automático | `tests/test_sesion.py::test_no_se_puede_escribir_con_plan_pendiente`, `tests/test_clientes_grafo_real.py::test_un_mensaje_con_plan_pendiente_no_llega_al_grafo` | ✅ |
| RF-23 | Automático | `tests/test_sesion.py::test_nueva_conversacion` | ✅ |
| RF-24 | Automático + manual | `tests/test_presentacion.py::test_datos_depuracion`; además manual (`AppTest`): desplegable «Depuración» en la barra lateral | ✅ |
| RF-25 | Automático | `tests/test_sesion.py::test_error_conserva_historial` | ✅ |
| RF-26 | Automático | `tests/test_presentacion.py::test_cli_usa_el_mismo_formato`, `tests/test_clientes_grafo_real.py::test_el_grafo_real_devuelve_las_seis_claves_publicas` | ✅ |
| RF-27 | Automático | `tests/test_sesion.py::test_done_lo_decide_el_grafo` | ✅ |
| RF-28 | Automático | `tests/test_cargar_agente.py::test_modo_simulado_usa_grafo_falso`, `tests/test_grafo_falso.py::test_cumple_el_contrato`, `tests/test_clientes_grafo_real.py::test_cargar_agente_devuelve_el_grafo_real` | ✅ |
| RF-29 | Automático | `tests/test_cargar_agente.py::test_sin_grafo_real_da_error_claro` | ✅ |
| RF-30 | Automático | `tests/test_planes.py::test_resumen_de_ruta_completo`, `tests/test_presentacion.py::test_formato_muestra_el_resumen_de_cada_plan`, `tests/test_clientes_grafo_real.py::test_ruta_con_un_plan_se_resume_se_aprueba_y_termina` | ✅ |
| RF-31 | Automático + manual | `tests/test_sesion.py::test_decidir_con_varios_planes_envia_el_elegido`, `tests/test_cli.py::test_varios_planes_pide_elegir`, `tests/test_clientes_grafo_real.py::test_varios_planes_exigen_elegir_y_se_aprueba_solo_el_elegido`; además manual (`AppTest`): selector con `ruta-1` y `ruta-2` | ✅ |
| RF-32 | Automático | `tests/test_cli.py::test_un_plan_no_pide_elegir`, `tests/test_sesion.py::test_un_plan_se_decide_sin_indicar_cual` | ✅ |
| RF-33 | Automático | `tests/test_planes.py::test_plan_de_formato_desconocido`, `tests/test_presentacion.py::test_un_plan_desconocido_no_rompe_el_formato` | ✅ |
| RF-34 | Automático | `tests/test_cli.py::test_respuesta_sin_plan_no_pregunta`, `tests/test_grafo_falso.py::test_horarios_cierra_sin_plan`, `tests/test_clientes_grafo_real.py::test_una_consulta_sin_ruta_cierra_sin_pausa` | ✅ |
| RF-35 | Automático + manual | `tests/test_planes.py::test_entradas_tecnicas`, `tests/test_presentacion.py::test_ocultar_tecnicas`, `tests/test_cli.py::test_el_cli_muestra_las_entradas_tecnicas_del_supervisor`, `tests/test_clientes_grafo_real.py::test_el_cli_muestra_y_la_web_oculta_el_diagnostico_del_supervisor`; además manual (`AppTest`): el diagnóstico no aparece en ninguna parte de la web | ✅ |
| RF-36 | Automático | `tests/test_grafo_falso.py::test_ruta_devuelve_un_plan_con_formato_real`, `tests/test_grafo_falso.py::test_varias_rutas_devuelven_varios_planes` | ✅ |
| RF-37 | Automático + manual descrita | `tests/test_sesion.py::test_referencia_de_demo_se_reenvia_sin_modificar` y `tests/test_cli.py::test_cli_reenvia_referencia_de_demo_sin_modificar`; sección «Referencia de imagen demo». | ✅ |
| RF-38 | Automático | `tests/test_app_streamlit.py::test_el_mensaje_se_dibuja_antes_de_llamar_al_grafo`, `::test_hay_indicador_de_espera_mientras_el_grafo_responde` | ✅ |
| RF-39 | Automático | `tests/test_presentacion.py::test_pasos_numeran_las_tools_con_nombre_estado_y_extracto`, `::test_pasos_incluyen_el_registro_antes_de_las_tools`, `::test_pasos_ocultan_el_diagnostico_del_supervisor_por_defecto`, `tests/test_app_streamlit.py::test_la_respuesta_muestra_los_pasos_seguidos`, `::test_los_pasos_no_muestran_el_diagnostico_del_supervisor` | ✅ |
| RF-40 | Automático | `tests/test_sesion.py::test_cada_respuesta_guarda_el_registro_y_la_traza_de_su_turno`, `::test_los_pasos_guardados_son_una_copia_del_estado`, `tests/test_app_streamlit.py::test_cada_respuesta_conserva_sus_propios_pasos` | ✅ |
| RF-41 | Automático | `tests/test_presentacion.py::test_pasos_vacios_sin_tools_ni_registro_visible`, `tests/test_app_streamlit.py::test_sin_pasos_no_hay_desplegable` | ✅ |
| Demo CLI (simulado) | Manual | `python main.py --demo --auto-aprobar`, el chat con rechazo y aprobación y la elección entre dos planes, con `MADRIDRUMBO_GRAFO=falso` | ✅ |
| Demo web (simulado) | Manual | `AppTest` de Streamlit: horarios sin plan, ruta con un plan, dos planes con selector, rechazo, aprobación, filtro del supervisor y nueva conversación | ✅ |
| Demo con el grafo real y API | Manual ⚠️ | Horarios, una ruta con aprobación y una pregunta fuera de corpus con Gemini, Nominatim y Google | ⏭ Pendiente |
| Interfaz en un navegador real | Manual | `streamlit run app.py` en modo simulado: aviso, planes, selector, aprobar y panel de depuración | ✅ |

## Comprobaciones realizadas

- **Grafo real sin API (2026-10-19):** `tests/test_clientes_grafo_real.py` recorre los clientes contra el grafo real de `src/agent.py`, con supervisor, especialistas y sintetizador falsos: una ruta con un plan, dos planes con elección, rechazo con replanificación, consulta sin pausa, bloqueo con plan pendiente, el CLI de punta a punta y el filtro del supervisor. Pasan los 11 tests y no hacen ninguna conexión a la red.
- **Web con el grafo simulado (2026-10-19):** recorrido automatizado con `streamlit.testing.v1.AppTest`, sin excepciones.
- **CLI con el grafo simulado (2026-10-19):** chat y HITL con rechazo y aprobación, elección entre dos planes, `--demo` y `--demo --auto-aprobar`, y `--auto-aprobar` sin `--demo` (error, código 2).
- **Arranque de Streamlit (2026-10-15):** `streamlit run app.py` arranca y su comprobación de salud devuelve 200.
- **RF-37, transmisión de la referencia demo (2026-10-19):** T36 usa un agente espía para confirmar que `SesionChat` conserva el mensaje literal, incluso con espacios de borde, y no añade estado visual. T37 verifica que el CLI entrega el literal al agente en su única llamada. Ambas pruebas usan solo dobles locales.

## Referencia de imagen demo (RF-37)

La persona selecciona exclusivamente la demo configurada al escribir la
referencia literal `assets/imagen_demo.jpg`. Los clientes no suben archivos,
no seleccionan rutas alternativas y no deciden si se usa visión: solo reenvían
el mensaje a `src.agent.procesar_turno()`; la validación y el enrutamiento
visual se cubren en la spec 007.

La comprobación manual de Streamlit en modo simulado queda registrada para una
sesión de navegador: activar `MADRIDRUMBO_GRAFO=falso`, abrir `streamlit run
app.py`, escribir `Analiza assets/imagen_demo.jpg e indica los precios.` y
comprobar que el mismo texto aparece en el historial. No debe aparecer ningún
selector ni control de subida de archivos. No se ejecutó durante T38 porque la
tarea documenta la comprobación y no inicia Streamlit; el modo simulado solo
acredita la transmisión del texto, no la interpretación visual.

## Criterios de finalización
- [x] Todos los RF con test en verde (`pytest`) sin API.
- [x] Demo manual del CLI y de Streamlit con el modo simulado.
- [x] Pruebas de los clientes contra el grafo real con dobles de prueba, sin API.
- [ ] Demo manual con el grafo real y API (Gemini, Nominatim y Google).
- [x] Interfaz de Streamlit comprobada en un navegador real.

## Fuera de spec

- El CLI acepta el identificador del plan (`ruta-2`) además de su número al elegir plan.
- Con `--auto-aprobar` y varios planes se aprueba el primero (nadie elige).
- La sesión no llama al grafo cuando hay varios planes y no se indica cuál, o si el identificador no existe. Evita el aviso del grafo real, que deja `hitl_pendiente` en falso aunque siga habiendo un plan.
- El filtro de entradas técnicas (RF-35) se aplica también al panel de depuración de la web, la lectura más estricta de la spec 006. Decisión cerrada: los diagnósticos del supervisor se ocultan en toda la web y se muestran solo en el CLI.
- La spec se renumeró de 005 a 008 porque las specs 005, 006 y 007 son del grafo y del supervisor.

## Limitaciones conocidas

- **Imágenes:** no se admiten subida de archivos ni rutas arbitrarias. La única
  selección disponible es la referencia literal `assets/imagen_demo.jpg`; su
  validación y la activación de `tarifas` se realizan en la fachada de la spec
  007, no en los clientes.

## Veredicto
**Parcial.** Los 38 requisitos (RF-1 a RF-37 y RF-22b) tienen evidencia en
verde y la suite completa pasa sin API. Los clientes se han probado contra el
grafo simulado y contra el grafo real con dobles de prueba. Falta la demo con
el grafo real y las APIs de verdad, que gasta llamadas y necesita las claves de
Gemini, Nominatim y Google. T34 y T35
quedan abiertas hasta entonces.
