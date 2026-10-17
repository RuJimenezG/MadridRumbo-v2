# Spec 006 — Robustez y observabilidad de decisiones LLM del Supervisor

> Estado: Aprobada · Fecha: 2026-10-16

## Contexto y objetivo

El Supervisor del grafo multiagente depende de una decisión estructurada del LLM para seleccionar especialistas. Actualmente, una decisión correcta puede quedar descartada por detalles de presentación y los fallos que activan el fallback no quedan diferenciados de forma suficiente para depurarlos. Esta funcionalidad hace que las decisiones JSON válidas y las respuestas con un bloque JSON Markdown recuperable se acepten de forma consistente, conserva el fallback determinista ante entradas no válidas o fallos del proveedor y aporta un diagnóstico técnico seguro. La persona usuaria final seguirá recibiendo una respuesta controlada, sin secretos ni información interna.

## Usuarios / actores

- Persona usuaria que consulta transporte público de Madrid y recibe una respuesta controlada.
- Cliente técnico que invoca las operaciones públicas del grafo y revisa su registro de diagnóstico.
- Equipo de desarrollo que investiga por qué se aplicó el fallback del Supervisor.
- LLM proveedor de la decisión de roles del Supervisor.

## Historias de usuario

- H1: Como persona usuaria quiero que una decisión válida del Supervisor se aplique para que mi consulta llegue al especialista correcto.
- H2: Como equipo quiero identificar de forma segura el motivo de cada fallback para poder depurarlo sin revelar información confidencial.
- H3: Como persona usuaria quiero que distintas formulaciones equivalentes de una ruta se reconozcan para obtener un plan de viaje.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-1: EL SISTEMA solicita al LLM del Supervisor una única decisión en JSON válido cuyo campo `roles` contiene una lista de roles admitidos.
- RF-2: EL SISTEMA muestra al LLM del Supervisor el ejemplo JSON válido `{"roles": ["auxiliar"]}`.
- RF-3: EL SISTEMA instruye al LLM del Supervisor para que no incluya Markdown ni texto fuera del JSON.
- RF-4: CUANDO el LLM del Supervisor devuelve un objeto JSON que contiene exclusivamente `roles` como una lista ordenada de entre cero y veinte cadenas de roles admitidos, EL SISTEMA usa esa decisión sin activar el fallback determinista.
- RF-5: CUANDO el LLM del Supervisor devuelve una decisión JSON válida dentro de un bloque Markdown sin etiqueta o con etiqueta `json`, sin distinguir mayúsculas y minúsculas, EL SISTEMA retira únicamente el envoltorio y los espacios exteriores del bloque y usa la decisión sin activar el fallback determinista.
- RF-6: SI la respuesta del LLM del Supervisor usa comillas simples en lugar de JSON válido, ENTONCES EL SISTEMA la clasifica como `json_invalido` y activa el fallback determinista.
- RF-7: SI la respuesta del LLM del Supervisor contiene texto adicional fuera de una decisión JSON o de su bloque Markdown recuperable, ENTONCES EL SISTEMA la clasifica como `json_invalido` y activa el fallback determinista.
- RF-8: SI la llamada al proveedor del LLM del Supervisor falla, devuelve contenido vacío o no textual, o informa de un bloqueo de seguridad, ENTONCES EL SISTEMA clasifica el fallo como `proveedor` y activa el fallback determinista.
- RF-9: SI la decisión JSON del LLM del Supervisor contiene campos distintos de `roles`, no contiene una lista de roles, supera veinte roles o contiene un valor de rol no admitido, ENTONCES EL SISTEMA clasifica el fallo como `roles_invalidos` y activa el fallback determinista.
- RF-10: CUANDO el fallback determinista se activa por una decisión del Supervisor, EL SISTEMA conserva el motivo clasificado en el registro técnico incluido en el resultado público del grafo.
- RF-11: CUANDO el LLM del Supervisor produce una decisión válida, EL SISTEMA conserva en el registro técnico incluido en el resultado público del grafo la categoría `sin_fallback`.
- RF-12: EL SISTEMA limita la categoría del registro técnico de decisiones del Supervisor a `proveedor`, `json_invalido`, `roles_invalidos` o `sin_fallback`.
- RF-13: EL SISTEMA conserva en el registro técnico de decisiones del Supervisor un resumen no sensible asociado a la categoría.
- RF-14: EL SISTEMA no registra en el diagnóstico de decisiones del Supervisor claves API, prompts completos ni datos confidenciales.
- RF-15: CUANDO el cliente técnico usa la CLI, EL SISTEMA permite consultar la categoría y el resumen técnico del fallo del Supervisor.
- RF-16: CUANDO la persona usuaria usa el chat de Streamlit, EL SISTEMA no muestra la categoría ni el resumen técnico del fallo del Supervisor.
- RF-17: CUANDO el fallback determinista recibe una consulta con la formulación «quiero ir de A a B», EL SISTEMA la deriva al especialista de rutas aunque haya mayúsculas, tildes, puntuación o texto adicional.
- RF-18: CUANDO el fallback determinista recibe una consulta con la formulación «necesito ir de A a B», EL SISTEMA la deriva al especialista de rutas aunque haya mayúsculas, tildes, puntuación o texto adicional.
- RF-19: CUANDO el fallback determinista recibe una consulta con la formulación «voy de A a B», EL SISTEMA la deriva al especialista de rutas aunque haya mayúsculas, tildes, puntuación o texto adicional.
- RF-20: CUANDO una de las formulaciones de ruta reconocidas contiene un origen y un destino válidos, EL SISTEMA solicita un plan de ruta antes de presentar cualquier plan para aprobación humana.
- RF-21: SI una de las formulaciones de ruta reconocidas no incluye ambos extremos, ENTONCES EL SISTEMA solicita primero una aclaración sin registrar una ruta reconocida.
- RF-22: EL SISTEMA proporciona una guía de comprobación manual en español con Gemini real que diferencia una decisión LLM válida de un fallback y permite provocar un fallback de forma reproducible.
- RF-23: EL SISTEMA incluye en la guía de comprobación manual cómo revisar de forma segura la causa clasificada de un fallback.
- RF-24: EL SISTEMA configura la solicitud a Gemini del Supervisor con `response_mime_type="application/json"`.
- RF-25: CUANDO termina un turno, EL SISTEMA conserva el diagnóstico del Supervisor únicamente en el resultado de ese turno y no lo persiste como parte del historial de la conversación.

