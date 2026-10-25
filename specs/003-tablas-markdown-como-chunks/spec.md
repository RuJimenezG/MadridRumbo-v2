# Spec 003 — Tablas Markdown como chunks indivisibles

> Estado: Aprobada · Fecha: 2026-10-14

## Contexto y objetivo

Los documentos Markdown del corpus contienen tablas cuyos datos solo conservan su significado completo si se mantienen junto a su título y sus encabezados. La fragmentación actual puede separarlas al aplicar el tamaño ordinario de los chunks. Se quiere preservar cada tabla con formato conocido como una unidad de recuperación íntegra, sin alterar el tratamiento normal del resto del corpus.

## Usuarios / actores

- Persona usuaria que consulta precios, tarifas u otros datos estructurados del corpus.
- Equipo que prepara e indexa el corpus RAG.

## Historias de usuario

- H1: Como usuaria quiero que el asistente recupere una tabla completa con su título para interpretar correctamente sus datos.
- H2: Como equipo quiero que las tablas con el formato acordado no se dividan al preparar el corpus.

## Requisitos funcionales

- RF-1: CUANDO un archivo Markdown de `data/` contiene una línea de título seguida de una tabla con fila de encabezados, fila separadora Markdown y al menos una fila de contenido, EL SISTEMA reconoce el conjunto como una tabla con significado propio.
- RF-2: CUANDO EL SISTEMA reconoce una tabla con significado propio, EL SISTEMA genera exactamente un chunk que contiene el título inmediatamente anterior, los encabezados, la fila separadora y todas las filas de contenido de esa tabla.
- RF-3: EL SISTEMA conserva íntegro el chunk de cada tabla reconocida aunque su longitud supere el tamaño ordinario configurado para los chunks.
- RF-4: EL SISTEMA no incluye el título ni ninguna parte de la misma ocurrencia de tabla reconocida en otro chunk del documento.
- RF-5: SI una tabla Markdown no cumple el formato indicado, incluyendo la ausencia de título, fila de encabezados o fila separadora, ENTONCES EL SISTEMA la procesa como texto normal.
- RF-6: EL SISTEMA aplica la fragmentación ordinaria a los contenidos de los archivos Markdown que no formen parte de una tabla reconocida.
- RF-7: EL SISTEMA mantiene el comportamiento de fragmentación existente para los formatos de corpus distintos de Markdown.

## Requisitos no funcionales

- Coste: los tests de esta funcionalidad no llaman a LLM, embeddings ni ChromaDB.
- Compatibilidad: la preparación del corpus conserva los metadatos de trazabilidad existentes para todos los chunks.
- Idioma: los mensajes y la documentación añadidos para esta funcionalidad están en español.

## Casos límite

- Una tabla cuyo contenido completo supera el tamaño ordinario de chunk: RF-3.
- Dos tablas consecutivas, incluso si repiten el mismo título: RF-2 y RF-4 para cada ocurrencia.
- Texto antes, entre o después de las tablas: RF-6.
- Una tabla sin título, sin fila de encabezados o sin fila separadora Markdown: RF-5.
- Un PDF, un CSV de paradas u otro formato no Markdown: RF-7.

## Fuera de alcance

- Corregir, normalizar o completar tablas Markdown mal formadas.
- Tratar como tablas bloques HTML, tablas de PDF o datos CSV distintos de los bloques de paradas existentes.
- Cambiar la recuperación, el prompt o la generación de respuestas del RAG.
- Cambiar el contenido de los archivos del corpus.

## Criterios de finalización

- Todos los RF tienen tests automatizados en verde con `pytest`, sin API.
- Una prueba de preparación con tablas del formato acordado demuestra que cada tabla se conserva en un único chunk con su título y sin fragmentos duplicados en otros chunks.

## Dudas abiertas

Ninguna.
