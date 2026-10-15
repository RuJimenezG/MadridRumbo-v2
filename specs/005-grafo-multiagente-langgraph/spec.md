# Spec 005 — Grafo multiagente con LangGraph

> Estado: Aprobada · Fecha: 2026-10-15

## Contexto y objetivo

MadridRumbo ya dispone de un RAG y de herramientas especializadas para rutas, información temporal, cálculos e imágenes, pero aún no tiene una conversación única que decida qué capacidades necesita cada consulta, conserve el contexto y permita aprobar los planes antes de aplicarlos. Esta funcionalidad crea una orquestación multiagente que dirige cada petición a uno o varios especialistas, reúne sus resultados en una respuesta clara y mantiene la conversación identificada por `thread_id`. Así, CLI y Streamlit podrán consumir posteriormente el mismo contrato de conversación.

## Usuarios / actores

- Persona usuaria que consulta información de transporte de Madrid mediante un futuro cliente CLI o Streamlit.
- Supervisor que decide qué rol o roles atienden cada consulta y cuándo finaliza el flujo.
- Especialistas de rutas, herramientas auxiliares y contenido multimodal.
- RAG de MadridRumbo, que aporta respuestas documentales ancladas al corpus CRTM.
- Persona que aprueba o rechaza un plan antes de que el sistema lo aplique.

## Historias de usuario

- H1: Como usuaria quiero hacer una consulta en lenguaje natural para que el sistema la dirija a la capacidad adecuada.
- H2: Como usuaria quiero recibir una respuesta sencilla que integre los resultados de todos los especialistas necesarios.
- H3: Como usuaria quiero revisar y aprobar un plan antes de que se aplique para conservar el control de la conversación.
- H4: Como usuaria quiero continuar una conversación con el mismo identificador para que el sistema conserve su contexto.
- H5: Como equipo quiero límites configurables para evitar conversaciones o ciclos de tools sin fin.
- H6: Como equipo quiero una traza de las tools usadas para poder revisar qué información produjo la respuesta.

## Requisitos funcionales (criterios de aceptación en EARS)

### Grafo y orquestación

- RF-1: EL SISTEMA proporciona un grafo LangGraph con los nodos Supervisor, `nodo_rag`, `nodo_horarios`, `nodo_rutas`, `nodo_auxiliar`, `nodo_tarifas` y Sintetizador.
- RF-2: CUANDO recibe una consulta, EL SISTEMA permite al Supervisor elegir el siguiente rol entre RAG, horarios, rutas, auxiliar, tarifas y finalización.
- RF-3: CUANDO una consulta necesita capacidades de más de un especialista, EL SISTEMA encadena los especialistas necesarios en el mismo turno antes de sintetizar el resultado y puede repetir un mismo rol.
- RF-4: EL SISTEMA no deriva una consulta a un rol distinto de los roles admitidos por el grafo.
- RF-5: CUANDO el Supervisor finaliza la derivación, EL SISTEMA envía al Sintetizador los resultados disponibles de los especialistas ejecutados.
- RF-6: SI el modelo del Supervisor falla o devuelve una decisión no interpretable, ENTONCES EL SISTEMA usa una decisión determinista para elegir un rol o solicitar una reformulación.
- RF-7: CUANDO el fallback determinista reconoce una consulta de rutas, EL SISTEMA la deriva a rutas.
- RF-8: CUANDO el fallback determinista reconoce una consulta sobre horarios de transporte, EL SISTEMA la deriva a horarios.
- RF-9: CUANDO el fallback determinista reconoce una consulta sobre hora actual o cálculo, EL SISTEMA la deriva a auxiliar.
- RF-57: CUANDO el fallback determinista reconoce una consulta sobre una imagen, EL SISTEMA la deriva a tarifas.
- RF-10: CUANDO el fallback determinista reconoce una consulta documental sobre transporte público de Madrid, EL SISTEMA la deriva a `nodo_rag`.
- RF-11: SI el fallback determinista no puede clasificar la consulta, ENTONCES EL SISTEMA pide que se reformule e indica el alcance de rutas, información del corpus CRTM, hora, cálculos e imágenes.
- RF-42: CUANDO el fallback determinista encadena varios roles, EL SISTEMA los ejecuta en el orden RAG, horarios, auxiliar, rutas y tarifas.

