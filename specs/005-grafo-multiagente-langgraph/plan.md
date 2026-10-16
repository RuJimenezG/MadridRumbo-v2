# Plan técnico — Spec 005: Grafo multiagente con LangGraph

> Basado en spec.md (estado: Aprobada). Este plan no añade clientes CLI o Streamlit ni cambia los contratos de las tools existentes.

## Alcance y restricciones

- El nombre definitivo del antiguo especialista multimodal será nodo_tarifas, implementado en src/agents/tarifas.py. No se creará un segundo nodo_multimodal.
- Las llamadas directas al RAG que gestione el grafo pertenecen a nodo_rag, con la excepción explícita de nodo_horarios. Las consultas que planificar_ruta ya realiza internamente al RAG se conservarán como parte atómica de esa tool.
- La aprobación humana solo se activa para una ruta válida entre origen y destino. Las aclaraciones, ambigüedades y errores de la tool de rutas no activan HITL.
- Se mantendrá el límite heredado MAX_STEPS_ESPECIALISTA y se añadirá un límite transversal por turno; los tests seguirán usando dobles y no inicializarán servicios de red, LLM, ChromaDB ni embeddings.

## Archivos afectados

| Archivo | Crear / modificar | Qué cambia | RF |
|---|---|---|---|
| requirements.txt | Modificar | Añadir LangGraph con un rango compatible de versión para usar StateGraph, InMemorySaver, interrupt y Command. | RF-1, RF-35 |
| config.py | Modificar | Añadir MAX_TURNOS_CONVERSACION y MAX_CICLOS_TOOLS, inicialmente 10 y 8, y centralizar las allowlists de rag, horarios, auxiliar, rutas y tarifas. | RF-38, RF-39, RF-43, RF-44, RF-58 |
| src/estado.py | Crear | Declarar el estado interno del grafo, reducers y modelos de plan: historial, cola de roles, notas, traza, planes con ID, contador de turnos, contador de tools del turno, HITL y resultado público. | RF-25 a RF-28, RF-35 a RF-37, RF-47 |
| src/modelos.py | Crear | Encapsular de forma perezosa los adaptadores de modelo para supervisor, especialistas y sintetizador; permitir su inyección en pruebas sin solicitar claves al importar. | RF-6, RF-19, RF-56 |
| src/supervisor_reglas.py | Modificar | Conservar elegir_rol_por_palabras y añadir reglas deterministas de múltiples roles, normalización, orden y mensaje de reformulación. | RF-6 a RF-11, RF-42, RF-57 |
| src/supervisor.py | Crear | Validar la salida estructurada del supervisor, construir una cola finita de roles admitidos y delegar en las reglas Python cuando el LLM falle o sea inválido. | RF-2 a RF-6 |
| src/agents/base.py | Modificar | Mantener su contrato de notas y traza, pero aceptar el ejecutor acotado que inyecta el grafo para compartir el presupuesto transversal sin eliminar MAX_STEPS_ESPECIALISTA. | RF-18, RF-19, RF-39, RF-50 |
| src/agents/rag.py | Crear | Implementar nodo_rag con la única tool directa rag_ask y conservar respuestas, abstenciones, fuentes y errores. | RF-10, RF-16, RF-17, RF-44 |
| src/agents/auxiliar.py | Crear | Implementar nodo_auxiliar con hora_actual y calculadora exclusivamente. | RF-9, RF-13, RF-14, RF-43, RF-45, RF-46 |
| src/agents/rutas.py | Crear | Completar el especialista de rutas previsto por la Spec 004, extraer origen/destino con el contexto persistido y usar únicamente planificar_ruta. | RF-7, RF-12, RF-29 a RF-34, RF-59 |
| src/agents/horarios.py | Modificar | Integrarlo como nodo del grafo conservando su secuencia hora_actual y rag_ask y su allowlist específica. | RF-8, RF-58, RF-59 |
| src/agents/tarifas.py | Modificar | Convertir el antiguo nodo multimodal en nodo_tarifas: describir_imagen obtiene los importes y nodo_auxiliar realiza el cálculo posterior cuando proceda. Retirar rag_ask de su prompt y allowlist directos. | RF-15, RF-44, RF-46, RF-57 |
| src/sintetizador.py | Crear | Generar una síntesis sencilla, anclada en notas y resultados; incluir un renderizado determinista de respaldo si el sintetizador falla. | RF-5, RF-17, RF-19 a RF-22, RF-56 |
| src/graph.py | Crear | Construir, compilar y ejecutar el StateGraph, el checkpointer, el enrutamiento entre nodos, los límites, el ciclo de replanteamiento y la pausa HITL nativa. | RF-1 a RF-5, RF-18, RF-28 a RF-50 |
| src/agent.py | Crear | Exponer las dos fachadas públicas, validar entradas, recuperar el checkpoint por thread_id y proyectar el estado a las seis claves del contrato. | RF-23 a RF-28, RF-48 a RF-55 |
| tests/dobles_grafo.py | Crear | Ofrecer LLM, sintetizador, ejecutor de tools y checkpointer falsos, contadores de llamadas y resultados de ruta secuenciales. | RNF de coste y todos los RF con tests |
| tests/test_supervisor_grafo.py y tests/test_fallback_horarios.py | Crear / modificar | Cubrir decisiones válidas, cadenas y repeticiones, fallback para todos los roles, orden y petición de reformulación; preservar la prueba heredada de horarios. | RF-2 a RF-11, RF-42, RF-57 |
| tests/test_agentes_grafo.py, tests/test_especialista_rutas.py, tests/test_allowlist_horarios.py y tests/test_allowlist_multimodal.py | Crear / modificar | Cubrir los cinco especialistas, sus allowlists, trazas y excepciones de RAG; completar la cobertura pendiente del nodo_rutas. | RF-12 a RF-19, RF-43 a RF-46, RF-58, RF-59 |
| tests/test_sintetizador.py | Crear | Verificar síntesis anclada, información parcial y respaldo cuando el modelo de síntesis falla. | RF-20 a RF-22, RF-56 |
| tests/test_agent_contrato.py | Crear | Verificar las firmas, las seis claves y tipos públicos, entradas inválidas y la ausencia de mutaciones en controles fallidos. | RF-23 a RF-28, RF-51 a RF-55 |
| tests/test_grafo_hitl.py | Crear | Verificar pausa, selección de plan, aprobación, rechazo, replanificación y bloqueo de mensajes mientras el plan está pendiente. | RF-29 a RF-34, RF-47 a RF-49 |
| tests/test_grafo_persistencia.py y tests/test_grafo_limites.py | Crear | Verificar aislamiento y recuperación por thread_id, límites de turnos y tools, resumen y fin controlado. | RF-35 a RF-41, RF-50, RF-53 |
| tests/test_flujo_imagen_calculo.py | Modificar | Mover la comprobación imagen → calculadora al flujo entre nodo_tarifas y nodo_auxiliar, manteniendo orden, importes y operación. | RF-46 y compatibilidad con Spec 002 RF-21 a RF-23 |

