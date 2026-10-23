# Spec 008 — Clientes CLI y Streamlit del grafo multiagente

> Estado: Aprobada (cambios del 2026-10-19 aprobados el mismo día) · Aprobada originalmente el 2026-10-15 · Antes numerada 005 · Responsable: José Manuel Gil Ruiz

## Contexto y objetivo

El enunciado exige que el mismo grafo multiagente se use desde un CLI y desde una app Streamlit, con la pausa HITL (aprobar o rechazar el plan antes de cerrar), trazas visibles y persistencia por identificador de conversación. Hoy `main.py` está vacío y `app.py` es un chat que llama directamente al RAG, sin grafo, sin HITL y sin trazas (spec 000). El grafo lo construyó otra persona del equipo y ya está en `develop` (specs 005, 006 y 007): expone el contrato que esta spec proponía.

**Cambio del 2026-10-19.** Al leer el grafo real aparecen diferencias que afectan a los clientes: los planes pendientes no son textos sino rutas con identificador y datos estructurados; puede haber varios planes a la vez y hay que indicar cuál se aprueba o rechaza; solo las consultas de rutas pausan para aprobación (horarios y RAG cierran directamente); y el chat web no debe mostrar los diagnósticos técnicos del supervisor.

Esta spec define los dos clientes como **capas finas** sobre el grafo: muestran lo que el grafo devuelve y le trasladan las decisiones de la persona usuaria, sin decidir nada por su cuenta. Se desarrollan y prueban contra un grafo simulado que cumple el contrato acordado, y se enchufan al grafo real cuando exista.

## Usuarios / actores

- Persona usuaria que consulta transporte de Madrid por terminal o por la web.
- Persona que presenta el proyecto y necesita una demo reproducible con un solo comando.
- Equipo, que valida el HITL y las trazas.

## Historias de usuario

- H1: Como usuaria quiero conversar con el asistente por terminal y aprobar o rechazar su plan a mano para controlar lo que se cierra.
- H2: Como usuaria quiero hacer lo mismo desde una web con botones y ver la conversación completa.
- H3: Como presentadora quiero una demo de un solo comando con varios casos representativos.
- H4: Como equipo quiero ver qué especialista y qué tools actuaron, para depurar y para el informe.
- H5: Como equipo quiero que CLI y web muestren lo mismo ante el mismo pedido.

## Requisitos funcionales

### Chat por terminal (CLI)

- RF-1: CUANDO se ejecuta `python main.py` sin opciones, EL SISTEMA abre un chat interactivo en el que la persona escribe mensajes y ve la respuesta del asistente.
- RF-2: MIENTRAS dure el chat interactivo, EL SISTEMA envía todos los mensajes con el mismo identificador de conversación.
- RF-3: SI la persona envía un mensaje vacío, ENTONCES EL SISTEMA no consulta al grafo y vuelve a pedir un mensaje.
- RF-4: CUANDO la persona escribe `salir`, EL SISTEMA termina sin error.
- RF-5: SI el grafo falla, ENTONCES EL SISTEMA muestra un mensaje de error en español y permite seguir escribiendo.

### Aprobación humana (HITL) en el CLI

- RF-6: CUANDO el grafo devuelve un plan pendiente de aprobación, EL SISTEMA muestra el plan con su identificador y un resumen legible y pregunta si se aprueba o se rechaza.
- RF-7: EL SISTEMA no cierra ningún plan sin una decisión explícita de la persona usuaria, salvo en la demo con `--auto-aprobar`.
- RF-8: CUANDO la persona aprueba, EL SISTEMA transmite la aprobación al grafo y muestra que la conversación ha terminado únicamente si el grafo lo indica.
- RF-9: CUANDO la persona rechaza, EL SISTEMA transmite el rechazo al grafo, indica que el plan no se ha cerrado y, si el grafo devuelve otro plan pendiente, lo muestra; si no, permite escribir otro mensaje en la misma conversación.
- RF-10: SI la respuesta a la pregunta de aprobar o rechazar no es válida, ENTONCES EL SISTEMA vuelve a preguntar sin consultar al grafo.

### Demo del CLI

