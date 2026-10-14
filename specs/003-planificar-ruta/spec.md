# Spec 003 — Planificar ruta en transporte público

> Estado: Aprobada · Fecha: 2026-10-14

## Contexto y objetivo

Hoy MadridRumbo responde preguntas sobre el corpus CRTM (RAG), pero no sabe cómo ir de una dirección a otra. Queremos una herramienta `planificar_ruta(origen, destino)` que, a partir de dos direcciones en texto libre, devuelva el tiempo y el trayecto en transporte público de la red del CRTM y, con el RAG, la zona tarifaria y el precio del billete. Un especialista "rutas" del grafo usará esta herramienta. Así la persona usuaria obtiene en una sola respuesta cómo llegar, cuánto tarda y cuánto cuesta, y distingue qué dato viene de la ruta y cuál del corpus.

## Usuarios / actores

- Persona usuaria que pregunta cómo ir de un lugar a otro por CLI o Streamlit.
- Especialista "rutas" del grafo, que invoca la herramienta.
- Equipo que mantiene el sistema y define el ámbito de cobertura.

## Historias de usuario

- H1: Como usuaria quiero indicar un origen y un destino en lenguaje natural para saber cómo llegar en transporte público y cuánto tarda.
- H2: Como usuaria quiero conocer la zona tarifaria y el precio del billete de mi trayecto para saber cuánto me costará.
- H3: Como usuaria quiero que el sistema me pida aclaración cuando mi dirección sea ambigua, en lugar de calcular una ruta equivocada.
- H4: Como usuaria quiero saber qué datos proceden de la ruta y cuáles del corpus para saber en qué fuente confiar.
- H5: Como equipo quiero definir en un único punto el ámbito de cobertura para poder cambiarlo sin tocar el comportamiento.

## Requisitos funcionales (criterios de aceptación en EARS)

### Geocodificación y ámbito

- RF-1: CUANDO se invoca `planificar_ruta`, EL SISTEMA convierte el origen y el destino de texto libre a coordenadas mediante Nominatim.
- RF-2: EL SISTEMA define el ámbito de cobertura (el territorio que cubre el corpus CRTM) en un único punto de configuración.
- RF-3: EL SISTEMA solo considera candidatos de Nominatim que estén dentro del ámbito de cobertura.
- RF-4: SI Nominatim devuelve solo resultados fuera del ámbito para el origen o el destino, ENTONCES EL SISTEMA rechaza la consulta con un mensaje que indica que esa dirección está fuera de cobertura.
- RF-5: SI el origen o el destino queda fuera de cobertura, ENTONCES EL SISTEMA no llama a Google Routes.
- RF-6: SI Nominatim no devuelve ningún resultado para el origen o el destino, ENTONCES EL SISTEMA informa de que no encontró la dirección y pide una más precisa.
- RF-7: SI hay un único candidato dentro del ámbito, ENTONCES EL SISTEMA continúa sin preguntar e indica en la respuesta la dirección identificada.
- RF-8: SI hay varios candidatos dentro del ámbito, ENTONCES EL SISTEMA no calcula la ruta, muestra un número limitado de candidatos y pide a la persona que elija o concrete.
- RF-9: EL SISTEMA formula la petición de aclaración de los RF-6 y RF-8 en la respuesta de la conversación, sin usar la pausa de aprobación humana del grafo (HITL).
- RF-10: SI el origen y el destino resuelven a la misma ubicación, ENTONCES EL SISTEMA informa de ello y no calcula la ruta.

### Cálculo de la ruta

