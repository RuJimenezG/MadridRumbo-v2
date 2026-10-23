# Informe de decisiones — MadridRumbo (Project Break 2)

> Grupo 3: Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.
> Este borrador recoge la parte de **José Manuel Gil Ruiz**: tool auxiliar de hora y su especialista, tool multimodal y calculadora (secciones 1 a 5) y los clientes CLI y Streamlit (sección 6). La parte de **Guzmán López Barceló** (la tool `planificar_ruta`, el especialista de rutas, la alternativa BiciMAD y el clima) está en las secciones 1 a 3, 5, 7 y 8 y, con más detalle, en la sección 9. Las secciones del grafo y el RAG las completa Rubén. La sección 8 incorpora las decisiones de alto impacto aprobadas en las specs de todo el proyecto. Actualizado el 2026-10-23.

## 0. Ampliación del alcance

Se ha decidido ampliar el alcance del proyecto. Originalmente este se restringía a tarifas y normativa relacionada con la red de transporte del Consorcio Regional de Transportes de Madrid. Al convertir el proyecto de un sistema RAG a otro multiagente las posibilidades de resolución de consultas se amplían enormemente, permitiendo ampliar el alcance a la consulta de rutas, horarios e información relacionada con el viaje.

## 1. Grafo: especialistas y momento HITL

### Especialistas de esta parte

| Especialista | Para qué existe | Tools permitidas |
|---|---|---|
| `horarios` | Preguntas sobre cuándo, a qué hora y hasta cuándo hay servicio. Combina la hora actual con los horarios del corpus. | `hora_actual`, `rag_ask` |
| `tarifas` | Lee los textos e importes de una imagen de tarifas. La cuenta la hace el especialista `auxiliar` (Rubén, spec 005). | `describir_imagen` |

**Por qué estos dos.** Una pregunta como «¿puedo coger el metro ahora?» depende de la hora y el día, un dato que el LLM no puede conocer. Una pregunta como «¿cuánto cuestan 3 billetes?» pide una cuenta exacta, que tampoco se le debe dejar hacer de cabeza. Separar ambos casos da a cada especialista un prompt corto y unas tools acotadas, y cumple el requisito de al menos dos especialistas. Cuando se integró el grafo, Rubén repartió el flujo de la imagen: en mi versión `tarifas` leía la imagen y calculaba; ahora `tarifas` solo extrae los importes y `auxiliar` (`hora_actual` y `calculadora`) hace la operación, lo que deja cada especialista con una única responsabilidad.

**Cómo funcionan.** Los dos comparten un mini-bucle (`src/agents/base.py`): el LLM propone una tool o una nota final, y el código decide qué se ejecuta. Los límites están en Python y no en el LLM:
- Solo se ejecutan las tools de la lista del especialista (`TOOLS_POR_ESPECIALISTA`). Una tool inventada o ajena se bloquea y queda en la traza como «bloqueada».
- Máximo `MAX_STEPS_ESPECIALISTA` (3) tools por turno; al llegar al tope devuelve lo obtenido.
- Si el LLM falla o responde algo no interpretable, la nota es un error controlado, sin excepción.
- El especialista devuelve solo `notas` y `traza`. **Nunca decide `done`**: eso corresponde al grafo y al humano.

**Fallback del supervisor.** `elegir_rol_por_palabras` (spec 001; hoy generalizado por `elegir_roles_por_reglas`, que encadena varios roles) deriva a `horarios` los mensajes con términos como hora, horario, ahora, hoy, noche, última, primera, abre, cierra o frecuencia (sin distinguir mayúsculas ni acentos). Si no hay coincidencia devuelve `None` y decide el siguiente criterio.

**Momento HITL.** En el grafo real (spec 005) la pausa ocurre **solo cuando hay un plan de ruta pendiente**: el nodo `pausa_hitl` detiene el grafo antes de aplicarlo y solo una aprobación humana da `done=True`. Las consultas de horarios y del RAG se responden y cierran directamente, sin pausa. Mis especialistas no cierran el plan: solo aportan notas antes de la síntesis. Es una decisión de diseño razonable (solo lo que tiene efecto práctico, un plan de viaje, pide confirmación), aunque implica que el HITL solo se vea con rutas.