- RF-11: CUANDO se ejecuta `python main.py --demo`, EL SISTEMA lanza tres pedidos fijos, uno tras otro, cada uno en su propia conversación: «¿Hasta qué hora hay metro hoy?», «¿Cómo puedo ir desde la Puerta del Sol hasta la Estación de Atocha?» y «¿Cuál es la capital de Francia?».
- RF-12: CUANDO se ejecuta `--demo` sin `--auto-aprobar`, EL SISTEMA pide la aprobación humana de cada plan.
- RF-13: DONDE se ejecute `python main.py --demo --auto-aprobar`, EL SISTEMA aprueba cada plan automáticamente e indica en pantalla que lo ha hecho.
- RF-14: SI se usa `--auto-aprobar` sin `--demo`, ENTONCES EL SISTEMA muestra un error y no inicia el chat.

### Trazas visibles

- RF-15: EL SISTEMA muestra, en cada turno del CLI, la respuesta, el registro de depuración completo del grafo (spec 011) y la traza de tools con su nombre y estado.
- RF-16: EL SISTEMA muestra, en cada turno del CLI, el identificador de conversación y si hay un plan pendiente o la conversación ha terminado.

### Chat web (Streamlit)

- RF-17: CUANDO se ejecuta `streamlit run app.py`, EL SISTEMA muestra un chat con el historial de la conversación.
- RF-18: MIENTRAS la sesión del navegador siga abierta, EL SISTEMA mantiene el mismo identificador de conversación entre mensajes.
- RF-19: CUANDO el grafo devuelve un plan pendiente, EL SISTEMA muestra el plan y los botones Aprobar y Rechazar en la barra lateral.
- RF-20: CUANDO la persona pulsa Aprobar, EL SISTEMA transmite la aprobación al grafo y muestra que la conversación ha terminado únicamente si el grafo lo indica.
- RF-21: CUANDO la persona pulsa Rechazar, EL SISTEMA transmite el rechazo al grafo, descarta el plan en pantalla y permite escribir otro mensaje en la misma conversación.
- RF-22: MIENTRAS no haya plan pendiente, EL SISTEMA mantiene los botones Aprobar y Rechazar desactivados.
- RF-22b: MIENTRAS haya un plan pendiente de decisión, EL SISTEMA mantiene desactivado el cuadro de mensaje.
- RF-23: CUANDO la persona pulsa «Nueva conversación», EL SISTEMA crea un identificador nuevo y vacía el historial y el estado en pantalla.
- RF-24: EL SISTEMA ofrece un panel de depuración desplegable con el registro de depuración completo del grafo (spec 011), la traza de tools, el identificador de conversación y los indicadores de plan pendiente y de conversación terminada.
- RF-25: SI el grafo falla, ENTONCES EL SISTEMA muestra un mensaje de error en español sin perder el historial.
- RF-38: CUANDO la persona envía un mensaje en la web, EL SISTEMA lo muestra en el chat de inmediato, sin esperar a la respuesta del grafo, y muestra un indicador de espera hasta que llega la respuesta.
- RF-39: EL SISTEMA muestra bajo cada respuesta del asistente en la web un desplegable «Pasos seguidos» con un resumen del turno: las tools ejecutadas (nombre, estado y extracto), los pasos de control que no sean diagnósticos técnicos del supervisor (RF-35) y, para las entradas heredadas en texto, el propio texto. La entrada, la salida y el detalle completos de cada paso solo se muestran en el panel de depuración.
- RF-40: EL SISTEMA conserva los pasos de cada turno junto a su respuesta, de modo que el desplegable de una respuesta anterior no cambia con los turnos siguientes.
- RF-42: CUANDO el registro del turno trae entradas de nodo, EL SISTEMA muestra como primera línea de «Pasos seguidos» el flujo recorrido, con los nodos en el orden en que actuaron (por ejemplo «Flujo: supervisor → rutas → sintetizador»), sin contar el diagnóstico técnico del supervisor.
- RF-41: SI un turno no ejecutó ninguna tool ni dejó ninguna entrada de registro visible, ENTONCES EL SISTEMA no muestra el desplegable «Pasos seguidos» en esa respuesta.

### Contrato común

