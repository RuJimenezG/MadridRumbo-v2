# Tareas — Spec 005: Grafo multiagente con LangGraph

> Una tarea cada vez: /sdd-implementar Tn. Pruebas primero. Marca [x] solo al terminar la tarea y deja python -m pytest en verde.

- [x] T1. Declarar la dependencia LangGraph, los límites MAX_TURNOS_CONVERSACION y MAX_CICLOS_TOOLS, y las allowlists finales en requirements.txt y config.py. (RF-38, RF-39, RF-43, RF-44, RF-58)
  - Prueba primero: crear tests/test_config_grafo.py para comprobar los dos límites y las cinco allowlists, incluidas las excepciones de horarios y la retirada de RAG directo de tarifas.
  - Implementar: añadir el rango de LangGraph acordado, los valores iniciales 10 y 8 y la configuración centralizada sin tocar secretos.
  - **Hecho cuando:** tests/test_config_grafo.py y python -m pytest completos terminan en verde.

- [x] T2. Crear los dobles comunes y el modelo de estado interno/proyección pública del grafo. (RF-25, RF-26, RF-27, RF-35, RF-47)
  - Prueba primero: crear tests/test_estado_grafo.py para el estado inicial, planes con ID estable, reducers de auditoría y la proyección exacta de las seis claves públicas.
  - Implementar: crear tests/dobles_grafo.py y src/estado.py sin importar proveedores ni leer credenciales.
  - **Hecho cuando:** tests/test_estado_grafo.py y python -m pytest completos terminan en verde.

- [x] T3. Añadir adaptadores perezosos e inyectables para modelo de supervisor, especialistas y sintetizador. (RF-6, RF-19, RF-56)
  - Prueba primero: crear tests/test_modelos_grafo.py que demuestre que importar los módulos no crea clientes ni pide claves y que los dobles inyectados se usan.
  - Implementar: crear src/modelos.py con interfaces mínimas y manejo controlado de errores, reutilizando la configuración existente solo al ejecutar en producción.
  - **Hecho cuando:** tests/test_modelos_grafo.py y python -m pytest completos terminan en verde.

- [x] T4. Ampliar el fallback determinista del supervisor sin romper elegir_rol_por_palabras heredado. (RF-6, RF-7, RF-8, RF-9, RF-10, RF-11, RF-42, RF-45, RF-46, RF-57)
  - Prueba primero: ampliar tests/test_fallback_horarios.py y crear casos en tests/test_supervisor_grafo.py para cada intención, combinación, orden, distinción hora/horario, imagen con total y reformulación con el alcance completo.
  - Implementar: añadir una función de múltiples roles normalizada en src/supervisor_reglas.py; reservar la dependencia tarifas → auxiliar para total de imagen.
  - **Hecho cuando:** los casos de fallback y python -m pytest completos terminan en verde.

- [x] T5. Implementar la decisión estructurada y validada del Supervisor. (RF-2, RF-3, RF-4, RF-6)
  - Prueba primero: añadir casos para decisión válida, cadena, repetición, finish, JSON inválido, excepción y rol prohibido en tests/test_supervisor_grafo.py.
  - Implementar: crear src/supervisor.py para convertir la respuesta del LLM en una cola finita de roles admitidos o delegar en el fallback Python.
  - **Hecho cuando:** tests/test_supervisor_grafo.py y python -m pytest completos terminan en verde.

- [x] T6. Implementar nodo_rag con la tool rag_ask y conservación de evidencia, abstención y fallo. (RF-16, RF-17, RF-18, RF-19, RF-44)
  - Prueba primero: añadir a tests/test_agentes_grafo.py dobles de RAG con evidencia, abstención y error, verificando la traza de cuatro campos y que no se admite otra tool.
  - Implementar: crear src/agents/rag.py sobre el ejecutor controlado y la allowlist de configuración.
  - **Hecho cuando:** los casos de nodo_rag y python -m pytest completos terminan en verde.

- [x] T7. Implementar nodo_auxiliar restringido a hora_actual y calculadora. (RF-9, RF-13, RF-14, RF-18, RF-19, RF-43)
  - Prueba primero: añadir casos de hora, operación válida, error de calculadora y propuesta de tool no permitida en tests/test_agentes_grafo.py.
  - Implementar: crear src/agents/auxiliar.py con el contrato de especialista existente y sin llamadas directas a RAG.
  - **Hecho cuando:** los casos de nodo_auxiliar y python -m pytest completos terminan en verde.

