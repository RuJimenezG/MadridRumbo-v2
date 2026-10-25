# Tareas — Spec 007: Guardas semánticas para consultas textuales de tarifas

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.
>
> No se modificarán `main.py`, `app.py`, `rag/rag_cli.py`, `rag/responder.py`,
> `src/tools/describir_imagen.py`, `config.py` ni `src/supervisor_reglas.py`.

- [x] T1. Escribir primero las pruebas unitarias del catálogo y de sus predicados puros; crear `src/catalogo_roles.py` con las cinco responsabilidades, los términos tarifarios explícitos, la normalización y la sustitución posicional de una cola ya validada. (RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7, RF-8, RF-9, RF-10, RF-16)
      Hecho cuando: `python -m pytest tests/test_catalogo_roles.py -q` termina en verde y cubre mayúsculas, tildes, puntuación, plurales o flexiones simples, referencia textual a foto/cartel, orden, repeticiones y contador de correcciones.

- [x] T2. Escribir primero las pruebas del Supervisor; generar sus instrucciones desde el catálogo y aplicar, solo a una decisión LLM ya validada, la corrección de `tarifas` a `rag` sin tocar el fallback vigente. (RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7, RF-8, RF-9, RF-10, RF-11, RF-14, RF-15, RF-16, RF-17)
      Hecho cuando: `python -m pytest tests/test_supervisor_grafo.py -q` termina en verde e incluye una decisión `{"roles": ["tarifas"]}` para «¿Cuánto cuesta el Combinado Metro?», una cola repetida y un escenario con imagen válida que conserva `tarifas`, además de comprobar `sin_fallback`, el contador seguro y la ausencia de respuesta LLM cruda.

- [x] T3. Escribir primero las pruebas de estado y contrato; transportar únicamente el contador seguro de corrección por el contexto efímero y proyectarlo como segunda línea canónica de `log`, sin añadir claves públicas ni persistir diagnóstico o contexto de imagen. (RF-14, RF-15, RF-16, RF-17, RF-18, RF-19)
      Hecho cuando: `python -m pytest tests/test_estado_grafo.py tests/test_agent_contrato.py -q` termina en verde y demuestra las seis claves públicas, `sin_fallback` separado de `correccion_semantica=aplicada`, resumen fijo con número, ausencia de datos crudos y ausencia del indicador en checkpoint, historial, reanudación HITL y turno posterior.

- [x] T4. Escribir primero las pruebas de contexto de ejecución; ampliar el contexto interno del grafo y de `procesar_turno` para que cada turno empiece sin imagen y para que una integración interna ya validada pueda señalar una imagen válida —incluida la demo seleccionada explícitamente— sin alterar el contrato público. (RF-8, RF-10, RF-11, RF-15, RF-17)
      Hecho cuando: `python -m pytest tests/test_flujo_imagen_calculo.py tests/test_agent_contrato.py -q` termina en verde y comprueba que una mera referencia a una foto/cartel no habilita visión, que la demo solo lo hace al marcarse explícitamente y que el contexto no se conserva entre turnos.

- [x] T5. Escribir primero las pruebas de enrutamiento defensivo; hacer que `nodo_tarifas` no invoque su LLM ni `describir_imagen` si falta imagen válida y que el envoltorio del grafo reemplace internamente ese primer `tarifas` por `rag`, sin llamar a RAG desde el especialista visual. (RF-9, RF-11, RF-12, RF-13)
      Hecho cuando: `python -m pytest tests/test_grafo_enrutamiento.py -q` termina en verde y demuestra que una llegada directa a `tarifas` sin imagen ejecuta `rag_ask` y cero llamadas a `describir_imagen`, mientras que una imagen válida conserva una sola llamada visual.

- [x] T6. Escribir primero la prueba de regresión extremo a extremo con todos los dobles; comprobar que una decisión JSON válida pero semánticamente errónea para Combinado Metro conserva la respuesta RAG anclada y la traza canónica, sin APIs ni credenciales reales. (RF-9, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17)
      Hecho cuando: `python -m pytest tests/test_grafo_enrutamiento.py::test_combinado_metro_corregido_llama_rag_ask_y_conserva_traza -q` termina en verde y verifica una llamada a `rag_ask`, cero a `describir_imagen`, una traza con las cuatro claves permitidas y diagnóstico seguro independiente.