- RF-26: EL SISTEMA obtiene del grafo la respuesta, el plan, la traza y los indicadores de plan pendiente y de conversación terminada, y los presenta con el mismo contenido en el CLI y en Streamlit para un mismo pedido.
- RF-27: EL SISTEMA no decide en los clientes si la conversación ha terminado ni qué especialista actúa: solo lo muestra.
- RF-28: DONDE esté activado el modo simulado mediante una variable de entorno, EL SISTEMA usa un grafo simulado en lugar del real y lo indica al iniciar el CLI y en la barra lateral de Streamlit.
- RF-29: SI no hay grafo real disponible y el modo simulado no está activado, ENTONCES EL SISTEMA muestra un mensaje en español que explica cómo activar el modo simulado y no inicia el chat.
- RF-30: CUANDO el grafo devuelve un plan de ruta, EL SISTEMA muestra su identificador, el origen, el destino, la duración total, los tramos con su modo y línea, y la zona y el precio cuando existan.
- RF-31: CUANDO hay más de un plan pendiente, EL SISTEMA pide elegir el plan por su número antes de aprobar o rechazar, y transmite al grafo el identificador del plan elegido.
- RF-32: CUANDO hay un único plan pendiente, EL SISTEMA no pide elegir plan y lo aprueba o rechaza directamente.
- RF-33: SI un plan tiene un formato que el cliente no reconoce, ENTONCES EL SISTEMA muestra sus datos de forma legible en lugar de fallar.
- RF-34: CUANDO el grafo devuelve una respuesta sin plan pendiente, EL SISTEMA muestra la respuesta y no pregunta nada.
- RF-35: EL SISTEMA muestra las entradas técnicas del supervisor en el CLI y en el panel de depuración de la web, y no las muestra en el chat ni en «Pasos seguidos».
- RF-36: DONDE esté activo el modo simulado, EL SISTEMA devuelve planes con el mismo formato que el grafo real y, para algunos pedidos, varios planes a la vez.
- RF-37: CUANDO una persona escribe una consulta que contiene literalmente `assets/imagen_demo.jpg` en el CLI o en Streamlit, EL SISTEMA transmite ese mensaje sin modificar al mismo grafo que usan ambos clientes.

## Requisitos no funcionales

- Coste: ningún test de esta spec llama a un LLM, a embeddings, a ChromaDB ni a Streamlit en ejecución; usan un grafo simulado.
- Idioma: mensajes, preguntas y botones en español.
- Modularidad: la presentación de resultados compartida vive aparte de las dos interfaces; los clientes no contienen lógica del grafo.
- Configuración: las preguntas y los textos fijos de la demo en un único punto de configuración.
- Seguridad: los clientes no leen ni muestran el `.env` ni las claves.

## Casos límite

- Mensaje vacío o solo espacios: RF-3.
- Respuesta inválida al aprobar o rechazar: RF-10.
- Rechazar y escribir otro mensaje en la misma conversación: RF-9 y RF-21.
- Interrupción con `salir` o `Ctrl+C`: RF-4.
- Fallo del grafo en mitad de la conversación: RF-5 y RF-25.
- Dos o más planes de ruta pendientes a la vez: RF-31 y RF-32.
- Plan con campos ausentes o de otro tipo (p. ej. ruta sin tramos): RF-33.
- Consulta de horarios o de RAG, que el grafo cierra sin pausa: RF-34.
- Mensaje nuevo mientras hay un plan pendiente: lo bloquea el cliente (RF-22b) y, si llegara al grafo, este responde con un aviso.
- Grafo real todavía sin subir: RF-28 y RF-29.
- `--auto-aprobar` sin `--demo`: RF-14.
- Pulsar «Nueva conversación» con un plan pendiente: RF-23 (se descarta el plan y el estado).
- Pulsar Aprobar o Rechazar sin plan pendiente: RF-22.
- Una consulta que contiene literalmente `assets/imagen_demo.jpg`: RF-37 y las guardas de imagen de la spec 007.

## Fuera de alcance

- Subir imágenes desde los clientes o seleccionar archivos arbitrarios: solo se puede seleccionar la imagen demo configurada mediante la referencia literal `assets/imagen_demo.jpg`.

