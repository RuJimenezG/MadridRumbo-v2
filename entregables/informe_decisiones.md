# Informe de decisiones — MadridRumbo (Project Break 2)

> Grupo 3: Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.
> Este borrador recoge la parte de **José Manuel Gil Ruiz** (tool auxiliar de hora y su especialista, tool multimodal y calculadora). Las secciones marcadas `[PENDIENTE]` las completa el equipo o dependen de piezas aún no integradas.

## 1. Grafo: especialistas y momento HITL

### Especialistas de esta parte

| Especialista | Para qué existe | Tools permitidas |
|---|---|---|
| `horarios` | Preguntas sobre cuándo, a qué hora y hasta cuándo hay servicio. Combina la hora actual con los horarios del corpus. | `hora_actual`, `rag_ask` |
| `tarifas` | Preguntas de precios y totales a partir de una imagen de tarifas. | `describir_imagen`, `calculadora`, `rag_ask` |

**Por qué estos dos.** Una pregunta como «¿puedo coger el metro ahora?» depende de la hora y el día, un dato que el LLM no puede conocer. Una pregunta como «¿cuánto cuestan 3 billetes?» pide una cuenta exacta, que tampoco se le debe dejar hacer de cabeza. Separar ambos casos da a cada especialista un prompt corto y unas tools acotadas, y cumple el requisito de al menos dos especialistas.

**Cómo funcionan.** Los dos comparten un mini-bucle (`src/agents/base.py`): el LLM propone una tool o una nota final, y el código decide qué se ejecuta. Los límites están en Python y no en el LLM:
- Solo se ejecutan las tools de la lista del especialista (`TOOLS_POR_ESPECIALISTA`). Una tool inventada o ajena se bloquea y queda en la traza como «bloqueada».
- Máximo `MAX_STEPS_ESPECIALISTA` (3) tools por turno; al llegar al tope devuelve lo obtenido.
- Si el LLM falla o responde algo no interpretable, la nota es un error controlado, sin excepción.
- El especialista devuelve solo `notas` y `traza`. **Nunca decide `done`**: eso corresponde al grafo y al humano.

**Fallback del supervisor.** `elegir_rol_por_palabras` deriva a `horarios` los mensajes con términos como hora, horario, ahora, hoy, noche, última, primera, abre, cierra o frecuencia (sin distinguir mayúsculas ni acentos). Si no hay coincidencia devuelve `None` y decide el siguiente criterio.

**Momento HITL.** `[PENDIENTE: equipo]` Lo define quien lleve el grafo (`src/graph.py`). Mis especialistas no cierran el plan: solo aportan notas antes de la síntesis.

## 2. Tools: qué hace cada una y cómo se enchufa el RAG

Todas viven en `src/tools/` y se ejecutan a través de `ejecutar_tool(nombre, args, traza)`, que aplica la allowlist `TOOLS_PERMITIDAS` y registra en la traza el nombre, los argumentos, el estado (ok, error o bloqueada) y un extracto del resultado.

| Tool | Tipo | Qué hace |
|---|---|---|
| `hora_actual` | Auxiliar determinista | Devuelve fecha, hora, día de la semana y tipo de día (laborable, sábado o domingo) en la zona horaria configurada (`Europe/Madrid`). Sin red ni LLM. |
| `calculadora` | Auxiliar determinista | Evalúa `+ - * /`, paréntesis y signo menos con decimales con coma o punto. Usa `ast` y `Decimal`, **sin `eval`**: cualquier otra cosa (funciones, potencias, nombres) da un error controlado. Resultado con máximo 2 decimales. |
| `describir_imagen` | Multimodal | Lee una imagen de `assets/` con Gemini y devuelve en español los textos y cifras visibles, sin inventar. |
| `rag_ask` | RAG | Delega en `rag.responder.rag_ask`. |

**Seguridad de `describir_imagen`.** Solo lee archivos dentro de `assets/` (rutas como `../.env` o absolutas se rechazan), solo JPG, JPEG y PNG, y con un máximo de 4 MB. Si el modelo falla, devuelve `ERROR:` sin inventar contenido.