- RF-11: CUANDO el origen y el destino están geocodificados y dentro del ámbito, EL SISTEMA calcula la ruta con Google Routes a partir de sus coordenadas.
- RF-12: EL SISTEMA calcula la ruta considerando solo los modos de la red del CRTM: metro, metro ligero/tranvía, autobús y Cercanías.
- RF-13: EL SISTEMA admite el desplazamiento a pie únicamente como tramo de una ruta en transporte público.
- RF-14: SI la persona no indica hora de salida, ENTONCES EL SISTEMA calcula la ruta con salida en el momento de la consulta.
- RF-15: CUANDO Google Routes devuelve una ruta, EL SISTEMA devuelve el tiempo total y el trayecto, tramo a tramo.
- RF-16: SI Google Routes falla por error o falta de conexión, ENTONCES EL SISTEMA informa de que no se pudo calcular la ruta.
- RF-17: SI Google Routes responde pero no hay ruta en transporte público, ENTONCES EL SISTEMA informa de que no hay ruta disponible y no da zona ni precio.
- RF-18: EL SISTEMA no inventa ni estima tiempos ni trayectos en ningún caso.

### Zona tarifaria y precio

- RF-19: SI la persona no indica título de transporte, ENTONCES, una vez calculada la ruta, EL SISTEMA consulta al RAG la zona tarifaria del trayecto y el precio del billete sencillo.
- RF-20: SI Google Routes falla por error o falta de conexión (RF-16) y ambas direcciones se geocodificaron dentro del ámbito, ENTONCES EL SISTEMA consulta igualmente al RAG la zona tarifaria y el precio.
- RF-21: SI el RAG no aporta evidencia suficiente de zona o precio, ENTONCES EL SISTEMA entrega la ruta e indica expresamente que no pudo determinar la zona o el precio con el corpus.
- RF-22: SI el RAG aporta la zona pero no el precio, o al revés, ENTONCES EL SISTEMA informa solo del dato disponible y declara cuál falta.
- RF-23: EL SISTEMA no estima ni inventa ningún precio ni zona que el RAG no haya respaldado.
- RF-24: EL SISTEMA indica en la respuesta qué datos proceden de la ruta (Google) y cuáles del corpus (RAG).

### Especialista "rutas"

- RF-25: EL SISTEMA incluye en el grafo un especialista "rutas" que usa `planificar_ruta`.
- RF-26: SI falta el origen o el destino, ENTONCES EL SISTEMA no invoca ninguna herramienta y pide en la respuesta el dato que falta; si faltan ambos, pide ambos.
- RF-27: EL SISTEMA no asume ninguna ubicación por defecto para el origen ni para el destino.
- RF-28: CUANDO la persona aporta en un turno posterior el dato que faltaba, EL SISTEMA lo combina con lo ya dicho en la conversación sin volver a pedirlo, dependiendo de la persistencia de la conversación que define otra spec.
- RF-29: SI la consulta no es de rutas, ENTONCES el especialista no invoca ninguna herramienta e indica en su nota que no es una consulta de rutas.
- RF-30: EL SISTEMA registra una traza de cada invocación de `planificar_ruta`.

### Hora de salida y título de transporte

- RF-31: DONDE la persona pide una hora de salida concreta, EL SISTEMA calcula la ruta con esa hora de salida.
- RF-32: SI la hora de salida pedida es anterior al momento de la consulta, ENTONCES EL SISTEMA informa de que esa hora ya ha pasado, no calcula nada y pide otra hora.
- RF-33: SI la hora de salida pedida no se puede interpretar, ENTONCES EL SISTEMA informa de ello, no calcula nada y pide que se indique de nuevo.
- RF-34: SI la hora de salida pedida supera la antelación máxima configurada, ENTONCES EL SISTEMA informa de esa antelación máxima, no calcula nada y pide otra hora.
- RF-35: DONDE la persona pide un título de transporte de la lista cerrada (billete sencillo o billete de 10 viajes), EL SISTEMA consulta al RAG el precio de ese título en lugar del billete sencillo.
- RF-36: SI el título pedido no está en la lista cerrada, ENTONCES EL SISTEMA entrega igualmente la ruta, informa de la zona tarifaria del trayecto (que no depende del título), informa de que ese título no está disponible, muestra los títulos disponibles y omite únicamente el precio.
- RF-37: SI el corpus no aporta el precio del título considerado, ENTONCES EL SISTEMA informa de que no pudo determinar el precio de ese título, sin sustituirlo por el de otro (ver RF-21, RF-22 y RF-23).
- RF-38: EL SISTEMA indica en toda respuesta de `planificar_ruta` la hora de salida y el título de transporte que ha considerado, sean los predeterminados o los pedidos.
- RF-39: SI la persona pide una hora de llegada, ENTONCES EL SISTEMA informa de que solo se admite hora de salida, no calcula nada y pide una hora de salida.

