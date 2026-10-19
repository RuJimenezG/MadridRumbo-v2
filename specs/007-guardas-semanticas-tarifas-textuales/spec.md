# Spec 007 — Guardas semánticas para consultas textuales de tarifas

> Estado: Aprobada · Fecha: 2026-10-18

## Contexto y objetivo

El Supervisor puede recibir una decisión JSON formalmente válida que deriva una pregunta puramente textual sobre precios, billetes, abonos o tarifas al especialista visual `tarifas`. Esa derivación es semánticamente incorrecta cuando no hay una imagen válida: impide usar el corpus CRTM como evidencia y puede provocar una llamada de visión innecesaria. Esta funcionalidad establece límites compartidos para los roles, corrige de forma segura esas derivaciones y permite observar la corrección sin confundirla con un fallback ni revelar la respuesta del modelo.

## Usuarios / actores

- Persona usuaria que consulta tarifas, billetes o abonos de transporte público de Madrid.
- Supervisor que selecciona los especialistas del grafo.
- Especialistas `rag`, `tarifas`, `horarios`, `rutas` y `auxiliar`.
- Cliente técnico que revisa el diagnóstico de una decisión del Supervisor.
- Equipo de desarrollo que mantiene las reglas de derivación.

## Historias de usuario

- H1: Como persona usuaria quiero que una consulta textual sobre tarifas se responda con evidencia del corpus CRTM para recibir información respaldada.
- H2: Como persona usuaria quiero que una imagen de tarifas se interprete visualmente para poder conocer los datos que contiene.
- H3: Como equipo quiero distinguir una corrección semántica de un fallback para poder revisar una derivación sin ocultar su causa.

## Requisitos funcionales (criterios de aceptación en EARS)

- RF-1: EL SISTEMA mantiene un catálogo único de responsabilidades y restricciones para los roles `rag`, `tarifas`, `horarios`, `rutas` y `auxiliar`.
- RF-2: EL SISTEMA indica al Supervisor que `rag` atiende consultas textuales sobre normativa, tarifas, billetes, abonos y documentos del CRTM.
- RF-3: EL SISTEMA indica al Supervisor que `tarifas` interpreta una imagen, foto o cartel aportado y lee los datos que contiene.
- RF-4: EL SISTEMA indica al Supervisor que `horarios` atiende horarios y frecuencias de transporte.
- RF-5: EL SISTEMA indica al Supervisor que `rutas` planifica desplazamientos entre un origen y un destino.
- RF-6: EL SISTEMA indica al Supervisor que `auxiliar` atiende la hora actual y los cálculos.
- RF-7: EL SISTEMA indica al Supervisor que una consulta textual sin imagen que contiene «tarifa», «precio», «billete», «abono», «dinero», «gastar» o «costar» debe seleccionar `rag`.
- RF-8: EL SISTEMA indica al Supervisor que no debe seleccionar `tarifas` sin una imagen aportada válida.
- RF-9: CUANDO una decisión válida del Supervisor selecciona una o más veces `tarifas` para una consulta textual definida en RF-7 sin una imagen aportada válida, EL SISTEMA sustituye cada aparición de `tarifas` por `rag` en la misma posición de la derivación y conserva el orden y las repeticiones restantes.
- RF-10: CUANDO una consulta textual sobre tarifas se refiere a una imagen, foto o cartel sin que exista una imagen aportada válida, EL SISTEMA la trata como consulta textual sin imagen y la deriva a `rag`.
- RF-11: CUANDO una consulta sobre tarifas incluye una imagen aportada válida, incluida la imagen demo configurada, EL SISTEMA permite la derivación a `tarifas` aunque la imagen no contenga tarifas.
- RF-12: SI `tarifas` recibe una consulta sin una imagen aportada válida, ENTONCES EL SISTEMA no invoca `describir_imagen` y deriva la consulta a `rag`.
- RF-13: CUANDO `rag` atiende una consulta textual sobre tarifas, EL SISTEMA conserva su respuesta anclada al corpus CRTM y la traza de la llamada a `rag_ask`.
- RF-14: CUANDO EL SISTEMA modifica una derivación válida por la incompatibilidad semántica de tarifas textuales sin imagen, EL SISTEMA registra un indicador técnico independiente de corrección semántica.
- RF-15: CUANDO EL SISTEMA registra una corrección semántica, EL SISTEMA conserva `sin_fallback` como categoría del diagnóstico de fallback únicamente en el resultado del turno.
- RF-16: CUANDO EL SISTEMA registra una corrección semántica, EL SISTEMA conserva un resumen técnico seguro de la redirección a `rag` que indica cuántas apariciones de `tarifas` se corrigieron.
- RF-17: EL SISTEMA no conserva la respuesta cruda del LLM en el diagnóstico de una corrección semántica.
- RF-18: CUANDO un cliente técnico usa la CLI, EL SISTEMA permite consultar el indicador y el resumen seguro de una corrección semántica.
- RF-19: CUANDO una persona usa el chat de Streamlit, EL SISTEMA no muestra el indicador ni el resumen técnico de una corrección semántica.
- RF-20: EL SISTEMA documenta cómo distinguir una corrección semántica de un fallback y cómo revisar su diagnóstico seguro.

