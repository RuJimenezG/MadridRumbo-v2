# Spec 010 — Lugares, bloques literales y precio en `planificar_ruta`

> Estado: **Borrador** (Fases A y B implementadas 2026-10-21; T16 el 2026-10-22, con dobles; pendientes de aprobar; ver `validacion.md`) · Fecha: 2026-10-21
> Cambia comportamiento de las specs 004 (RF-27, en Fase B) y 009 (RF-4, RF-13, RF-16, RF-23 y RF-25, en Fase A). Ver «Cambios explícitos sobre specs anteriores». No se edita ninguna spec anterior.

## Contexto y objetivo

Los diagnósticos del 2026-10-21 (sin coste, más una ruta real) detectaron cinco problemas en la consulta de rutas:

- **(a) Bloques que se pierden.** Las «Opciones» de una ruta ambigua, el bloque de bici y la línea del clima no siempre llegan a la persona usuaria: el especialista de rutas reescribe el resultado de la herramienta (`rutas.py`, segunda llamada al LLM) y el sintetizador es un LLM al que solo se le pide «resume» (`modelos.py`). Hoy solo el aviso de Google de la bici y la atribución de Open-Meteo se fuerzan por código (`_avisos_obligatorios`, spec 009).
- **(b) Nominatim y los prefijos.** Con «Metro X» o «Estación de metro X» devuelve 0 resultados; con el nombre solo, sí («Legazpi, Madrid» da 2, «Concha Espina, Madrid» da 7).
- **(c) Bici invisible con el clima caído.** Si Open-Meteo falla (p. ej. `URLError`), la bici desaparece en silencio: sin bici, sin línea y sin motivo.
- **(d) El RAG no ve la conversación.** El especialista del RAG recibe solo el mensaje del turno, sin historial; el de rutas sí recibe historial. Una pregunta posterior «¿y cuánto cuesta?» llega al RAG sin origen ni destino.
- **(e) El corpus ya trae paradas con zona y dirección** (`Paradas CRTM.csv`: Legazpi y Concha Espina figuran en Metro, zona A). Aprovecharlo es la futura Fase C; aquí solo se documenta.

Esta spec se divide en dos fases:

- **Fase A (T1–T5)**, a implementar ya: normalización del texto de los lugares, campo `bloques` y su volcado determinista por el sintetizador, política del clima caído y precio por título pedido.
- **Fase B (T6–T8)**: segunda capa de resolución de ambigüedad con el LLM, acotada y siempre declarada (T6 y T7 implementadas; T8, validación y mejoras futuras).

## Usuarios / actores

- Persona usuaria que pregunta por una ruta (CLI o Streamlit, mismo grafo).
- Especialista `rutas` (`src/agents/rutas.py`, de Rubén y Guzmán) y sintetizador (`src/sintetizador.py`, de Rubén y Guzmán): se tocan en Fase A solo en lo indicado.

## Historias de usuario

- H1: Como persona usuaria quiero escribir «Metro Legazpi» o «Estación de metro Concha Espina» y que se encuentre el lugar, para no tener que adivinar cómo lo espera el buscador.
- H2: Como persona usuaria quiero ver siempre las opciones cuando mi dirección es ambigua, para poder elegir una.
- H3: Como persona usuaria quiero ver el tiempo, la alternativa en bici o el motivo por el que no se ofrece, para entender la respuesta.
- H4: Como persona usuaria quiero que, si no se puede comprobar el tiempo, se me ofrezca igualmente la bici avisándome, para no perder la alternativa por un fallo ajeno.
- H5: Como persona usuaria quiero que el precio sea el del título que he pedido («abono joven») y poder preguntarlo después con «¿y cuánto cuesta?».

## Requisitos funcionales (criterios de aceptación en EARS)

### Fase A

#### Normalización del texto de los lugares (T1)

- RF-1: CUANDO `planificar_ruta` va a geocodificar un extremo, EL SISTEMA quita del **inicio** del texto, antes de enviarlo a Nominatim, uno de los prefijos «estación de metro», «estación de», «parada de» o «metro» (sin distinguir mayúsculas ni tildes) y los separadores (espacios, comas, dos puntos o guiones) que le sigan. Una sola pasada: solo se quita el primer prefijo que case.
- RF-2: SI tras quitar el prefijo no queda texto, ENTONCES EL SISTEMA no cambia el texto. Un texto sin esos prefijos llega a Nominatim idéntico, sin añadir «Madrid» y sin llamadas extra (como mucho 2 llamadas a Nominatim por consulta, sin cambios).
- RF-3: EL SISTEMA usa el texto normalizado solo para Nominatim; los mensajes, las frases de error y el campo `origen`/`destino` siguen mostrando lo que escribió la persona o el nombre que devolvió Nominatim.

#### Campo `bloques` (T2)

