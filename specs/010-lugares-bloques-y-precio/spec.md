# Spec 010 — Lugares, bloques literales y precio en `planificar_ruta`

> Estado: **Borrador** (Fase A implementada 2026-10-21, pendiente de aprobar; Fase B solo especificada) · Fecha: 2026-10-21
> Cambia comportamiento de las specs 004 (RF-27, en Fase B) y 009 (RF-23 y RF-25, en Fase A). Ver «Cambios explícitos sobre specs anteriores». No se edita ninguna spec anterior.

## Contexto y objetivo

Los diagnósticos del 2026-10-21 (sin coste, más una ruta real) detectaron cinco problemas en la consulta de rutas:

- **(a) Bloques que se pierden.** Las «Opciones» de una ruta ambigua, el bloque de bici y la línea del clima no siempre llegan a la persona usuaria: el especialista de rutas reescribe el resultado de la herramienta (`rutas.py`, segunda llamada al LLM) y el sintetizador es un LLM al que solo se le pide «resume» (`modelos.py`). Hoy solo el aviso de Google de la bici y la atribución de Open-Meteo se fuerzan por código (`_avisos_obligatorios`, spec 009).
- **(b) Nominatim y los prefijos.** Con «Metro X» o «Estación de metro X» devuelve 0 resultados; con el nombre solo, sí («Legazpi, Madrid» da 2, «Concha Espina, Madrid» da 7).
- **(c) Bici invisible con el clima caído.** Si Open-Meteo falla (p. ej. `URLError`), la bici desaparece en silencio: sin bici, sin línea y sin motivo.
- **(d) El RAG no ve la conversación.** El especialista del RAG recibe solo el mensaje del turno, sin historial; el de rutas sí recibe historial. Una pregunta posterior «¿y cuánto cuesta?» llega al RAG sin origen ni destino.
- **(e) El corpus ya trae paradas con zona y dirección** (`Paradas CRTM.csv`: Legazpi y Concha Espina figuran en Metro, zona A). Aprovecharlo es la futura Fase C; aquí solo se documenta.

Esta spec se divide en dos fases:

- **Fase A (T1–T5)**, a implementar ya: normalización del texto de los lugares, campo `bloques` y su volcado determinista por el sintetizador, política del clima caído y precio por título pedido.
- **Fase B (T6–T8)**, solo especificada: segunda capa de resolución de ambigüedad con el LLM, acotada y siempre declarada.

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
- RF-7: CUANDO el estado es `ok` y la bici no se ofrece o no está disponible, EL SISTEMA añade a `bloques` **una línea corta con el motivo**: hora pedida (R1), distancia fuera del rango de 1 a 6 km (R2), mal tiempo (R0, con sus motivos), sin bicis en el origen, sin huecos en el destino, misma estación (R3 y R4) o alternativa no disponible (EMT sin credenciales o caída, o Google caído; una sola frase para todos esos fallos).
- RF-8: CUANDO el estado es `ok` y hubo consulta de clima, EL SISTEMA añade a `bloques` la línea del clima (la de RF-24 de la spec 009) o, si el clima no estaba disponible, la línea de RF-10. Orden de `bloques` en `ok`: clima, después bici o motivo (el mismo que en el `mensaje`).

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

### Fase B (solo especificada; sin implementar)

#### Segunda capa de ambigüedad en la herramienta (T6)

- RF-19: DONDE se indique `texto_alternativo_origen` o `texto_alternativo_destino` (un único texto por extremo), EL SISTEMA lo geocodifica con Nominatim (con la normalización de RF-1) y le aplica la verificación de Madrid de RF-55 de la spec 004: +1 llamada a Nominatim por extremo, **como máximo 4 en total**.
- RF-20: SI el texto alternativo no se verifica (0 candidatos, ambiguo, fuera de ámbito o sin Madrid verificado), ENTONCES EL SISTEMA devuelve el error correspondiente sin más intentos.
- RF-21: DONDE se indique `probable_origen` o `probable_destino` (bool) junto a `opcion_origen`/`opcion_destino`, EL SISTEMA marca que la opción fue una **elección automática** del LLM: el `mensaje` indica qué se usó y cómo corregirlo (indicar otra opción o una dirección más precisa), y añade esa frase a `bloques`.

#### Prompt de rutas para la capa 2 (T7)

- RF-22: EL LLM de rutas actúa **una sola vez por extremo**, y solo cuando el turno anterior ya devolvió ese extremo como no válido (ambiguo o no encontrado) y la nueva entrada de la persona tampoco lo resuelve.
- RF-23: SI hay candidatos mostrados, ENTONCES el LLM elige solo entre ellos (`opcion_*` con `probable_*` verdadero); con confianza baja vuelve a preguntar a la persona.
- RF-24: SI hubo 0 candidatos, ENTONCES el LLM propone **un único** texto alternativo por extremo (`texto_alternativo_*`).

### Cambios explícitos sobre specs anteriores

- **Spec 004, RF-27** («no asume ninguna ubicación por defecto para el origen ni el destino»): **se revierte conscientemente en la Fase B** (RF-21 a RF-24). Con la capa 2, el LLM puede elegir una opción o proponer un texto alternativo cuando la entrada no es válida por segunda vez. Siempre se declara qué se usó y cómo corregirlo. En Fase A no cambia.
- **Spec 004, RF-8** (ambigua: no se calcula, se muestran candidatos): se mantiene en Fase A. En Fase B, la elección de la capa 2 es el único caso en que se calcula una ruta con un extremo que fue ambiguo sin elección explícita de la persona.
- **Spec 009, RF-25** («sin dato de clima no se ofrece bici»): **cambia** (RF-10): con el clima no disponible, la bici se ofrece con un aviso. **Spec 009, RF-23** se mantiene para el mal tiempo (RF-9).
- **Spec 009, RF-4 y RF-16** (el `mensaje` solo habla de la bici en R3/R4/no disponible/ok): el `mensaje` no cambia; los motivos de R0, R1 y R2 viajan solo en `bloques` (RF-7).

