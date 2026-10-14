# Spec 001 — Tool auxiliar `hora_actual` y especialista de horarios

> Estado: Aprobada · Fecha: 2026-10-14 · Responsable: José Manuel Gil Ruiz

## Contexto y objetivo

El enunciado exige una herramienta auxiliar determinista (ni RAG ni API) y un grafo con al menos dos especialistas. Hoy MadridRumbo no tiene ni tools ni especialistas (spec 000). Preguntas como «¿puedo coger el metro ahora?» o «¿hasta qué hora hay servicio hoy?» dependen de la hora y el día actuales, un dato que el LLM no puede conocer y que no debe inventar. Queremos una tool que lo dé y un especialista que la combine con el RAG.

## Usuarios / actores

- Persona usuaria que pregunta por horarios o por «ahora / hoy / esta noche».
- Supervisor del grafo, que deriva esas preguntas al especialista.
- Equipo que integra la tool y el especialista en el grafo.

## Historias de usuario

- H1: Como usuaria quiero que el asistente sepa qué hora y día es para que sus respuestas sobre horarios sean pertinentes.
- H2: Como equipo quiero una tool determinista y testeable para no depender de ninguna API en esa parte.
- H3: Como equipo quiero un especialista de horarios con prompt propio para repartir el trabajo entre agentes.

## Requisitos funcionales

### Tool `hora_actual`

- RF-1: CUANDO se invoca la tool `hora_actual`, EL SISTEMA devuelve en texto la fecha, la hora en formato HH:MM, el día de la semana y el tipo de día (laborable, sábado o domingo) en la zona horaria de Madrid.
- RF-2: EL SISTEMA no requiere ningún argumento para ejecutar `hora_actual`.
- RF-3: EL SISTEMA no usa red ni LLM para ejecutar `hora_actual`.
- RF-4: EL SISTEMA obtiene la zona horaria de un único valor de configuración.
- RF-5: SI no se puede determinar la hora (zona horaria inválida o reloj no disponible), ENTONCES EL SISTEMA devuelve un mensaje de error controlado en lugar de lanzar una excepción.
- RF-6: EL SISTEMA solo permite ejecutar `hora_actual` como tool si figura en la allowlist.
- RF-7: CUANDO se ejecuta `hora_actual`, EL SISTEMA registra en la traza nombre, argumentos, estado (ok / error) y un extracto del resultado.

### Especialista `horarios`

- RF-8: EL SISTEMA incluye un especialista `horarios` con prompt propio, responsable de las preguntas sobre cuándo, a qué hora y hasta cuándo hay servicio.
- RF-9: CUANDO la consulta depende del momento actual («ahora», «hoy», «esta noche»), EL SISTEMA invoca `hora_actual` antes de redactar la nota.
- RF-10: CUANDO la consulta necesita datos de horarios del corpus, EL SISTEMA invoca el RAG como tool.
- RF-11: SI el RAG no aporta evidencia sobre un horario, ENTONCES la nota del especialista lo indica y no inventa horarios.
- RF-12: SI el LLM propone una tool que no está en la allowlist del especialista, ENTONCES EL SISTEMA no la ejecuta y lo registra en la traza.
- RF-13: EL SISTEMA limita las llamadas a tools del especialista a un máximo configurable por turno; al alcanzarlo, termina y devuelve la nota con lo obtenido hasta ese punto.
- RF-14: EL SISTEMA devuelve al grafo una nota de texto y la traza de tools del especialista, sin decidir por sí mismo que la conversación ha terminado (`done`).
- RF-15: SI el LLM falla o devuelve una respuesta no interpretable, ENTONCES EL SISTEMA devuelve una nota de error controlada sin lanzar excepción.
- RF-16: CUANDO el mensaje contiene términos de horario (hora, horario, ahora, hoy, noche, última, primera, abre, cierra, frecuencia), EL SISTEMA permite al fallback determinista del supervisor elegir `horarios`.

## Requisitos no funcionales

- Determinismo: `hora_actual`, dado un instante fijo, devuelve siempre el mismo texto.
- Coste: ningún test de esta spec llama a un LLM, a embeddings ni a ChromaDB.
- Idioma: salidas y prompts en español.
- Configuración: zona horaria y tope de pasos en un único punto de configuración.

## Casos límite

- Cambio de hora (CET/CEST) y fin de semana: RF-1.
- Zona horaria mal configurada: RF-5.
- Tool inventada por el LLM: RF-12.
- Bucle de tools sin fin: RF-13.
- Salida del LLM sin formato válido: RF-15.

## Fuera de alcance

- Festivos nacionales o locales (la tool solo distingue laborable, sábado y domingo).
- Elegir otra zona horaria desde la conversación.
- Construir el grafo, el supervisor o la allowlist global 
- Datos de horarios: salen del RAG, no se codifican.

## Criterios de finalización

- Todos los RF con test en verde (`pytest`), sin API.
- Demo manual en CLI: «¿hasta qué hora hay metro hoy?» muestra en la traza `hora_actual` y `rag_ask` (cuando el grafo esté integrado).

## Dudas abiertas

Ninguna.

## Decisiones tomadas

- **Contrato con el grafo (2026-10-14).** Resuelve la duda sobre cómo recibe el especialista el LLM, las tools y el estado. Se implementa así y se ajustará en la integración si quien lleve `src/graph.py` necesita cambios:
  - El especialista es una función `nodo_horarios(estado, llm, ejecutar)`; el LLM y la ejecución de tools se inyectan.
  - Estado de entrada: diccionario con `mensaje` (texto), `notas` (lista de textos) y `traza` (lista de entradas).
  - Salida: diccionario con solo `notas` y `traza`, sin `done`.
  - El LLM recibe una lista de mensajes `{"role", "content"}` y devuelve `{"tool", "args"}` para pedir una tool o `{"final"}` para dar la nota.
  - Cada tool se ejecuta con `ejecutar_tool(nombre, args, traza)`, que deja en la traza `tool`, `args`, `status` (ok, error o bloqueada) y `preview`.
- **Dependencias aprobadas (2026-10-14):** `tzdata` y `pytest`.
