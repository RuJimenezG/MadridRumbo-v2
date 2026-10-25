# Tareas — Spec 006: Robustez y observabilidad de decisiones LLM del Supervisor

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` solo al terminar la tarea y deja `python -m pytest` en verde. Esta spec no modifica `main.py`, `app.py` ni crea clientes CLI o Streamlit.

- [x] T1. Configurar un adaptador inyectable exclusivo para la solicitud JSON del Supervisor. (RF-1, RF-8, RF-24)
  - Prueba primero: ampliar `tests/test_modelos_grafo.py` con un cliente Gemini falso que capture `generate_content`, cubriendo `response_mime_type="application/json"` en el adaptador del Supervisor, su ausencia en especialistas/sintetizador y la traducción controlada de fallos, contenido vacío, no textual y bloqueo.
  - Implementar: ajustar `src/modelos.py` para que solo el adaptador del Supervisor solicite JSON al proveedor y exponga al nodo una frontera distinguible de fallo de proveedor, sin crear clientes ni leer credenciales al importar.
  - **Hecho cuando:** los casos nuevos de `tests/test_modelos_grafo.py` y `python -m pytest` completos terminan en verde, sin llamadas de red.

- [x] T2. Corregir el prompt y crear el normalizador JSON estricto del Supervisor. (RF-2, RF-3, RF-5, RF-6, RF-7)
  - Prueba primero: ampliar `tests/test_supervisor_grafo.py` para comprobar el ejemplo exacto `{"roles": ["auxiliar"]}`, la instrucción de responder únicamente JSON y la aceptación de fences completos sin etiqueta, `json` o `JSON`, con espacios exteriores; cubrir el rechazo de comillas simples, texto adicional y fences no permitidos.
  - Implementar: actualizar `src/supervisor.py` con un normalizador acotado a esos envoltorios y parseo JSON estándar, sin extraer objetos parciales ni reparar contenido.
  - **Hecho cuando:** los casos de prompt, Markdown recuperable y JSON inválido de `tests/test_supervisor_grafo.py`, más `python -m pytest`, terminan en verde.

- [x] T3. Validar la decisión de roles y clasificar el fallback sin datos sensibles. (RF-4, RF-8, RF-9, RF-12, RF-13, RF-14)
  - Prueba primero: ampliar `tests/test_supervisor_grafo.py` con objeto que contiene exclusivamente `roles`, lista vacía, repetición y veinte roles válidos; y con campos extra, falta de `roles`, tipo erróneo, más de veinte roles, rol prohibido, error del proveedor, vacío/no texto/bloqueo. Usar centinelas de secreto, prompt y respuesta cruda para verificar que no se exponen.
  - Implementar: endurecer la validación en `src/supervisor.py`, conservar el fallback determinista y producir solamente las categorías `proveedor`, `json_invalido`, `roles_invalidos` o `sin_fallback` con resúmenes de un catálogo fijo.
  - **Hecho cuando:** los escenarios válidos no activan fallback, los inválidos sí lo hacen con la categoría esperada, y `tests/test_supervisor_grafo.py` junto con `python -m pytest` terminan en verde.

- [x] T4. Transportar el diagnóstico del Supervisor por el contexto efímero del grafo. (RF-10, RF-11, RF-25)
  - Prueba primero: ampliar `tests/test_grafo_enrutamiento.py` y `tests/test_supervisor_grafo.py` con un doble de Supervisor para demostrar que cada decisión deja un diagnóstico en un contexto de invocación y que el fallback conserva su motivo clasificado.
  - Implementar: adaptar `src/graph.py` y `src/supervisor.py` para usar `context_schema`/`Runtime.context` de LangGraph y pasar un colector mutable por `invoke(..., context=...)`, sin añadirlo a `EstadoGrafo`, reducers, `log` interno ni `traza`.
  - **Hecho cuando:** las pruebas muestran `sin_fallback` para decisión válida y la causa correcta para fallback, y `python -m pytest` termina en verde sin persistir ese contexto.

- [x] T5. Proyectar el diagnóstico seguro únicamente en el resultado público del turno. (RF-10 a RF-16, RF-25)
  - Prueba primero: ampliar `tests/test_agent_contrato.py`, `tests/test_estado_grafo.py` y `tests/test_grafo_persistencia.py` para verificar las seis claves y el tipo `log: list[str]`, la entrada canónica segura en una copia del resultado actual, y su ausencia de `traza`, checkpoint, siguiente turno y reanudación HITL.
  - Implementar: ajustar `src/agent.py` y `src/estado.py` para crear el contexto por llamada, pasarlo al grafo y añadir la entrada saneada solo al resultado proyectado. Mantener el contrato preparado para clientes futuros: una CLI podrá leer `log` y Streamlit deberá omitir `log` y `traza`; no modificar `main.py` ni `app.py`.
  - **Hecho cuando:** los tests de contrato y persistencia confirman que no hay claves nuevas ni diagnóstico reutilizado, y `python -m pytest` termina en verde.

- [x] T6. Ampliar las reglas deterministas para las tres formulaciones de ruta. (RF-17, RF-18, RF-19)
  - Prueba primero: ampliar `tests/test_supervisor_grafo.py` o el fichero específico de reglas con tablas de casos para «quiero ir de», «necesito ir de» y «voy de», incluyendo mayúsculas, tildes, puntuación, espacios y texto adicional.
  - Implementar: ajustar `src/supervisor_reglas.py` para reconocer explícitamente esas formulaciones tras la normalización existente, sin ampliar otras intenciones ni alterar el orden determinista de roles.
  - **Hecho cuando:** los tres grupos de variantes devuelven `rutas` y `python -m pytest` termina en verde.

- [x] T7. Pedir aclaración antes de invocar el flujo de rutas cuando falte un extremo. (RF-21)
  - Prueba primero: ampliar `tests/test_especialista_rutas.py` con las tres formulaciones incompletas y dobles contadores del LLM, `planificar_ruta`, traza e HITL.
  - Implementar: adaptar `src/agents/rutas.py` para detectar la formulación explícita incompleta y devolver una aclaración controlada antes de invocar modelo, tool o registrar una ruta.
  - **Hecho cuando:** cada caso incompleto devuelve la aclaración y los cuatro contadores permanecen a cero; `python -m pytest` termina en verde.

- [x] T8. Integrar el fallback de rutas válido hasta el plan pendiente de aprobación. (RF-17 a RF-20)
  - Prueba primero: ampliar `tests/test_grafo_enrutamiento.py` con Supervisor que falla, LLM de rutas y ejecutor de tools falsos; para cada formulación válida verificar una llamada a `planificar_ruta`, plan normalizado y pausa HITL.
  - Implementar: corregir únicamente las conexiones necesarias de `src/supervisor_reglas.py`, `src/graph.py` y `src/agents/rutas.py` para mantener el recorrido fallback → `nodo_rutas` → `planificar_ruta` → HITL con origen y destino válidos.
  - **Hecho cuando:** los tres escenarios alcanzan el plan pendiente sin API real y `python -m pytest` termina en verde.

- [x] T9. Documentar la comprobación manual segura con Gemini real y el contrato de clientes futuros. (RF-15, RF-16, RF-22, RF-23)
  - Prueba primero: revisar que las pruebas automatizadas de T1 a T8 ya cubren la frontera pública y que no requieren credenciales ni red.
  - Implementar: crear `specs/006-robustez-observabilidad-supervisor/validacion.md` con instrucciones en español para invocar en desarrollo `procesar_turno`, identificar `sin_fallback`, provocar `proveedor` con una clave de proceso deliberadamente inválida sin leer, mostrar ni modificar `.env`, y revisar exclusivamente el resumen seguro de `log`. Documentar que una CLI futura podrá presentarlo y que Streamlit futuro no podrá renderizar ni conservar `log`/`traza`; no ejecutar la comprobación real sin petición expresa.
  - **Hecho cuando:** `validacion.md` contiene los dos escenarios, el resultado esperado y las precauciones de secretos/coste; `python -m pytest` termina en verde.

- [x] T10. Ejecutar la regresión integrada de la Spec 006 y ajustar solo expectativas afectadas. (RF-1 a RF-25)
  - Prueba primero: revisar la matriz de trazabilidad de `plan.md` y ejecutar los tests de Supervisor, modelo, grafo, rutas, contrato y persistencia creados o ampliados en T1 a T8.
  - Implementar: corregir exclusivamente incompatibilidades de integración en los archivos ya incluidos en el plan; no tocar contratos de tools, `main.py`, `app.py`, `rag/rag_cli.py`, configuraciones ni clientes futuros.
  - **Hecho cuando:** `python -m pytest` termina en verde y todos los RF-1 a RF-25 tienen una prueba automática o la comprobación manual documentada.

- [x] T11. Validación final RF por RF (`/sdd-validar`). (Todos)
  - Prueba primero: revisar la trazabilidad de `plan.md`, `tasks.md` y la evidencia de tests.
  - Implementar: completar `validacion.md` con cada RF, su evidencia, el veredicto Sí/No y las comprobaciones manuales pendientes, sin cambiar código durante esta tarea.
  - **Hecho cuando:** `validacion.md` contiene el veredicto correspondiente para todos los RF y `python -m pytest` termina en verde.

Cobertura comprobada: los RF-1 a RF-25 aparecen al menos en una tarea; RF-15 y RF-16 se cubren en la frontera pública preparada en T5 y se documentan para sus futuros clientes en T9, sin modificar `main.py` ni `app.py`.

## Corrección de regresión: test sin Gemini

- [x] T12. Aislar con dobles el fallback público del Supervisor. (RF-10 a RF-14; coste)
  - Prueba primero: ampliar `tests/test_agent_contrato.py::test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` para inyectar los cinco especialistas falsos y registrar la invocación del doble `auxiliar` para la consulta «¿Qué hora es?».
  - Implementar: construir el grafo de ese test con `especialistas` inyectados, manteniendo el Supervisor que devuelve texto no JSON, el Sintetizador falso y todas las aserciones actuales sobre el diagnóstico público seguro.
  - **Hecho cuando:** el test de regresión confirma que se invocó el doble `auxiliar`, no solicita credenciales ni conecta con Gemini, y `python -m pytest` termina en verde.

- [x] T13. Validar y documentar la regresión sin API. (RF-10 a RF-14; coste)
  - Prueba primero: ejecutar `tests/test_agent_contrato.py::test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` y la suite completa para comprobar que no requieren credenciales ni red.
  - Implementar: actualizar `specs/006-robustez-observabilidad-supervisor/validacion.md` con la evidencia del test aislado y el resumen de `python -m pytest`, sin modificar comportamiento de producción.
  - **Hecho cuando:** `validacion.md` identifica el test como cobertura de la regresión y registra una suite completa verde sin APIs ni credenciales reales.