## Requisitos no funcionales

- **Coste.** Sin cambios en Fase A: Nominatim ≤ 2, Google ≤ 1 + 3 de bici, RAG ≤ 2, EMT ≤ 2, Open-Meteo ≤ 1. Fase B sube Nominatim a ≤ 4 (RF-19).
- **Secretos.** Ni claves ni tokens en el resultado, en `bloques`, en la traza ni en el log (RF-11, RF-15).
- **Tests.** Ninguno llama a Nominatim, Google, EMT, Open-Meteo, RAG ni LLM: dobles (`tests/dobles_ruta.py::Escenario`, modelo falso del sintetizador).
- **Dependencias.** Ninguna nueva. Configuración (textos fijos) en `config.py`.
- **Idioma.** Español.

## Casos límite

- Texto igual a un prefijo («Metro», «Estación de»): no cambia (RF-2).
- «Metropolitano», «Metrosur»: no empiezan por el prefijo «metro» como palabra completa; no cambian (RF-1).
- «Metro de Madrid» pierde «Metro» y queda «de Madrid»: se acepta, no es un lugar que se pregunte por nombre (RF-1).
- «Parada de metro X» pierde solo «Parada de» y queda «metro X» (una sola pasada, RF-1).
- Ruta ambigua en un extremo y no encontrada en el otro: `bloques` lleva las dos frases (RF-5).
- Varias rutas en un turno (replanificación): el sintetizador añade los bloques de cada una sin repetir textos idénticos (RF-13, RF-14).
- Resultado de la herramienta que no es JSON (`ERROR: no se pudo ejecutar planificar_ruta.`): se ignora en el volcado (RF-15).
- Clima no disponible y mal trayecto para bici (distancia, estaciones): la línea de RF-10 y el motivo de la bici conviven en `bloques` (RF-7, RF-8).

## Fuera de alcance

- **Fase C**: consultar las paradas del corpus (nombre, tipo, zona y dirección) y geocodificar su dirección; ver `plan.md`.
- Tool de geocodificación propia, salida estructurada del sintetizador y marca estable contra duplicados por paráfrasis (T8, mejoras futuras).
- Cambiar `modelos.py`, `catalogo_roles.py`, `supervisor_reglas.py`, el grafo, el RAG, el corpus o `output/chunks.json`.
- Forzar por código el `mensaje` de `ruta_no_calculada` y `sin_ruta`, la zona y el precio (ver «Dudas abiertas»).

## Criterios de finalización

- Fase A: RF-1 a RF-18 con test en verde (`python -m pytest`, sin API).
- Fase B: solo documentada en spec, plan y tareas; sin código.
- No hay demos reales en esta spec: la comprobación real queda para una validación posterior autorizada.

## Dudas abiertas

- [NECESITA ACLARACIÓN — `tarifa_solicitada` duplicaría `titulo`] La herramienta ya tiene el parámetro opcional `titulo` (texto libre, saneado, con «billete sencillo» por defecto) que se incorpora a la pregunta de precio al RAG y a la cabecera. Un parámetro nuevo duplicaría su función. La hipótesis detrás del encargo era que faltaba; lo que falta es que **`PROMPT_RUTAS` lista `titulo?` sin explicarlo**. Decisión provisional: no crear `tarifa_solicitada` y arreglar el prompt (RF-17, RF-18). Si se prefiere el nombre nuevo, es un cambio mecánico (alias de `titulo`) que se haría antes de aprobar.
- [NECESITA ACLARACIÓN — «¿y cuánto cuesta?» puede no llegar a `rutas`] El supervisor puede encolar `rag` (por «cuesta», término tarifario) en vez de `rutas`; entonces la regla de RF-18 nunca se ejecuta y el RAG recibe la frase sin contexto. Se arregla con la ficha del rol `rutas` (`catalogo_roles.py`, de Rubén), que queda como mejora futura (T8).
- [NECESITA ACLARACIÓN — fallos de la bici en una sola frase] RF-7 pide distinguir «EMT no disponible o sin credenciales» de «Google no disponible». Distinguirlos exige un campo nuevo en `bici` (p. ej. `causa`) y modificar tres tests con igualdad exacta del dict `bici`. En Fase A se usa la frase existente («La alternativa en bici (BiciMAD) no está disponible ahora.») para todos.
- [NECESITA ACLARACIÓN — la «opción usada» no está en `bloques`] La nota de la spec 004 (T24) «Para el origen se usó la opción N…» va en el `mensaje` pero no en `bloques`. En Fase B (RF-21) sí; si se quiere ya en Fase A, es una línea.
- [NECESITA ACLARACIÓN — zona, precio y errores de ruta no se fuerzan] `bloques` no incluye la zona ni el precio del RAG, ni el `mensaje` de `ruta_no_calculada` o `sin_ruta`. El sintetizador puede seguir resumiéndolos. Se deja fuera para no mezclar texto del RAG con bloques fijos.
- [DECISIÓN — `fuera_cobertura`] RF-5 incluye `fuera_cobertura` junto a `ambigua` y `direccion_no_encontrada`: sigue la misma ruta de código y la frase se pierde igual.
