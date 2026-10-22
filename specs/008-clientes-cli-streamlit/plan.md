# Plan técnico — Spec 008

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento que no esté en la spec.
> **Actualizado el 2026-10-19** para el grafo real: la sección «Cambios por el grafo real» del final prevalece sobre lo anterior cuando se contradicen.

## Archivos afectados
| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/clientes/__init__.py` | Crear | Paquete de los clientes | — |
| `src/clientes/contrato.py` | Crear | Contrato con el grafo: claves del estado, `estado_vacio()` y `normalizar_estado()` | RF-26, RF-27 |
| `src/clientes/presentacion.py` | Crear | Funciones puras compartidas: `formatear_turno`, `interpretar_decision`, `es_salida`, `es_mensaje_vacio`, `datos_depuracion` | RF-3, RF-4, RF-10, RF-15, RF-16, RF-24, RF-26 |
| `src/clientes/sesion.py` | Crear | `SesionChat`: identificador de conversación, estado, enviar, decidir, nueva conversación y control de errores | RF-2, RF-5, RF-8, RF-9, RF-18 a RF-23, RF-22b, RF-25, RF-27 |
| `src/clientes/grafo_falso.py` | Crear | Grafo simulado que cumple el contrato (para pruebas y modo simulado) | RF-28 |
| `src/clientes/cargar.py` | Crear | `cargar_agente()`: grafo real o simulado según la variable de entorno | RF-28, RF-29 |
| `src/clientes/cli.py` | Crear | `ejecutar_cli(argumentos, agente, leer, escribir)`: chat, HITL y demo con entrada y salida inyectables | RF-1 a RF-16 |
| `main.py` | Modificar (hoy vacío) | Capa fina: lee argumentos y llama a `ejecutar_cli` | RF-1, RF-11 a RF-14 |
| `app.py` | Reemplazar | Cliente Streamlit del grafo: chat, barra lateral con Aprobar y Rechazar, panel de depuración, Nueva conversación | RF-17 a RF-25, RF-22b, RF-28 |
| `config.py` | Modificar | `PEDIDOS_DEMO`, `PALABRAS_SALIR`, `PALABRAS_APROBAR`, `PALABRAS_RECHAZAR`, `VARIABLE_MODO_SIMULADO` | RF-4, RF-10, RF-11, RF-28 |
| `tests/test_presentacion.py` | Crear | Funciones puras | RF-3, RF-4, RF-10, RF-15, RF-16, RF-24, RF-26 |
| `tests/test_sesion.py` | Crear | Lógica de sesión compartida con Streamlit | RF-2, RF-5, RF-8, RF-9, RF-18 a RF-23, RF-22b, RF-25, RF-27 |
| `tests/test_cli.py` | Crear | Chat y HITL con entrada y salida falsas | RF-1 a RF-10 |
| `tests/test_cli_demo.py` | Crear | Demo y `--auto-aprobar` | RF-11 a RF-14 |
| `tests/test_cargar_agente.py` | Crear | Modo simulado y ausencia del grafo real | RF-28, RF-29 |
| `tests/test_grafo_falso.py` | Crear | El simulado cumple el contrato | RF-28 |

No se añaden dependencias: Streamlit ya está en `requirements.txt`.

## Contrato

**Propuesta** basada en el enunciado (`procesar_turno` y `aprobar_plan` en `src/agent.py`). Se ajustará cuando el grafo real exista.

```text
procesar_turno(estado: dict, mensaje: str, thread_id: str) -> dict
aprobar_plan(estado: dict, thread_id: str, aprobado: bool) -> dict
```

El estado que devuelve el grafo es un diccionario con estas claves. Las que falten se rellenan con su valor por defecto:

| Clave | Tipo | Por defecto | Significado |
|---|---|---|---|
| `respuesta` | `str` | `""` | Respuesta para la persona usuaria |
| `plan` | `list[dict]` | `[]` | Planes pendientes de decisión: `{"id": "ruta-1", "resultado": {...}}` (ver «Cambios por el grafo real») |
| `log` | `list[str]` | `[]` | Qué especialistas actuaron, p. ej. `[supervisor] -> horarios` |
| `traza` | `list[dict]` | `[]` | Entradas `{"tool", "args", "status", "preview"}` (las de `ejecutar_tool`) |
| `hitl_pendiente` | `bool` | `False` | Hay un plan esperando aprobar o rechazar |
| `done` | `bool` | `False` | La conversación ha terminado; **solo lo pone el grafo** |

Ejemplo de turno:
```text
sesion.enviar("¿Hasta qué hora hay metro hoy?")
→ estado: respuesta="El metro cierra a la 1:30...", plan=["Informar horario"], hitl_pendiente=True, done=False
sesion.decidir(aprobado=True)
→ estado: hitl_pendiente=False, done=True
```

Cómo se escoge el grafo:
```text
cargar_agente():
  si el entorno trae MADRIDRUMBO_GRAFO=falso -> grafo_falso (y se avisa al iniciar)
  si no, intenta importar src.agent
      si falla -> error en español que indica cómo activar el modo simulado