- RF-4: EL SISTEMA añade al resultado de `planificar_ruta` un campo **aditivo** `bloques`: lista de textos literales que deben llegar a la persona usuaria. Solo existe cuando tiene al menos un elemento. El campo `mensaje` y el resto de campos no cambian.
- RF-5: CUANDO el estado es `ambigua`, `direccion_no_encontrada` o `fuera_cobertura`, EL SISTEMA añade a `bloques` una frase por cada extremo con problema, la misma que va en el `mensaje` (sin la cabecera de hora y título). En `ambigua` esa frase contiene las opciones numeradas.
- RF-6: CUANDO el estado es `ok` y `bici.estado == "ok"`, EL SISTEMA añade a `bloques` el párrafo «Alternativa en bici (BiciMAD): …» tal como va en el `mensaje`.
- RF-7: CUANDO el estado es `ok` y la bici no se ofrece o no está disponible, EL SISTEMA añade a `bloques` **una línea corta con el motivo**: hora pedida (R1), distancia fuera del rango de 1 a 6 km (R2), mal tiempo (R0, con sus motivos), sin bicis en el origen, sin huecos en el destino, misma estación (R3 y R4) o alternativa no disponible (con una frase por causa: RF-27).
- RF-8: CUANDO el estado es `ok` y hubo consulta de clima, EL SISTEMA añade a `bloques` la línea del clima (la de RF-24 de la spec 009) o, si el clima no estaba disponible, la línea de RF-10. Orden de `bloques` en `ok`: zona y precio (RF-25), clima, bici o motivo y, al final, los avisos de opción usada (RF-21).

#### Política del clima (T3) — revisa RF-23 y RF-25 de la spec 009

- RF-9: SI el tiempo es **apto = falso** (hay dato y es malo), ENTONCES EL SISTEMA no ofrece bici y pide la ruta con `LESS_WALKING`, como hoy (spec 009, RF-22 y RF-23).
- RF-10: SI el clima **no se puede consultar** (`clima.estado == "no_disponible"`) y solo en ese caso, ENTONCES EL SISTEMA aplica la regla de oferta de la bici sin R0 (la bici sigue el flujo normal) y añade a `bloques` la línea «No se pudo comprobar el tiempo; la alternativa en bici se ofrece sin esa comprobación». La petición de tránsito **no** lleva `LESS_WALKING`.
- RF-11: SI la consulta del clima falla, ENTONCES EL SISTEMA registra en el log solo el tipo de la excepción y, en un `URLError`, su `reason`; nunca la URL con credenciales, claves ni el cuerpo de la respuesta.
- RF-12: SI la persona pidió hora de salida o de llegada, ENTONCES no se consulta el clima ni se añade su línea (spec 009, RF-27, sin cambios); la bici sigue sin ofrecerse (R1) y ahora se indica el motivo (RF-7).

#### Volcado de bloques por el sintetizador (T4)

- RF-13: DESPUÉS del texto del LLM, EL SINTETIZADOR añade al final, en orden y separados por una línea en blanco, los `bloques` de cada resultado de `planificar_ruta` que no estén ya en la respuesta. Lee `resultados[].resultado` (el JSON completo de la herramienta), no las notas.
- RF-14: EL SINTETIZADOR sigue añadiendo después el aviso de Google de la bici y la atribución de Open-Meteo (spec 009, RF-12 y RF-24) si faltan. Un texto no se añade si ya aparece en la respuesta **o en un bloque ya añadido** (el bloque de bici contiene el aviso de Google; el de clima, la atribución).
- RF-15: SI un resultado no se puede leer (no es JSON, o no es un objeto), ENTONCES EL SINTETIZADOR lo ignora sin romper los demás ni activar el respaldo, y registra en el log solo el tipo del error.
- RF-16: SI el LLM del sintetizador falla, ENTONCES el respaldo determinista (que ya vuelca los resultados enteros) se mantiene sin cambios.

#### Precio por título pedido (T5)

- RF-17: EL SISTEMA incorpora el título que pidió la persona («abono joven», «billete sencillo»…) a la consulta de precio al RAG, con como mucho 2 llamadas al RAG (zona y precio) y sin cambiar nada si no se indica título. **Ya lo hace el parámetro `titulo`** (spec 004, RF-35, RF-47 y RF-51: se sanea, se muestra en la cabecera y entra en `PREGUNTA_PRECIO`); no se crea `tarifa_solicitada` (ver «Dudas abiertas»).
- RF-18: EL PROMPT del especialista de rutas (`PROMPT_RUTAS`) indica que:
  - extraiga del mensaje el título de transporte que pida la persona y lo pase en `titulo`, y lo omita si no pide ninguno (sin listas ni ejemplos de títulos en el prompt: spec 004, RF-35 y RF-50);
  - ante un resultado `ambigua`, copie literalmente las opciones numeradas del `mensaje` de la herramienta en su `final`;
  - ante `ruta_no_calculada`, no reescriba el resultado: copie el `mensaje` de la herramienta;
  - si la persona pregunta después «¿y cuánto cuesta?», vuelva a llamar a la herramienta con los mismos origen y destino del historial más el `titulo` pedido.

### Fase B (implementada 2026-10-21)

#### Ajustes de la Fase A (T5b, 2026-10-21)

