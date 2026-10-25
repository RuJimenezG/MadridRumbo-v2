# Informe de decisiones — MadridRumbo (Project Break 2)

> Grupo 2: Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.

## 0. Ampliación del alcance y metodología SDD

Se ha decidido ampliar el alcance del proyecto. Originalmente este se restringía a tarifas y normativa relacionada con la red de transporte del Consorcio Regional de Transportes de Madrid. Al convertir el proyecto de un sistema RAG a otro multiagente las posibilidades de resolución de consultas se amplían enormemente, permitiendo ampliar el alcance a la consulta de rutas, horarios e información relacionada con el viaje.

Las funcionalidades de esta parte se desarrollaron con Spec-Driven Development, cada una con spec (requisitos en notación EARS), plan, tareas y validación.

## 1. Grafo: especialistas y momento HITL

Se decidió crear el grafo con un nodo supervisor, un nodo sintetizador de la respuesta e incluir los siguientes especialistas: auxiliar, rag, tarifas (multimodal) y rutas.

**Momento HITL.** En el grafo la pausa ocurre **solo cuando hay un plan de ruta pendiente**.

## 2. Tools

Todas viven en `src/tools/` y se ejecutan a través de `ejecutar_tool(nombre, args, traza)`, que aplica la allowlist `TOOLS_PERMITIDAS` y registra en la traza el nombre, los argumentos, el estado (ok, error o bloqueada) y un extracto del resultado.

| Tool | Tipo | Qué hace |
|---|---|---|
| `hora_actual` | Auxiliar determinista | Devuelve fecha, hora, día de la semana y tipo de día (laborable, sábado o domingo) en la zona horaria configurada (`Europe/Madrid`). Sin red ni LLM. |
| `calculadora` | Auxiliar determinista | Evalúa `+ - * /`, paréntesis y signo menos con decimales con coma o punto. Usa `ast` y `Decimal`, **sin `eval`**: cualquier otra cosa (funciones, potencias, nombres) da un error controlado. Resultado con máximo 2 decimales. |
| `describir_imagen` | Multimodal | Lee una imagen de `assets/` con Gemini y devuelve en español los textos y cifras visibles, sin inventar. |
| `rag_ask` | RAG | Delega en `rag.responder.rag_ask`. |
| `planificar_ruta` | API externa + RAG | Convierte origen y destino en coordenadas (Nominatim), pide el itinerario en transporte público (Google Routes) y consulta al RAG la zona y el precio. Si procede, añade una alternativa en BiciMAD (EMT) y el tiempo en el origen (Open-Meteo). Si falla la parte de BiciMAD o el clima, la ruta de transporte llega igual con un aviso. |

## 3. HITL: una aprobación y un rechazo

Se decidió que el planificador de rutas, tras la pausa HITL, si se producía rechazo recalculase una nueva ruta. Pendiente de implementación en un futuro evolutivo.

## 4. Multimodal: imagen usada y resultado

