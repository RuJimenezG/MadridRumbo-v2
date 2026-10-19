# Spec 005 — Clientes CLI y Streamlit del grafo multiagente

> Estado: Aprobada · Fecha: 2026-10-15 · Responsable: José Manuel Gil Ruiz

## Contexto y objetivo

El enunciado exige que el mismo grafo multiagente se use desde un CLI y desde una app Streamlit, con la pausa HITL (aprobar o rechazar el plan antes de cerrar), trazas visibles y persistencia por identificador de conversación. Hoy `main.py` está vacío y `app.py` es un chat que llama directamente al RAG, sin grafo, sin HITL y sin trazas (spec 000). El grafo lo construye otra persona del equipo y aún no existe.

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

- RF-6: CUANDO el grafo devuelve un plan pendiente de aprobación, EL SISTEMA muestra el plan y pregunta si se aprueba o se rechaza.
- RF-7: EL SISTEMA no cierra ningún plan sin una decisión explícita de la persona usuaria, salvo en la demo con `--auto-aprobar`.
- RF-8: CUANDO la persona aprueba, EL SISTEMA transmite la aprobación al grafo y muestra que la conversación ha terminado únicamente si el grafo lo indica.
- RF-9: CUANDO la persona rechaza, EL SISTEMA transmite el rechazo al grafo, indica que el plan no se ha cerrado y permite escribir otro mensaje en la misma conversación.
- RF-10: SI la respuesta a la pregunta de aprobar o rechazar no es válida, ENTONCES EL SISTEMA vuelve a preguntar sin consultar al grafo.

### Demo del CLI

- RF-11: CUANDO se ejecuta `python main.py --demo`, EL SISTEMA lanza tres pedidos fijos, uno tras otro, cada uno en su propia conversación: «¿Hasta qué hora hay metro hoy?», «Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» y «¿Cuál es la capital de Francia?».
- RF-12: CUANDO se ejecuta `--demo` sin `--auto-aprobar`, EL SISTEMA pide la aprobación humana de cada plan.
- RF-13: DONDE se ejecute `python main.py --demo --auto-aprobar`, EL SISTEMA aprueba cada plan automáticamente e indica en pantalla que lo ha hecho.
- RF-14: SI se usa `--auto-aprobar` sin `--demo`, ENTONCES EL SISTEMA muestra un error y no inicia el chat.

### Trazas visibles

- RF-15: EL SISTEMA muestra, en cada turno del CLI, la respuesta, el registro de qué especialistas actuaron y la traza de tools con su nombre y estado.
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
- RF-24: EL SISTEMA ofrece un panel de depuración desplegable con el registro de especialistas, la traza de tools, el identificador de conversación y los indicadores de plan pendiente y de conversación terminada.
- RF-25: SI el grafo falla, ENTONCES EL SISTEMA muestra un mensaje de error en español sin perder el historial.

### Contrato común

- RF-26: EL SISTEMA obtiene del grafo la respuesta, el plan, la traza y los indicadores de plan pendiente y de conversación terminada, y los presenta con el mismo contenido en el CLI y en Streamlit para un mismo pedido.
- RF-27: EL SISTEMA no decide en los clientes si la conversación ha terminado ni qué especialista actúa: solo lo muestra.
- RF-28: DONDE esté activado el modo simulado mediante una variable de entorno, EL SISTEMA usa un grafo simulado en lugar del real y lo indica al iniciar el CLI y en la barra lateral de Streamlit.
- RF-29: SI no hay grafo real disponible y el modo simulado no está activado, ENTONCES EL SISTEMA muestra un mensaje en español que explica cómo activar el modo simulado y no inicia el chat.

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
- Grafo real todavía sin subir: RF-28 y RF-29.
- `--auto-aprobar` sin `--demo`: RF-14.
- Pulsar «Nueva conversación» con un plan pendiente: RF-23 (se descarta el plan y el estado).
- Pulsar Aprobar o Rechazar sin plan pendiente: RF-22.

## Fuera de alcance

- La lógica del grafo, el supervisor, los especialistas, la síntesis, el HITL interno y el checkpointer (los construye otra persona del equipo).
- Pedir o enviar el motivo del rechazo: el rechazo solo descarta el plan y se continúa con otro mensaje.
- Persistencia en disco entre reinicios (SqliteSaver) y despliegue.
- Subir imágenes desde Streamlit: solo se usa la imagen demo.
- Editar el plan antes de aprobarlo.
- Autenticación de usuarios y varios usuarios simultáneos.
- Conservar el chat antiguo de `app.py` que consultaba directamente al RAG; sigue disponible el CLI del módulo RAG.

## Criterios de finalización

- Todos los RF con test en verde (`pytest`) sin API, contra un grafo simulado, salvo los de interfaz web que se validan a mano.
- Demo manual del CLI (`--demo`) y de Streamlit contra el grafo real cuando exista.

## Dudas abiertas

Ninguna.

## Decisiones tomadas

- **Contrato con el grafo (2026-10-15).** Se propone en el plan un contrato basado en el enunciado. Como el grafo real aún no existe, se toma como propuesta y se ajustará cuando se suba el real.
- **Streamlit con plan pendiente (2026-10-15).** Se bloquea el cuadro de mensaje hasta que se apruebe o se rechace el plan (RF-22b).
- Desarrollo contra un grafo simulado, con modo simulado visible para el usuario (RF-28 y RF-29).
- El rechazo solo descarta el plan; no se pide motivo.
- `app.py` pasa a ser el cliente del grafo y sustituye al chat directo al RAG.
- Modos del CLI: interactivo por defecto, `--demo` y `--auto-aprobar`.
- La demo lanza tres pedidos fijos (RF-11).