- RF-25: CUANDO el estado es `ok` y el RAG devolvió la zona o el precio (estado `ok`), EL SISTEMA añade a `bloques` el texto de zona y precio tal como va en el `mensaje` («Zona (RAG): … Precio (RAG): …»). Si no hay ninguno, no se añade nada.
- RF-26: CUANDO el estado es `ruta_no_calculada`, EL SISTEMA añade a `bloques` el texto del fallo (sin la cabecera), que incluye la zona y el precio si los hay.
- RF-27: SI la bici no está disponible, ENTONCES `bici` incluye el campo `causa` (`sin_credenciales`, `emt`, `google` o `interno`) y su `motivo` y su frase son los de esa causa (`FRASES_NO_DISPONIBLE`). `interno` (error inesperado) conserva la frase genérica anterior. En los demás estados de `bici` no existe `causa`.
- RF-28: LA FICHA del rol `rutas` (`catalogo_roles.py`) indica que el rol incluye la zona y el precio del trayecto y que las preguntas de precio de seguimiento sobre una ruta ya planificada van a `rutas`. Solo texto (en `limites`; la `responsabilidad` no cambia).

#### Supervisor: ruta con precio (T9, 2026-10-21)

Diagnóstico con el LLM real (10 llamadas al supervisor, solo ese): con la ficha de RF-28 «cuánto cuesta» sin título pasa de `[rutas, rag]` a `[rutas]`, pero «…y cuánto cuesta el abono joven» sigue dando `[rutas, rag]` y «¿Cuánto cuesta el abono joven?» solo `[rag]` (correcto). `corregir_tarifas_textuales` no intervino (el modelo nunca eligió `tarifas`) y el fallback por palabras tampoco.

- RF-29: LA FICHA de `rutas` y la regla de exclusión de `instrucciones_para_supervisor` dicen que la zona y el precio del trayecto valen «también para un título concreto (p. ej. abono joven)», y la regla pasa a: «Una consulta textual de tarifa sin imagen y sin origen ni destino debe seleccionar rag; con origen y destino selecciona rutas, que incluye la zona y el precio del trayecto, también para un título concreto (p. ej. abono joven).»
- RF-30: SI el mensaje tiene forma de ruta con origen y destino (un verbo de desplazamiento —ir, voy, llegar, llego, viajar…— y la estructura «de/desde X a/al/hasta Y») y `rutas` no está en la cola del supervisor, ENTONCES EL SISTEMA añade `rutas` **al principio** de la cola. Nunca quita ni reordena otros roles (`rag` incluido). Se aplica tanto a la decisión del LLM como al fallback por palabras. Un mensaje vacío, sin esa forma (solo precio, «¿Cómo voy a pagar el abono?», solo destino) no cambia la cola.

#### Segunda capa de ambigüedad en la herramienta (T6)

- RF-19: DONDE se indique `texto_alternativo_origen` o `texto_alternativo_destino` (un único texto por extremo), EL SISTEMA lo geocodifica con Nominatim (con la normalización de RF-1) y le aplica la verificación de Madrid de RF-55 de la spec 004: +1 llamada a Nominatim por extremo, **como máximo 4 en total**.
- RF-20: SI el texto alternativo no se verifica (0 candidatos, ambiguo, fuera de ámbito o sin Madrid verificado), ENTONCES EL SISTEMA descarta el alternativo, devuelve el error original de ese extremo y no hace más intentos. Si Nominatim falla al geocodificarlo, el estado es `geocodificacion_fallida`. El alternativo solo se usa si el extremo no se resolvió; un texto vacío o que no es texto se ignora.
- RF-21: DONDE se indique `probable_origen` o `probable_destino` (verdadero) junto a `opcion_origen`/`opcion_destino`, EL SISTEMA marca que la opción fue una **elección automática** del LLM: el `mensaje` indica qué se usó y cómo corregirlo (indicar otra opción o una dirección más precisa). Todas las notas de «qué se usó» (opción elegida con o sin `probable_*`, y texto alternativo) van también al final de `bloques`. `probable_*` sin opción, o distinto de `true`, se ignora.

#### Prompt de rutas para la capa 2 (T7)

- RF-22: EL LLM de rutas actúa **una sola vez por extremo**, y solo cuando el turno anterior ya devolvió ese extremo como no válido (ambiguo o no encontrado) y la nueva entrada de la persona tampoco lo resuelve.
- RF-23: SI hay candidatos mostrados, ENTONCES el LLM elige solo entre ellos (`opcion_*` con `probable_*` verdadero); con confianza baja vuelve a preguntar a la persona.
- RF-24: SI hubo 0 candidatos, ENTONCES el LLM propone **un único** texto alternativo por extremo (`texto_alternativo_*`).

#### «De X al Y» y «en bici» llegan a la herramienta (T10, 2026-10-21)

Diagnóstico (sin llamadas reales): «¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu?» devolvía «Falta indicar el destino» sin llamar a ninguna tool, porque el atajo `_aclaracion_formulacion_incompleta` (`rutas.py`) solo reconocía «a» como separador y buscaba la **última** aparición. «Como puedo ir en bici desde Cibeles hasta Plaza de España?» no pasa por ese atajo: el LLM de rutas lo rechazaba («solo transporte público») porque `PROMPT_RUTAS` no dice nada de bici (el rechazo no está en el código).