### Especialista de rutas

| Especialista | Para qué existe | Tools permitidas |
|---|---|---|
| `rutas` | Cómo ir de un origen a un destino, con duración, zona y precio. | `planificar_ruta` |

**Por qué existe.** Un itinerario necesita coordenadas, tiempos y precios que salen de servicios externos y del RAG; el LLM no puede conocerlos ni estimarlos. Por eso el especialista no calcula nada: llama a `planificar_ruta` y entrega el resultado tal cual, sin reescribirlo. Si un lugar es ambiguo, copia las opciones y espera la elección de la persona.

**Cómo encaja en el grafo.** Es el único especialista cuyo resultado genera un plan sujeto a HITL. Para no depender solo del LLM, el supervisor tiene dos reglas deterministas en Python: si el mensaje trae un origen y un destino, añade `rutas` aunque el modelo no la haya elegido, y una respuesta con números tras una ambigüedad («2 y 1») va directa a `rutas` sin pasar por el modelo. La segunda regla nació de un fallo real: el supervisor tomó «2 y 2» por una suma y llamó a la calculadora.

## 2. Tools: qué hace cada una y cómo se enchufa el RAG

Todas viven en `src/tools/` y se ejecutan a través de `ejecutar_tool(nombre, args, traza)`, que aplica la allowlist `TOOLS_PERMITIDAS` y registra en la traza el nombre, los argumentos, el estado (ok, error o bloqueada) y un extracto del resultado.

| Tool | Tipo | Qué hace |
|---|---|---|
| `hora_actual` | Auxiliar determinista | Devuelve fecha, hora, día de la semana y tipo de día (laborable, sábado o domingo) en la zona horaria configurada (`Europe/Madrid`). Sin red ni LLM. |
| `calculadora` | Auxiliar determinista | Evalúa `+ - * /`, paréntesis y signo menos con decimales con coma o punto. Usa `ast` y `Decimal`, **sin `eval`**: cualquier otra cosa (funciones, potencias, nombres) da un error controlado. Resultado con máximo 2 decimales. |
| `describir_imagen` | Multimodal | Lee una imagen de `assets/` con Gemini y devuelve en español los textos y cifras visibles, sin inventar. |
| `rag_ask` | RAG | Delega en `rag.responder.rag_ask`. |
| `planificar_ruta` | API externa + RAG | Convierte origen y destino en coordenadas (Nominatim), pide el itinerario en transporte público (Google Routes) y consulta al RAG la zona y el precio. Si procede, añade una alternativa en BiciMAD (EMT) y el tiempo en el origen (Open-Meteo). Si falla la parte de BiciMAD o el clima, la ruta de transporte llega igual con un aviso. |

**Seguridad de `describir_imagen`.** Solo lee archivos dentro de `assets/` (rutas como `../.env` o absolutas se rechazan), solo JPG, JPEG y PNG, y con un máximo de 4 MB. Si el modelo falla, devuelve `ERROR:` sin inventar contenido. Un error temporal (503, 429 o de red) se reintenta **una vez** tras 2 segundos, y la causa real del fallo (tipo, código y estado, nunca el mensaje completo ni la clave) queda en el registro; el agente sigue viendo el mensaje genérico para no filtrar detalles internos (ver el fallo 1 de la sección 5).

**Cómo se enchufa el RAG.** El especialista llama a `rag_ask` como una tool más de la allowlist; el RAG no se sustituye. Si no hay evidencia, el RAG se abstiene («No lo sé, no está en los documentos.») y el especialista lo refleja en su nota sin inventar horarios ni precios. El RAG ya está integrado en `develop`; la `rag_ask` real todavía no se ha ejercitado con el índice generado y Gemini (el índice no existe en mi máquina: ver el fallo 7).

**`planificar_ruta` y el RAG.** En las rutas el RAG no se expone al especialista: lo llama la propia tool (spec 004, RF-19). La zona se consulta primero. El precio se pregunta antes sin la zona y, solo si el RAG se abstiene, con ella (máximo tres consultas al RAG por ruta), porque con la zona incluida en la pregunta el RAG tendía a abstenerse. Lo que el RAG no sabe no se estima: el bloque de la respuesta dice que no se pudo determinar.