## Requisitos no funcionales

- Idioma: todos los mensajes a la persona usuaria están en español.
- Secretos: la clave de Google Routes se lee solo del entorno (`.env`), nunca del código ni del repositorio.
- Configuración: ámbito de cobertura, número máximo de candidatos a mostrar, antelación máxima de la hora de salida, lista cerrada de títulos de transporte y demás límites se definen en un único punto de configuración.
- Dependencias: no se añaden dependencias nuevas; el plan valorará la librería estándar de Python para las llamadas HTTP.
- Tests: ningún test llama a Nominatim, a Google Routes, al RAG ni al LLM; usan dobles de prueba.
- Uso responsable de Nominatim: no más de 1 petición por segundo e identificación de la aplicación, según su política de uso.
- Coste: una consulta de ruta realiza como máximo 2 llamadas a Nominatim y 1 a Google Routes.

## Casos límite

- Dirección homónima fuera del ámbito junto con otra dentro: se descarta la de fuera; lo cubre RF-3.
- Único resultado fuera del ámbito: RF-4, RF-5.
- Varios candidatos dentro del ámbito: RF-8, RF-9.
- Ningún resultado de Nominatim: RF-6.
- Origen y destino en la misma ubicación: RF-10.
- Google caído o sin conexión: RF-16, RF-18, RF-20.
- Sin ruta en transporte público: RF-17.
- RAG sin evidencia, total o parcial: RF-21, RF-22, RF-23.
- Falta origen o destino, o ambos: RF-26, RF-27.
- Dato faltante aportado en el turno siguiente: RF-28.
- Consulta que no es de rutas: RF-29.
- Hora de salida pasada: RF-32.
- Hora de salida no interpretable: RF-33.
- Hora de salida demasiado lejana: RF-34.
- Hora de llegada pedida en lugar de hora de salida: RF-39.
- Título pedido no incluido en la lista cerrada (incluidos los abonos): RF-36.
- Título sin precio en el corpus: RF-37.

## Fuera de alcance

- Elegir hora de llegada.
- Abonos y cualquier título distinto del billete sencillo y el billete de 10 viajes.
- Otros modos de transporte (bici, coche, etc.); a pie solo como tramo de la ruta.
- Rutas alternativas múltiples.
- Decidir a quién se deriva una consulta o cuándo termina la conversación (supervisor del grafo).
- Pausa de aprobación humana (HITL) y persistencia por `thread_id`, que pertenecen a otras specs.
- Cómo se comprueba el ámbito, cómo se restringen los modos en la API, el número máximo de candidatos y la estructura de la respuesta; se deciden en el plan.
- Cambios en la ingesta o el índice del RAG.

## Criterios de finalización

- Todos los RF tienen test en verde (`pytest`) con dobles para Nominatim, Google Routes, RAG y LLM.
- Demo manual de una consulta completa (origen y destino válidos) con ruta, zona y precio.
- Demo manual de un caso fuera de cobertura y de uno con dirección ambigua.

## Dudas abiertas

- [NECESITA ACLARACIÓN: quién aporta la hora actual (RF-14, RF-32), y si su herramienta entra en esta spec o en otra. No bloquea el plan, pero el plan debe diseñar la fuente de la hora de modo que se pueda sustituir sin tocar el resto]
