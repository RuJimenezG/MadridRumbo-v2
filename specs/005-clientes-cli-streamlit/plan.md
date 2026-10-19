# Plan técnico — Spec 005

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento que no esté en la spec.

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
| `plan` | `list[str]` | `[]` | Viñetas del plan pendiente de decisión |
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