## Contrato

Las únicas funciones públicas nuevas serán:

    procesar_turno(estado, mensaje, thread_id) -> dict
    aprobar_plan(estado, thread_id, aprobado: bool) -> dict

El resultado tendrá exactamente estas seis claves:

    {
      "respuesta": "He encontrado una ruta; elige el plan que quieres aprobar.",
      "plan": [
        {
          "id": "ruta-1",
          "resultado": {
            "estado": "ok",
            "ruta": {"...": "..."}
          }
        }
      ],
      "log": ["nodo_rutas completado"],
      "traza": [
        {
          "tool": "planificar_ruta",
          "args": {"origen": "Atocha", "destino": "Sol"},
          "status": "ok",
          "preview": "..."
        }
      ],
      "hitl_pendiente": true,
      "done": false
    }

Cada plan público tendrá un ID estable mientras esté pendiente. Para seleccionar uno de varios, el cliente pasará ese ID como estado de control; el checkpoint seguirá siendo la fuente de verdad:

    resultado = procesar_turno({}, "¿Cómo voy de Atocha a Sol?", "viaje-42")
    aprobar_plan(
        {"plan_id_seleccionado": resultado["plan"][0]["id"]},
        "viaje-42",
        True,
    )

El argumento estado debe ser un diccionario. Un diccionario vacío con un thread_id válido recupera el snapshot persistido o inicia una conversación vacía; sus datos no sustituyen el estado almacenado. Solo los campos de control documentados, como plan_id_seleccionado durante una aprobación, se leen desde el cliente. Esto evita que un cliente altere un plan persistido.