### Especialistas y RAG

- RF-12: CUANDO `nodo_rutas` atiende una consulta de viaje, EL SISTEMA usa la tool `planificar_ruta` antes de presentar un plan para su aprobación.
- RF-13: CUANDO `nodo_auxiliar` necesita conocer el momento actual, EL SISTEMA usa la tool `hora_actual`.
- RF-14: CUANDO `nodo_auxiliar` necesita resolver una expresión aritmética, EL SISTEMA usa la tool `calculadora`.
- RF-15: CUANDO `nodo_tarifas` atiende una consulta sobre una imagen, EL SISTEMA usa la tool `describir_imagen`.
- RF-16: CUANDO `nodo_rag` atiende una consulta documental, EL SISTEMA usa la tool del RAG para responder con evidencia del corpus CRTM.
- RF-17: EL SISTEMA conserva los mensajes de error, abstención y procedencia que devuelvan las tools y el RAG.
- RF-18: CUANDO una tool se invoca, EL SISTEMA añade a la traza una entrada con `tool`, `args`, `status` y `preview`.
- RF-19: SI una tool o un especialista no puede completar su trabajo, ENTONCES EL SISTEMA conserva su resultado controlado en la traza y permite al Sintetizador informar de la limitación.
- RF-43: EL SISTEMA permite a `nodo_auxiliar` invocar únicamente las tools `hora_actual` y `calculadora`.
- RF-44: EL SISTEMA reserva la invocación directa de la tool del RAG para `nodo_rag`.
- RF-45: CUANDO una consulta necesita evidencia documental y la hora actual, EL SISTEMA encadena `nodo_rag` y `nodo_auxiliar` en ese orden.
- RF-46: DONDE una consulta solicita calcular un total a partir de importes visibles en una imagen, EL SISTEMA encadena `nodo_tarifas` y `nodo_auxiliar`.
- RF-58: EL SISTEMA permite a `nodo_horarios` invocar únicamente las tools `hora_actual` y `rag_ask`.
- RF-59: EL SISTEMA conserva las consultas internas al RAG de `nodo_horarios` y de `planificar_ruta`.

### Síntesis y resultado público

- RF-20: CUANDO hay resultados de uno o varios especialistas, EL SISTEMA devuelve una respuesta sintetizada en español y en lenguaje sencillo.
- RF-21: EL SISTEMA no inventa datos que no estén presentes en los resultados de los especialistas o del RAG.
- RF-22: CUANDO solo se obtiene parte de la información solicitada, EL SISTEMA indica qué parte está disponible y qué parte no pudo obtener.
- RF-23: EL SISTEMA expone en `src/agent.py` `procesar_turno(estado, mensaje, thread_id) -> dict` para procesar un mensaje de conversación.
- RF-24: EL SISTEMA expone en `src/agent.py` `aprobar_plan(estado, thread_id, aprobado: bool) -> dict` para resolver una aprobación humana pendiente.
- RF-25: CUANDO se invoca cualquiera de las dos operaciones públicas, EL SISTEMA devuelve un diccionario con las claves `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done`.
- RF-26: EL SISTEMA devuelve `plan` como lista, `log` como lista, `traza` como lista, `hitl_pendiente` como booleano y `done` como booleano.
- RF-27: EL SISTEMA devuelve cada entrada de `traza` con las claves `tool`, `args`, `status` y `preview`.
- RF-28: EL SISTEMA deja la decisión de `done` exclusivamente en el grafo.

### Aprobación humana de planes

