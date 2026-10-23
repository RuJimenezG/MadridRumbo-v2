# Spec 011 — Depuración pública del grafo

> Estado: **Aprobada** · Fecha: 2026-10-22
> Sustituye expresamente la ocultación de diagnósticos del Supervisor **solo en el panel de depuración** de Streamlit de las specs 006, 007 y 008. El chat y su desplegable «Pasos seguidos» mantienen el filtro vigente. No modifica las seis claves de primer nivel del contrato público definido en la spec 005.

## Contexto y objetivo

El contrato público del grafo ya contiene un campo `log`, pero actualmente solo ofrece textos aislados y los clientes no pueden reconstruir de forma fiable qué nodos se ejecutaron ni qué información recibieron y devolvieron. Esto dificulta diagnosticar una ejecución del grafo, especialmente cuando intervienen varios especialistas, una pausa HITL o un fallback del Supervisor.

Esta funcionalidad convierte `log` en un registro público, estructurado y cronológico de cada llamada al grafo. La CLI y el panel de depuración de Streamlit podrán mostrarlo completo al terminar la llamada, para que el equipo de desarrollo pueda seguir los nodos ejecutados y el estado que circula entre ellos, sin exponer secretos ni contenido sensible.

## Usuarios / actores

- Equipo de desarrollo que depura ejecuciones del grafo multiagente.
- Cliente CLI que presenta el resultado y el registro de una llamada pública.
- Panel de depuración de Streamlit que presenta el mismo registro completo.
- Supervisor, especialistas, sintetizador y nodos de control del grafo que producen los pasos observables.

## Historias de usuario

- H1: Como desarrolladora quiero ver, en orden, los nodos ejecutados para saber el recorrido seguido por una consulta.
- H2: Como desarrolladora quiero consultar el estado de entrada y salida de cada nodo para entender qué información se transmitió entre ellos.
- H3: Como desarrolladora quiero revisar el mismo registro desde CLI y Streamlit para depurar sin depender de una interfaz concreta.
- H4: Como equipo quiero que el registro de depuración no revele secretos ni contenido sensible.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-1: EL SISTEMA conserva las seis claves de primer nivel `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done` en el resultado de cada operación pública del grafo.
- RF-2: EL SISTEMA devuelve `log` como una lista ordenada de entradas estructuradas de depuración pertenecientes exclusivamente a la llamada pública que acaba de terminar.
- RF-3: EL SISTEMA incluye en cada entrada de `log` los campos `paso`, `tipo`, `nodo`, `entrada`, `salida`, `resultado` y `detalle`.
- RF-4: EL SISTEMA limita `tipo` a `nodo`, `tool` o `control`, y limita `resultado` a `completado`, `fallido` o `rechazado`.
- RF-5: CUANDO se ejecuta un nodo de LangGraph, EL SISTEMA añade a `log` una entrada con `tipo` igual a `nodo`, cuyo `paso` es un entero consecutivo desde 1 y cuyo `nodo` identifica el nodo ejecutado.
- RF-6: CUANDO se invoca una tool, EL SISTEMA añade a `log` una entrada con `tipo` igual a `tool`, cuyo `paso` conserva la secuencia cronológica y cuyo `nodo` identifica la tool invocada.
- RF-7: CUANDO se ejecuta un nodo de LangGraph, EL SISTEMA registra en `entrada` una instantánea completa y saneada del estado inmediatamente anterior a la ejecución del nodo.
- RF-8: CUANDO termina un nodo de LangGraph, EL SISTEMA registra en `salida` una instantánea completa y saneada del estado combinado tras aplicar la actualización del nodo y los reducers correspondientes.
- RF-9: CUANDO se invoca una tool, EL SISTEMA registra en `entrada` sus argumentos saneados y en `salida` su resultado saneado.
- RF-10: CUANDO un nodo o una tool termina correctamente, EL SISTEMA registra `resultado` con el valor `completado` y `detalle` igual a `null`.
- RF-11: SI un nodo o una tool falla o no puede completar su trabajo, ENTONCES EL SISTEMA conserva en `log` los pasos anteriores, añade la entrada de ese paso con `resultado` igual a `fallido`, `salida` igual a `null` si no existe salida y `detalle` con la categoría y el resumen seguro del fallo disponibles.
- RF-12: SI una llamada pública se rechaza antes de ejecutar el grafo por una entrada no válida, un plan pendiente, la ausencia de un plan pendiente o una selección de plan inválida, ENTONCES EL SISTEMA devuelve en `log` una sola entrada con `paso` igual a 1, `tipo` igual a `control`, `nodo` igual a `fachada`, `entrada` y `salida` iguales a `null`, `resultado` igual a `rechazado` y `detalle` con el motivo controlado.
- RF-13: CUANDO una llamada pública pausa el flujo para HITL, EL SISTEMA devuelve los pasos ejecutados hasta la pausa en el `log` de esa llamada.
- RF-14: CUANDO se reanuda un flujo mediante una operación pública de aprobación o rechazo, EL SISTEMA inicia un nuevo `log` para esa llamada y no mezcla en él los pasos de llamadas anteriores.
- RF-15: EL SISTEMA no persiste `log` como historial de conversación ni como parte del estado recuperable por `thread_id`.
- RF-16: EL SISTEMA conserva en las instantáneas de `entrada` y `salida` todos los campos de estado disponibles salvo los valores que deban sanearse por seguridad o limitarse por tamaño.
- RF-17: SI una instantánea contiene un valor de un campo de credencial o contraseña, ENTONCES EL SISTEMA sustituye su contenido por una indicación de que fue ocultado por seguridad.
- RF-18: EL SISTEMA considera campos de credencial o contraseña los que se llamen `api_key`, `token`, `secret`, `password`, `authorization`, `cookie` o `credentials`, sin distinguir mayúsculas y minúsculas.
- RF-19: SI una instantánea contiene un prompt completo o un cuerpo completo de respuesta externa, ENTONCES EL SISTEMA sustituye su contenido por una indicación de que fue ocultado por seguridad.
- RF-20: SI la representación JSON segura de un valor no saneado supera 10.000 caracteres, ENTONCES EL SISTEMA la sustituye por un resumen que identifica el campo y comunica que se omitió por longitud.
- RF-21: SI un valor de estado no es texto, número, booleano, `null`, lista o diccionario, ENTONCES EL SISTEMA lo representa mediante su tipo y un resumen seguro, sin usar su representación cruda.
- RF-22: EL SISTEMA no incluye en `log` claves API, tokens, contraseñas, cabeceras de autorización, prompts completos ni cuerpos completos de respuestas externas.
- RF-23: CUANDO la CLI presenta el resultado de una llamada pública, EL SISTEMA muestra todas las entradas estructuradas de `log` en su orden, incluidos los diagnósticos del Supervisor.
- RF-24: CUANDO Streamlit presenta su panel de depuración, EL SISTEMA muestra todas las entradas estructuradas de `log` en su orden, incluidos los diagnósticos del Supervisor.
- RF-25: CUANDO Streamlit presenta el chat o su desplegable «Pasos seguidos», EL SISTEMA mantiene ocultos los diagnósticos técnicos del Supervisor.
- RF-26: EL SISTEMA no elimina ni modifica la estructura de las entradas de `traza` de tools (`tool`, `args`, `status` y `preview`).
- RF-27: EL SISTEMA devuelve el `log` completo solo al finalizar `procesar_turno` o `aprobar_plan` y no emite eventos parciales a CLI ni a Streamlit durante la ejecución.