| Entrada | Respuesta y efecto |
|---|---|
| thread_id vacío, nulo o solo espacios | Error controlado, sin ejecutar grafo ni tools. |
| estado no es un diccionario | Error controlado, sin ejecutar grafo ni tools. |
| mensaje vacío o solo espacios | Solicitud de una consulta válida, sin grafo, tools ni incremento de turno. |
| aprobar_plan sin snapshot, sin plan pendiente, ID de plan ausente cuando hay varios o ID desconocido | Aviso controlado; no se modifica el checkpoint. |
| mensaje nuevo con un plan pendiente | Aviso de plan pendiente, con planes y traza persistidos; no se ejecuta supervisor, sintetizador, especialista ni tool. |

En los flujos válidos, solo los nodos terminales del grafo escriben done. Las respuestas de validación que no pueden iniciar un grafo usan el valor protocolario done igual a falso: no representan una decisión de finalización ni alteran una conversación.

## Estado, enrutamiento y límites

El estado interno separará el historial persistente de la proyección pública. Contendrá, como mínimo, historial de mensajes, mensaje actual, cola de roles, resultados y notas de especialistas, log, traza, planes pendientes con ID, plan_id_seleccionado, argumentos de replanificación, turnos completados, tools ejecutadas en el turno, respuesta, hitl_pendiente y done. Los reducers de LangGraph acumularán solo los campos auditables; al comenzar un mensaje válido se creará una colección de salida nueva para ese turno y se archivará el contexto necesario en historial.

El supervisor aceptará una respuesta estructurada y finita con roles de la lista rag, horarios, rutas, auxiliar y tarifas. Validará tipo, nombres y longitud antes de convertirla en cola; un resultado inválido o una excepción del LLM se sustituirá por reglas Python. La cola permite que el mismo rol aparezca más de una vez, pero no permite que un nombre no admitido llegue a una arista del grafo.

Las reglas deterministas detectarán combinaciones y las ordenarán como rag, horarios, auxiliar, rutas y tarifas. Distinguirán una pregunta de hora actual de un horario de transporte. Una petición documental más hora actual producirá rag seguido de auxiliar. Una petición de total sobre una imagen es una dependencia específica: se ejecutará tarifas y después auxiliar para poder calcular a partir de los importes ya extraídos; esta dependencia concreta prevalece sobre el orden general porque cumple RF-46 y preserva el orden imagen → calculadora de la Spec 002. Si no se reconoce ningún ámbito, se terminará con una petición de reformulación que enumere rutas, corpus CRTM, hora, cálculos e imágenes.

Las allowlists previstas en config.py serán:

| Especialista | Tools directas permitidas |
|---|---|
| rag | rag_ask |
| horarios | hora_actual, rag_ask |
| auxiliar | hora_actual, calculadora |
| rutas | planificar_ruta |
| tarifas | describir_imagen |

Por tanto, nodo_horarios conserva su excepción explícita para consultar el RAG. nodo_rutas solo invoca la tool exterior planificar_ruta; sus consultas internas existentes a rag_ask para zona y precio no se reemplazarán ni duplicarán. En la traza del grafo se contabilizará esa invocación exterior de rutas como una tool. Su resultado, fuentes, abstenciones y errores internos se conservarán en las notas y la síntesis.

MAX_TURNOS_CONVERSACION contará un mensaje válido de la persona y la respuesta que produce el sistema como un turno. El contador aumentará al producir la respuesta de un mensaje, también si esta deja un plan pendiente; una aprobación o rechazo que reanuda ese mismo plan no abre otro turno. Al recibir el mensaje siguiente después de alcanzar el máximo, el grafo ejecutará solo un terminal de resumen, sin supervisor, especialistas ni tools, avisará del límite y dejará done en verdadero.

MAX_CICLOS_TOOLS será un presupuesto transversal de invocaciones directas autorizadas por ese turno lógico. Un ejecutor decorado, compartido por todos los nodos, comprobará el presupuesto antes de llamar al ejecutor global y aumentará el contador únicamente cuando se ejecute la tool. El contador se conserva a través de la interrupción HITL, de modo que rechazar una ruta no permite eludir el límite. Cuando se alcance el máximo, no se fabricará una llamada de tool adicional: el grafo conservará lo obtenido, sintetizará un resumen con aviso y fijará done en verdadero. Las llamadas internas opacas de planificar_ruta se mantienen atómicas y no se contarán por separado.