```

## Lógica clave
```text
SesionChat(agente):
  thread_id = nuevo uuid ; estado = estado_vacio()
  enviar(mensaje):  # RF-3 se comprueba antes, en el cliente
      try: estado = normalizar(agente.procesar_turno(estado, mensaje, thread_id))
      except Exception: error = "mensaje en español"; el historial y el estado no cambian
  decidir(aprobado):
      try: estado = normalizar(agente.aprobar_plan(estado, thread_id, aprobado))
      except Exception: igual que arriba
  puede_decidir  = estado["hitl_pendiente"]           # RF-22
  puede_escribir = not estado["hitl_pendiente"]       # RF-22b
  nueva_conversacion(): thread_id = nuevo uuid ; estado = estado_vacio() ; historial vacío   # RF-23
  # done y hitl_pendiente se copian del grafo; la sesión nunca los calcula (RF-27)

cli (ejecutar_cli):
  --auto-aprobar sin --demo -> error y salida                      # RF-14
  --demo: por cada pedido de PEDIDOS_DEMO -> nueva SesionChat, enviar, y si hay plan:
        con --auto-aprobar aprueba e informa; sin él pregunta       # RF-11 a RF-13
  interactivo: bucle leer mensaje
        salida -> terminar ; vacío -> repetir ; si no -> enviar
        si hitl_pendiente: mostrar plan y preguntar hasta decisión válida   # RF-6, RF-7, RF-10
        mostrar formatear_turno(estado, thread_id)                  # RF-15, RF-16, RF-26

app.py (Streamlit):
  sesion en st.session_state ; historial en pantalla
  chat_input desactivado si not sesion.puede_escribir               # RF-22b
  barra lateral: botones Aprobar y Rechazar desactivados si not sesion.puede_decidir
  expander con datos_depuracion(estado, thread_id)                            # RF-24
  botón "Nueva conversación" -> sesion.nueva_conversacion()
  aviso del modo simulado en la barra lateral                       # RF-28