- RF-29: CUANDO una persona solicita una ruta entre un punto de origen y un punto de destino y `nodo_rutas` genera uno o varios planes, EL SISTEMA marca `hitl_pendiente` como verdadero, devuelve los planes para su revisión y no los aplica todavía.
- RF-30: MIENTRAS `hitl_pendiente` sea verdadero, EL SISTEMA mantiene `done` como falso.
- RF-31: CUANDO se aprueba un plan de ruta pendiente, EL SISTEMA lo considera correcto, devuelve su resultado y marca `done` como verdadero.
- RF-32: CUANDO se rechaza un plan de ruta pendiente, EL SISTEMA lo descarta, vuelve a invocar `planificar_ruta` para proponer una ruta diferente y mantiene `done` como falso.
- RF-33: CUANDO se rechaza un plan, EL SISTEMA conserva la conversación para que pueda continuar en el mismo `thread_id`.
- RF-34: EL SISTEMA no usa HITL para las peticiones de aclaración conversacional que devuelvan las tools de rutas.
- RF-47: CUANDO hay varios planes de ruta pendientes, EL SISTEMA identifica cada plan y aplica o rechaza únicamente el plan indicado en el estado recibido por `aprobar_plan`.
- RF-48: MIENTRAS exista un plan pendiente en una conversación, SI `procesar_turno` recibe un mensaje nuevo con el mismo `thread_id`, ENTONCES EL SISTEMA devuelve un aviso de que hay un plan pendiente y conserva `hitl_pendiente` como verdadero y `done` como falso.
- RF-49: MIENTRAS exista un plan pendiente en una conversación, EL SISTEMA no ejecuta Supervisor, Sintetizador, especialistas ni tools al recibir un mensaje nuevo con el mismo `thread_id`.

### Persistencia y límites

- RF-35: EL SISTEMA conserva el estado de cada conversación mediante un checkpointer identificado por `thread_id`.
- RF-36: CUANDO se procesa un nuevo mensaje con un `thread_id` existente, EL SISTEMA recupera el contexto de esa conversación.
- RF-37: CUANDO se procesa un mensaje con un `thread_id` nuevo, EL SISTEMA inicia una conversación independiente.
- RF-38: EL SISTEMA permite configurar en `config.py` el número máximo de turnos de cada conversación.
- RF-39: EL SISTEMA permite configurar en `config.py` el número máximo de invocaciones individuales de tools autorizadas por procesamiento de turno.
- RF-40: EL SISTEMA contabiliza cada par formado por un mensaje de la persona usuaria y una respuesta del sistema como un turno de conversación.
- RF-41: SI una conversación ya ha completado su número máximo de turnos al recibir un nuevo mensaje, ENTONCES EL SISTEMA deja de ejecutar nuevos especialistas o tools, devuelve un resumen de lo obtenido, avisa de que se alcanzó el límite y marca `done` como verdadero.
- RF-50: SI un procesamiento alcanza su número máximo de invocaciones individuales de tools autorizadas, ENTONCES EL SISTEMA deja de ejecutar nuevas tools, devuelve un resumen de lo obtenido, avisa de que se alcanzó el límite y marca `done` como verdadero.
- RF-51: SI `aprobar_plan` se invoca sin un plan pendiente o con un `thread_id` inexistente, ENTONCES EL SISTEMA informa de que no existe un plan pendiente y no modifica la conversación persistida.
- RF-52: SI `thread_id` está vacío, ENTONCES EL SISTEMA devuelve un mensaje de error controlado y no ejecuta el grafo ni una tool.
- RF-53: CUANDO `estado` está vacío y `thread_id` es válido, EL SISTEMA recupera el estado persistido de la conversación o inicia un estado vacío si el identificador no tiene historial.
- RF-54: SI `estado` no es un diccionario, ENTONCES EL SISTEMA devuelve un mensaje de error controlado y no ejecuta el grafo ni una tool.
- RF-55: SI `mensaje` está vacío o contiene solo espacios, ENTONCES EL SISTEMA pide una consulta válida, no ejecuta el grafo ni una tool y no lo contabiliza como turno.
- RF-56: SI el Sintetizador falla, ENTONCES EL SISTEMA informa del fallo y devuelve la información obtenida de los demás especialistas.

