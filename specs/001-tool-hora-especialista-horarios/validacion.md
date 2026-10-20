# Validación — Spec 001

> Fecha: 2026-10-14 · Actualizada el 2026-10-19 tras integrarse el grafo (spec 005) · Resultado de `pytest`: 623 passed, 0 failed (`develop`)

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_hora_actual.py::test_formato_laborable`, `::test_sabado_domingo` | ✅ |
| RF-2 | Automático | `tests/test_hora_actual.py::test_sin_argumentos` | ✅ |
| RF-3 | Automático | `tests/test_hora_actual.py::test_sin_red` | ✅ |
| RF-4 | Automático | `tests/test_hora_actual.py::test_zona_horaria_configurable` | ✅ |
| RF-5 | Automático | `tests/test_hora_actual.py::test_zona_invalida` | ✅ |
| RF-6 | Automático | `tests/test_allowlist_horarios.py::test_hora_en_allowlist` | ✅ |
| RF-7 | Automático | `tests/test_allowlist_horarios.py::test_traza_ok` | ✅ |
| RF-8 | Automático | `tests/test_especialista_horarios.py::test_prompt_propio` | ✅ |
| RF-9 | Automático | `tests/test_especialista_horarios.py::test_usa_hora_actual` | ✅ |
| RF-10 | Automático | `tests/test_especialista_horarios.py::test_usa_rag`, `tests/test_allowlist_horarios.py::test_rag_ask_en_allowlist` | ✅ |
| RF-11 | Automático | `tests/test_especialista_horarios.py::test_abstencion_sin_evidencia` | ✅ |
| RF-12 | Automático | `tests/test_allowlist_horarios.py::test_tool_no_permitida`, `tests/test_especialista_horarios.py::test_tool_fuera_de_especialista_no_se_ejecuta` | ✅ |
| RF-13 | Automático | `tests/test_especialista_horarios.py::test_max_steps` | ✅ |
| RF-14 | Automático | `tests/test_especialista_horarios.py::test_no_decide_done` | ✅ |
| RF-15 | Automático | `tests/test_especialista_horarios.py::test_llm_falla`, `::test_respuesta_invalida` | ✅ |
| RF-16 | Automático | `tests/test_fallback_horarios.py::test_palabras_horario` (y `test_cada_palabra_clave`, `test_sin_acentos_ni_mayusculas`) | ✅ |
| Integración | Automático | El especialista `horarios` forma parte del grafo (spec 005); las consultas de horarios las prueba `tests/test_grafo_enrutamiento.py::test_horarios_y_rutas_mantienen_sus_consultas_internas_sin_duplicar_rag` | ✅ |
| Demo | Manual ⚠️ API | «¿Hasta qué hora hay metro hoy?» con el grafo real, el RAG indexado y Gemini → traza con `hora_actual` y `rag_ask` | ⏭ Pendiente |

## Criterios de finalización
- [x] Todos los RF con test en verde (`pytest`) sin API.
- [x] El especialista está integrado en el grafo y probado con dobles (specs 005 a 007).
- [ ] Demo manual con el grafo real y las APIs (RAG indexado y Gemini).

## Fuera de spec
- `rag_ask` registrada en la allowlist global (`src/tools/__init__.py`). La spec exige que el especialista pueda invocar el RAG (RF-10) pero no dice quién lo registra. El RAG ya está integrado en `develop` (PR #1 y #3), así que el import funciona; no se ha probado con el RAG indexado y Gemini.
- Estado «error» en la traza cuando el resultado empieza por `ERROR` o cuando la tool lanza una excepción (el plan lo preveía, la spec no).
- Mini-bucle extraído a `src/agents/base.py` para compartirlo con el especialista de tarifas (spec 002). El comportamiento no cambia.
- `elegir_rol_por_palabras` (RF-16) sigue existiendo y con sus tests, pero ya no es el fallback del supervisor real: la spec 005 (RF-8, RF-9 y RF-42) lo generaliza en `elegir_roles_por_reglas`, que encadena varios roles. Es una evolución del mismo requisito, no un fallo.
- Rubén adaptó `src/agents/horarios.py` y `base.py` para el grafo (prompt con la excepción de horarios y solo sus dos tools, y límite compartido de tools por turno) y añadió tests propios en `tests/test_especialista_horarios.py` y `tests/test_allowlist_horarios.py`. Los requisitos RF-8 a RF-15 siguen cubiertos por los mismos tests.

## Veredicto
**Parcial.** Los 16 RF tienen test en verde y la suite completa pasa (623 passed en `develop`). El especialista `horarios` ya está integrado en el grafo y probado con dobles sin API. Falta la demo con el grafo real, el RAG indexado y Gemini («¿hasta qué hora hay metro hoy?»), que gasta API y todavía no se ha hecho. T11 queda abierta hasta entonces.