```

## Decisiones técnicas
| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| `SesionChat` compartida por CLI y Streamlit | Cada cliente con su lógica | Cumple la constitución (clientes finos, mismo contrato) y permite probar la web sin Streamlit |
| `ejecutar_cli(argumentos, agente, leer, escribir)` con entrada y salida inyectables | Usar `input()` y `print()` directamente | Se prueba con funciones falsas sin simular la terminal |
| Presentación en funciones puras (`formatear_turno`) | Formatear en cada cliente | Garantiza el mismo contenido en CLI y web (RF-26) |
| Estado como diccionario con claves por defecto | Clase de datos rígida | El grafo real puede añadir claves; los clientes solo leen las que conocen |
| Grafo simulado dentro de `src/clientes/` con variable de entorno | Simulado solo en `tests/` | Permite hacer las demos manuales antes de que exista el grafo real (RF-28) |
| `done` y `hitl_pendiente` se copian del grafo | Calcularlos en el cliente | Constitución y RF-27 |
| Un identificador por conversación con `uuid4` | Contador o fecha | Único y válido como `thread_id` del checkpointer |
| Streamlit no se prueba con tests | Pruebas con `streamlit.testing` | Se valida a mano, como indica `docs/tests_sin_api.md`; la lógica queda cubierta en `SesionChat` |

## Estrategia de tests
Todos sin API (ver `docs/tests_sin_api.md`): grafo simulado, `leer` con una lista de entradas y `escribir` que acumula líneas.
- **RF-1/2/3/4/5**: CLI con grafo falso y entradas `["hola", "", "salir"]`; se comprueba que se imprime la respuesta, que todos los mensajes llevan el mismo `thread_id`, que el vacío no llega al grafo, que `salir` termina y que un grafo que lanza excepción no corta el chat.
- **RF-6/7/8/9/10**: grafo falso que devuelve plan pendiente; `["pedido", "x", "n", "salir"]` comprueba la pregunta, la repetición ante «x» y el rechazo; `aprobar_plan` nunca se llama si no hay decisión; un grafo que devuelve `done=False` tras aprobar no muestra «terminada».
- **RF-11/12/13/14**: `--demo` hace tres consultas con tres `thread_id` distintos y los textos de `PEDIDOS_DEMO`; con `--auto-aprobar` no se llama a `leer`; sin él se pregunta; `--auto-aprobar` solo da error y no abre el chat.
- **RF-15/16/26**: `formatear_turno` incluye respuesta, log, traza, identificador y banderas; test de que la salida del CLI contiene exactamente ese texto.
- **RF-18/19/20/21/22/22b/23/25/27**: pruebas sobre `SesionChat` (identificador estable, `puede_decidir` y `puede_escribir`, aprobar y rechazar, nueva conversación, error que conserva el historial, `done` lo decide el grafo).
- **RF-24**: `datos_depuracion` devuelve log, traza, `thread_id` y banderas; el desplegable visual se ve a mano.
- **RF-28/29**: con la variable activada se carga el simulado y se avisa; sin grafo real y sin variable se devuelve el error con las instrucciones.
- **A mano (sin tests)**: RF-17, la apariencia de RF-19, RF-22, RF-22b, RF-23 y RF-24 en Streamlit, y la demo completa del CLI. Se hacen con el modo simulado y después con el grafo real; se anotan en `validacion.md`.

## Riesgos
- El contrato es una propuesta: si el grafo real usa otros nombres o campos, hay que ajustar `contrato.py` y `cargar.py`, no el resto. Está aislado a propósito.
- El simulado puede ocultar fallos del grafo real (p. ej. cómo informa de la pausa HITL): la demo con el grafo real debe repetirse.
- Reemplazar `app.py` borra el chat directo al RAG; conviene avisar al equipo antes de subir.
- `main.py` y `app.py` son archivos compartidos y puede haber conflicto si alguien los toca en otra rama.
- Streamlit vuelve a ejecutar el script en cada interacción: el estado debe vivir en `st.session_state` y no en variables globales.

## Trazabilidad
| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | `cli.py`, `main.py` | `tests/test_cli.py::test_chat_interactivo_responde` |
| RF-2 | `sesion.py` | `tests/test_cli.py::test_mismo_thread_id_en_todo_el_chat` |
| RF-3 | `presentacion.py`, `cli.py` | `tests/test_cli.py::test_mensaje_vacio_no_llama_al_grafo` |
| RF-4 | `presentacion.py`, `cli.py` | `tests/test_cli.py::test_salir_termina` |
| RF-5 | `sesion.py` | `tests/test_cli.py::test_fallo_del_grafo_no_corta_el_chat` |
| RF-6 | `cli.py` | `tests/test_cli.py::test_plan_pendiente_pregunta_decision` |
| RF-7 | `cli.py` | `tests/test_cli.py::test_no_cierra_sin_decision` |
| RF-8 | `sesion.py`, `cli.py` | `tests/test_cli.py::test_aprobar_muestra_terminada_solo_si_el_grafo_lo_dice` |
| RF-9 | `sesion.py`, `cli.py` | `tests/test_cli.py::test_rechazar_permite_seguir` |
| RF-10 | `presentacion.py`, `cli.py` | `tests/test_cli.py::test_decision_invalida_repregunta` |
| RF-11 | `cli.py`, `config.py` | `tests/test_cli_demo.py::test_demo_lanza_tres_pedidos` |
| RF-12 | `cli.py` | `tests/test_cli_demo.py::test_demo_sin_auto_pide_aprobacion` |
| RF-13 | `cli.py` | `tests/test_cli_demo.py::test_demo_auto_aprueba` |
| RF-14 | `cli.py` | `tests/test_cli_demo.py::test_auto_aprobar_sin_demo_da_error` |
| RF-15 | `presentacion.py` | `tests/test_presentacion.py::test_formato_incluye_respuesta_log_traza` |
| RF-16 | `presentacion.py` | `tests/test_presentacion.py::test_formato_incluye_thread_id_y_banderas` |
| RF-17 | `app.py` | Manual |
| RF-18 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_thread_id_estable` |
| RF-19 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_plan_pendiente_activa_decision` + manual |
| RF-20 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_aprobar_transmite_al_grafo` |
| RF-21 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_rechazar_descarta_plan` |
| RF-22 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_decidir_solo_con_plan_pendiente` |
| RF-22b | `sesion.py`, `app.py` | `tests/test_sesion.py::test_no_se_puede_escribir_con_plan_pendiente` |
| RF-23 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_nueva_conversacion` |
| RF-24 | `presentacion.py`, `app.py` | `tests/test_presentacion.py::test_datos_depuracion` + manual |
| RF-25 | `sesion.py`, `app.py` | `tests/test_sesion.py::test_error_conserva_historial` |
| RF-26 | `presentacion.py` | `tests/test_presentacion.py::test_cli_usa_el_mismo_formato` |
| RF-27 | `sesion.py` | `tests/test_sesion.py::test_done_lo_decide_el_grafo` |
| RF-28 | `cargar.py`, `grafo_falso.py` | `tests/test_cargar_agente.py::test_modo_simulado_usa_grafo_falso`, `tests/test_grafo_falso.py::test_cumple_el_contrato` |
| RF-29 | `cargar.py` | `tests/test_cargar_agente.py::test_sin_grafo_real_da_error_claro` |

## Cambios por el grafo real (2026-10-19)

El grafo real (`src/agent.py`, specs 005 a 007) cumple nuestro contrato, con tres diferencias que recogen los RF-30 a RF-36.

### Contrato confirmado

```text
procesar_turno(estado: dict, mensaje: str, thread_id: str) -> dict        # igual que lo propuesto
aprobar_plan(estado: dict, thread_id: str, aprobado: bool) -> dict         # estado puede traer "plan_id_seleccionado"
```

- **`plan`** es `list[{"id": str, "resultado": dict}]`. Para una ruta, `resultado` trae `estado`, `origen.direccion`, `destino.direccion`, `ruta.duracion_min`, `ruta.tramos[{modo, linea, desde, hasta, duracion_min}]`, `zona` y `precio` (`{estado, texto, fuente}`), `hora_salida` y `titulo`.
- **Varios planes:** `aprobar_plan` exige `estado["plan_id_seleccionado"]`; con un único plan lo deduce. Si falta o no existe devuelve un aviso con `hitl_pendiente=False` aunque siga habiendo un plan pendiente, así que el cliente **no debe fiarse de esa bandera tras un aviso controlado**.
- **Solo las rutas pausan.** Horarios y RAG devuelven `hitl_pendiente=False` y `done=True` sin plan.
- **El checkpoint es la fuente de verdad:** el `estado` del cliente solo sirve para indicar el plan elegido.
- **Entradas técnicas del supervisor** en `log`: empiezan por `Supervisor: categoria=` o `Supervisor: correccion_semantica=`.

### Archivos afectados (además de los ya previstos)
| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/clientes/planes.py` | Crear | Funciones puras: `resumir_plan`, `ids_de_planes`, `es_entrada_tecnica_supervisor` | RF-30, RF-33, RF-35 |
| `src/clientes/presentacion.py` | Modificar | `formatear_turno` y `datos_depuracion` muestran planes con resumen y aceptan `ocultar_tecnicas` | RF-6, RF-30, RF-35 |
| `src/clientes/sesion.py` | Modificar | `decidir(aprobado, plan_id=None)` envía `plan_id_seleccionado`; propiedad `planes` | RF-31, RF-32 |
| `src/clientes/grafo_falso.py` | Modificar | Planes con formato real, varios planes para algunos pedidos y sin plan para el resto | RF-34, RF-36 |
| `src/clientes/cli.py` | Modificar | Elegir plan cuando hay varios; resumen de cada plan; muestra entradas técnicas | RF-6, RF-9, RF-31, RF-32, RF-35 |
| `app.py` | Modificar | Selector de plan en la barra lateral y filtro de entradas técnicas en toda la web | RF-31, RF-35 |
| `config.py` | Modificar | `PEDIDOS_DEMO` (horarios, ruta, fuera de corpus) y `PREFIJOS_DIAGNOSTICO_SUPERVISOR` | RF-11, RF-35 |
| `tests/test_planes.py` | Crear | Resumen, identificadores y filtro | RF-30, RF-33, RF-35 |
| `tests/test_clientes_grafo_real.py` | Crear | Los clientes contra el grafo real con los dobles de `tests/dobles_grafo.py` (sin API) | RF-26, RF-30 a RF-34 |
| Tests existentes del simulado, sesión y CLI | Modificar | Usar un pedido de ruta para provocar el plan pendiente | RF-34, RF-36 |

