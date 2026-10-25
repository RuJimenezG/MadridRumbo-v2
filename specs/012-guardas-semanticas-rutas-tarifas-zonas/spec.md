# Spec 012 — Guardas semánticas de rutas para tarifas entre zonas

> Estado: **Aprobada** · Fecha: 2026-10-23
> Complementa la spec 007 para las decisiones que seleccionan `rutas` de forma semánticamente incompatible en consultas textuales sobre tarifas entre zonas tarifarias. Mantiene vigentes las responsabilidades de `rutas` y las consultas de precio dentro de una ruta real definidas por las specs 004, 005 y 010.

## Contexto y objetivo

El Supervisor puede devolver una decisión formalmente válida que interpreta códigos de zonas tarifarias como extremos geográficos. En consecuencia, una pregunta documental como «precio del abono A-B2» puede llegar a `rutas`, que pide un origen y un destino, en vez de al RAG, que es quien debe responder los precios, billetes y abonos con evidencia del corpus CRTM. Esta funcionalidad aclara el significado de las zonas tarifarias en las instrucciones del Supervisor y añade una corrección semántica determinista para las derivaciones incompatibles, sin afectar las solicitudes reales de itinerarios ni el contrato compartido por CLI y Streamlit.

## Usuarios / actores

- Persona usuaria que consulta precios, billetes o abonos entre zonas tarifarias de Madrid.
- Persona usuaria que solicita una ruta entre dos lugares físicos y puede preguntar también por su precio.
- Supervisor que selecciona los roles del grafo.
- Especialistas `rag` y `rutas`.
- Cliente técnico y equipo de desarrollo que revisan los diagnósticos seguros del Supervisor.

## Historias de usuario

- H1: Como persona usuaria quiero que un precio de abono entre zonas se consulte en la documentación del CRTM para recibir una respuesta respaldada.
- H2: Como persona usuaria quiero que una petición de ruta entre lugares físicos siga llegando al especialista de rutas aunque mencione el precio.
- H3: Como equipo quiero detectar y registrar de forma segura las correcciones semánticas del Supervisor para poder depurarlas sin confundirlas con un fallback.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-1: EL SISTEMA indica al Supervisor que los códigos `A`, `B1`, `B2`, `B3`, `C1`, `C2`, `E1` y `E2` son zonas tarifarias y no representan por sí mismos un origen ni un destino físico.
- RF-2: EL SISTEMA identifica como consulta textual de tarifa entre zonas una consulta sin imagen aportada válida que menciona un término de tarifa, precio, billete o abono y relaciona explícitamente dos códigos de zona tarifaria admitidos.
- RF-3: EL SISTEMA reconoce como relaciones explícitas entre dos zonas tarifarias las expresiones «entre … y …», «de … a …» y la unión de ambos códigos mediante un guion, sin distinguir mayúsculas y minúsculas.
- RF-4: EL SISTEMA no identifica una consulta como tarifa entre zonas únicamente porque mencione un solo código de zona tarifaria.
- RF-5: SI una consulta textual de tarifa entre zonas contiene una petición de ruta con dos lugares físicos, ENTONCES EL SISTEMA no aplica la corrección semántica de rutas de esta spec.
- RF-6: CUANDO una decisión válida del Supervisor incluye una o más apariciones de `rutas` para una consulta textual de tarifa entre zonas sin petición de ruta con dos lugares físicos, EL SISTEMA sustituye cada aparición de `rutas` por `rag` en la misma posición.
- RF-7: CUANDO EL SISTEMA aplica la sustitución de RF-6, EL SISTEMA conserva el orden y las repeticiones de los demás roles de la derivación.
- RF-8: CUANDO EL SISTEMA aplica la sustitución de RF-6, EL SISTEMA conserva el diagnóstico de fallback `sin_fallback` de la decisión válida del Supervisor.
- RF-9: CUANDO EL SISTEMA aplica la sustitución de RF-6, EL SISTEMA registra un diagnóstico técnico independiente del fallback que identifica la corrección semántica de `rutas` a `rag` y el número de apariciones corregidas.
- RF-10: EL SISTEMA no conserva la respuesta cruda del LLM en el diagnóstico técnico de la corrección semántica de rutas.
- RF-11: CUANDO un cliente técnico consulta el registro de depuración del turno, EL SISTEMA permite revisar el diagnóstico seguro de la corrección semántica de rutas por separado del diagnóstico de fallback.
- RF-12: CUANDO una persona usuaria consulta el chat o el desplegable «Pasos seguidos» de Streamlit, EL SISTEMA no muestra el diagnóstico técnico de la corrección semántica de rutas.
- RF-13: CUANDO una consulta textual de tarifa entre zonas se deriva a `rag`, EL SISTEMA conserva la respuesta anclada al corpus CRTM y la traza de la consulta documental vigente.
- RF-14: CUANDO una consulta incluye una imagen aportada válida, EL SISTEMA conserva el comportamiento multimodal vigente y no aplica la detección textual de tarifa entre zonas de esta spec.
- RF-15: CUANDO una consulta no relaciona explícitamente dos zonas tarifarias, EL SISTEMA conserva las reglas de derivación vigentes.
- RF-16: CUANDO una consulta pide una ruta entre dos lugares físicos y pregunta además por un precio o un abono, EL SISTEMA conserva los roles documentales y de rutas que correspondan conforme a las reglas vigentes.

