# Tareas — Spec 008

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.
> Cada tarea termina con `python -m pytest` sin errores nuevos (sin API). Las marcadas ⚠️ dependen de piezas de otras personas del equipo.

- [x] T1. Configuración y paquete: añadir a `config.py` `PEDIDOS_DEMO` (los tres pedidos de RF-11), `PALABRAS_SALIR`, `PALABRAS_APROBAR`, `PALABRAS_RECHAZAR` y `VARIABLE_MODO_SIMULADO`; crear `src/clientes/__init__.py`. (RF-4, RF-10, RF-11, RF-28)
      Hecho cuando: `python -c "import config; print(len(config.PEDIDOS_DEMO), config.VARIABLE_MODO_SIMULADO)"` imprime `3` y el nombre de la variable.
- [x] T2. Escribir los tests de presentación y contrato (`formatear_turno` con respuesta, log, traza, identificador y banderas; `interpretar_decision`; `es_salida`; `datos_depuracion`; `normalizar_estado` rellena claves ausentes). (RF-3, RF-4, RF-10, RF-15, RF-16, RF-24, RF-26)
      Hecho cuando: `tests/test_presentacion.py` existe y falla porque los módulos aún no existen.
- [x] T3. Implementar `src/clientes/contrato.py` (`estado_vacio`, `normalizar_estado`) y `src/clientes/presentacion.py`. (RF-3, RF-4, RF-10, RF-15, RF-16, RF-24, RF-26)
      Hecho cuando: `pytest tests/test_presentacion.py` en verde, salvo `test_cli_usa_el_mismo_formato` (T10).
- [x] T4. Escribir los tests del grafo simulado: cumple el contrato, devuelve plan pendiente, aprueba y rechaza, y acepta un fallo forzado. (RF-28)
      Hecho cuando: `tests/test_grafo_falso.py` existe y falla.
- [x] T5. Implementar `src/clientes/grafo_falso.py`. (RF-28)
      Hecho cuando: `pytest tests/test_grafo_falso.py` en verde.
- [x] T6. Escribir los tests de `SesionChat`: identificador estable, enviar, plan pendiente, aprobar, rechazar, `puede_decidir`, `puede_escribir`, nueva conversación, error que conserva el historial y `done` decidido por el grafo. (RF-2, RF-5, RF-8, RF-9, RF-18 a RF-23, RF-22b, RF-25, RF-27)
      Hecho cuando: `tests/test_sesion.py` existe y falla.
- [x] T7. Implementar `src/clientes/sesion.py`. (RF-2, RF-5, RF-8, RF-9, RF-18 a RF-23, RF-22b, RF-25, RF-27)
      Hecho cuando: `pytest tests/test_sesion.py` en verde.
- [x] T8. Escribir los tests de `cargar_agente`: modo simulado activado por variable y aviso, y error claro sin grafo real ni variable. (RF-28, RF-29)
      Hecho cuando: `tests/test_cargar_agente.py` existe y falla.
- [x] T9. Implementar `src/clientes/cargar.py`. (RF-28, RF-29)
      Hecho cuando: `pytest tests/test_cargar_agente.py` en verde.
- [x] T10. Escribir los tests del chat del CLI con entrada y salida falsas: responde, mismo identificador, mensaje vacío, `salir`, fallo del grafo y formato igual al de la presentación. (RF-1 a RF-5, RF-26)
       Hecho cuando: los tests de chat de `tests/test_cli.py` y `tests/test_presentacion.py::test_cli_usa_el_mismo_formato` existen y fallan.
- [x] T11. Implementar el chat de `src/clientes/cli.py` y dejar `main.py` como capa fina que lo llama. (RF-1 a RF-5, RF-26)
       Hecho cuando: pasan los tests de T10; `python main.py` con el modo simulado abre el chat (comprobación manual).
- [x] T12. Escribir los tests del HITL en el CLI: pregunta, nunca cierra sin decisión, aprobar con `done` del grafo, rechazar y seguir, decisión inválida. (RF-6 a RF-10)
       Hecho cuando: los tests de HITL de `tests/test_cli.py` existen y fallan.
- [x] T13. Implementar el HITL en `src/clientes/cli.py`. (RF-6 a RF-10)
       Hecho cuando: `pytest tests/test_cli.py` en verde.
- [x] T14. Escribir los tests de la demo: tres pedidos con tres identificadores, pide aprobación sin `--auto-aprobar`, `--auto-aprobar` aprueba solo, y error si falta `--demo`. (RF-11 a RF-14)
       Hecho cuando: `tests/test_cli_demo.py` existe y falla.
- [x] T15. Implementar `--demo` y `--auto-aprobar` en `src/clientes/cli.py` y `main.py`. (RF-11 a RF-14)
       Hecho cuando: `pytest tests/test_cli_demo.py` en verde y `python main.py --demo --auto-aprobar` con el modo simulado recorre los tres pedidos (manual).