### Lógica clave
```text
resumir_plan(plan):
  r = plan["resultado"]  (si no es un diccionario -> mostrar el plan en bruto, RF-33)
  líneas = ["Plan {id}"]
  origen y destino (si existen), duración total, tramos "modo línea: desde -> hasta (n min)", zona, precio
  los campos ausentes se omiten; un plan desconocido se vuelca como "clave: valor" legible

SesionChat.decidir(aprobado, plan_id=None):
  si hay más de un plan y plan_id es None -> no llama al grafo (el cliente debe pedir la elección)
  estado_envio = {**estado, "plan_id_seleccionado": plan_id}  (solo si hay plan_id)
  agente.aprobar_plan(estado_envio, thread_id, aprobado)
  si el grafo responde con un aviso y deja hitl_pendiente=False pero había plan, el cliente
       se re-sincroniza en el siguiente mensaje (el grafo lo bloquea y devuelve el plan)

CLI tras un turno con planes pendientes:
  mostrar el resumen de cada plan
  si hay varios: pedir el número (inválido -> repreguntar)
  pedir s/n y llamar a decidir(aprobado, plan_id)
  tras rechazar, si el grafo devuelve otro plan, repetir; si no, seguir escribiendo

Streamlit: selector de planes si hay varios; botones con plan_id; filtra las entradas técnicas (RF-35)
```