## Lógica clave

    procesar_turno(estado, mensaje, thread_id):
        validar thread_id, estado y mensaje
        snapshot = recuperar por configurable.thread_id
        si snapshot tiene hitl_pendiente:
            devolver su proyección con aviso; no invocar el grafo
        si ya alcanzó MAX_TURNOS_CONVERSACION:
            invocar solo el terminal de límite y proyectar su estado
        iniciar el turno, reiniciar contador de tools de salida
        invocar el StateGraph con configurable.thread_id
        devolver la proyección de sus seis campos públicos

    StateGraph para un mensaje válido:
        entrada -> supervisor
        supervisor -> siguiente especialista de la cola -> supervisor
        cuando no quedan roles:
            si hay resultados de rutas estado=ok con origen, destino y ruta:
                crear planes con ID, sintetizar, done=falso, hitl_pendiente=verdadero
                pausar con interrupt después de persistir el estado
            si no:
                sintetizar o usar su respaldo, done=verdadero

    aprobar_plan(estado, thread_id, aprobado):
        validar entrada y recuperar el snapshot
        comprobar que hay plan pendiente e identificar plan_id_seleccionado
        reanudar el mismo grafo con Command e interrupt
        si aprobado:
            aceptar solo el plan seleccionado, cerrar los demás pendientes,
            sintetizar el resultado aceptado y fijar done=verdadero
        si rechazado:
            descartar solo el plan seleccionado, reutilizar sus argumentos guardados,
            volver a nodo_rutas y mantener done=falso
        proyectar el estado que haya decidido el grafo

    ejecución de un especialista:
        verificar allowlist y presupuesto transversal
        ejecutar tool mediante el ejecutor común
        añadir exactamente tool, args, status y preview a la traza
        conservar respuestas, abstenciones y errores como notas
        si se alcanza un límite, pasar al terminal de resumen

El normalizador de rutas tratará como plan únicamente un resultado de planificar_ruta que pueda interpretarse como objeto o JSON con estado igual a ok y una ruta no vacía. No inferirá éxito desde status de la traza: la implementación heredada puede marcar como ok una cadena cuyo contenido informe error_interno. Los estados de datos faltantes, ambigüedad, fuera de cobertura, sin ruta o error se sintetizarán como aclaración o limitación normal, sin llamar a interrupt.

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Usar un StateGraph compilado con InMemorySaver por defecto e inyectable en pruebas. | Bucle Python propio o estado enviado entero por el cliente. | LangGraph y el checkpointer por thread_id son requisitos; el snapshot preserva la conversación y evita confiar en datos manipulables por el cliente. |
| Mantener una fachada mínima en src/agent.py y un factory perezoso del grafo. | Acoplar el grafo a CLI, Streamlit o a la inicialización de Gemini. | Cumple el contrato único para futuros clientes y permite importar y probar sin claves ni costes. |
| Validar una cola finita de roles del supervisor y consumirla nodo a nodo. | Confiar en texto libre del LLM o permitir aristas dinámicas. | Permite encadenar y repetir especialistas, pero impide roles fuera de allowlist y ciclos no acotados. |
| Ampliar las reglas Python sin retirar elegir_rol_por_palabras. | Reemplazar el fallback heredado por clasificación LLM. | Preserva compatibilidad de horarios y ofrece un fallback determinista incluso ante fallo del modelo. |
| Configurar tarifas con solo describir_imagen y delegar calculadora en auxiliar. | Mantener calculadora en tarifas o ejecutar la calculadora dos veces. | Da a cada especialista la responsabilidad definida por la Spec 005 y conserva el flujo observable de la Spec 002: primero imagen, después cálculo, sin estimaciones. |
| Usar interrupt y Command para HITL después de guardar ruta, planes y respuesta. | Pausar antes de ejecutar planificar_ruta o simular la pausa con una bandera sin LangGraph. | Las tools se ejecutan antes de la aprobación, el checkpointer conserva el punto exacto de reanudación y done sigue siendo decisión del grafo. |
| Identificar el plan elegido con estado["plan_id_seleccionado"]. | Añadir un cuarto parámetro a aprobar_plan o aprobar todos los planes. | Respeta la firma aprobada y permite aplicar o rechazar únicamente el plan indicado. |
| Contar una llamada exterior a planificar_ruta como una tool del grafo. | Contar también sus consultas RAG internas o repetirlas desde nodo_rag. | Conserva el contrato y coste internos de la tool de rutas, evita duplicar RAG y mantiene un límite comprobable en la orquestación. |
| Sintetizador con salida anclada y renderizado determinista de respaldo. | Devolver siempre la salida libre de un LLM o perder toda la respuesta si falla. | Evita inventar datos, informa resultados parciales y cumple la degradación controlada exigida. |
| Añadir LangGraph con rango de versión compatible en requirements.txt. | Depender de una instalación transitiva o escribir un checkpointer manual. | Hace reproducible una instalación limpia y usa el componente requerido por la spec. |