## 3. HITL: una aprobación y un rechazo

Observado con el **grafo real** (`src/agent.py`) y la parte de modelos, especialistas y tools sustituida por dobles de prueba, sin gastar API (`tests/test_clientes_grafo_real.py`, PR de los clientes). No es una demostración con las APIs reales: eso sigue pendiente (sección 5, fallo 7).

**Una aprobación.** Pedido: «Dame una ruta de Atocha a Sol.» El supervisor elige `rutas`, el grafo se pausa y devuelve el plan `ruta-1` (metro línea 1, 12 min) con `hitl_pendiente=True` y `done=False`. Al aprobarlo el grafo da `done=True`, vacía los planes pendientes y la conversación puede continuar en el mismo `thread_id`.

**Un rechazo.** Mismo pedido: al rechazar `ruta-1` el grafo **replanifica en el mismo hilo** con los mismos argumentos y propone `ruta-2` (autobús línea 27, 20 min), de nuevo con `hitl_pendiente=True` y `done=False`. El supervisor se ejecutó una sola vez y el especialista de rutas dos. Aprobar `ruta-2` cierra la conversación.

**Con las APIs reales.** Pedido: «¿Cómo voy de Puerta del Sol al Estadio Santiago Bernabéu y cuánto cuesta el abono joven?». El sistema pidió aclarar un lugar con varias opciones, elegí la `1`, apareció el plan `ruta-1` con zona, precio, clima y alternativa en BiciMAD, y lo aprobé con `s`. Un seguimiento («¿y cómo puedo ir en bici?») reutilizó la opción elegida y el título «abono joven», pero **creó un segundo plan idéntico** y el ya aprobado volvió a aparecer junto al nuevo, así que el CLI pedía elegir entre `ruta-1` y `ruta-2`. El rechazo con las APIs reales queda pendiente de probar.

**Qué observé que no esperaba.**
- Con **varios planes a la vez**, `aprobar_plan` exige indicar cuál (`plan_id_seleccionado`). Sin identificador, el grafo responde con un aviso y deja `hitl_pendiente=False` aunque el plan siga pendiente; por eso los clientes no llaman al grafo sin elección.
- Un mensaje nuevo con un plan pendiente no ejecuta ningún nodo: el grafo devuelve un aviso y conserva el plan.
- **El rechazo no descarta sin más: replanifica.** Los clientes deben mostrar el nuevo plan en lugar de volver al chat.

## 4. Multimodal: imagen usada y resultado