- La lógica del grafo, el supervisor, los especialistas, la síntesis, el HITL interno y el checkpointer (los construye otra persona del equipo).
- Pedir o enviar el motivo del rechazo: el rechazo solo descarta el plan y se continúa con otro mensaje.
- Persistencia en disco entre reinicios (SqliteSaver) y despliegue.
- Editar el plan antes de aprobarlo.
- Autenticación de usuarios y varios usuarios simultáneos.
- Conservar el chat antiguo de `app.py` que consultaba directamente al RAG; sigue disponible el CLI del módulo RAG.

## Criterios de finalización

- Todos los RF con test en verde (`pytest`) sin API, contra un grafo simulado, salvo los de interfaz web que se validan a mano.
- Demo manual del CLI (`--demo`) y de Streamlit contra el grafo real cuando exista.

## Dudas abiertas

Ninguna. Cerrada: **alcance de RF-35.** Los diagnósticos del supervisor se ocultan en el chat y en «Pasos seguidos» y se muestran en el CLI y en el panel de depuración de la web (cambio del 2026-10-23, al adoptar el registro estructurado de la spec 011; antes se ocultaban en toda la web).

## Decisiones tomadas

- **Pasos seguidos (2026-10-22, incidencia #19).** El CLI ya muestra en cada turno el registro y la traza (RF-15) y no cambia. La web pasa a mostrarlos bajo cada respuesta (RF-39 a RF-41), con el filtro de RF-35. Solo se dispone de lo que el contrato de seis claves expone: la traza de tools y el registro. El recorrido por especialistas (qué rol actuó) no es visible hasta que el grafo lo exponga, y eso lo decide su autor.
- **«Pasos seguidos» como resumen (2026-10-23).** La spec 011 convierte `log` en entradas estructuradas con la entrada y la salida completas de cada nodo y tool. Volcarlas en el chat daba unos 9.700 caracteres en una ruta simple. «Pasos seguidos» pasa a ser un resumen (flujo de nodos, pasos de control y tools de la traza) y el detalle completo queda en el panel de depuración. Con el registro estructurado ya es posible mostrar el flujo por especialistas (RF-42), cosa que antes no.
- **Mensaje visible al enviar (2026-10-22).** Streamlit solo dibujaba el mensaje al terminar el turno, porque el historial se pinta antes de llamar al grafo. Ahora se dibuja la burbuja de la persona y un indicador de espera antes de llamarlo (RF-38).

- **Contrato con el grafo (2026-10-15).** Se propone en el plan un contrato basado en el enunciado. Como el grafo real aún no existe, se toma como propuesta y se ajustará cuando se suba el real.
- **Streamlit con plan pendiente (2026-10-15).** Se bloquea el cuadro de mensaje hasta que se apruebe o se rechace el plan (RF-22b).
- Desarrollo contra un grafo simulado, con modo simulado visible para el usuario (RF-28 y RF-29).
- El rechazo solo descarta el plan; no se pide motivo.
- `app.py` pasa a ser el cliente del grafo y sustituye al chat directo al RAG.
- Modos del CLI: interactivo por defecto, `--demo` y `--auto-aprobar`.
- La demo lanza tres pedidos fijos (RF-11), cambiados el 2026-10-19 a horarios, ruta y fuera de corpus: con el grafo real solo las rutas pausan para HITL; una consulta que no selecciona explícitamente la imagen demo se desvía al RAG.
- **Imagen demo por referencia literal (aprobada 2026-10-19).** La mención exacta `assets/imagen_demo.jpg` en un mensaje selecciona la imagen demo para ese turno en ambos clientes; no habilita subida de archivos ni selección de otras rutas.
- **Contrato confirmado (2026-10-19)** contra `src/agent.py`: mismas funciones, firmas y seis claves. Cambia solo el formato de `plan` (lista de `{id, resultado}`) y que `aprobar_plan` necesita `plan_id_seleccionado` si hay varios planes. El grafo trata el checkpoint como fuente de verdad: el `estado` que envía el cliente solo sirve para indicar el plan elegido.
- **Renumerada a 008** el 2026-10-19: la 005, la 006 y la 007 ya existían en `develop` (grafo y supervisor).