- RF-31: EL ATAJO de aclaración de extremos de `rutas` acepta «a», «al» y «hasta» como separador del destino y parte por la **primera** aparición. Con separador y texto a ambos lados no devuelve aviso y la petición llega al LLM y a la herramienta; sin texto tras el separador («voy de Sol a», «voy de Sol al»), o sin él, sigue devolviendo el aviso de destino que falta. Si el separador es lo primero («voy de al Sol»), falta el origen.
- RF-32: SI la persona pide ir en bici (o en BiciMAD) con origen y destino, ENTONCES `PROMPT_RUTAS` indica solicitar `planificar_ruta` igualmente y que el `final` copie lo que devuelva la herramienta (ruta de transporte, alternativa en BiciMAD si procede o el motivo por el que no se ofrece), sin rechazar la petición por ser en bici. No hay listas ni ejemplos de títulos (spec 004, RF-35 y RF-50).

#### Correcciones de la prueba real (T11, 2026-10-21)

- RF-33: EL SINTETIZADOR solo fuerza los `bloques` y avisos de los resultados de `planificar_ruta` del **turno actual**. `resultados` acumula toda la conversación (reducer `acumular_listas`, sin reinicio); no tenía marca de turno. Ahora cada resultado que añade un especialista lleva `turno` = nº de mensajes de la persona en `historial` (no cambia al reanudar tras el HITL) y el sintetizador ignora los de otros turnos. Los resultados sin marca (conversaciones guardadas antes, dobles de tests) se incluyen como hasta ahora. El LLM del sintetizador sigue viendo todos los resultados.
- RF-34: SI entre los candidatos dentro de la caja de cobertura hay alguno de la Comunidad de Madrid verificado (`verificar_candidato`), ENTONCES solo ellos entran en la lista de «Opciones» y en la elección (`opcion_*`); uno solo se elige sin preguntar. Sin ningún candidato verificado no se filtra nada y el error lo da después la verificación (RF-55 de la spec 004). Causa: `AMBITO_COBERTURA` es una caja (39,88–41,17 N; −4,58–−3,05 E) que incluye partes de Guadalajara, Toledo, Segovia…, y la verificación de Madrid solo se aplicaba al candidato ya elegido: «Puerta del Sol, Galápagos, Guadalajara» salía como opción 2 y, al elegirla, `verificar_candidato` la rechazaba («no se pudo verificar que la dirección esté en la Comunidad de Madrid»).

#### Certificados de Open-Meteo (T12, 2026-10-21)

- RF-35: LA consulta del clima (Open-Meteo, y solo ella) verifica el certificado del servidor con el bundle de `certifi` cuando `certifi` es importable, y con el contexto por defecto de Python si no. La verificación del certificado y del nombre del servidor siempre está activa: nunca se usa `CERT_NONE`, `check_hostname = False` ni un contexto sin verificar. La EMT y Google no cambian. Motivo: en Windows, el contexto por defecto usa el almacén del sistema y Open-Meteo fallaba con `CERTIFICATE_VERIFY_FAILED: certificate has expired`; con el bundle de `certifi` responde HTTP 200 (2 llamadas reales de diagnóstico, 2026-10-21).
- **Dependencias (art. 12):** se añade `certifi` a `requirements.txt`. Ya estaba instalado como dependencia transitiva de `httpx` y `requests`; ahora se declara. Ninguna otra.

#### Precio en dos intentos (T13, 2026-10-21)

Medición con el RAG real (10 llamadas en total, ver `validacion.md`): el precio de «abono joven» y el de «billete sencillo» **se abstienen siempre que la pregunta los condiciona a una zona** («en la zona A», «zona A precio», «en Madrid»), y se contestan sin zona: «¿Cuánto cuesta el abono joven?» da 20,00 € y 10,00 €; «¿Cuánto cuesta el billete sencillo?» da una tabla (ordinario 1,50 / 1,80 / 2,00 €, y por discapacidad y familia numerosa, «según las tablas vigentes para 2026 para Metro Zona A y ML1»). El RAG añade matices que el corpus no desambigua (tres importes por categoría), pero el texto es utilizable y se entrega tal cual.

- RF-36: LA primera pregunta de precio al RAG es `¿Cuánto cuesta el {titulo}?`, **sin zona** (`PREGUNTA_PRECIO`). Se hace aunque la zona no se haya podido determinar; no se hace si el título no es interpretable (RF-48 de la spec 004).
- RF-37: SI la primera pregunta de precio se abstiene (`sin_evidencia`) y se dispone de la zona (estado `ok`, saneada, de longitud ≤ `ZONA_LONGITUD_MAX`), ENTONCES EL SISTEMA hace un segundo intento con zona: `Tarifa y precio del {titulo} {zona}` (`PREGUNTA_PRECIO_CON_ZONA`, la formulación que mejor funcionó con zona). Un error del RAG en el primer intento (excepción) no provoca segundo intento. Si ambos se abstienen, el precio es `sin_evidencia`.
- RF-38: EL SISTEMA realiza como máximo **3** llamadas al RAG por consulta de ruta: zona, precio y, solo tras una abstención, precio con zona. Sin reintentos.

#### Contexto del sintetizador y seguimiento (T14, 2026-10-21)