## Requisitos no funcionales

- Seguridad: el diagnóstico técnico no conserva ni revela claves API, prompts completos ni datos confidenciales.
- Compatibilidad: esta funcionalidad no cambia las claves ni los tipos del contrato público de las dos operaciones del grafo.
- Coste: las pruebas automatizadas de esta funcionalidad no llaman a Gemini ni a ninguna API, credencial, embedding o base de datos reales.
- Idioma: los mensajes visibles y la guía manual están en español.

## Casos límite

- Decisión JSON correcta con lista vacía para finalizar, con roles repetidos o con veinte roles: RF-4.
- Decisión JSON correcta envuelta en un bloque Markdown sin etiqueta o con etiqueta `json` en cualquier capitalización: RF-5.
- Decisión con comillas simples: RF-6.
- Decisión con texto adicional: RF-7.
- Rol prohibido, campo adicional, lista ausente, tipo incorrecto o más de veinte roles: RF-9.
- Error, contenido vacío, contenido no textual o bloqueo del proveedor: RF-8.
- Diagnóstico que pudiera incluir secretos o contenido interno: RF-10 a RF-16 y RF-25.
- Consultas «quiero ir de A a B», «necesito ir de A a B» y «voy de A a B» con mayúsculas, tildes, puntuación o texto adicional: RF-17 a RF-21.

## Fuera de alcance

- Cambiar el contrato público de las dos operaciones del grafo para procesar un turno o aprobar un plan.
- Eliminar o sustituir el fallback determinista del Supervisor.
- Modificar los contratos de las tools existentes.
- Corregir fallos específicos de Gemini Vision, RAG, Google Routes o Nominatim que no impidan registrar de forma segura la decisión del Supervisor.
- Aceptar como JSON válido decisiones con comillas simples o corregir automáticamente contenido distinto del envoltorio Markdown `json` recuperable.

## Criterios de finalización

- Todos los RF tienen pruebas automatizadas en verde con `pytest` y dobles sin APIs ni credenciales reales.
- Las pruebas cubren decisión JSON válida, bloque Markdown `json`, comillas simples, texto adicional, rol prohibido y error de proveedor.
- Una prueba con un doble de Gemini demuestra que la solicitud del Supervisor configura `response_mime_type="application/json"`.
- Las pruebas demuestran que las tres formulaciones de ruta derivan a rutas y solicitan un plan cuando origen y destino son válidos, y piden aclaración antes cuando falta uno de los extremos.
- La guía manual con Gemini real permite comprobar una decisión válida, provocar un fallback reproducible y revisar su causa clasificada sin exponer secretos.
- La suite completa continúa ejecutándose sin APIs ni credenciales reales.

## Dudas abiertas

Ninguna.
