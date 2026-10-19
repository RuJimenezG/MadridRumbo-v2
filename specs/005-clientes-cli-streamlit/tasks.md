# Tareas — Spec 005

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
- [ ] T18. ⚠️ Integración con el grafo real cuando exista en `develop`: ajustar `contrato.py` y `cargar.py` a sus nombres y repetir las demos del CLI y de Streamlit. (RF-26, RF-29, todos los de interfaz)
       Hecho cuando: `python main.py --demo` y `streamlit run app.py` funcionan con el grafo real y `pytest` sigue en verde.
- [ ] T19. Validación final RF por RF (`/sdd-validar`). (Todos)
       Hecho cuando: `validacion.md` con veredicto «Sí».