## Requisitos no funcionales

- Compatibilidad: esta funcionalidad no cambia el contrato público, la allowlist ni la implementación interna de `rag_ask` o `describir_imagen`.
- Coherencia: las instrucciones entregadas al Supervisor y las restricciones aplicadas a sus decisiones usan el mismo catálogo de roles.
- Seguridad: el diagnóstico de correcciones semánticas no revela respuestas crudas del LLM, claves API, prompts completos ni datos confidenciales.
- Coste: las pruebas automatizadas de esta funcionalidad no llaman a LLM, APIs, credenciales, embeddings ni bases de datos reales.
- Idioma: los mensajes visibles y la documentación añadida están en español.

## Casos límite

- Una decisión JSON válida que selecciona únicamente `tarifas` para una consulta textual de Combinado Metro sin imagen: RF-9, RF-13 y RF-14 a RF-17.
- Una decisión JSON válida que selecciona repetidamente `tarifas` para una consulta textual sin imagen: RF-9 y RF-16.
- Una consulta textual sobre tarifas que menciona un cartel o una foto sin aportar una imagen válida: RF-10.
- Una consulta que aporta una imagen válida sin tarifas o usa la imagen demo configurada: RF-11.
- Una llegada directa a `tarifas` sin imagen válida pese a las guardas de derivación: RF-12.
- Un fallo de proveedor, JSON inválido o roles inválidos: conserva el fallback y su diagnóstico definidos en la spec 006.
- Una decisión correcta sin incompatibilidad semántica: conserva la categoría `sin_fallback` definida en la spec 006 sin registrar una corrección semántica.
- Un turno posterior al que contiene una corrección semántica: no conserva su indicador ni su resumen técnico: RF-15.

## Fuera de alcance

- Cambiar el contrato público, la allowlist o la implementación interna de `rag_ask` o `describir_imagen`.
- Alterar los documentos del corpus CRTM o los precios que aporta el RAG.
- Sustituir o modificar el fallback vigente ante fallos de proveedor, JSON inválido o roles inválidos.
- Resolver la continuidad de `nodo_auxiliar`.
- Renombrar o generalizar `nodo_tarifas` como `nodo_multimodal`.
- Añadir nuevas modalidades, herramientas o especialistas.

## Criterios de finalización

- Todos los RF tienen pruebas automatizadas en verde con `pytest` y dobles sin APIs ni credenciales reales.
- Una prueba con una decisión LLM válida pero errónea, `{"roles": ["tarifas"]}`, para una consulta textual de Combinado Metro demuestra una llamada a `rag_ask`, conserva su respuesta anclada y su traza, y demuestra cero llamadas a `describir_imagen`.
- Una prueba con una imagen válida de tarifas demuestra que se mantiene el recorrido por `tarifas` y una llamada a `describir_imagen`.
- Una prueba con roles `tarifas` repetidos demuestra que cada aparición se sustituye por `rag` sin alterar el orden de la derivación.
- Una prueba demuestra que la corrección semántica es observable mediante su indicador y resumen seguro, conserva `sin_fallback` solo en el resultado del turno y no expone la respuesta cruda del LLM.
- La documentación explica cómo revisar la corrección semántica y distinguirla de un fallback.
- La suite completa continúa ejecutándose sin APIs ni credenciales reales.

## Dudas abiertas

Ninguna.
