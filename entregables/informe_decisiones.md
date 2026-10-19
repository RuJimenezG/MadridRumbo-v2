# Informe de decisiones — MadridRumbo (Project Break 2)

> Grupo 3: Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.
> Este borrador recoge la parte de **José Manuel Gil Ruiz**: tool auxiliar de hora y su especialista, tool multimodal y calculadora (secciones 1 a 5) y los clientes CLI y Streamlit (sección 6). Las secciones del grafo, el RAG y las rutas las completan Rubén y Guzmán. Actualizado el 2026-10-19, ya con el grafo real en `develop`.

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

## 2. Tools: qué hace cada una y cómo se enchufa el RAG

Todas viven en `src/tools/` y se ejecutan a través de `ejecutar_tool(nombre, args, traza)`, que aplica la allowlist `TOOLS_PERMITIDAS` y registra en la traza el nombre, los argumentos, el estado (ok, error o bloqueada) y un extracto del resultado.

| Tool | Tipo | Qué hace |
|---|---|---|
| `hora_actual` | Auxiliar determinista | Devuelve fecha, hora, día de la semana y tipo de día (laborable, sábado o domingo) en la zona horaria configurada (`Europe/Madrid`). Sin red ni LLM. |
| `calculadora` | Auxiliar determinista | Evalúa `+ - * /`, paréntesis y signo menos con decimales con coma o punto. Usa `ast` y `Decimal`, **sin `eval`**: cualquier otra cosa (funciones, potencias, nombres) da un error controlado. Resultado con máximo 2 decimales. |
| `describir_imagen` | Multimodal | Lee una imagen de `assets/` con Gemini y devuelve en español los textos y cifras visibles, sin inventar. |
| `rag_ask` | RAG | Delega en `rag.responder.rag_ask`. |

**Seguridad de `describir_imagen`.** Solo lee archivos dentro de `assets/` (rutas como `../.env` o absolutas se rechazan), solo JPG, JPEG y PNG, y con un máximo de 4 MB. Si el modelo falla, devuelve `ERROR:` sin inventar contenido. Un error temporal (503, 429 o de red) se reintenta **una vez** tras 2 segundos, y la causa real del fallo (tipo, código y estado, nunca el mensaje completo ni la clave) queda en el registro; el agente sigue viendo el mensaje genérico para no filtrar detalles internos (ver el fallo 1 de la sección 5).

**Cómo se enchufa el RAG.** El especialista llama a `rag_ask` como una tool más de la allowlist; el RAG no se sustituye. Si no hay evidencia, el RAG se abstiene («No lo sé, no está en los documentos.») y el especialista lo refleja en su nota sin inventar horarios ni precios. El RAG ya está integrado en `develop`; la `rag_ask` real todavía no se ha ejercitado con el índice generado y Gemini (el índice no existe en mi máquina: ver el fallo 7).

## 3. HITL: una aprobación y un rechazo

Observado con el **grafo real** (`src/agent.py`) y la parte de modelos, especialistas y tools sustituida por dobles de prueba, sin gastar API (`tests/test_clientes_grafo_real.py`, PR de los clientes). No es una demostración con las APIs reales: eso sigue pendiente (sección 5, fallo 7).

**Una aprobación.** Pedido: «Dame una ruta de Atocha a Sol.» El supervisor elige `rutas`, el grafo se pausa y devuelve el plan `ruta-1` (metro línea 1, 12 min) con `hitl_pendiente=True` y `done=False`. Al aprobarlo el grafo da `done=True`, vacía los planes pendientes y la conversación puede continuar en el mismo `thread_id`.

**Un rechazo.** Mismo pedido: al rechazar `ruta-1` el grafo **replanifica en el mismo hilo** con los mismos argumentos y propone `ruta-2` (autobús línea 27, 20 min), de nuevo con `hitl_pendiente=True` y `done=False`. El supervisor se ejecutó una sola vez y el especialista de rutas dos. Aprobar `ruta-2` cierra la conversación.

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

**Qué no demuestra esta prueba.** La expresión `3*1,50+5,00` la escribió el script de la demo; no la construyó un LLM a partir del texto de la imagen. El flujo completo (un LLM leyendo la imagen y otro proponiendo la operación) sigue sin probarse con un modelo real. Hoy, además, **no se puede ejecutar de punta a punta desde los clientes**: la spec 007 solo activa `tarifas` con una imagen aportada válida, pero `src/agent.py` fija `imagen_valida=False` en cada turno y la API pública no ofrece forma de aportarla. Una consulta sobre una imagen se desvía al RAG, que no ve imágenes (fallo 5).

**Incidencias durante la demo.** Antes de que funcionara hubo tres fallos externos al código, todos con el mismo mensaje genérico de la tool:
- `gemini-3.6-flash` (el modelo configurado en el proyecto) devolvió `503 UNAVAILABLE` por demanda alta.
- `gemini-2.5-flash` devolvió `404`: Google lo ha retirado para cuentas nuevas.
- Una primera clave mal configurada dio `400 API_KEY_INVALID`.