**Cómo se enchufa el RAG.** El especialista llama a `rag_ask` como una tool más de la allowlist; el RAG no se sustituye. Si no hay evidencia, el RAG se abstiene («No lo sé, no está en los documentos.») y el especialista lo refleja en su nota sin inventar horarios ni precios. `[PENDIENTE]` La `rag_ask` real depende de integrar `feature/tools-rag`.

## 3. HITL: una aprobación y un rechazo

`[PENDIENTE: equipo]` Se completa cuando el grafo esté integrado: qué plan se aprobó, cuál se rechazó y qué se observó.

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

**Qué no demuestra esta prueba.** La expresión `3*1,50+5,00` la escribió el script de la demo; no la construyó un LLM a partir del texto de la imagen. El flujo completo del especialista `tarifas` (el LLM leyendo la imagen y proponiendo él mismo la operación) sigue sin probarse con un modelo real, porque falta el grafo y el cliente LLM de los especialistas.

**Incidencias durante la demo.** Antes de que funcionara hubo tres fallos externos al código, todos con el mismo mensaje genérico de la tool:
- `gemini-3.6-flash` (el modelo configurado en el proyecto) devolvió `503 UNAVAILABLE` por demanda alta.
- `gemini-2.5-flash` devolvió `404`: Google lo ha retirado para cuentas nuevas.
- Una primera clave mal configurada dio `400 API_KEY_INVALID`.

Con `gemini-3.8-flash` funcionó a la primera llamada válida.

## 5. Fallos conocidos y siguientes pasos

1. **La tool oculta la causa de los errores del modelo y no reintenta.** Durante la demo, un `503` pasajero, un `404` por modelo retirado y una clave inválida produjeron exactamente el mismo mensaje («el modelo no pudo describir la imagen»), y hizo falta un script de diagnóstico para ver la causa real. *Siguiente paso:* registrar la causa en un log, reintentar una vez ante `503`/`429` y dejar un modelo de respaldo configurable. Es un cambio de comportamiento, así que primero hay que añadirlo a la spec 002.
2. **La lectura de cifras solo se ha verificado en una imagen.** Con la captura de cuatro precios el modelo acertó, pero no hay garantía en imágenes más densas o de peor calidad: un error al leer «1,50» o «5,00» llevaría a un total incorrecto. *Siguiente paso:* mostrar los importes leídos en la nota para que el humano los valide en el HITL y probar con más imágenes.
3. **`hora_actual` no conoce los festivos.** Solo distingue laborable, sábado y domingo, así que un festivo se trata como un día laborable y el especialista podría dar un horario equivocado. *Siguiente paso:* incorporar un calendario de festivos como dato (CSV) o consultarlo al RAG.
4. **El bucle depende de que el LLM cumpla el protocolo JSON** (`{"tool","args"}` o `{"final"}`). Si no lo cumple, el especialista devuelve una nota de error controlada, pero la pregunta queda sin responder. *Siguiente paso:* pasar a `bind_tools` de LangChain o validar y reintentar una vez antes de rendirse; en MLOps, medir la tasa de respuestas no interpretables.

**Otras limitaciones.** El modelo configurado en el proyecto (`gemini-3.6-flash`) no respondió en la demo por saturación; con `gemini-3.8-flash` sí. La `rag_ask` real depende de integrar `feature/tools-rag`; `elegir_rol_por_palabras` y los especialistas no están todavía conectados a un grafo; y las palabras clave del fallback pueden solaparse con las de otros especialistas, por lo que el orden de las reglas del supervisor debe acordarse.

## 6. Trabajo con SDD

Las dos funcionalidades se desarrollaron con Spec-Driven Development: `specs/001-tool-hora-especialista-horarios/` y `specs/002-multimodal-imagen-calculadora/`, cada una con spec (requisitos EARS), plan, tareas y validación. Resultado: 39 requisitos funcionales con test en verde (16 y 23), 75 tests sin API en total. La validación de ambas está en estado **Parcial** por las demos manuales pendientes.