## Requisitos no funcionales

- Compatibilidad: esta funcionalidad no modifica las seis claves de primer nivel ni los tipos del contrato público de las operaciones del grafo.
- RAG: la funcionalidad no modifica el contrato ni la implementación interna de `rag_ask`, la recuperación ni el corpus CRTM.
- Seguridad: el diagnóstico técnico no incluye respuestas crudas del LLM, claves API, prompts completos ni datos confidenciales.
- Coste: las pruebas automatizadas no llaman a LLM, APIs externas, embeddings ni ChromaDB reales; emplean dobles de prueba.
- Dependencias: la funcionalidad no añade dependencias.
- Idioma: los mensajes y diagnósticos técnicos visibles se presentan en español, salvo los identificadores existentes de roles.

## Casos límite

- «Dime el precio del abono transporte de 30 días entre las zonas A y B2.»: se deriva a `rag` y nunca únicamente a `rutas` (RF-2, RF-3 y RF-6).
- «¿Cuánto cuesta el abono de A a B1?»: se deriva a `rag` (RF-2, RF-3 y RF-6).
- «Precio del abono A-B2»: se deriva a `rag` (RF-2, RF-3 y RF-6).
- Una decisión válida `{"roles": ["rutas"]}` para una consulta A–B2: se corrige a `rag`, sin activar fallback y con diagnóstico semántico independiente (RF-6 y RF-8 a RF-11).
- Una derivación con `rutas` repetido y otros roles: cada aparición incompatible se sustituye por `rag` sin alterar el orden ni las demás repeticiones (RF-6 y RF-7).
- «¿Cómo voy desde Sol hasta Atocha y cuánto cuesta el abono?»: conserva `rutas` y la atención documental o tarifaria necesaria (RF-5 y RF-16).
- «¿Cómo llego desde la zona A a Sol?»: no se considera una relación entre dos zonas tarifarias y conserva las reglas vigentes (RF-4 y RF-15).
- Una consulta de tarifa con imagen aportada válida: conserva el flujo multimodal vigente (RF-14).
- Un fallo de proveedor, JSON inválido o roles inválidos: conserva el fallback y su diagnóstico definidos por la spec 006; no se confunde con esta corrección semántica.

## Fuera de alcance

- Cambiar la implementación interna, recuperación, corpus o evidencia devuelta por `rag_ask`.
- Modificar la planificación de rutas, la geocodificación, las APIs externas o el comportamiento de precio ya asociado a una ruta real.
- Añadir roles, tools, modalidades de entrada o dependencias.
- Cambiar la estructura del contrato público del grafo, de la traza de tools o del registro de depuración.
- Alterar la guarda vigente para consultas textuales sin imagen derivadas a `tarifas`, salvo la coexistencia necesaria de ambas guardas.
- Resolver consultas de tarifas que no relacionen explícitamente dos zonas tarifarias.

## Criterios de finalización

- Todos los RF tienen pruebas automatizadas en verde con `python -m pytest` y dobles sin API, embeddings ni ChromaDB real.
- Las pruebas unitarias cubren la detección de pares de zonas para las formulaciones «entre», «de … a …» y con guion, incluidos cambios de mayúsculas y minúsculas.
- Una prueba con un Supervisor simulado que devuelve `{"roles": ["rutas"]}` para una consulta A–B2 demuestra que la derivación final es `rag`.
- Las pruebas demuestran que las tres consultas textuales de precio entre zonas indicadas en esta spec se derivan a `rag`.
- Una prueba de no regresión demuestra que una ruta real entre dos lugares físicos conserva `rutas`, incluso si pide también información de precio.
- Una prueba demuestra que una sola mención de «zona A» no activa la guarda de tarifa entre zonas.
- Las pruebas demuestran que la corrección semántica conserva el orden de la cola, no activa fallback, deja un diagnóstico técnico seguro separado y no expone la respuesta cruda del LLM.
- Una prueba demuestra que una imagen válida mantiene el comportamiento multimodal existente.

## Dudas abiertas

Ninguna.