Problema: con resultados de `planificar_ruta` la respuesta era el resumen del LLM más los `bloques` literales; el LLM parafraseaba los bloques (el filtro «ya está en la respuesta» es textual) y se repetían; además veía resultados de turnos anteriores y los resumía como actuales. Se mantiene el LLM (RF-20 de la spec 005 intacto).

- RF-39: EL CONTEXTO que recibe el LLM del sintetizador no contiene el texto de los `bloques` que luego se añaden literales: se quita la clave `bloques` de cada resultado de `planificar_ruta` y las apariciones de cada bloque en su `mensaje` y en las `notas`. CUANDO hay bloques, el contexto lleva además la clave `nota`: «Zona, precio, clima, bici y opciones se añaden después de forma automática; no los repitas ni los resumas.» Los bloques se siguen añadiendo al final (RF-13). Sin bloques, el contexto no cambia (sin `nota`). El respaldo determinista y los avisos usan el contexto completo, sin modificar. No se toca `modelos.py`: la nota viaja en el contexto anclado.
- RF-40: EL CONTEXTO que recibe el LLM solo incluye los `resultados` del turno actual (marca `turno`, RF-33); los de turnos anteriores no se le pasan. Los resultados sin marca se incluyen como hasta ahora. Límite: `notas` y `traza` no llevan marca de turno y se pasan enteras.
- RF-41: `PROMPT_RUTAS` indica que, en una pregunta de seguimiento sobre la misma ruta («¿y cómo puedo ir en bici?»), se pide `planificar_ruta` con los mismos textos de origen y destino, las mismas opciones elegidas (`opcion_origen`/`opcion_destino` si la persona eligió con un número) y el mismo `titulo` del historial. Sin listas ni ejemplos de títulos (spec 004, RF-35 y RF-50).

**T14, punto 2 — la versión determinista no se aplicó por conflicto; se aplica la alternativa (T15, RF-42 y RF-43) que mantiene el LLM.** Versión descartada: que tras aprobar el plan el grafo solo confirme de forma breve y determinista, sin invocar al sintetizador. Tras la aprobación, `aceptar_plan` → `sintetizador_aprobacion` (el mismo nodo con el LLM) → `finalizar_turno`; por eso vuelve a imprimirse el resumen completo, con los mismos resultados del turno y los bloques otra vez. Choca con RF-31 de la spec 005 («devuelve su resultado»), con su plan («sintetizar el resultado aceptado y fijar done=verdadero») y con RF-20 («respuesta sintetizada»), y los tests `test_grafo_hitl.py::test_aprobacion_reanuda_con_command_y_cierra_solo_el_plan_elegido` y `test_clientes_grafo_real.py::test_varios_planes_exigen_elegir_y_se_aprueba_solo_el_elegido` fijan que la respuesta tras aprobar sale del sintetizador. Alternativa que respeta RF-20 (propuesta, no aplicada): mantener el LLM, pero cuando hay `plan_aprobado` pasarle una `nota` de «el plan ya se mostró; confirma brevemente la aprobación sin repetir la ruta» y no añadir los bloques (ya se mostraron).

#### Confirmación tras aprobar el plan (T15, 2026-10-21)

Causa del resumen repetido: tras `pausa_hitl`, `aceptar_plan` conserva el plan y `sintetizador_aprobacion` (el mismo `nodo_sintetizador` con el LLM) sintetiza otra vez con los mismos resultados del turno y vuelve a añadir los bloques y avisos.

- RF-42: EN la rama de aprobación del plan (nodo `sintetizador_aprobacion`), EL SINTETIZADOR (mismo nodo, con el LLM) recibe en el contexto la `nota` «El plan ya se mostró; confirma brevemente la aprobación sin repetir la ruta.» (en lugar de la de RF-39), con los textos de los `bloques` quitados como en RF-39, y su respuesta se devuelve tal cual: **no se añaden bloques ni avisos**. Si el LLM falla, el respaldo es el de siempre (RF-56 de la spec 005).
- RF-43: LA rama de aprobación se identifica por el nodo que sintetiza, no por `plan_aprobado`: ese campo no se borra después y seguiría puesto en los turnos siguientes de la conversación. Sin aprobación (turnos normales, aunque `plan_aprobado` siga en el estado) nada cambia: nota de RF-39 y bloques y avisos al final. Con varios planes pendientes sigue exigiéndose elegir uno (RF-47 de la spec 005): sin selector no se reanuda ni se sintetiza.

Tensión con la spec 005, asumida: RF-31 pide que la aprobación «devuelva su resultado»; la respuesta confirma la aprobación sin repetir la ruta. El plan elegido sigue disponible en `plan_aprobado` y en las notas del contexto del LLM.

#### Elección tras una ambigua, duplicados y clima solo si la bici es posible (T16, 2026-10-22)