### Decisiones técnicas
| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Resumen genérico y tolerante de `resultado` | Depender de todas las claves exactas | El grafo puede añadir campos y no debe romper la pantalla (RF-33) |
| Elegir plan por número (1, 2…) mostrando su identificador | Pedir escribir `ruta-2` | Más cómodo en terminal y en una lista de la web |
| Filtrar entradas técnicas por prefijo configurable | Ocultar todo el `log` | Se mantiene el registro de especialistas, que el enunciado pide ver |
| Probar contra el grafo real con los dobles de Rubén | Solo contra el simulado | Demuestra el contrato real sin gastar API |
| El simulado solo pausa en rutas | Que pause siempre | Se parece al real y evita una demo engañosa |

### Estrategia de tests
- **`test_planes.py`:** plan completo, plan sin tramos, plan sin zona ni precio, formato desconocido, lista vacía, identificadores y detección de entradas técnicas.
- **Simulado, sesión y CLI:** ajustar los pedidos a una ruta; casos con uno y con varios planes; sin plan para horarios y RAG.
- **`test_clientes_grafo_real.py`:** con `crear_grafo(...)` y los dobles de `tests/dobles_grafo.py`, enchufado en `agent._GRAFO`, se recorre: ruta con un plan, aprobar y terminar; ruta con varios planes, elegir uno; rechazar y conservar el hilo; consulta sin ruta que cierra sin pausa; entradas técnicas ocultas en la web y visibles en el CLI.
- **A mano:** Streamlit con el modo simulado (selector de plan y filtro) y, con el grafo real y API, una ruta de verdad (⚠️ gasta Gemini, Nominatim y Google).