**Imagen.** `assets/imagen_demo.jpg` (800 x 260 px): captura de la sección «Billetes de autobuses EMT» de [RedTransporte](https://www.redtransporte.com/madrid/precios-abonos.html), tomada el 2026-10-14. Contiene cuatro precios:

| Concepto | Importe |
|---|---|
| Billete sencillo EMT | 1,50 € |
| Billete sencillo TransBus | 1,80 € |
| Billete Exprés Aeropuerto | 5,00 € |
| Metrobús 10 viajes | 7,30 € |

**Por qué esta imagen.** Se probó antes con el plano nocturno de la EMT, pero no contenía importes y no permitía la demo de cálculo. No se encontró ningún cartel de tarifas ya hecho en imagen (las webs oficiales publican las tarifas como texto), así que se hizo una captura propia. Aviso: es una captura de una web de terceros, no un cartel oficial, y esa página no indica licencia; se usa con fines educativos.

**Demo prevista.** «Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» → `describir_imagen` y después `calculadora` con `3*1,50+5,00`, que da **9,50 €**.

**Qué devolvió la tool.** Ejecutada el 2026-10-14 contra la API real de Gemini con el modelo `gemini-3.8-flash`, `describir_imagen` leyó los cuatro precios sin errores ni cifras inventadas:

```
Los precios que aparecen en la imagen son los siguientes:
* Billete sencillo EMT: 1,50 €
* Billete sencillo TransBus: 1,80 €
* Billete Exprés Aeropuerto: 5,00 €
* Metrobús 10 viajes: 7,30 €
```

Después `calculadora` con `3*1,50+5,00` devolvió **9,50**, el total correcto. La traza muestra las dos llamadas en este orden, ambas con estado «ok».

**Qué no demuestra esta prueba.** La expresión `3*1,50+5,00` la escribió el script de la demo; no la construyó un LLM a partir del texto de la imagen. El flujo completo (un LLM leyendo la imagen y otro proponiendo la operación) sigue sin probarse con un modelo real. Desde el cambio aprobado en las specs 007 y 008, los clientes pueden seleccionar la imagen demo solo al mencionar literalmente `assets/imagen_demo.jpg` en el mensaje. No admiten subida de archivos ni otras rutas: una referencia genérica a una imagen sigue sin acreditar una imagen válida y se deriva al RAG.

**Incidencias durante la demo.** Antes de que funcionara hubo tres fallos externos al código, todos con el mismo mensaje genérico de la tool:
- `gemini-3.6-flash` (el modelo configurado en el proyecto) devolvió `503 UNAVAILABLE` por demanda alta.
- `gemini-2.5-flash` devolvió `404`: Google lo ha retirado para cuentas nuevas.
- Una primera clave mal configurada dio `400 API_KEY_INVALID`.

Con `gemini-3.8-flash` funcionó a la primera llamada válida, por lo que `MODELO_VISION` en `config.py` pasó a ese modelo, independiente de `GENERATION_MODEL` (el del RAG).

## 5. Fallos conocidos y siguientes pasos

1. **La tool ocultaba la causa de los errores del modelo y no reintentaba. Resuelto y mergeado en `develop` (PR #11).** Durante la demo, un `503` pasajero, un `404` por modelo retirado y una clave inválida dieron exactamente el mismo mensaje y hizo falta un script de diagnóstico para ver la causa. Se especificó (spec 002, RF-24 a RF-27) y se implementó: un reintento tras 2 s ante 429, 500, 502, 503, 504 y fallos de red; ninguno ante 400, 401, 403 o 404; y un registro con tipo, código y estado sin datos sensibles. 16 casos de test sin API, con los errores reales de `google-genai` construidos a mano. *Pendiente:* comprobarlo contra un 503 real de Gemini.
2. **La lectura de cifras solo se ha verificado en una imagen.** Con la captura de cuatro precios el modelo acertó, pero no hay garantía en imágenes más densas o de peor calidad: un error al leer «1,50» o «5,00» llevaría a un total incorrecto. *Siguiente paso:* mostrar los importes leídos en la nota para que el humano los valide en el HITL y probar con más imágenes.
3. **`hora_actual` no conoce los festivos.** Solo distingue laborable, sábado y domingo, así que un festivo se trata como un día laborable y el especialista podría dar un horario equivocado. *Siguiente paso:* incorporar un calendario de festivos como dato (CSV) o consultarlo al RAG.
4. **El bucle depende de que el LLM cumpla el protocolo JSON** (`{"tool","args"}` o `{"final"}`). Si no lo cumple, el especialista devuelve una nota de error controlada, pero la pregunta queda sin responder. *Siguiente paso:* pasar a `bind_tools` de LangChain o validar y reintentar una vez antes de rendirse; en MLOps, medir la tasa de respuestas no interpretables.
5. **El flujo multimodal está limitado a la imagen demo.** Las specs 007 y 008 aprobaron que la referencia literal `assets/imagen_demo.jpg` seleccione la demo únicamente para ese turno. No hay subida de archivos ni selección de otras rutas; una mención genérica a una imagen se desvía al RAG. Esta restricción evita que una referencia textual active visión sin un archivo autorizado. *Siguiente paso:* si se necesitan imágenes aportadas por la persona usuaria, definir una nueva spec para su validación y transporte seguro, sin ampliar el contrato actual de forma implícita.
6. **Un test del grafo llama a Gemini de verdad.** `tests/test_agent_contrato.py::test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` no inyecta los especialistas: con una clave en el entorno hace 8 intentos de conexión a Google y sin clave pide la clave por terminal. Rompe el principio de tests sin API. *Siguiente paso:* inyectar `especialistas` falsos, como el resto de tests.
7. **La demo con las APIs reales no se ha hecho.** El RAG no está indexado en mi máquina y faltan las claves de Google Routes y el contacto de Nominatim, por lo que no hay plan de ruta ni HITL real. La validación de las specs 001, 002 y 008 sigue en **Parcial** por esto. *Actualización:* las rutas sí se han probado con las APIs reales con otra configuración del equipo (secciones 3 y 9).
8. **Tras aprobar el plan, el LLM vuelve a resumir la ruta entera.** Al sintetizador se le pide confirmar brevemente, pero en real el modelo lo ignora (RF-42 y RF-43 de la spec 010 no se cumplen). *Siguiente paso:* una confirmación determinista, lo que exige modificar el RF-20 de la spec 005.
9. **Un seguimiento crea un plan duplicado.** Cada resultado `ok` propone un plan nuevo, aunque ya haya uno aprobado idéntico. *Siguiente paso:* no crear el plan si ya existe uno aprobado igual.
10. **El historial no guarda las respuestas del asistente.** Solo guarda los mensajes de la persona, así que el supervisor no sabía a qué respondía un «2 y 2» y lo tomó por una suma. Lo resolví con una regla determinista para elegir opciones, pero cualquier otro seguimiento que dependa de lo mostrado tendrá el mismo problema. *Siguiente paso:* guardar las respuestas en el estado, lo que cambia el contrato de la spec 005.
11. **El precio por ruta no está resuelto del todo.** El RAG devuelve a veces varias opciones sin etiquetar (por ejemplo 1,50 / 1,80 / 2,00 € para un billete sencillo) y no indica cuál corresponde a la ruta. Además, mi índice local estaba incompleto (313 de 4054 chunks, solo 7 de 3748 paradas), por lo que la zona fallaba, y en los chunks de paradas aparecen caracteres rotos («Descripci�n»). *Siguiente paso:* repetir la prueba con el índice completo y revisar la codificación del CSV en la ingesta.

**Otras limitaciones.** El RAG sigue con `gemini-3.6-flash` (`GENERATION_MODEL`), que dio un 503 por saturación en la demo de visión; conviene que el equipo valore cambiarlo también. La PR #7 trajo `output/chunks.json` con más de 52.000 líneas y cambió `MAX_FILAS_CSV` a `None` y `EMBED_RPM_LIMIT` a 2000, que con la cuota gratuita de Gemini (100 por minuto) daría errores al indexar. Y las palabras clave del fallback pueden solaparse con las de otros especialistas, por lo que el orden de las reglas del supervisor debe acordarse.

## 6. Clientes CLI y Streamlit (spec 008)

El enunciado pide que el CLI y Streamlit sean clientes del mismo grafo, con la pausa HITL, trazas visibles y nueva conversación. Los hice como **capas finas** sobre una lógica común, y empecé contra un grafo simulado porque el real no existía; cuando Rubén lo subió, comprobé que su contrato coincidía con el que había propuesto y adapté lo que cambiaba.

**Diseño.** Todo está en `src/clientes/` y `main.py` y `app.py` solo dibujan:

| Módulo | Responsabilidad |
|---|---|
| `contrato.py` | Las seis claves que devuelve el grafo: `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done`. |
| `planes.py` | Resumen legible de un plan de ruta, identificadores y filtro de las entradas técnicas del supervisor. |
| `presentacion.py` | Formato común, para que CLI y web muestren lo mismo ante el mismo pedido. |
| `sesion.py` | La conversación: identificador, estado, historial, errores y qué se puede hacer en cada momento. La comparten los dos clientes. |
| `cargar.py` | Elige el grafo real o, con `MADRIDRUMBO_GRAFO=falso`, el simulado, avisándolo en pantalla. |
| `grafo_falso.py` | Grafo de pruebas que se parece al real (solo las rutas pausan, con uno o varios planes). |

**Comportamiento.**
- **CLI:** chat con la pregunta `[s/n]` cuando hay un plan, elección por número si hay varios, `--demo` con tres pedidos (horarios, ruta y fuera de corpus) y `--auto-aprobar`. Muestra también el registro técnico del supervisor.
- **Streamlit:** chat, planes con resumen legible en la barra lateral, selector si hay varios, botones Aprobar y Rechazar, cuadro de mensaje bloqueado mientras haya un plan pendiente, «Nueva conversación» y panel de depuración, que **no** muestra los diagnósticos del supervisor (spec 006).
- **Reglas de fondo:** los clientes nunca deciden `done` ni qué especialista actúa; un fallo del grafo se avisa en español sin detalles internos y el chat sigue.

**Decisiones.**
- **Contrato aislado en un solo archivo.** Adaptar el cliente al grafo real fue cambiar el formato de `plan` y añadir el identificador del plan, no reescribir nada.
- **No llamar al grafo sin elección con varios planes.** El grafo respondería con un aviso que deja `hitl_pendiente=False` aunque el plan siga pendiente, y la pantalla quedaría desincronizada.
- **El simulado se parece al real a propósito.** La primera versión pausaba con cualquier mensaje y habría dado una demo engañosa: con el grafo real solo pausan las rutas.
- **Demo cambiada.** Se sustituyó el pedido de la imagen por una ruta porque la ruta es el único flujo que enseña el HITL. La imagen demo puede seleccionarse mediante su referencia literal, pero no genera una pausa HITL ni habilita subida de archivos.

**Cómo se comprobó.** 37 requisitos con test en verde y 623 tests sin API en `develop`. 11 de ellos recorren los clientes contra el **grafo real** con los especialistas, el supervisor y el sintetizador sustituidos por dobles, y no hacen ninguna conexión a la red; la web se recorrió con la herramienta de pruebas de Streamlit y se vio en un navegador real (modo simulado). Pendiente: la demo con las APIs reales.

**Limitaciones.** Los clientes no permiten aportar imágenes arbitrarias: solo reconocen la imagen demo mediante la referencia literal aprobada; con el grafo real la sesión vive en memoria y se pierde al reiniciar el proceso; y el filtro de los diagnósticos del supervisor se aplica a toda la web, lectura más estricta que la de la spec 006, pendiente de confirmar con Rubén.

## 7. Trabajo con SDD

Las tres funcionalidades de esta parte se desarrollaron con Spec-Driven Development, cada una con spec (requisitos en notación EARS), plan, tareas y validación: `specs/001-tool-hora-especialista-horarios/` (16 requisitos), `specs/002-multimodal-imagen-calculadora/` (27 con el cambio de reintento) y `specs/008-clientes-cli-streamlit/` (37). Todos tienen test en verde y sin API.

El SDD se notó sobre todo en tres momentos. Primero, cuando el grafo real llegó y obligó a cambiar el diseño: había una spec y un plan que actualizar en lugar de un código que reescribir a ciegas. Segundo, al renumerar la spec de los clientes de 005 a 008 porque colisionaba con la del grafo. Y tercero, al comprobar que los tests que citaban mis validaciones seguían existiendo: cinco habían desaparecido cuando Rubén reescribió `tests/test_flujo_imagen_calculo.py`, y la validación habría quedado diciendo algo falso.

Las validaciones de las tres specs están en estado **Parcial** por las demos con APIs reales que quedan pendientes.

Las funcionalidades de rutas también siguen SDD, con la misma estructura de spec, plan, tareas y validación: `specs/004-planificar-ruta/`, `specs/009-alternativa-bicimad/` y `specs/010-lugares-bloques-y-precio/`. Dos momentos lo justificaron. Primero, al querer componer la respuesta final de forma determinista para que el LLM no perdiera ni duplicara bloques: el RF-20 de la spec 005 exige una respuesta sintetizada, así que la spec frenó esa idea y se adoptó otra solución (ver sección 8). Segundo, al rellenar la validación de la 010: se marcó como cumplido solo lo que tenía evidencia real y el resto quedó como pendiente de verificación, en vez de darlo por bueno. La validación de la 010 está en estado **Parcial**.

## 8. Decisiones de alto impacto del proyecto

Esta sección completa las decisiones que afectan a la arquitectura y al comportamiento global del sistema, más allá de las funcionalidades desarrolladas en las secciones anteriores.

- **RAG: tablas Markdown como unidades de evidencia.** Las tablas Markdown válidas se detectan durante la fragmentación, se conservan con su título como un único chunk indivisible y se marcan con la estrategia `tabla_markdown`. El resto del documento continúa con el fragmentado ordinario. Así se evita separar filas y perder el contexto de una tarifa o condición.
- **Rutas: fuentes, límites y evidencia.** `planificar_ruta` geocodifica con Nominatim dentro del ámbito configurado (Comunidad de Madrid), pide el itinerario de transporte público a Google Routes y consulta el RAG para la zona y el precio. La zona se consulta antes que el precio; el precio se pregunta primero sin la zona y, si el RAG se abstiene, con ella. Ningún tiempo, zona o importe se estima cuando la fuente no aporta evidencia. Las horas de salida y llegada son excluyentes y se validan antes de llamar a servicios externos. Los lugares ambiguos se resuelven en dos capas: opciones numeradas (solo candidatos de la Comunidad de Madrid, sin duplicados) y, si no hay candidatos, un único reintento con un texto alternativo; el mensaje siempre indica qué opción se usó.
- **Grafo: estado y control de la orquestación.** El grafo LangGraph conserva cada conversación mediante un checkpointer por `thread_id`; su fachada pública mantiene las seis claves `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done`. El supervisor entrega una cola finita de roles admitidos, y Python mantiene los límites transversales de turnos e invocaciones de tools. El HITL solo se activa para planes de ruta válidos.
- **Supervisor: decisiones estructuradas y observabilidad segura.** La respuesta del Supervisor se solicita como JSON y se valida de forma estricta en Python. Si falla el proveedor, el JSON o los roles, se aplica el fallback determinista. El diagnóstico usa solo las categorías `proveedor`, `json_invalido`, `roles_invalidos` y `sin_fallback`, con resúmenes fijos y no sensibles; se expone solo en el resultado del turno, sin persistirlo en el historial, el checkpoint o la traza.
- **Tarifas textuales e imagen demo.** Un catálogo único define roles y restricciones. Una pregunta textual de tarifas sin imagen válida se redirige de `tarifas` a RAG, preservando la allowlist y la evidencia documental. La señal de imagen es efímera y la demo exige la referencia literal aprobada; una corrección semántica se registra en una línea segura adicional de `log`, sin alterar la categoría de fallback ni el contrato público.
- **Alternativa BiciMAD y clima.** La oferta de BiciMAD se decide en Python con reglas configurables de distancia, disponibilidad y estaciones distintas; no la decide el LLM. La disponibilidad procede de EMT y los tiempos de los tramos a pie y bici de Google Routes, sin estimaciones ni alternativas parciales. Sin hora solicitada y solo si la bici es posible por distancia, se consulta el clima actual del origen con Open-Meteo: un tiempo no apto evita ofrecer bici y pide la ruta de transporte con preferencia de menos trayectos a pie; si el clima no está disponible, la bici se ofrece con un aviso. Los campos `bici` y `clima` se añaden de forma aditiva al resultado de ruta, sin cambiar RAG ni el contrato previo.
- **Respuesta final: bloques literales.** La zona, el precio, el clima, la alternativa en bici y la opción de lugar usada se añaden tal cual a la respuesta, porque el LLM los omitía, parafraseaba o duplicaba. El modelo solo redacta el resumen: se le quitan esos bloques del contexto y solo se le pasan los resultados del turno actual. Así se respeta la respuesta sintetizada que exige la spec 005 sin perder datos.

## 9. Rutas, BiciMAD y clima

Mi parte es la tool `planificar_ruta` y el especialista `rutas` que la usa. Dado un origen y un destino, devuelve el itinerario en transporte público y, si procede, una alternativa en BiciMAD y el tiempo en el origen. Se desarrolló con SDD en `specs/004-planificar-ruta/`, `specs/009-alternativa-bicimad/` y `specs/010-lugares-bloques-y-precio/`.

**Cómo funciona.** El orden es fijo y lo decide Python, no el LLM:

| Paso | Servicio | Para qué | Si falla |
|---|---|---|---|
| 1 | Nominatim | Coordenadas de origen y destino | Pide aclarar: lugar ambiguo, no encontrado o fuera de cobertura |
| 2 | Google Routes (transporte público) | Itinerario y duración | `ruta_no_calculada`, con un aviso |
| 3 | RAG | Zona y precio | El bloque dice que no se pudo determinar; no se inventa |
| 4 | EMT BiciMAD + Google Routes | Alternativa en bici | La ruta de transporte llega intacta con un aviso |
| 5 | Open-Meteo | Tiempo actual en el origen | La bici se ofrece con un aviso de que no se pudo comprobar el tiempo |

Los límites por consulta están en Python: como máximo 4 llamadas a Google (1 de transporte, 1 de bici y 2 a pie), 2 a la EMT, 1 a Open-Meteo y 3 al RAG.

**Por qué decide Python.** La bici se ofrece solo si no se pide hora, la distancia en línea recta entre origen y destino está entre 1 y 6 km, la estación de origen tiene bicis, la de destino huecos libres, ambas están a 500 m o menos y son distintas. Un tiempo no apto (lluvia, llovizna, nieve, tormenta, menos de 5 °C, más de 32 °C o viento de más de 30 km/h) evita ofrecerla. Los umbrales están en `config.py`. El clima solo se consulta si la bici es posible.

**Ambigüedad y lugares.** Nominatim devuelve candidatos y solo se conservan los de la Comunidad de Madrid, sin duplicados. Se normalizan prefijos como «Metro X», que Nominatim no encontraba. Si hay varios candidatos, se pregunta con opciones numeradas y se acepta «2», «2 y 1» o «la 2 y la 1». Si no hay ninguno, el especialista propone un texto alternativo con un único reintento por extremo. El mensaje siempre indica qué opción se usó y cómo corregirla. Este último paso está verificado con tests y pendiente de probar en real.

**Bloques literales.** Zona, precio, clima, bici y opción usada se añaden tal cual a la respuesta, porque el LLM los omitía o duplicaba (sección 8).

**Cómo se comprobó.** Más de mil tests sin API, con dobles de Nominatim, Google, EMT, Open-Meteo y el RAG, y pruebas reales en el CLI y en Streamlit con las cuatro APIs. El detalle, requisito por requisito, está en `specs/010-lugares-bloques-y-precio/validacion.md`, y las pruebas contra la EMT y Open-Meteo en `specs/009-alternativa-bicimad/verificacion-emt.md` y `verificacion-open-meteo.md`.

**Qué observé que no esperaba.**
- El almacén de certificados de Windows daba `certificate has expired` con Open-Meteo. Lo resolví con el bundle de `certifi` para esa llamada, sin desactivar nunca la verificación TLS.
- El login de la EMT devuelve el código «00» (token nuevo) o «01» (token aún vigente), y ambos son válidos. La EMT es lenta: el login tiene un límite de 10 s y las estaciones de 20 s, así que en el peor caso la alternativa tarda entre 25 y 30 s.
- Google no devolvió ningún aviso de beta en las rutas a pie y en bici, así que la respuesta incluye un texto fijo equivalente.
- Con mal tiempo, pedir la ruta con menos caminata empeoró una muestra de 20 a 36 minutos. Es una sola muestra y la decisión queda por revisar.
- El supervisor tomó «2 y 2», respuesta a una ambigüedad, por una suma y llamó a la calculadora. Lo corregí con una regla determinista (sección 1).

**Limitaciones.**
- No hay modo «solo bici»: una petición «en bici» calcula igualmente la ruta de transporte y añade la alternativa.
- El criterio de «estación activa» (en servicio y sin baja virtual) es una suposición que no he verificado con la EMT.
- El precio por ruta no está resuelto del todo (fallo 11, sección 5), y los fallos 8 a 10 de esa sección son del grafo y del historial, no de la tool.
