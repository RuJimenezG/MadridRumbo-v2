# Validación — Spec 012

> Fecha: 2026-10-23 · Resultado de `python -m pytest`: **1256 passed**

| RF | Cómo se comprueba | Test o comprobación | Resultado |
| --- | --- | --- | --- |
| RF-1 | Las instrucciones del Supervisor identifican todos los códigos como zonas tarifarias. | `tests/test_catalogo_roles.py::test_instrucciones_aclaran_que_los_codigos_son_zonas_tarifarias` | Sí |
| RF-2 | El detector exige término tarifario, dos zonas explícitas y consulta sin imagen. | `tests/test_catalogo_roles.py::test_detecta_consultas_tarifarias_que_relacionan_dos_zonas` | Sí |
| RF-3 | Se aceptan «entre … y …», «de … a …», guion y variantes de mayúsculas. | `tests/test_catalogo_roles.py::test_detecta_consultas_tarifarias_que_relacionan_dos_zonas` | Sí |
| RF-4 | Una sola zona no activa la guarda. | `tests/test_catalogo_roles.py::test_no_detecta_sin_par_tarifario_explicito_o_con_ruta_fisica` | Sí |
| RF-5 | Una ruta con dos lugares físicos conserva `rutas` aunque mencione precio y zonas. | `tests/test_supervisor_grafo.py::test_ruta_fisica_con_precio_y_zonas_conserva_rutas_y_rag`; `tests/test_grafo_enrutamiento.py::test_ruta_fisica_con_precio_conserva_rutas_y_rag` | Sí |
| RF-6 | Una cola LLM válida con `rutas` para A–B2 se corrige a `rag`. | `tests/test_supervisor_grafo.py::test_decision_llm_valida_con_rutas_para_zonas_se_corrige_a_rag`; `tests/test_grafo_enrutamiento.py::test_consulta_de_zonas_corregida_llama_rag_ask_y_conserva_traza` | Sí |
| RF-7 | La corrección conserva orden y repeticiones de la cola. | `tests/test_supervisor_grafo.py::test_correccion_de_rutas_conserva_orden_y_repeticiones` | Sí |
| RF-8 | La decisión corregida mantiene `sin_fallback`. | `tests/test_supervisor_grafo.py::test_decision_llm_valida_con_rutas_para_zonas_se_corrige_a_rag` | Sí |
| RF-9 | Se publica un control técnico con la categoría y contador de correcciones. | `tests/test_depuracion.py::test_correccion_de_rutas_del_supervisor_se_proyecta_como_control_efimero` | Sí |
| RF-10 | El diagnóstico no incorpora la respuesta cruda simulada del LLM. | `tests/test_agent_contrato.py::test_correccion_de_rutas_registra_diagnostico_tecnico_separado` | Sí |
| RF-11 | La corrección se consulta separada del fallback en el registro técnico. | `tests/test_agent_contrato.py::test_correccion_de_rutas_registra_diagnostico_tecnico_separado`; `tests/test_depuracion.py::test_correccion_de_rutas_del_supervisor_se_proyecta_como_control_efimero` | Sí |
| RF-12 | La presentación técnica se filtra del chat. | `tests/test_presentacion.py::test_ocultar_tecnicas_filtra_el_control_de_correccion_semantica` | Sí |
| RF-13 | La redirección ejecuta `rag_ask`, mantiene evidencia y la traza documental. | `tests/test_grafo_enrutamiento.py::test_consulta_de_zonas_corregida_llama_rag_ask_y_conserva_traza` | Sí |
| RF-14 | Una imagen válida desactiva la guarda textual. | `tests/test_catalogo_roles.py::test_imagen_valida_excluye_la_deteccion_textual_de_zonas`; `tests/test_supervisor_grafo.py::test_imagen_valida_conserva_tarifas_en_una_decision_valida` | Sí |
| RF-15 | Consultas fuera del patrón de dos zonas mantienen el comportamiento existente. | `tests/test_catalogo_roles.py::test_no_detecta_sin_par_tarifario_explicito_o_con_ruta_fisica` | Sí |
| RF-16 | Ruta física y atención tarifaria mantienen los especialistas correspondientes. | `tests/test_supervisor_grafo.py::test_ruta_fisica_con_precio_y_zonas_conserva_rutas_y_rag`; `tests/test_grafo_enrutamiento.py::test_ruta_fisica_con_precio_conserva_rutas_y_rag` | Sí |

## Criterios de finalización

- [x] Todos los RF tienen pruebas automatizadas en verde sin API, embeddings ni ChromaDB real.
- [x] Se cubren los conectores «entre», «de … a …» y guion, incluidas mayúsculas y minúsculas.
- [x] Un Supervisor simulado que devuelve `{"roles": ["rutas"]}` para A–B2 termina derivando a RAG.
- [x] Las tres consultas tarifarias de aceptación se cubren mediante pruebas parametrizadas.
- [x] Una ruta entre lugares físicos conserva `rutas`, incluso junto con precio o abono.
- [x] Una única mención de «zona A» no activa la guarda.
- [x] La corrección mantiene la cola, evita fallback y deja un diagnóstico técnico seguro separado.
- [x] Una imagen válida mantiene el comportamiento multimodal vigente.
- [x] La suite completa pasa: `1256 passed`.

## Fuera de spec

Nada. El control técnico usa `resultado: "rechazado"` porque el contrato de depuración previo reserva `completado` para entradas sin detalle; no altera el fallback ni el contrato público.

## Veredicto

**Sí.** RF-1 a RF-16 están cubiertos por pruebas sin servicios externos y la suite completa finaliza con `1256 passed`.