- [x] T16. Sustituir `app.py` por el cliente Streamlit: chat, barra lateral con Aprobar y Rechazar, cuadro de mensaje bloqueado con plan pendiente, panel de depuración, Nueva conversación y aviso del modo simulado. (RF-17 a RF-25, RF-22b, RF-28)
       Hecho cuando: `streamlit run app.py` con el modo simulado permite recorrer chat, aprobar, rechazar y nueva conversación (comprobación manual anotada en `validacion.md`) y `pytest` sigue en verde.
- [x] T17. Documentar en el README cómo lanzar el CLI, la demo y Streamlit, y cómo activar el modo simulado. (RF-1, RF-11, RF-17, RF-28)
       Hecho cuando: los comandos del README se ejecutan tal cual con el modo simulado.
- [x] T18. (Sustituida por T20 a T35: el grafo real ya existe y obliga a adaptar los clientes.)

## Cambio del 2026-10-19: adaptación al grafo real

> Una tarea cada vez y con los tests primero, como arriba. Las tareas que gastan API van marcadas ⚠️ y solo se ejecutan si se piden.

- [x] T20. Configuración: nuevos `PEDIDOS_DEMO` (horarios, ruta y fuera de corpus) y `PREFIJOS_DIAGNOSTICO_SUPERVISOR` en `config.py`. (RF-11, RF-35)
       Hecho cuando: `python -c "import config; print(config.PEDIDOS_DEMO[1], config.PREFIJOS_DIAGNOSTICO_SUPERVISOR)"` imprime la ruta y los dos prefijos.
- [x] T21. Escribir los tests de `planes.py`: resumen de ruta completo, sin tramos, sin zona ni precio, formato desconocido, identificadores y entradas técnicas del supervisor. (RF-30, RF-33, RF-35)
       Hecho cuando: `tests/test_planes.py` existe y falla.
- [x] T22. Implementar `src/clientes/planes.py`. (RF-30, RF-33, RF-35)
       Hecho cuando: `pytest tests/test_planes.py` en verde.
- [x] T23. Escribir los tests del grafo simulado con formato real: planes `{id, resultado}`, varios planes para algunos pedidos y ninguna pausa en horarios y RAG. (RF-34, RF-36)
       Hecho cuando: los tests nuevos de `tests/test_grafo_falso.py` existen y fallan.
- [x] T24. Adaptar `grafo_falso.py` y ajustar los tests de simulado, sesión y CLI que asumían pausa con cualquier mensaje. (RF-34, RF-36)
       Hecho cuando: `pytest` en verde.
- [x] T25. Escribir los tests de sesión con identificador de plan: un plan, varios planes, que el elegido llegue al grafo y que no se llame sin elección. (RF-31, RF-32)
       Hecho cuando: los tests nuevos de `tests/test_sesion.py` existen y fallan.
- [x] T26. Implementar `decidir(aprobado, plan_id)` y la propiedad `planes` en `sesion.py`. (RF-31, RF-32)
       Hecho cuando: `pytest tests/test_sesion.py` en verde.
- [x] T27. Escribir los tests de presentación: planes con resumen y entradas técnicas visibles u ocultas. (RF-6, RF-30, RF-35)
       Hecho cuando: los tests nuevos de `tests/test_presentacion.py` existen y fallan.
- [x] T28. Adaptar `presentacion.py`. (RF-6, RF-30, RF-35)
       Hecho cuando: `pytest tests/test_presentacion.py` en verde.
- [x] T29. Escribir los tests del CLI: resumen del plan, elegir entre varios planes, un plan sin pregunta de elección, respuesta sin plan sin pregunta y rechazo con nuevo plan. (RF-6, RF-9, RF-31, RF-32, RF-34, RF-35)
       Hecho cuando: los tests nuevos de `tests/test_cli.py` y `tests/test_cli_demo.py` existen y fallan.
- [x] T30. Adaptar `cli.py`. (RF-6, RF-9, RF-31, RF-32, RF-34, RF-35)
       Hecho cuando: `pytest tests/test_cli.py tests/test_cli_demo.py` en verde.
- [x] T31. Adaptar `app.py`: selector de plan, botones con identificador y filtro de entradas técnicas en toda la web. (RF-31, RF-35)
       Hecho cuando: el recorrido con `AppTest` en modo simulado pasa (selector con dos planes, aprobar uno y filtro) y `pytest` sigue en verde.
- [x] T32. Escribir `tests/test_clientes_grafo_real.py` con el grafo real y los dobles de `tests/dobles_grafo.py` (sin API) y corregir lo que falle. (RF-26, RF-30 a RF-34)
       Hecho cuando: `pytest tests/test_clientes_grafo_real.py` en verde.
- [x] T33. Actualizar el README con la demo nueva, los planes y la elección entre varios. (RF-11, RF-30, RF-31)
       Hecho cuando: los comandos del README funcionan en modo simulado.
- [ ] T34. ⚠️ Demo con el grafo real y API (Gemini, Nominatim y Google): una consulta de horarios, una ruta con aprobación y una pregunta fuera de corpus. Solo si se pide.
       Hecho cuando: los resultados quedan anotados en `validacion.md`.
- [ ] T35. (Parcial: falta la demo con el grafo real y API, T34) Validación final RF por RF (`/sdd-validar`). (Todos)
       Hecho cuando: `validacion.md` con veredicto «Sí».
