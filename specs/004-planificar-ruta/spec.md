# Spec 004 — Planificar ruta en transporte público

> Estado: Aprobada · Fecha: 2026-10-14 · **Modificada 2026-10-16 (`/sdd-cambio`), pendiente de aprobación:** hora de llegada (RF-39, RF-43 a RF-45), títulos libres (RF-35, RF-36 obsoleto, RF-46 a RF-49, RF-51 a RF-53) y fecha/hora actuales y formato ISO para el especialista (RF-50, RF-50b). Dudas cerradas el mismo día (RF-43 decidido). Lo obsoleto se marca como tal y no se renumera nada.

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
- RF-40: SI Nominatim falla (error, timeout, error HTTP o límite de peticiones), ENTONCES EL SISTEMA informa de que no pudo localizar las direcciones, no llama a Google Routes ni al RAG y pide reintentar más tarde.

### Cálculo de la ruta

- RF-11: CUANDO el origen y el destino están geocodificados y dentro del ámbito, EL SISTEMA calcula la ruta con Google Routes a partir de sus coordenadas.
- RF-12: EL SISTEMA calcula la ruta considerando solo los modos de la red del CRTM: metro, metro ligero/tranvía, autobús y Cercanías.
- RF-13: EL SISTEMA admite el desplazamiento a pie únicamente como tramo de una ruta en transporte público.
- RF-14: SI la persona no indica ni hora de salida ni hora de llegada, ENTONCES EL SISTEMA calcula la ruta con salida en el momento de la consulta.
- RF-15: CUANDO Google Routes devuelve una ruta, EL SISTEMA devuelve el tiempo total y el trayecto, tramo a tramo.
- RF-16: SI Google Routes falla por error o falta de conexión, ENTONCES EL SISTEMA informa de que no se pudo calcular la ruta.
- RF-17: SI Google Routes responde pero no hay ruta en transporte público, ENTONCES EL SISTEMA informa de que no hay ruta disponible y no da zona ni precio.
- RF-18: EL SISTEMA no inventa ni estima tiempos ni trayectos en ningún caso.
- RF-42: SI ocurre un error inesperado en la herramienta, ENTONCES EL SISTEMA devuelve un mensaje de error controlado en español, sin lanzar excepción y sin mostrar detalles internos, y lo registra en la traza.

### Zona tarifaria y precio

- RF-19: SI la persona no indica título de transporte, ENTONCES, una vez calculada la ruta, EL SISTEMA consulta al RAG la zona tarifaria del trayecto y el precio del billete sencillo.
- RF-20: SI Google Routes falla por error o falta de conexión (RF-16) y ambas direcciones se geocodificaron dentro del ámbito, ENTONCES EL SISTEMA consulta igualmente al RAG la zona tarifaria y el precio.
- RF-21: SI el RAG no aporta evidencia suficiente de zona o precio, ENTONCES EL SISTEMA entrega la ruta e indica expresamente que no pudo determinar la zona o el precio con el corpus.
- RF-22: SI el RAG aporta la zona pero no el precio, o al revés, ENTONCES EL SISTEMA informa solo del dato disponible y declara cuál falta. (El caso "precio sin zona" no se da: sin zona no se consulta el precio, RF-52.)
- RF-23: EL SISTEMA no estima ni inventa ningún precio ni zona que el RAG no haya respaldado.
- RF-24: EL SISTEMA indica en la respuesta qué datos proceden de la ruta (Google) y cuáles del corpus (RAG).
- RF-41: SI el RAG falla por error al consultar la zona o el precio, ENTONCES EL SISTEMA entrega la ruta e informa de que no pudo consultar la zona ni el precio, sin sustituirlos por valores propios.

### Especialista "rutas"