- [x] T8. Adaptar el antiguo especialista multimodal como nodo_tarifas, responsable solo de describir la imagen. (RF-15, RF-18, RF-19, RF-44, RF-57)
  - Prueba primero: actualizar tests/test_allowlist_multimodal.py y tests/test_flujo_imagen_calculo.py para comprobar que tarifas llama describir_imagen, conserva importes o ausencia de importes y no llama a calculadora ni RAG directamente.
  - Implementar: ajustar prompt, allowlist y nota de src/agents/tarifas.py; conservar el cálculo para el posterior nodo_auxiliar del grafo.
  - **Hecho cuando:** los tests multimodales actualizados y python -m pytest completos terminan en verde.

- [x] T9. Integrar nodo_horarios como especialista del grafo conservando sus llamadas permitidas. (RF-8, RF-17, RF-18, RF-19, RF-58, RF-59)
  - Prueba primero: ampliar tests/test_especialista_horarios.py y tests/test_allowlist_horarios.py para cubrir hora_actual, rag_ask, sus fallos controlados y la prohibición de cualquier tercera tool.
  - Implementar: adaptar src/agents/horarios.py a las dependencias inyectadas sin cambiar su comportamiento de horarios ni duplicar consultas RAG.
  - **Hecho cuando:** los tests de horarios y python -m pytest completos terminan en verde.

- [x] T10. Completar nodo_rutas sobre planificar_ruta y el contexto conversacional. (RF-7, RF-12, RF-17, RF-18, RF-19, RF-34, RF-59)
  - Prueba primero: ampliar tests/test_especialista_rutas.py con origen/destino completos, dato aportado en un turno posterior, falta de datos, JSON de tool y verificación de una única llamada exterior planificar_ruta.
  - Implementar: crear src/agents/rutas.py, reutilizar el contrato de la Spec 004 y conservar las consultas RAG internas de planificar_ruta sin sustituirlas por nodo_rag.
  - **Hecho cuando:** los tests de rutas y python -m pytest completos terminan en verde.

- [x] T11. Implementar el Sintetizador anclado y su respaldo determinista. (RF-5, RF-20, RF-21, RF-22, RF-56)
  - Prueba primero: crear tests/test_sintetizador.py para respuesta simple en español, información parcial, abstención/error conservado y fallo del modelo de síntesis.
  - Implementar: crear src/sintetizador.py para resumir únicamente notas y resultados disponibles y devolver el respaldo con aviso si el modelo falla.
  - **Hecho cuando:** tests/test_sintetizador.py y python -m pytest completos terminan en verde.

- [x] T12. Construir el StateGraph base y conectar Supervisor, los cinco especialistas y Sintetizador. (RF-1, RF-2, RF-3, RF-4, RF-5, RF-28)
  - Prueba primero: añadir pruebas de compilación y de recorrido con dobles en tests/test_grafo_enrutamiento.py: un rol, cadena, repetición, finish y rechazo de una arista no permitida.
  - Implementar: crear src/graph.py con factory inyectable, nodos declarados y aristas que consuman la cola; solo los terminales del grafo escribirán done.
  - **Hecho cuando:** tests/test_grafo_enrutamiento.py y python -m pytest completos terminan en verde.

- [x] T13. Añadir el ejecutor transversal del grafo, la agregación de trazas y las cadenas dependientes entre especialistas. (RF-17, RF-18, RF-19, RF-43 a RF-46, RF-58, RF-59)
  - Prueba primero: ampliar tests/test_grafo_enrutamiento.py y tests/test_agentes_grafo.py con RAG → auxiliar, tarifas → auxiliar, horarios y rutas internas; verificar orden, una traza completa por llamada directa y que no se duplica RAG.
  - Implementar: inyectar en src/agents/base.py y src/graph.py un ejecutor común que preserve el límite local del especialista y agregue resultados del turno.
  - **Hecho cuando:** los flujos encadenados, los tests de traza y python -m pytest completos terminan en verde.

- [x] T14. Activar checkpointer por thread_id y recuperación/aislamiento de conversaciones. (RF-35, RF-36, RF-37, RF-53)
  - Prueba primero: crear tests/test_grafo_persistencia.py para recuperar historial y contexto con el mismo ID, empezar vacío con estado vacío e impedir fugas entre dos IDs.
  - Implementar: compilar el factory del grafo con InMemorySaver por defecto e inyectable, usando configurable.thread_id en todas las invocaciones válidas.
  - **Hecho cuando:** tests/test_grafo_persistencia.py y python -m pytest completos terminan en verde.