## Requisitos no funcionales

- Arquitectura: LangGraph gestiona el flujo y el estado persistente; el contrato público queda preparado para clientes CLI y Streamlit sin acoplarse a una interfaz concreta.
- Seguridad: solo se ejecutan las tools autorizadas para cada especialista y ninguna llamada de tool queda fuera de la traza.
- Coste: los tests de esta funcionalidad no llaman a LLM, APIs externas, embeddings ni ChromaDB reales; usan dobles de prueba.
- Configuración: los límites de turnos y de ciclos de tools se centralizan en `config.py`.
- Idioma: los mensajes visibles, los planes y las síntesis se presentan en español.
- Robustez: los fallos del Supervisor, de especialistas y de tools producen resultados controlados sin exponer detalles internos.

## Casos límite

- El LLM del Supervisor falla o responde con un rol inválido: RF-6 y RF-42.
- El fallback no reconoce la consulta: RF-11.
- Una consulta requiere rutas y cálculo, o cualquier otra combinación de especialistas: RF-3 y RF-42.
- La consulta solo puede responderse con el corpus CRTM: RF-16.
- Una consulta combina evidencia documental y hora actual: RF-45.
- Una consulta pide calcular un total a partir de una imagen: RF-46.
- Una consulta pide horarios de transporte: RF-8 y RF-58.
- Una tool falla o queda bloqueada: RF-18 y RF-19.
- Una ruta genera uno o varios planes: RF-29, RF-30 y RF-47.
- La persona rechaza un plan: RF-32 y RF-33.
- Llega un mensaje mientras hay un plan pendiente: RF-48 y RF-49.
- Una tool de rutas pide aclarar origen, destino u otro dato: RF-34.
- Dos conversaciones usan identificadores distintos: RF-35 a RF-37.
- Se invoca una aprobación sin plan pendiente, con identificador vacío, estado inválido o mensaje vacío: RF-51 a RF-55.
- Falla el Sintetizador: RF-56.
- Se alcanza el máximo de turnos: RF-40 y RF-41.
- Se alcanza el máximo de invocaciones de tools: RF-39 y RF-50.

## Fuera de alcance

- Construir los clientes CLI y Streamlit que consumirán este contrato.
- Cambiar el contrato o la lógica interna del RAG, `planificar_ruta`, `hora_actual`, `calculadora` o `describir_imagen` definidos en sus specs.
- Añadir nuevas APIs externas, nuevas modalidades o nuevas tools.
- Diseñar la interfaz visual con la que la persona revisará un plan pendiente.
- Gestionar autenticación de usuarios o compartir una conversación entre personas distintas.
- Ejecutar acciones externas no cubiertas por las tools autorizadas.

## Criterios de finalización

- Todos los RF tienen tests automatizados en verde con `pytest` y dobles para LLM, checkpointer, especialistas, RAG y tools.
- Una prueba demuestra que el Supervisor puede encadenar al menos dos especialistas en un turno.
- Una prueba demuestra el fallback determinista para cada rol admitido y para una consulta no clasificable.
- Una prueba demuestra que una ruta genera uno o varios planes, se aprueba un plan seleccionado y finaliza, y se rechaza un plan sin perder el contexto del mismo `thread_id`.
- Una prueba demuestra el aislamiento entre dos `thread_id` distintos.
- Una prueba demuestra que cada límite configurado devuelve el resumen disponible y su aviso correspondiente sin ejecutar más especialistas o tools.
- Una prueba demuestra que un mensaje nuevo no ejecuta el grafo mientras haya un plan pendiente.
- Una prueba demuestra el comportamiento controlado de una aprobación sin plan, entradas vacías o inválidas y un fallo del Sintetizador.

## Dudas abiertas

Ninguna.