## Requisitos no funcionales

- Seguridad: el registro no revela los valores definidos como sensibles en RF-17 a RF-22, incluso si aparecen en el estado de un nodo, en una tool o en un error.
- Compatibilidad: se mantienen las seis claves de primer nivel y los tipos de `plan`, `traza`, `hitl_pendiente` y `done` del contrato público actual; `log` cambia de una lista de textos a una lista de entradas estructuradas definida por RF-3 y RF-4.
- Coste: las pruebas automatizadas no llaman a LLM, APIs externas, embeddings ni ChromaDB reales; usan dobles de prueba.
- Rendimiento: cada valor individual representado en una instantánea queda limitado según RF-20.
- Idioma: los nombres de campos públicos del registro y los resúmenes de error se presentan en español, salvo identificadores de nodos o tools ya existentes.
- Configuración: el límite de longitud de RF-15 se define en un único punto de configuración.

## Casos límite

- Consulta rechazada por `thread_id`, estado o mensaje inválidos: una entrada de control sin ejecución del grafo (RF-12).
- Mensaje bloqueado mientras hay un plan pendiente, aprobación sin plan y selección de plan inválida: una entrada de control que explica el rechazo (RF-12).
- Consulta que ejecuta varios especialistas y tools: una entrada consecutiva por cada nodo y tool ejecutados (RF-2, RF-5 a RF-10).
- Pausa HITL y posterior aprobación o rechazo: registros separados por llamada, sin mezclar sus pasos (RF-13 y RF-14).
- Error controlado de nodo, herramienta o proveedor: pasos anteriores conservados, salida `null` si no existe y fallo categorizado sin datos sensibles (RF-11 y RF-17 a RF-22).
- Estado que contiene credenciales o una respuesta externa extensa: valor ocultado o resumido de forma identificable (RF-17 a RF-22).
- Valor no JSON, como una excepción o fecha: tipo y resumen seguro, sin representación cruda (RF-21).
- Un valor exactamente de 10.000 caracteres JSON seguros: se conserva; uno de 10.001 se resume (RF-20).
- Diagnóstico de fallback del Supervisor: se ve en CLI y en el panel de depuración de Streamlit, pero no en el chat ni en «Pasos seguidos» (RF-23 a RF-25).

## Fuera de alcance

- Emitir eventos en tiempo real, streaming del grafo o actualizaciones de la interfaz antes de que termine una llamada pública.
- Persistir historiales de depuración entre llamadas, reinicios del proceso o conversaciones.
- Cambiar la lógica de decisión del Supervisor, de los especialistas, del sintetizador, de HITL o de las tools.
- Modificar el contrato estructural de `traza` o sustituirla por `log`.
- Mostrar prompts completos, cuerpos completos de respuestas externas, secretos o credenciales aunque ayuden al diagnóstico.
- Incorporar un servicio externo de observabilidad, almacenamiento de logs, exportación de ficheros o telemetría.

## Criterios de finalización

- Todos los RF tienen pruebas automatizadas en verde con `python -m pytest` y dobles sin API.
- Una prueba demuestra el orden, los campos y las instantáneas de entrada y salida de un turno con múltiples nodos.
- Una prueba demuestra que la CLI y el panel de depuración de Streamlit reciben y muestran el mismo `log`, incluido un diagnóstico del Supervisor, mientras el chat de Streamlit lo mantiene filtrado.
- Una prueba demuestra que una pausa HITL y su reanudación devuelven logs separados por llamada.
- Una prueba demuestra que las credenciales, los prompts y cuerpos externos completos, los valores no JSON y los valores de más de 10.000 caracteres no se exponen.
- Una prueba demuestra que las entradas inválidas y los fallos controlados conservan un registro de depuración seguro.

## Dudas abiertas

Ninguna.