**Imagen.** `assets/imagen_demo.jpg` (800 x 260 px): captura de la sección «Billetes de autobuses EMT» de [RedTransporte](https://www.redtransporte.com/madrid/precios-abonos.html), tomada el 2026-10-14. Contiene cuatro precios:

| Concepto | Importe |
|---|---|
| Billete sencillo EMT | 1,50 € |
| Billete sencillo TransBus | 1,80 € |
| Billete Exprés Aeropuerto | 5,00 € |
| Metrobús 10 viajes | 7,30 € |

**Por qué esta imagen.** Se probó antes con el plano nocturno de la EMT, pero no contenía importes y no permitía la demo de cálculo. No se encontró ningún cartel de tarifas ya hecho en imagen (las webs oficiales publican las tarifas como texto), así que se hizo una captura propia. Aviso: es una captura de una web de terceros, no un cartel oficial, y esa página no indica licencia; se usa con fines educativos.

## 5. Clientes CLI y Streamlit

CLI y Streamlit son clientes del mismo grafo, con la pausa HITL, trazas visibles y nueva conversación. 

**Decisiones.**
- **Contrato aislado en un solo archivo.** Adaptar el cliente al grafo real fue cambiar el formato de `plan` y añadir el identificador del plan, no reescribir nada.
- **No llamar al grafo sin elección con varios planes.** El grafo respondería con un aviso que deja `hitl_pendiente=False` aunque el plan siga pendiente, y la pantalla quedaría desincronizada.
- **«Pasos seguidos» es un resumen, no el registro.** Al adoptar el registro estructurado (entradas con la entrada y la salida completas de cada nodo y tool), el desplegable del chat llegó a mostrar unos 9.700 caracteres en una ruta simple. Pasó a resumirse en una línea de flujo, los pasos de control y las tools, y el detalle completo quedó en el panel de depuración. Con el registro estructurado ya se puede mostrar qué nodos actuaron, algo que antes el contrato no permitía.
- **El mensaje se dibuja antes de llamar al grafo.** Streamlit solo pintaba la pregunta al terminar el turno porque el historial se dibuja antes de la llamada; ahora se dibuja la burbuja y un indicador de espera primero.
- **Demo cambiada.** Se sustituyó el pedido de la imagen por una ruta porque la ruta es el único flujo que enseña el HITL. La imagen demo puede seleccionarse mediante su referencia literal, pero no genera una pausa HITL ni habilita subida de archivos.

## 6. Rutas, BiciMAD y clima

**Por qué decide Python.** La bici se ofrece solo si no se pide hora, la distancia en línea recta entre origen y destino está entre 1 y 6 km, la estación de origen tiene bicis, la de destino huecos libres, ambas están a 500 m o menos y son distintas. Un tiempo no apto (lluvia, llovizna, nieve, tormenta, menos de 5 °C, más de 32 °C o viento de más de 30 km/h) evita ofrecerla. Los umbrales están en `config.py`. El clima solo se consulta si la bici es posible.

**Ambigüedad y lugares.** Nominatim devuelve candidatos y solo se conservan los de la Comunidad de Madrid, sin duplicados. Se normalizan prefijos como «Metro X», que Nominatim no encontraba. Si hay varios candidatos, se pregunta con opciones numeradas y se acepta «2», «2 y 1» o «la 2 y la 1». Si no hay ninguno, el especialista propone un texto alternativo con un único reintento por extremo. El mensaje siempre indica qué opción se usó y cómo corregirla. Este último paso está verificado con tests y pendiente de probar en real.

**Bloques literales.** Zona, precio, clima, bici y opción usada se añaden tal cual a la respuesta, porque el LLM los omitía o duplicaba (sección 8).

## 7. Otras decisiones que impactan en el proyecto

Esta sección completa las decisiones que afectan a la arquitectura y al comportamiento global del sistema, más allá de las funcionalidades desarrolladas en las secciones anteriores.

- **RAG: tablas Markdown como unidades de evidencia.** Las tablas Markdown válidas se detectan durante la fragmentación, se conservan con su título como un único chunk indivisible y se marcan con la estrategia `tabla_markdown`. El resto del documento continúa con el fragmentado ordinario. Así se evita separar filas y perder el contexto de una tarifa o condición.
- **Rutas: fuentes, límites y evidencia.** `planificar_ruta` geocodifica con Nominatim dentro del ámbito configurado (Comunidad de Madrid), pide el itinerario de transporte público a Google Routes y consulta el RAG para la zona y el precio. La zona se consulta antes que el precio; el precio se pregunta primero sin la zona y, si el RAG se abstiene, con ella. Ningún tiempo, zona o importe se estima cuando la fuente no aporta evidencia. Las horas de salida y llegada son excluyentes y se validan antes de llamar a servicios externos. Los lugares ambiguos se resuelven en dos capas: opciones numeradas (solo candidatos de la Comunidad de Madrid, sin duplicados) y, si no hay candidatos, un único reintento con un texto alternativo; el mensaje siempre indica qué opción se usó.
- **Grafo: estado y control de la orquestación.** El grafo LangGraph conserva cada conversación mediante un checkpointer por `thread_id`; su fachada pública mantiene las seis claves `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done`. El supervisor entrega una cola finita de roles admitidos, y Python mantiene los límites transversales de turnos e invocaciones de tools. El HITL solo se activa para planes de ruta válidos.
- **Supervisor: decisiones estructuradas y observabilidad segura.** La respuesta del Supervisor se solicita como JSON y se valida de forma estricta en Python. Si falla el proveedor, el JSON o los roles, se aplica el fallback determinista. El diagnóstico usa solo las categorías `proveedor`, `json_invalido`, `roles_invalidos` y `sin_fallback`, con resúmenes fijos y no sensibles; se expone solo en el resultado del turno, sin persistirlo en el historial, el checkpoint o la traza.
- **Tarifas textuales e imagen demo.** Un catálogo único define roles y restricciones. Una pregunta textual de tarifas sin imagen válida se redirige de `tarifas` a RAG, preservando la allowlist y la evidencia documental. La señal de imagen es efímera y la demo exige la referencia literal aprobada; una corrección semántica se registra en una línea segura adicional de `log`, sin alterar la categoría de fallback ni el contrato público.
- **Alternativa BiciMAD y clima.** La oferta de BiciMAD se decide en Python con reglas configurables de distancia, disponibilidad y estaciones distintas; no la decide el LLM. La disponibilidad procede de EMT y los tiempos de los tramos a pie y bici de Google Routes, sin estimaciones ni alternativas parciales. Sin hora solicitada y solo si la bici es posible por distancia, se consulta el clima actual del origen con Open-Meteo: un tiempo no apto evita ofrecer bici y pide la ruta de transporte con preferencia de menos trayectos a pie; si el clima no está disponible, la bici se ofrece con un aviso. Los campos `bici` y `clima` se añaden de forma aditiva al resultado de ruta, sin cambiar RAG ni el contrato previo.
- **Respuesta final: bloques literales.** La zona, el precio, el clima, la alternativa en bici y la opción de lugar usada se añaden tal cual a la respuesta, porque el LLM los omitía, parafraseaba o duplicaba. El modelo solo redacta el resumen: se le quitan esos bloques del contexto y solo se le pasan los resultados del turno actual.

---

## 8. Fallos conocidos y siguientes pasos

1. **`hora_actual` no conoce los festivos.** Solo distingue laborable, sábado y domingo, así que un festivo se trata como un día laborable y el especialista podría dar un horario equivocado. *Siguiente paso:* incorporar un calendario de festivos como dato (CSV) o consultarlo al RAG.
2. **El bucle depende de que el LLM cumpla el protocolo JSON** (`{"tool","args"}` o `{"final"}`). Si no lo cumple, el especialista devuelve una nota de error controlada, pero la pregunta queda sin responder. *Siguiente paso:* pasar a `bind_tools` de LangChain o validar y reintentar una vez antes de rendirse; en MLOps, medir la tasa de respuestas no interpretables.
3. **El flujo multimodal está limitado a la imagen demo.** Se decidió que la referencia literal `assets/imagen_demo.jpg` seleccione la demo únicamente para ese turno. No hay subida de archivos ni selección de otras rutas; una mención genérica a una imagen se desvía al RAG. Esta restricción evita que una referencia textual active visión sin un archivo autorizado. *Siguiente paso:* si se necesitan imágenes aportadas por la persona usuaria, definir una nueva spec para su validación y transporte seguro, sin ampliar el contrato actual de forma implícita.
4. **La demo de imagen y cálculo no encadena de forma fiable ni es rápida.** `ejecutar_especialista` (`src/agents/base.py`) solo da al modelo el prompt y el mensaje original, no las notas de los especialistas anteriores, así que `auxiliar` no ve los importes que leyó `tarifas`; y el supervisor no siempre incluye `auxiliar`. Una ejecución tardó 161 s. *Siguiente paso:* pasar a cada especialista las notas previas del turno, con un test, y medir la latencia.
5. **El historial no guarda las respuestas del asistente.** Solo guarda los mensajes de la persona, así que el supervisor no sabía a qué respondía un «2 y 2» y lo tomó por una suma. Lo resolví con una regla determinista para elegir opciones, pero cualquier otro seguimiento que dependa de lo mostrado tendrá el mismo problema. *Siguiente paso:* guardar las respuestas en el estado.
6. **El precio por ruta no está resuelto del todo.** El RAG devuelve a veces varias opciones sin etiquetar (por ejemplo 1,50 / 1,80 / 2,00 € para un billete sencillo) y no indica cuál corresponde a la ruta. Además, mi índice local estaba incompleto (313 de 4054 chunks, solo 7 de 3748 paradas), por lo que la zona fallaba, y en los chunks de paradas aparecen caracteres rotos («Descripción»). *Siguiente paso:* Revisar la codificación del CSV en la ingesta.
7. **El checkpointer del grafo es en memoria.** Al reiniciar el proceso no se conserva una conversación ni los planes pendientes.
8. **Las rutas se calculan solo en transporte público y dentro de la Comunidad de Madrid.** La alternativa en bici es una oferta adicional (sin hora pedida, de 1 a 6 km y con buen tiempo) y no sustituye a la ruta. No existe un modo «solo bici»: una petición «en bici» calcula igualmente la ruta de transporte. Si la bici queda fuera del rango de 1 a 6 km, el mensaje no distingue entre trayecto demasiado corto y demasiado largo.
9. **La alternativa en BiciMAD depende de la EMT**, que es lenta: el login tiene un límite de 10 s y las estaciones de 20 s, de modo que en el peor caso añade entre 25 y 30 s. El criterio de «estación activa» es una suposición no verificada con la EMT.
10. **El precio de algunos títulos (por ejemplo el abono joven) depende de que el RAG recupere su tabla**, y a veces no la recupera. Cuando el RAG devuelve varias opciones sin etiquetar, la respuesta las muestra todas sin indicar cuál corresponde a la ruta. Renfe Avant se trata como tren pesado, porque Google no lo distingue de Cercanías.
11. **La web muestra los pasos de cada turno (tools y registro), pero no qué especialista lanzó cada tool:** el contrato público del grafo expone seis claves y no incluye ese dato.
12. **El RAG se ancla al corpus disponible y no garantiza una abstención determinista fuera de él**; la instrucción de abstención se aplica en el prompt.