- RF-25: EL SISTEMA incluye en el grafo un especialista "rutas" que usa `planificar_ruta`.
- RF-26: SI falta el origen o el destino, ENTONCES EL SISTEMA no invoca ninguna herramienta y pide en la respuesta el dato que falta; si faltan ambos, pide ambos.
- RF-27: EL SISTEMA no asume ninguna ubicación por defecto para el origen ni para el destino.
- RF-28: CUANDO la persona aporta en un turno posterior el dato que faltaba, EL SISTEMA lo combina con lo ya dicho en la conversación sin volver a pedirlo, dependiendo de la persistencia de la conversación que define otra spec.
- RF-29: SI la consulta no es de rutas, ENTONCES el especialista no invoca ninguna herramienta e indica en su nota que no es una consulta de rutas.
- RF-30: EL SISTEMA registra una traza de cada invocación de `planificar_ruta`.
- RF-50: EN cada consulta, EL SISTEMA proporciona al especialista "rutas" la fecha y hora actuales, para que pueda convertir horas relativas ("mañana a las 8") a una hora concreta. El especialista ya no recibe lista de títulos de transporte.
- RF-50b: EL SISTEMA indica al especialista "rutas" que las horas (de salida y de llegada) se pasan a la herramienta en ISO 8601 con hora (p. ej. `2026-10-17T08:00`), porque la herramienta rechaza cualquier otro formato (RF-33).

### Hora de salida, hora de llegada y título de transporte

- RF-31: DONDE la persona pide una hora de salida concreta, EL SISTEMA calcula la ruta con esa hora de salida.
- RF-32: SI la hora pedida (de salida o de llegada) es anterior al momento de la consulta, ENTONCES EL SISTEMA informa de que esa hora ya ha pasado, no calcula nada y pide otra hora.
- RF-33: SI la hora pedida (de salida o de llegada) no se puede interpretar, ENTONCES EL SISTEMA informa de ello, no calcula nada y pide que se indique de nuevo.
- RF-34: SI la hora pedida (de salida o de llegada) supera la antelación máxima configurada, ENTONCES EL SISTEMA informa de esa antelación máxima, no calcula nada y pide otra hora.
- RF-35 *(reescrito 2026-10-16)*: DONDE la persona pide un título de transporte, sea cual sea, EL SISTEMA consulta al RAG el precio de ese título en lugar del de billete sencillo.
- ~~RF-36~~ **OBSOLETO (2026-10-16):** definía una lista cerrada de títulos y el rechazo de los no incluidos. Ya no hay lista cerrada: cualquier título se consulta al RAG y, si el corpus no lo aporta, se aplica RF-37. Sustituido por RF-46 a RF-49. El número no se reutiliza.
- RF-37: SI el corpus no aporta el precio del título considerado, ENTONCES EL SISTEMA informa de que no pudo determinar el precio de ese título, sin sustituirlo por el de otro (ver RF-21, RF-22 y RF-23).
- RF-38 *(ampliado)*: EL SISTEMA indica en toda respuesta de `planificar_ruta` la hora considerada (de salida o de llegada, según lo pedido) y el título de transporte que ha considerado, sean los predeterminados o los pedidos.
- RF-39 *(reescrito 2026-10-16; antes rechazaba la hora de llegada)*: DONDE la persona pide una hora de llegada, EL SISTEMA calcula la ruta en transporte público para llegar a esa hora, delegando en Google Routes el cálculo de la hora de salida, sin calcularla por su cuenta y con una sola llamada a Google Routes.
- RF-43: SI la persona indica a la vez una hora de salida y una hora de llegada, ENTONCES EL SISTEMA informa de que no se pueden combinar, no calcula nada y pide que elija una de las dos.- RF-44: CUANDO se calcula la ruta con hora de llegada y Google Routes devuelve la hora de salida resultante, EL SISTEMA la indica en la respuesta.
- RF-45: SI se calcula la ruta con hora de llegada y Google Routes no devuelve la hora de salida resultante, ENTONCES EL SISTEMA indica la hora de llegada considerada y que no pudo determinar la hora de salida, sin estimarla (ver RF-18).
- RF-46: CUANDO consulta el título de transporte considerado, sea cual sea (billete sencillo incluido), EL SISTEMA consulta primero al RAG la zona tarifaria del trayecto y después el precio de ese título en esa zona, porque los abonos se pagan por zona y no por trayecto.
- RF-47: ANTES de incluir el título pedido en una pregunta al RAG, EL SISTEMA lo sanea para que no contenga saltos de línea.
- RF-48 *(cerrado 2026-10-16)*: SI el título pedido supera la longitud máxima configurada (valor inicial: 60 caracteres), ENTONCES EL SISTEMA no consulta el precio, informa de que no pudo interpretar el título y entrega la ruta y la zona.
- RF-51: SI el título queda vacío tras sanearlo, ENTONCES EL SISTEMA considera el billete sencillo e indica ese título en la cabecera (RF-38).
- RF-52: SI el RAG no aporta la zona (sin evidencia) o falla al consultarla, ENTONCES EL SISTEMA no consulta el precio e informa de que faltan la zona y el precio, sin sustituirlos por valores propios.
- RF-53: ANTES de incluir en la pregunta de precio la zona devuelta por el RAG, EL SISTEMA la sanea igual que el título (sin saltos de línea y con la longitud máxima configurada). *(A comprobar en T17.)*
- RF-49: EL SISTEMA realiza como máximo 2 llamadas al RAG por consulta de ruta: una de zona y una de precio.