## Estrategia de tests

Todos los tests usarán un LLM falso con respuestas estructuradas, un sintetizador falso que puede fallar de forma controlada, un ejecutor de tools falso con contador y respuestas prefijadas, y un InMemorySaver nuevo por prueba. La protección de red existente seguirá activa; no se importará ni invocará el RAG real, Gemini, Google Routes, Nominatim, ChromaDB ni la tool de visión.

| Área | Comprobaciones |
|---|---|
| Supervisor y fallback | Un supervisor válido encadena y repite roles; excepciones, JSON inválido y roles prohibidos activan reglas Python. Se cubren rutas, horarios, hora/cálculo, imágenes, RAG, orden exacto, combinación RAG+hora y reformulación con alcance. |
| Especialistas y herramientas | Cada nodo solo acepta su allowlist; rag conserva evidencia o abstención; horarios usa su excepción hora_actual+rag_ask; rutas usa solo planificar_ruta; tarifas extrae importes; auxiliar calcula después de la imagen. Las tools bloqueadas no se ejecutan y cada ejecución real deja los cuatro campos de traza. |
| Rutas y RAG interno | Un doble devuelve JSON de ruta correcta, aclaración, ambigüedad y error_interno. Solo estado=ok con ruta crea plan; las otras respuestas no interrumpen. Se comprueba que el grafo no añade una llamada nodo_rag para suplir las consultas internas de rutas. |
| Contrato y entradas | Las dos funciones devuelven exactamente las seis claves y los tipos exigidos. thread_id, estado y mensaje inválidos no construyen ejecución ni aumentan contadores; una aprobación sin plan, sin hilo o sin selector no altera el snapshot. |
| HITL | Una ruta válida persiste planes con ID y pausa; la aprobación del ID seleccionado termina con done verdadero. El rechazo elimina solo el seleccionado, reutiliza sus argumentos y vuelve a invocar la tool mediante un doble secuencial. Un mensaje nuevo durante la pausa no llama a ningún nodo ni tool. |
| Persistencia | Dos llamadas con el mismo thread_id recuperan historial y datos de ruta; dos IDs no comparten planes, traza ni contexto. Un estado vacío usa el checkpoint cuando existe y crea uno vacío cuando no existe. |
| Límites | Se simulan topes pequeños por monkeypatch: el límite de turno ejecuta solo el resumen; el de tools es común a varios especialistas, no permite una llamada adicional y se conserva tras rechazo. Los mensajes vacíos, avisos de plan pendiente y controles fallidos no cuentan. |
| Síntesis | La síntesis usa solo notas disponibles, declara información parcial y conserva errores o abstenciones. Si falla el modelo, el renderizado de respaldo incluye el aviso y los resultados de los especialistas. |
| Regresión | Se actualizarán los tests de allowlist y del flujo imagen-cálculo al reparto nuevo de responsabilidades; se mantendrán verdes los tests heredados de reloj, calculadora, tools, RAG de rutas y fallback de horarios. |

No hay un RF que requiera validación manual para esta fase. La comprobación con proveedores reales queda fuera de los tests por coste y se podrá hacer más adelante desde los futuros clientes, sin formar parte de esta implementación.

## Riesgos