- [x] T7. Ejecutar la regresión completa tras integrar las guardas, sin cambiar clientes, allowlist, herramientas RAG/visión ni reglas de fallback de la spec 006. (RF-1, RF-2, RF-3, RF-4, RF-5, RF-6, RF-7, RF-8, RF-9, RF-10, RF-11, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17, RF-18, RF-19)
      Hecho cuando: `python -m pytest -ra` termina en verde sin llamadas a proveedores, APIs, embeddings ni ChromaDB reales.

- [x] T8. Validación final RF por RF (`/sdd-validar`): crear `validacion.md`, documentar cómo distinguir corrección semántica de fallback y cómo los futuros clientes técnico y Streamlit deben tratar `log` y `traza`, sin implementar ni modificar dichos clientes. (RF-18, RF-19, RF-20)
      Hecho cuando: `specs/007-guardas-semanticas-tarifas-textuales/validacion.md` contiene la matriz RF-1 a RF-20 con veredicto «Sí» y evidencia de pruebas, y `python -m pytest -ra` termina en verde.

## Cambio aprobado 2026-10-19: selección explícita de la imagen demo

- [x] T9. Escribir pruebas de contrato de la fachada para la referencia literal de la demo. (RF-21, RF-22, RF-23, RF-24)
      Hecho cuando: las pruebas, sin proveedores reales, verifican que solo el literal `assets/imagen_demo.jpg` activa `imagen_valida` para ese turno; que una demo configurada no válida conserva las guardas textuales; y que un turno posterior sin literal no hereda esa validez. Antes de implementar T10, las nuevas aserciones fallan por el valor fijo actual.
      Estado: completada el 2026-10-19. La regresión esperada falla de forma aislada: la fachada entrega `[False, False]` donde debe entregar `[True, False]`; no hay otros fallos en la suite.

- [x] T10. Calcular de forma efímera la validez de la demo en la fachada pública. (RF-21, RF-22, RF-23, RF-24)
      Archivos: `src/agent.py`.
      Hecho cuando: `procesar_turno()` mantiene su contrato y solo pasa `imagen_valida=True` al contexto del turno cuando el mensaje contiene el literal aprobado y la imagen demo configurada es un archivo permitido dentro de `config.IMAGENES_DIR`; no se añade estado persistente ni se modifica CLI, Streamlit, el grafo ni la tool de visión. Pasan las pruebas de T9 y `python -m pytest` sin red ni claves.
      Estado: completada el 2026-10-19. `python -m pytest tests/test_agent_contrato.py -q` y `python -m pytest -q` terminan correctamente.

- [x] T11. Cubrir la ruta visual de tarifas seleccionada desde la fachada. (RF-21, RF-22, RF-23)
      Archivos: `tests/test_flujo_imagen_calculo.py`, `tests/test_agent_contrato.py`.
      Hecho cuando: con modelos, especialistas y ejecutor de tools falsos, las pruebas comprueban que la selección válida alcanza la ruta de `tarifas` y puede invocar `describir_imagen`; una referencia genérica o una demo inválida no la invocan y se mantienen en la ruta textual. Pasa `python -m pytest` sin red ni claves.
      Estado: completada el 2026-10-19. Las pruebas focalizadas y `python -m pytest -q` terminan correctamente, sin proveedores reales.

- [x] T12. Registrar la validación del cambio de imagen demo. (RF-21, RF-22, RF-23, RF-24)
      Archivos: `specs/007-guardas-semanticas-tarifas-textuales/validacion.md`.
      Hecho cuando: se documentan los comandos, resultados y comprobaciones manuales de no persistencia entre turnos; `python -m pytest` termina correctamente y no se usan credenciales ni red.
      Estado: completada el 2026-10-19. `python -m pytest -q` termina correctamente; la demostración manual que consume proveedores queda documentada y no se ejecutó.