## Requisitos no funcionales

- Idioma: todos los mensajes a la persona usuaria están en español.
- Secretos: la clave de Google Routes se lee solo del entorno (`.env`), nunca del código ni del repositorio.
- Configuración: ámbito de cobertura, número máximo de candidatos a mostrar, antelación máxima de la hora pedida, longitud máxima del título de transporte y demás límites se definen en un único punto de configuración.
- Dependencias: no se añaden dependencias nuevas; el plan valorará la librería estándar de Python para las llamadas HTTP.
- Tests: ningún test llama a Nominatim, a Google Routes, al RAG ni al LLM; usan dobles de prueba.
- Uso responsable de Nominatim: no más de 1 petición por segundo e identificación de la aplicación, según su política de uso.
- Coste: una consulta de ruta realiza como máximo 2 llamadas a Nominatim, 1 a Google Routes (también con hora de llegada) y 2 al RAG (RF-49).

## Casos límite

- Dirección homónima fuera del ámbito junto con otra dentro: se descarta la de fuera; lo cubre RF-3.
- Único resultado fuera del ámbito: RF-4, RF-5.
- Varios candidatos dentro del ámbito: RF-8, RF-9.
- Ningún resultado de Nominatim: RF-6.
- Nominatim caído, con timeout, error HTTP o límite de peticiones: RF-40.
- Origen y destino en la misma ubicación: RF-10.
- Google caído o sin conexión: RF-16, RF-18, RF-20.
- Sin ruta en transporte público: RF-17.
- RAG sin evidencia, total o parcial: RF-21, RF-22, RF-23.
- RAG con error al consultar zona o precio: RF-41.
- Error inesperado en la herramienta: RF-42.
- Falta origen o destino, o ambos: RF-26, RF-27.
- Dato faltante aportado en el turno siguiente: RF-28.
- Consulta que no es de rutas: RF-29.
- Hora de salida pasada: RF-32.
- Hora de salida no interpretable: RF-33.
- Hora de salida demasiado lejana: RF-34.
- Hora de llegada pedida: RF-39, RF-44, RF-45.
- Hora de llegada pasada, no interpretable o demasiado lejana: RF-32, RF-33, RF-34.
- Hora de salida y hora de llegada a la vez: RF-43.
- Título cualquiera (billete sencillo, abonos, etc.): RF-35, RF-46.
- Título con saltos de línea, vacío tras sanear o demasiado largo: RF-47, RF-51, RF-48.
- Zona sin evidencia o con error del RAG: RF-52 (y RF-41 si es error).
- Zona devuelta por el RAG con saltos de línea o demasiado larga: RF-53.
- Título sin precio en el corpus: RF-37.
- ~~Título fuera de la lista cerrada: RF-36~~ (obsoleto).

## Fuera de alcance

- Calcular por nuestra cuenta la hora de salida a partir de la hora de llegada.
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

- [A COMPROBAR EN T17: que la zona que devuelve el RAG, saneada (RF-53), produce una pregunta de precio útil con el RAG real.]
- Cerradas el 2026-10-16: título vacío y título largo (RF-51, RF-48), zona sin evidencia o con error (RF-52), orden zona → precio para todos los títulos (RF-46), saneado de la zona (RF-53), formato ISO 8601 en el prompt (RF-50b).
- [A VERIFICAR EN T16: si la hora de llegada de Google Routes funciona con nuestra configuración (modo transporte público con los modos del CRTM y sin hora de salida) y si el campo de respuesta configurado devuelve la hora de salida. Si no la devuelve, se aplica RF-45. Si la hora de llegada no funcionara con esa configuración, RF-39 se revisa antes de implementarlo.]
- Cerrada el 2026-10-16: la hora actual (RF-14, RF-32, RF-34, RF-50) la aporta una única fuente, `ahora()` en `src/reloj.py`, tanto para la herramienta como para el prompt del especialista.
