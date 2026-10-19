# Validación — Spec 005

> Fecha: pendiente · Resultado de `pytest`: pendiente

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_cli.py::test_chat_interactivo_responde` | ⬜ |
| RF-2 | Automático | `tests/test_cli.py::test_mismo_thread_id_en_todo_el_chat` | ⬜ |
| RF-3 | Automático | `tests/test_cli.py::test_mensaje_vacio_no_llama_al_grafo` | ⬜ |
| RF-4 | Automático | `tests/test_cli.py::test_salir_termina` | ⬜ |
| RF-5 | Automático | `tests/test_cli.py::test_fallo_del_grafo_no_corta_el_chat` | ⬜ |
| RF-6 | Automático | `tests/test_cli.py::test_plan_pendiente_pregunta_decision` | ⬜ |
| RF-7 | Automático | `tests/test_cli.py::test_no_cierra_sin_decision` | ⬜ |
| RF-8 | Automático | `tests/test_cli.py::test_aprobar_muestra_terminada_solo_si_el_grafo_lo_dice` | ⬜ |
| RF-9 | Automático | `tests/test_cli.py::test_rechazar_permite_seguir` | ⬜ |
| RF-10 | Automático | `tests/test_cli.py::test_decision_invalida_repregunta` | ⬜ |
| RF-11 | Automático | `tests/test_cli_demo.py::test_demo_lanza_tres_pedidos` | ⬜ |
| RF-12 | Automático | `tests/test_cli_demo.py::test_demo_sin_auto_pide_aprobacion` | ⬜ |
| RF-13 | Automático | `tests/test_cli_demo.py::test_demo_auto_aprueba` | ⬜ |
| RF-14 | Automático | `tests/test_cli_demo.py::test_auto_aprobar_sin_demo_da_error` | ⬜ |
| RF-15 | Automático | `tests/test_presentacion.py::test_formato_incluye_respuesta_log_traza` | ⬜ |
| RF-16 | Automático | `tests/test_presentacion.py::test_formato_incluye_thread_id_y_banderas` | ⬜ |
| RF-17 | Manual | `streamlit run app.py` (modo simulado) → chat con historial | ⬜ |
| RF-18 | Automático | `tests/test_sesion.py::test_thread_id_estable` | ⬜ |
| RF-19 | Automático + manual | `tests/test_sesion.py::test_plan_pendiente_activa_decision`; botones visibles en la barra lateral | ⬜ |
| RF-20 | Automático | `tests/test_sesion.py::test_aprobar_transmite_al_grafo` | ⬜ |
| RF-21 | Automático | `tests/test_sesion.py::test_rechazar_descarta_plan` | ⬜ |
| RF-22 | Automático | `tests/test_sesion.py::test_decidir_solo_con_plan_pendiente` | ⬜ |
| RF-22b | Automático | `tests/test_sesion.py::test_no_se_puede_escribir_con_plan_pendiente` | ⬜ |
| RF-23 | Automático | `tests/test_sesion.py::test_nueva_conversacion` | ⬜ |
| RF-24 | Automático + manual | `tests/test_presentacion.py::test_datos_depuracion`; desplegable visible en Streamlit | ⬜ |
| RF-25 | Automático | `tests/test_sesion.py::test_error_conserva_historial` | ⬜ |
| RF-26 | Automático | `tests/test_presentacion.py::test_cli_usa_el_mismo_formato` | ⬜ |
| RF-27 | Automático | `tests/test_sesion.py::test_done_lo_decide_el_grafo` | ⬜ |
| RF-28 | Automático | `tests/test_cargar_agente.py::test_modo_simulado_usa_grafo_falso`, `tests/test_grafo_falso.py::test_cumple_el_contrato` | ⬜ |
| RF-29 | Automático | `tests/test_cargar_agente.py::test_sin_grafo_real_da_error_claro` | ⬜ |
| Demo CLI | Manual | `python main.py --demo --auto-aprobar` con modo simulado y luego con el grafo real | ⬜ |
| Demo web | Manual | `streamlit run app.py`: chat, aprobar, rechazar, nueva conversación y depuración | ⬜ |

## Comprobaciones manuales realizadas

- **2026-10-15, Streamlit con modo simulado** (`MADRIDRUMBO_GRAFO=falso`), recorrido automatizado con `streamlit.testing.v1.AppTest` sin excepciones, en el orden siguiente:
  1. Inicio: aviso de modo simulado visible, cuadro de mensaje activo, Aprobar y Rechazar desactivados (RF-17, RF-22, RF-28).
  2. Tras escribir un mensaje: plan en la barra lateral, Aprobar y Rechazar activos y cuadro de mensaje bloqueado con aviso (RF-19, RF-22b).
  3. Tras Rechazar: plan descartado, se puede escribir otra vez y no hay «terminada» (RF-21).
  4. Tras Aprobar: «Conversación terminada» en la barra lateral (RF-20).
  5. Nueva conversación: identificador nuevo e historial vacío (RF-23).
  6. Panel «Depuración» presente en la barra lateral (RF-24).
- **2026-10-15, CLI con modo simulado:** `python main.py` (chat y HITL con rechazo, respuesta no válida y aprobación), `python main.py --demo --auto-aprobar` y `python main.py --auto-aprobar` (error, código 2).
- **Pendiente:** ver la interfaz en un navegador real (aspecto de los botones y del panel) y repetir ambas demos con el grafo real.

## Criterios de finalización
- [ ] Todos los RF con test en verde (`pytest`) sin API.
- [ ] Demo manual del CLI y de Streamlit con el modo simulado.
- [ ] Demo manual del CLI y de Streamlit con el grafo real.

## Fuera de spec
Pendiente de revisar tras implementar.

## Veredicto
Pendiente.
