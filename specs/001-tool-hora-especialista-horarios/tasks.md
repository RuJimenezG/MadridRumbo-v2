# Tareas — Spec 001

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.

- [x] T1. Preparar entorno de tests: añadir `pytest` y `tzdata` a `requirements.txt`, crear `tests/__init__.py` y comprobar `pytest.ini`. (RF-4)
      Hecho cuando: `python -m pytest` arranca sin errores de importación.
- [x] T2. Añadir a `config.py` `ZONA_HORARIA = "Europe/Madrid"`, `MAX_STEPS_ESPECIALISTA = 3` y `TOOLS_POR_ESPECIALISTA = {"horarios": ["hora_actual", "rag_ask"]}`. (RF-4, RF-12, RF-13)
      Hecho cuando: `python -c "import config; print(config.ZONA_HORARIA)"` imprime `Europe/Madrid`.
- [x] T3. Escribir los tests de `hora_actual` (laborable, sábado, domingo, sin argumentos, sin red, zona configurable, zona inválida). (RF-1–5)
      Hecho cuando: los tests existen y fallan porque la función aún no existe.
- [x] T4. Implementar `src/tools/hora_actual.py`. (RF-1–5)
      Hecho cuando: `pytest tests/test_hora_actual.py` en verde.
- [x] T5. Escribir los tests de allowlist y traza (`hora_actual` permitida, tool inventada bloqueada, traza con nombre/args/status/preview). (RF-6, RF-7, RF-12)
      Hecho cuando: los tests existen y fallan.
- [x] T6. Registrar `hora_actual` en `src/tools/__init__.py` con `ejecutar_tool` y traza. Si el archivo ya existe en `develop` por otra rama, solo añadir el registro. (RF-6, RF-7, RF-12)
      Hecho cuando: `pytest tests/test_allowlist_horarios.py` en verde.
- [x] T7. Escribir los tests del especialista con LLM y tools falsos (prompt propio, usa hora, usa RAG, abstención, max_steps, sin `done`, LLM falla, respuesta inválida). (RF-8–15)
      Hecho cuando: los tests existen y fallan.
- [x] T8. Implementar `src/agents/horarios.py` (`PROMPT_HORARIOS`, `nodo_horarios`). (RF-8–15)
      Hecho cuando: `pytest tests/test_especialista_horarios.py` en verde.
- [x] T9. Escribir los tests e implementar la función de palabras clave del fallback del supervisor. (RF-16)
      Hecho cuando: `pytest tests/test_fallback_horarios.py` en verde.
- [x] T10. Acordar con quien lleve `src/graph.py` el contrato del estado y del LLM, y anotarlo en la spec. (RF-14)
      Hecho cuando: la duda abierta de la spec queda resuelta y marcada.
- [ ] T11. (Parcial: falta demo con grafo) Validación final RF por RF (`/sdd-validar`). (Todos)
      Hecho cuando: `validacion.md` con veredicto «Sí».