Con `gemini-3.8-flash` funcionó a la primera llamada válida, por lo que `MODELO_VISION` en `config.py` pasó a ese modelo, independiente de `GENERATION_MODEL` (el del RAG).

## 5. Fallos conocidos y siguientes pasos

1. **La tool ocultaba la causa de los errores del modelo y no reintentaba. Resuelto en una rama pendiente de PR.** Durante la demo, un `503` pasajero, un `404` por modelo retirado y una clave inválida dieron exactamente el mismo mensaje y hizo falta un script de diagnóstico para ver la causa. Se especificó (spec 002, RF-24 a RF-27) y se implementó: un reintento tras 2 s ante 429, 500, 502, 503, 504 y fallos de red; ninguno ante 400, 401, 403 o 404; y un registro con tipo, código y estado sin datos sensibles. 16 casos de test sin API, con los errores reales de `google-genai` construidos a mano. *Pendiente:* comprobarlo contra un 503 real de Gemini.
2. **La lectura de cifras solo se ha verificado en una imagen.** Con la captura de cuatro precios el modelo acertó, pero no hay garantía en imágenes más densas o de peor calidad: un error al leer «1,50» o «5,00» llevaría a un total incorrecto. *Siguiente paso:* mostrar los importes leídos en la nota para que el humano los valide en el HITL y probar con más imágenes.
3. **`hora_actual` no conoce los festivos.** Solo distingue laborable, sábado y domingo, así que un festivo se trata como un día laborable y el especialista podría dar un horario equivocado. *Siguiente paso:* incorporar un calendario de festivos como dato (CSV) o consultarlo al RAG.
4. **El bucle depende de que el LLM cumpla el protocolo JSON** (`{"tool","args"}` o `{"final"}`). Si no lo cumple, el especialista devuelve una nota de error controlada, pero la pregunta queda sin responder. *Siguiente paso:* pasar a `bind_tools` de LangChain o validar y reintentar una vez antes de rendirse; en MLOps, medir la tasa de respuestas no interpretables.
5. **El flujo multimodal es inalcanzable desde los clientes.** `src/agent.py` fija `imagen_valida=False` en cada turno (hay un test que lo exige) y la API pública no permite aportar una imagen. Antes de la PR #7 la pregunta «según la imagen…» llegaba a `tarifas`; desde ella se desvía al RAG. Es una regresión del requisito multimodal del enunciado. *Siguiente paso:* un campo opcional en `estado` (por ejemplo `estado["imagen"]`) que el agente valide contra `assets/` antes de marcar la imagen como válida; hay que decidirlo con quien lleva el grafo.
6. **Un test del grafo llama a Gemini de verdad.** `tests/test_agent_contrato.py::test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` no inyecta los especialistas: con una clave en el entorno hace 8 intentos de conexión a Google y sin clave pide la clave por terminal. Rompe el principio de tests sin API. *Siguiente paso:* inyectar `especialistas` falsos, como el resto de tests.
7. **La demo con las APIs reales no se ha hecho.** El RAG no está indexado en mi máquina y faltan las claves de Google Routes y el contacto de Nominatim, por lo que no hay plan de ruta ni HITL real. La validación de las specs 001, 002 y 008 sigue en **Parcial** por esto.

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
- **Demo cambiada.** Se sustituyó el pedido de la imagen por una ruta, porque la imagen no es alcanzable (fallo 5) y la ruta es lo único que enseña el HITL.

**Cómo se comprobó.** 37 requisitos con test en verde y 598 tests sin API en la rama de los clientes. 11 de ellos recorren los clientes contra el **grafo real** con los especialistas, el supervisor y el sintetizador sustituidos por dobles, y no hacen ninguna conexión a la red; la web se recorrió con la herramienta de pruebas de Streamlit. Pendientes: la demo con las APIs reales y ver la web en un navegador real.

**Limitaciones.** Ningún cliente puede aportar una imagen (fallo 5); con el grafo real la sesión vive en memoria y se pierde al reiniciar el proceso; y el filtro de los diagnósticos del supervisor se aplica a toda la web, lectura más estricta que la de la spec 006, pendiente de confirmar con Rubén.

## 7. Trabajo con SDD

Las tres funcionalidades de esta parte se desarrollaron con Spec-Driven Development, cada una con spec (requisitos en notación EARS), plan, tareas y validación: `specs/001-tool-hora-especialista-horarios/` (16 requisitos), `specs/002-multimodal-imagen-calculadora/` (27 con el cambio de reintento) y `specs/008-clientes-cli-streamlit/` (37). Todos tienen test en verde y sin API.

El SDD se notó sobre todo en tres momentos. Primero, cuando el grafo real llegó y obligó a cambiar el diseño: había una spec y un plan que actualizar en lugar de un código que reescribir a ciegas. Segundo, al renumerar la spec de los clientes de 005 a 008 porque colisionaba con la del grafo. Y tercero, al comprobar que los tests que citaban mis validaciones seguían existiendo: cinco habían desaparecido cuando Rubén reescribió `tests/test_flujo_imagen_calculo.py`, y la validación habría quedado diciendo algo falso.

Las validaciones de las tres specs están en estado **Parcial** por las demos con APIs reales que quedan pendientes.