- [x] T15. Exponer la fachada pública y sus validaciones sin efectos colaterales. (RF-23, RF-24, RF-25, RF-26, RF-27, RF-28, RF-51 a RF-55)
  - Prueba primero: crear tests/test_agent_contrato.py para las dos firmas, las seis claves y tipos, thread_id vacío, estado inválido, mensaje vacío, estado vacío recuperable y aprobación sin snapshot/plan.
  - Implementar: crear src/agent.py con factory perezoso, proyección pública y mensajes controlados; las validaciones no invocarán grafo ni tools ni modificarán el checkpoint.
  - **Hecho cuando:** tests/test_agent_contrato.py y python -m pytest completos terminan en verde.

- [x] T16. Normalizar resultados de rutas en planes identificados y pausar mediante HITL solo cuando procede. (RF-12, RF-29, RF-30, RF-34, RF-47)
  - Prueba primero: crear tests/test_grafo_hitl.py para JSON/dict estado ok con ruta, múltiples planes e IDs estables, y para estados de aclaración, ambigüedad, sin ruta y error_interno sin pausa.
  - Implementar: añadir al grafo el normalizador de rutas y el nodo de pausa con interrupt después de persistir planes, respuesta y done falso.
  - **Hecho cuando:** los casos de pausa y no-pausa y python -m pytest completos terminan en verde.

- [x] T17. Reanudar una pausa para aprobar exclusivamente el plan seleccionado. (RF-30, RF-31, RF-47)
  - Prueba primero: ampliar tests/test_grafo_hitl.py con selección mediante estado["plan_id_seleccionado"], aprobación de uno entre varios y cierre de los planes restantes.
  - Implementar: usar Command para reanudar el mismo checkpoint, aceptar el plan elegido y dejar que el nodo terminal fije done verdadero.
  - **Hecho cuando:** los casos de aprobación y python -m pytest completos terminan en verde.

- [x] T18. Gestionar rechazo y mensajes nuevos durante una pausa HITL. (RF-32, RF-33, RF-48, RF-49)
  - Prueba primero: ampliar tests/test_grafo_hitl.py con un doble secuencial de rutas para comprobar descarte del plan seleccionado, reinvocación con argumentos persistidos y done falso; añadir contadores que prueben que un mensaje nuevo no ejecuta ningún nodo ni tool.
  - Implementar: conectar la rama de rechazo de Command con nodo_rutas y la guardia de plan pendiente de procesar_turno, conservando el mismo thread_id.
  - **Hecho cuando:** los casos de rechazo y bloqueo de mensaje y python -m pytest completos terminan en verde.

- [x] T19. Aplicar y comprobar los límites globales de turnos y de invocaciones directas de tools. (RF-38, RF-39, RF-40, RF-41, RF-50)
  - Prueba primero: crear tests/test_grafo_limites.py con topes pequeños mediante monkeypatch para contador de pares usuario/respuesta, resumen al superar turnos, presupuesto compartido entre nodos y persistencia del presupuesto al rechazar un plan.
  - Implementar: añadir al grafo el contador por turno lógico, el ejecutor acotado y los terminales de resumen que avisan del límite y dejan done verdadero sin llamadas adicionales.
  - **Hecho cuando:** tests/test_grafo_limites.py y python -m pytest completos terminan en verde.

- [x] T20. Ejecutar la regresión integrada de la Spec 005 y ajustar únicamente expectativas heredadas que hayan cambiado de responsabilidad. (RF-1 a RF-59)
  - Prueba primero: añadir un escenario de extremo a extremo con dobles que encadene al menos dos especialistas, uno de rutas con HITL y uno de límite, sin red.
  - Implementar: corregir solo incompatibilidades de integración en tests existentes, especialmente el flujo imagen → calculadora ahora repartido entre tarifas y auxiliar; no modificar contratos de tools ni clientes fuera de alcance.
  - **Hecho cuando:** python -m pytest termina en verde y cubre todos los escenarios de finalización de la spec sin acceder a APIs.

- [x] T21. Validación final RF por RF (/sdd-validar). (Todos)
  - Prueba primero: revisar la matriz de trazabilidad de plan.md y ejecutar la suite completa.
  - Implementar: crear validacion.md con cada RF, su evidencia de test y el veredicto Sí/No; no se cambia código durante esta tarea.
  - **Hecho cuando:** validacion.md contiene veredicto “Sí” para todos los RF y python -m pytest termina en verde.

Cobertura comprobada: los RF-1 a RF-59 aparecen al menos en una tarea; RF-42, RF-43 a RF-50 y RF-57 a RF-59 están cubiertos explícitamente en T1, T4, T6 a T19.
