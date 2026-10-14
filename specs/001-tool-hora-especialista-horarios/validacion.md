# Validación — Spec 001

> Fecha: 2026-10-14 · Resultado de `pytest`: 75 passed, 0 failed

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
| Demo | Manual | CLI: «¿hasta qué hora hay metro hoy?» → traza con `hora_actual` y `rag_ask` (requiere grafo integrado) | ⏭ Omitida (ver «Veredicto») |

## Criterios de finalización
- [x] Todos los RF con test en verde (`pytest`) sin API.
- [ ] Demo manual realizada con el grafo integrado.

## Fuera de spec
- `rag_ask` registrada en la allowlist global (`src/tools/__init__.py`). La spec exige que el especialista pueda invocar el RAG (RF-10) pero no dice quién lo registra. Hasta que `feature/tools-rag` se integre en `develop`, la `rag_ask` real fallará al importar `rag.responder`.
- Estado «error» en la traza cuando el resultado empieza por `ERROR` o cuando la tool lanza una excepción (el plan lo preveía, la spec no).
- Mini-bucle extraído a `src/agents/base.py` para compartirlo con el especialista de tarifas (spec 002). El comportamiento no cambia.
- `elegir_rol_por_palabras` existe, pero todavía no hay supervisor ni grafo que la llamen.

## Veredicto
**Parcial.** Los 16 RF tienen test en verde y la suite completa pasa (75 passed). Falta la demo manual en CLI («¿hasta qué hora hay metro hoy?»), que exige el grafo integrado (`src/graph.py`). Además, la `rag_ask` real no se ha probado: depende de que se integre `feature/tools-rag`. T11 queda abierta hasta que se haga esa demo.