Diagnóstico (logs reales, sin llamadas nuevas): (1) Streamlit «Plaza de Cataluña → Sol» mostró dos opciones idénticas («Puerta del Sol») y la respuesta «2 y 2» fue a `calculadora`: el `historial` solo guarda los mensajes de la persona (`_registrar_mensaje`, `src/graph.py`), así que el supervisor y el LLM de rutas no ven las opciones y «2 y 2» parece una suma; el LLM de rutas, sin saber qué extremo era el ambiguo, volvió a llamar sin `opcion_*` (o con una que no cuadraba) y la herramienta devolvió otra vez `ambigua`. (2) CLI «Plaza Castilla → Rivas»: «Rivas» y «Rivas-Vaciamadrid» (mismo municipio) a más de `RADIO_MISMA_UBICACION_M` no se fusionaron. (3) El clima se consulta antes de comprobar la distancia de la bici (R2), por eso salieron a la vez `CLIMA_SIN_DATO_AVISO` y «fuera de rango». (4) `clima_origen` solo registra en el log las excepciones; un HTTP distinto de 200 o datos incompletos devuelven `no_disponible` sin dejar rastro.

- RF-44: EL SISTEMA trata como **el mismo lugar** dos candidatos (y deja el primero, el mejor clasificado por Nominatim) si: (a) están a ≤ `RADIO_MISMA_UBICACION_M` (como hasta ahora); o (b) su `direccion` es idéntica sin distinguir mayúsculas, tildes ni espacios (la persona no puede distinguirlos); o (c) ambos tienen el mismo `municipio` y el primer componente de su `direccion` (antes de la primera coma), normalizado (sin mayúsculas ni tildes, guiones como espacios), es el nombre del municipio o su comienzo por palabras completas («Rivas» → «Rivas-Vaciamadrid»). El criterio (c) no usa umbral numérico: los dos representan el **propio municipio** con otra etiqueta; las calles o lugares del municipio («Calle de Rivas», «Plaza Mayor») no lo cumplen. Se aplica después del filtro de la Comunidad de Madrid (RF-34): si queda un único lugar, el extremo no es ambiguo.
- RF-45: SI el último resultado de `planificar_ruta` de la conversación es `ambigua` y es del turno anterior (marca `turno`; sin marca se acepta), Y el mensaje solo contiene números de opción con, como mucho, las palabras «y», «e», «la», «el», «las», «los», «opción/opciones», «número», «origen», «destino», «para», «en» y puntuación, ENTONCES EL SUPERVISOR encola solo `rutas`, sin llamar al LLM ni a las reglas por palabras. Ejemplos: «2 y 2», «1», «la 2 y la 1», «origen 2, destino 1».
- RF-46: EN ese caso, EL ESPECIALISTA de rutas no llama al LLM: repite `planificar_ruta` con los argumentos del resultado ambiguo (mismos textos originales, horas y `titulo`, sin `opcion_*` anteriores, `probable_*` ni `texto_alternativo_*`) y las opciones así: con etiquetas «origen N»/«destino M», cada una a su extremo; sin etiquetas y dos números «N y M», `opcion_origen=N` y `opcion_destino=M` (una opción en un extremo no ambiguo la ignora la herramienta, como hasta ahora); un solo número, al extremo ambiguo si solo hay uno. Si los dos extremos eran ambiguos y llega un solo número, o hay más de dos números, no se interpreta y se sigue el flujo normal (LLM).
- RF-47: EL SISTEMA solo consulta el clima si se podría ofrecer la bici por las reglas sin red: sin hora pedida (R1) y con la distancia en el rango de la bici (R2, `BICI_DISTANCIA_MIN_M` a `BICI_DISTANCIA_MAX_M`). Si la bici se rechaza por distancia, no hay consulta a Open-Meteo, ni línea del clima, ni `CLIMA_SIN_DATO_AVISO`, ni `LESS_WALKING`; `bloques` lleva solo el motivo de R2. `CLIMA_SIN_DATO_AVISO` solo aparece cuando la bici sigue su flujo con el clima no disponible.
- RF-48: SI la consulta del clima no da un dato utilizable, ENTONCES EL SISTEMA registra en el log una **categoría** de causa: `sin_coordenadas`, `http_<código>`, `respuesta_invalida`, `datos_incompletos`, `timeout`, `tls`, `red` o `error` (otra excepción), más el tipo de la excepción y, en un `URLError`, su `reason` (RF-11). Nunca la URL, las coordenadas, claves ni el cuerpo de la respuesta.

### Cambios explícitos sobre specs anteriores