- planificar_ruta solicita una única alternativa de Google Routes. El rechazo garantiza una nueva invocación y un nuevo ID de propuesta, pero no puede garantizar que el proveedor devuelva un itinerario materialmente distinto sin ampliar la Spec 004.
- InMemorySaver mantiene conversaciones durante la vida del proceso, no tras un reinicio. La spec exige un checkpointer, no una base persistente; una futura necesidad de durabilidad requerirá una spec adicional.
- Las consultas RAG internas de planificar_ruta no se emiten mediante el ejecutor del grafo. Se preservarán como comportamiento atómico y sus resultados seguirán visibles en la respuesta, pero no se desglosarán como llamadas nuevas de traza ni de presupuesto.
- Repartir imagen y cálculo entre dos nodos cambia la prueba unitaria actual de tarifas. Se conservará el comportamiento de usuario y la traza secuencial exigidos por la Spec 002 mediante una prueba de integración del grafo.
- Un LLM puede entregar una estructura inesperada o una síntesis poco fiable. La validación Python, las allowlists, los resultados normalizados y el respaldo determinista evitarán que eso active roles indebidos, invente un resultado final o deje la conversación sin respuesta.
- El límite transversal debe interceptar todas las rutas que pasan por ejecutar_tool. Los tests de contador con cadenas de especialistas y replanificación protegerán frente a bypasses.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 a RF-5 | StateGraph, cola validada, nodos y sintetizador | tests/test_supervisor_grafo.py y tests/test_grafo_persistencia.py |
| RF-6 | Validación de LLM y fallback Python | tests/test_supervisor_grafo.py::test_fallo_o_decision_invalida_usa_fallback |
| RF-7 a RF-11 | Reglas de intención y reformulación | tests/test_supervisor_grafo.py::test_fallback_por_intencion_y_reformulacion |
| RF-42 y RF-57 | Orden determinista y detección de imagen | tests/test_supervisor_grafo.py::test_orden_y_tarifas_del_fallback |
| RF-12 y RF-34 | Nodo de rutas, normalizador y ausencia de HITL en aclaraciones | tests/test_agentes_grafo.py y tests/test_grafo_hitl.py::test_aclaracion_de_ruta_no_pausa |
| RF-13 a RF-16 | Nodos auxiliar, tarifas y RAG | tests/test_agentes_grafo.py::test_tools_por_especialista |
| RF-17 a RF-19 | Preservación de resultados, errores y traza | tests/test_agentes_grafo.py::test_traza_y_error_controlado |
| RF-20 a RF-22 | Síntesis sencilla, anclada y parcial | tests/test_sintetizador.py |
| RF-23 a RF-28 | Fachada pública, proyección y propiedad de done | tests/test_agent_contrato.py |
| RF-29 a RF-33 | Planes persistidos, interrupt, aprobación y rechazo | tests/test_grafo_hitl.py |
| RF-35 a RF-37 y RF-53 | Checkpointer, recuperación y aislamiento | tests/test_grafo_persistencia.py |
| RF-38 a RF-41 | Configuración, contador de turnos y terminal de resumen | tests/test_grafo_limites.py::test_limite_de_turnos |
| RF-43 a RF-46 | Allowlists, excepción de secuencia documental/hora e imagen/cálculo | tests/test_agentes_grafo.py y tests/test_flujo_imagen_calculo.py |
| RF-44, RF-58 y RF-59 | Restricción de RAG directo y excepciones de horarios/rutas | tests/test_agentes_grafo.py::test_excepciones_rag_directo_e_interno |
| RF-47 | Selector plan_id_seleccionado y actuación sobre un único plan | tests/test_grafo_hitl.py::test_selecciona_un_plan_concreto |
| RF-48 y RF-49 | Guardia de plan pendiente sin ejecución | tests/test_grafo_hitl.py::test_mensaje_con_plan_pendiente_no_ejecuta_nodos |
| RF-50 | Presupuesto transversal de tools y resumen | tests/test_grafo_limites.py::test_limite_global_de_tools |
| RF-51 a RF-55 | Validación de aprobación, thread_id, estado y mensaje | tests/test_agent_contrato.py::test_entradas_controladas_no_mutan_ni_ejecutan |
| RF-56 | Respaldo del sintetizador | tests/test_sintetizador.py::test_fallo_devuelve_informacion_obtenida |

La siguiente fase será descomponer este plan en tareas, una por una, solo tras tu aprobación.