### Riesgos añadidos
- La selección de la imagen demo depende de que el cliente preserve exactamente la referencia literal; los clientes no admiten otros archivos ni subida de imágenes.
- Un aviso controlado del grafo pone `hitl_pendiente=False` aunque quede un plan pendiente: puede desincronizar la pantalla un momento; se corrige con el siguiente mensaje.
- Los dobles de `tests/dobles_grafo.py` son de otra persona: si cambian, nuestros tests de integración pueden romperse.

### Trazabilidad añadida
| RF | Parte del plan | Test |
|---|---|---|
| RF-6, RF-9 (cambiados) | `cli.py`, `planes.py` | `tests/test_cli.py::test_plan_pendiente_muestra_resumen`, `::test_rechazar_muestra_el_nuevo_plan` |
| RF-11 (cambiado) | `config.py`, `cli.py` | `tests/test_cli_demo.py::test_demo_lanza_tres_pedidos` |
| RF-30 | `planes.py` | `tests/test_planes.py::test_resumen_de_ruta_completo` |
| RF-31 | `sesion.py`, `cli.py`, `app.py` | `tests/test_sesion.py::test_decidir_con_varios_planes_envia_el_elegido`, `tests/test_cli.py::test_varios_planes_pide_elegir` |
| RF-32 | `sesion.py`, `cli.py` | `tests/test_cli.py::test_un_plan_no_pide_elegir` |
| RF-33 | `planes.py` | `tests/test_planes.py::test_plan_de_formato_desconocido` |
| RF-34 | `cli.py` | `tests/test_cli.py::test_respuesta_sin_plan_no_pregunta` |
| RF-35 | `planes.py`, `presentacion.py`, `app.py` | `tests/test_planes.py::test_entradas_tecnicas`, `tests/test_presentacion.py::test_ocultar_tecnicas` |
| RF-36 | `grafo_falso.py` | `tests/test_grafo_falso.py::test_planes_con_formato_real`, `::test_varios_planes` |
| RF-26 (con el grafo real) | `contrato.py` | `tests/test_clientes_grafo_real.py` |

## Cambio aprobado 2026-10-19: transmisión de la referencia de imagen demo

Este complemento cubre RF-37. Los clientes no seleccionan archivos, no
interpretan imágenes y no deciden especialistas: trasladan la consulta literal
al mismo agente. La selección y validación de la demo pertenecen a la spec 007.

### Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `tests/test_sesion.py` | Modificar | Comprobar que la sesión compartida por CLI y Streamlit entrega al agente sin transformación un mensaje que contiene `assets/imagen_demo.jpg`. | RF-37 |
| `tests/test_cli.py` | Modificar | Recorrer el chat de terminal con un agente espía y verificar que recibe literalmente la referencia de la demo. | RF-37 |
| `specs/008-clientes-cli-streamlit/validacion.md` | Modificar | Sustituir la limitación ya resuelta de imagen por la evidencia de RF-37 y registrar la comprobación manual de Streamlit. | RF-37 |

No se modificarán `src/clientes/sesion.py`, `src/clientes/cli.py`, `app.py`,
`src/clientes/grafo_falso.py` ni el contrato del agente: la sesión ya llama a
`procesar_turno` con el mensaje recibido y ambos clientes ya delegan en ella.

### Contrato

El contrato permanece sin cambios:

```text
procesar_turno(estado: dict, mensaje: str, thread_id: str) -> dict
```

Ejemplo de transmisión desde ambos clientes:

```text
Entrada de la persona: Analiza assets/imagen_demo.jpg e indica los precios.
Mensaje recibido por el agente: Analiza assets/imagen_demo.jpg e indica los precios.
```

Los clientes no añaden `estado["imagen"]`, no sustituyen la ruta, no cambian
mayúsculas ni espacios del mensaje y no modifican las seis claves que devuelve
el agente.

### Lógica clave

```text
CLI:
    leer texto de la persona
    SesionChat.enviar(texto)

Streamlit:
    recibir texto de chat_input
    SesionChat.enviar(texto)

SesionChat.enviar(texto):
    guardar el texto original en historial
    llamar agente.procesar_turno(estado, texto, thread_id)
    aplicar solo el estado devuelto por el agente
```

### Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Probar la transmisión en `SesionChat` y también en el bucle de CLI. | Duplicar la selección de demo en cada interfaz. | `SesionChat` es la frontera común; la prueba de CLI confirma que la entrada llega a esa frontera sin transformarse. |
| Mantener una comprobación manual de Streamlit. | Arrancar Streamlit o usar proveedores reales dentro de `pytest`. | RF-37 solo requiere preservar el texto; la spec mantiene los tests sin ejecución de Streamlit ni APIs. |
| Dejar la semántica visual en la spec 007. | Programar en clientes reglas de imagen o invocaciones de tools. | Evita duplicar la guardia, conserva clientes finos y garantiza que CLI y web usan el mismo comportamiento del agente. |

### Estrategia de tests

| Área | Prueba y dobles | Cobertura |
|---|---|---|
| Sesión compartida | `GrafoFalso` o agente espía registra el tercer argumento de `procesar_turno`; `SesionChat.enviar` recibe un mensaje con la referencia literal y se compara por igualdad exacta. | RF-37 |
| CLI | Entrada y salida inyectadas, con agente espía; enviar la referencia y después `salir`, y comprobar que la única llamada conserva el texto exacto. | RF-37 |
| Streamlit | Comprobación manual con el modo simulado: escribir el mensaje literal y verificar que aparece sin cambios en el historial del chat. La selección visual real se comprobará con el grafo real según la spec 007. | RF-37 |

No se ejecutarán Gemini, Vision, RAG, embeddings, ChromaDB ni Streamlit como
parte de `pytest`.

### Riesgos

- El modo simulado acredita la transmisión del texto, pero no interpreta la
  imagen; la activación de `tarifas` se cubre con los dobles del grafo real de
  la spec 007.
- Cualquier normalización futura del cliente (por ejemplo, recortar o reescribir
  mensajes) debe preservar la referencia literal para no incumplir RF-37.
- La demostración visual con proveedores reales sigue siendo opcional y puede
  consumir API; no forma parte de la validación automatizada.

### Trazabilidad del cambio

| RF | Parte del plan | Test o comprobación |
|---|---|---|
| RF-37 | Sesión compartida y bucle de CLI sin transformaciones | `tests/test_sesion.py::test_referencia_de_demo_se_reenvia_sin_modificar` y `tests/test_cli.py::test_cli_reenvia_referencia_de_demo_sin_modificar` |
| RF-37 | Chat Streamlit conserva el mensaje literal | Manual: modo simulado, escribir la referencia y revisar el historial |

## Cambio 2026-10-22: mensaje visible al enviar y pasos seguidos en la web

| Archivo | Acción | Qué contiene |
|---|---|---|
| `src/clientes/presentacion.py` | Modificar | `pasos_del_turno(log, traza, ocultar_tecnicas)`: líneas con las tools numeradas y el registro visible; vacía si no hay nada (RF-39, RF-41). |
| `src/clientes/sesion.py` | Modificar | Cada respuesta del asistente guarda en el historial una copia del registro y de la traza de su turno (RF-40). |
| `app.py` | Modificar | Antes de llamar al grafo se dibuja la burbuja de la persona y un indicador de espera (RF-38); bajo cada respuesta se dibuja el desplegable «Pasos seguidos» (RF-39 a RF-41). |
| `tests/test_presentacion.py`, `tests/test_sesion.py`, `tests/test_app_streamlit.py` | Modificar / Crear | Tests sin API; los de Streamlit con `AppTest` y un agente de prueba. |

| RF | Cómo se cubre | Prueba |
|---|---|---|
| RF-38 | La burbuja y el indicador se dibujan antes de `enviar` | `tests/test_app_streamlit.py` |
| RF-39 | Desplegable con tools y registro visible | `tests/test_presentacion.py`, `tests/test_app_streamlit.py` |
| RF-40 | El historial guarda registro y traza por respuesta | `tests/test_sesion.py`, `tests/test_app_streamlit.py` |
| RF-41 | Sin pasos no hay desplegable | `tests/test_presentacion.py`, `tests/test_app_streamlit.py` |