- **Spec 004, RF-27** («no asume ninguna ubicación por defecto para el origen ni el destino»): **se revierte conscientemente en la Fase B** (RF-21 a RF-24). Con la capa 2, el LLM puede elegir una opción o proponer un texto alternativo cuando la entrada no es válida por segunda vez. Siempre se declara qué se usó y cómo corregirlo. En Fase A no cambia.
- **Spec 004, RF-8** (ambigua: no se calcula, se muestran candidatos): se mantiene en Fase A. En Fase B, la elección de la capa 2 es el único caso en que se calcula una ruta con un extremo que fue ambiguo sin elección explícita de la persona.
- **Spec 009, RF-25** («sin dato de clima no se ofrece bici»): **cambia** (RF-10): con el clima no disponible, la bici se ofrece con un aviso. **Spec 009, RF-23** se mantiene para el mal tiempo (RF-9).
- **Spec 009, RF-4, RF-13 y RF-16** (el `mensaje` solo habla de la bici en R3/R4/no disponible/ok): el `mensaje` no añade nada nuevo salvo que la frase de «no disponible» es ahora la de su causa (RF-27); los motivos de R0, R1 y R2 viajan solo en `bloques` (RF-7).
- **Spec 004, RF-49** (como máximo 2 llamadas al RAG): pasa a 3 (RF-38). **RF-52** (sin zona no se consulta el precio): el precio se consulta igualmente, porque la pregunta ya no depende de la zona (RF-36); sin zona no hay segundo intento. **RF-53** (el texto de zona entra en la pregunta de precio y, si supera `ZONA_LONGITUD_MAX`, no se consulta el precio): ahora solo condiciona el segundo intento (RF-37). **RF-46** (el precio se pregunta con la zona): el primer intento es sin zona.
- **Spec 009, RF-20 y RF-22** (sin hora pedida se consulta el clima y, si no es apto, la ruta se pide con `LESS_WALKING`): **cambia** por RF-47: en trayectos fuera del rango de la bici no se consulta el clima, no hay línea del tiempo y la ruta en transporte público se pide sin `LESS_WALKING` aunque llueva. **Spec 010, RF-8 y caso límite «Clima no disponible y mal trayecto para bici (distancia…)»**: con la distancia fuera de rango ya no conviven las dos líneas (sí con R3/R4, que se deciden tras la EMT).
- **Spec 004, RF-8 y RF-10** (ambigua con candidatos distintos; mismo punto a ≤ 100 m): se amplía la deduplicación (RF-44).
- **Spec 005, supervisor** (decide el LLM y, si falla, las reglas): tras una ambigua, una respuesta solo con números decide `rutas` de forma determinista (RF-45).
- **Spec 009, contrato de `bici`**: gana el campo aditivo `causa` en `no_disponible` (RF-27); los tests que comparaban el dict completo se ajustaron.

## Requisitos no funcionales

- **Coste.** Nominatim ≤ 2, Google ≤ 1 + 3 de bici, RAG ≤ 3 (RF-38; antes 2), EMT ≤ 2, Open-Meteo ≤ 1. Fase B sube Nominatim a ≤ 4 (RF-19).
- **Secretos.** Ni claves ni tokens en el resultado, en `bloques`, en la traza ni en el log (RF-11, RF-15).
- **Tests.** Ninguno llama a Nominatim, Google, EMT, Open-Meteo, RAG ni LLM: dobles (`tests/dobles_ruta.py::Escenario`, modelo falso del sintetizador).
- **Dependencias.** Solo `certifi` (RF-35), que ya estaba instalado. Configuración (textos fijos) en `config.py`.
- **Idioma.** Español.

## Casos límite

- Texto igual a un prefijo («Metro», «Estación de»): no cambia (RF-2).
- «Metropolitano», «Metrosur»: no empiezan por el prefijo «metro» como palabra completa; no cambian (RF-1).
- «Metro de Madrid» pierde «Metro» y queda «de Madrid»: se acepta, no es un lugar que se pregunte por nombre (RF-1).
- «Parada de metro X» pierde solo «Parada de» y queda «metro X» (una sola pasada, RF-1).
- Ruta ambigua en un extremo y no encontrada en el otro: `bloques` lleva las dos frases (RF-5).
- Varias rutas en un turno (replanificación): el sintetizador añade los bloques de cada una sin repetir textos idénticos (RF-13, RF-14).
- Resultado de la herramienta que no es JSON (`ERROR: no se pudo ejecutar planificar_ruta.`): se ignora en el volcado (RF-15).
- Clima no disponible y mal trayecto para bici por estaciones (R3/R4): la línea de RF-10 y el motivo de la bici conviven en `bloques` (RF-7, RF-8). Por distancia (R2) no se consulta el clima (RF-47).

## Fuera de alcance

- **Fase C**: consultar las paradas del corpus (nombre, tipo, zona y dirección) y geocodificar su dirección; ver `plan.md`.
- Tool de geocodificación propia, salida estructurada del sintetizador y marca estable contra duplicados por paráfrasis (T8, mejoras futuras).
- Un **modo de viaje solo bici** (ruta en bici de punta a punta, sin transporte público): ver «Mejoras futuras» en `validacion.md`.
- Cambiar `modelos.py`, `catalogo_roles.py`, `supervisor_reglas.py`, el grafo, el RAG, el corpus o `output/chunks.json`.
- Forzar por código el `mensaje` de `sin_ruta` («no hay ruta disponible…»).

## Criterios de finalización

- Fase A (RF-1 a RF-18 y RF-25 a RF-28), Fase B (RF-19 a RF-24) y las correcciones posteriores (RF-29 a RF-35) con test en verde (`python -m pytest`, sin API).
- No hay demos reales en esta spec: la comprobación real queda para una validación posterior autorizada.

## Dudas abiertas

### Cerradas el 2026-10-21 (T5b)

- [CERRADA] Fallos de EMT y Google en una sola frase → `causa` y frase por causa (RF-27).
- [CERRADA] La «opción usada» no estaba en `bloques` → ahora sí (RF-21).
- [CERRADA, salvo `sin_ruta`] Zona, precio y mensaje de `ruta_no_calculada` → RF-25 y RF-26. `sin_ruta` sigue sin forzarse.

### Pendientes

- [PARCIAL, T9 — la ficha de `rutas` no bastaba para el supervisor; RF-29 y RF-30 cubren la ruta con precio, falta el seguimiento «¿y cuánto cuesta?»] Ver `validacion.md` («Dudas»). Resumen: `instrucciones_para_supervisor` sigue diciendo «Una consulta textual de tarifa sin imagen debe seleccionar rag», que contradice la nueva línea de la ficha; el fallback por palabras (`supervisor_reglas.py`, no tocado) no reconoce «¿y cuánto cuesta?» y añade `rag` con «tarifa/billete/abono»; y el especialista RAG no ve el historial.
- [DECISIÓN — `causa` = `interno`] RF-27 pedía tres valores; se añade `interno` para el error inesperado (frase genérica de siempre).
- [CERRADA, T12 — Open-Meteo fallaba en Windows con `CERTIFICATE_VERIFY_FAILED: certificate has expired`] Aplicado el RF-35 (contexto con `certifi.where()` solo para Open-Meteo, siempre verificando; `certifi` en `requirements.txt`). Falta una comprobación real con el cliente nuevo (pendiente de autorización).
- [CERRADA, T13 — RF-36 a RF-38; el precio de «abono joven» salía «no disponible» con la zona sí disponible] Diagnóstico en `validacion.md`: la pregunta de precio de la herramienta incluye la zona («…en la zona indicada a continuación? La zona tarifaria es la zona A.») y el RAG **se abstiene** aunque el contexto recuperado menciona «joven»; «¿Cuánto cuesta el abono joven?» (sin zona) sí devuelve 20,00 € / 10,00 €, y «tarifa abono joven zona A» también. El precio del abono joven no depende de la zona en el corpus. La herramienta lo marca «no disponible» porque `_dato_rag` trata la frase de abstención como `sin_evidencia`. Propuesta sin aplicar: cambiar la formulación (ver `validacion.md`).
- [DECISIÓN — RF-32 no da una ruta solo en bici] Quien pide «en bici» recibe la ruta en transporte público y, solo si se cumplen las reglas de la spec 009 (sin hora pedida, 1 a 6 km, buen tiempo o clima no comprobado, estaciones con bicis y huecos), la alternativa en BiciMAD; si no, el motivo en `bloques`.
- [DECISIÓN — RF-30 es heurística] El patrón «verbo + de/desde X a/hasta Y» puede dar falsos positivos (p. ej. «voy a comprar un abono de 30 días a mi hijo» añadiría `rutas`); es inofensivo (el especialista pide origen y destino) pero no es exacto. No hay campo de diagnóstico de la corrección en `DecisionSupervisor` (a diferencia de `correcciones_tarifas`).
- [DECISIÓN — alternativo para extremos no resueltos] Si el extremo es ambiguo y no se eligió opción, el alternativo también se intenta; si no se verifica, el error es el original.

### Anteriores (con su estado)

- [NECESITA ACLARACIÓN — `tarifa_solicitada` duplicaría `titulo`] La herramienta ya tiene el parámetro opcional `titulo` (texto libre, saneado, con «billete sencillo» por defecto) que se incorpora a la pregunta de precio al RAG y a la cabecera. Un parámetro nuevo duplicaría su función. La hipótesis detrás del encargo era que faltaba; lo que falta es que **`PROMPT_RUTAS` lista `titulo?` sin explicarlo**. Decisión provisional: no crear `tarifa_solicitada` y arreglar el prompt (RF-17, RF-18). Si se prefiere el nombre nuevo, es un cambio mecánico (alias de `titulo`) que se haría antes de aprobar.
- [PARCIAL, T5b (c) — «¿y cuánto cuesta?» puede no llegar a `rutas`] El supervisor puede encolar `rag` (por «cuesta», término tarifario) en vez de `rutas`; entonces la regla de RF-18 nunca se ejecuta y el RAG recibe la frase sin contexto. Se arregla con la ficha del rol `rutas` (`catalogo_roles.py`, de Rubén), que queda como mejora futura (T8).
- [CERRADA, T5b — fallos de la bici en una sola frase] RF-7 pide distinguir «EMT no disponible o sin credenciales» de «Google no disponible». Distinguirlos exige un campo nuevo en `bici` (p. ej. `causa`) y modificar tres tests con igualdad exacta del dict `bici`. En Fase A se usa la frase existente («La alternativa en bici (BiciMAD) no está disponible ahora.») para todos.
- [CERRADA, T5b — la «opción usada» no está en `bloques`] La nota de la spec 004 (T24) «Para el origen se usó la opción N…» va en el `mensaje` pero no en `bloques`. En Fase B (RF-21) sí; si se quiere ya en Fase A, es una línea.
- [CERRADA, T5b salvo `sin_ruta` — zona, precio y errores de ruta no se fuerzan] `bloques` no incluye la zona ni el precio del RAG, ni el `mensaje` de `ruta_no_calculada` o `sin_ruta`. El sintetizador puede seguir resumiéndolos. Se deja fuera para no mezclar texto del RAG con bloques fijos.
- [DECISIÓN — `fuera_cobertura`] RF-5 incluye `fuera_cobertura` junto a `ambigua` y `direccion_no_encontrada`: sigue la misma ruta de código y la frase se pierde igual.
