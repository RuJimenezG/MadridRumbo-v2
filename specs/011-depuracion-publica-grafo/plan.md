# Plan técnico — Spec 011 (depuración pública del grafo)

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento fuera de los RF. No incorpora dependencias ni modifica las firmas públicas `procesar_turno(estado, mensaje, thread_id)` ni `aprobar_plan(estado, thread_id, aprobado)`.

## Archivos afectados

| Archivo | Crear / modificar | Qué cambia | RF |
|---|---|---|---|
| `config.py` | Modificar | Añade el límite único de 10.000 caracteres para valores de depuración. | RF-20 |
| `src/depuracion.py` | **Crear** | Centraliza los tipos de entrada, la sesión efímera por invocación, la serialización JSON segura, el saneado y la numeración de pasos. | RF-2 a RF-4, RF-10, RF-11, RF-16 a RF-22 |
| `src/graph.py` | Modificar | Ejecuta el grafo mediante sus eventos locales de streaming (`values`, `updates` y `tasks`) para obtener el estado antes y después de cada nodo; asocia la sesión efímera a `invocar_grafo` y `reanudar_grafo`, sin escribirla en el checkpointer. Tras un fallback del Supervisor, proyecta también su diagnóstico seguro como entrada estructurada del registro. | RF-5, RF-7, RF-8, RF-11, RF-13 a RF-15, RF-23 a RF-25, RF-27 |
| `src/agents/base.py` | Modificar | El ejecutor transversal notifica cada invocación de tool a la sesión efímera, con argumentos, resultado y estado saneados; conserva la allowlist, los límites y el contrato de `traza`. | RF-6, RF-9 a RF-11, RF-26 |
| `src/estado.py` | Modificar | Elimina `log` del estado persistible y proyecta exclusivamente el registro efímero de la llamada actual, sin alterar las otras cinco claves públicas ni `traza`. | RF-1, RF-2, RF-15, RF-26 |
| `src/agent.py` | Modificar | Crea una sesión de depuración por cada llamada, la pasa al recorrido normal o a la reanudación y produce la entrada `control` uniforme para validaciones y bloqueos previos al grafo. | RF-1, RF-12 a RF-15, RF-27 |
| `src/clientes/contrato.py` | Modificar | Documenta y normaliza `log` como lista de entradas estructuradas, no como lista de textos. | RF-1 a RF-4 |
| `src/clientes/presentacion.py` | Modificar | Formatea entradas estructuradas para CLI, deja el panel de depuración sin filtro y conserva el filtro técnico para el chat y «Pasos seguidos». | RF-23 a RF-25 |
| `src/clientes/cli.py` | Modificar mínimo | Consume el formato común de presentación de las entradas estructuradas. | RF-23 |
| `src/clientes/sesion.py` | Modificar mínimo / comprobar | Conserva copias profundas de las nuevas entradas por respuesta, sin mezclar turnos. | RF-2, RF-14, RF-15 |
| `app.py` | Modificar | El panel de depuración muestra el log completo; el desplegable de cada respuesta conserva `ocultar_tecnicas=True`. | RF-24, RF-25 |
| `tests/test_depuracion.py` | **Crear** | Pruebas puras de esquema, orden, saneado, límite y valores no JSON. | RF-2 a RF-4, RF-10, RF-11, RF-16 a RF-22 |
| `tests/test_agent_contrato.py` | Modificar | Contrato de seis claves, entradas de control, log por llamada y ausencia de log en el checkpoint. | RF-1, RF-12 a RF-15, RF-27 |
| `tests/test_estado_grafo.py` | Modificar | Proyección de resultado con log estructurado y `traza` inalterada. | RF-1, RF-2, RF-26 |
| `tests/test_grafo_persistencia.py` | Modificar | Turnos y reanudación HITL con logs aislados, estado persistente sin log y diagnóstico del Supervisor limitado a la invocación actual. | RF-13 a RF-15 |
| `tests/test_clientes_grafo_real.py` | Modificar | Fuerza un fallback del Supervisor en el grafo real y verifica que CLI y Streamlit reciben el diagnóstico estructurado de esa llamada. | RF-23 a RF-25 |
| `tests/test_presentacion.py` | Modificar | Formato CLI, panel sin filtro y chat / «Pasos seguidos» filtrados. | RF-23 a RF-25 |
| `tests/test_cli.py` y `tests/test_app_streamlit.py` | Modificar | CLI con entradas estructuradas y panel de Streamlit con diagnóstico visible, sin alterar el chat. | RF-23 a RF-25 |

## Contrato

Las firmas públicas se mantienen:

```text
procesar_turno(estado, mensaje, thread_id) -> dict
aprobar_plan(estado, thread_id, aprobado) -> dict
```

El resultado mantiene exactamente estas claves de primer nivel:

```text
respuesta: str
plan: list
log: list[EntradaDepuracion]       # cambia de list[str]
traza: list[{tool, args, status, preview}]
hitl_pendiente: bool
done: bool
```

Una entrada de `log` completa tiene este contrato:

```json
{
  "paso": 3,
  "tipo": "nodo",
  "nodo": "nodo_auxiliar",
  "entrada": {"mensaje": "¿Qué hora es?", "cola_roles": ["auxiliar"]},
  "salida": {"respuesta": "", "cola_roles": []},
  "resultado": "completado",
  "detalle": null
}
```

`tipo` es `nodo`, `tool` o `control`; `resultado` es `completado`, `fallido` o `rechazado`. En `nodo`, `entrada` y `salida` son snapshots completos saneados. En `tool`, son los argumentos y el resultado saneados. En `control`, ambos valen `null` y `detalle` contiene el motivo seguro.

## Corrección posterior a la validación

La validación detectó que `nodo_supervisor` deposita `categoria` y `resumen` en el contexto efímero de ejecución, pero el adaptador de eventos registraba únicamente snapshots del estado. Por ello, los clientes podían mostrar un diagnóstico estructurado inyectado por un doble, pero no el diagnóstico de un fallback real.

La corrección se limita al adaptador de `src/graph.py`:

- Después de registrar el snapshot completado del nodo `supervisor`, inspeccionará el contexto efímero de la llamada.
- Si la categoría indica fallback (es distinta de `sin_fallback`), añadirá inmediatamente una entrada con `tipo: "control"`, `nodo: "supervisor"`, `entrada: null`, `salida: null`, `resultado: "rechazado"` y `detalle: {"categoria", "resumen"}` ya saneado.
- No añadirá esa entrada para una decisión válida sin fallback, ni la guardará en el estado, historial o checkpoint.

Se usa `control` y `rechazado` porque el fallo corresponde a la decisión primaria del Supervisor, aunque el nodo pueda completar su recorrido aplicando el fallback. No se añade `detalle` al nodo completado: RF-10 exige que los nodos y tools completados mantengan `detalle: null`.

Las pruebas deben cubrir el flujo real completo: un modelo de Supervisor que produce una decisión inválida, la entrada de diagnóstico en el resultado público, su presencia en CLI y panel de depuración, y su ausencia en «Pasos seguidos» del chat.

Ejemplo de una validación sin ejecutar el grafo:

```json
{
  "respuesta": "El thread_id debe ser un texto no vacío.",
  "plan": [],
  "log": [{
    "paso": 1,
    "tipo": "control",
    "nodo": "fachada",
    "entrada": null,
    "salida": null,
    "resultado": "rechazado",
    "detalle": {"categoria": "validacion", "resumen": "El thread_id debe ser un texto no vacío."}
  }],
  "traza": [],
  "hitl_pendiente": false,
  "done": false
}
```

Los valores sensibles se reemplazan por un marcador seguro. Un valor no JSON se vuelve un objeto con su tipo y resumen seguro; un valor cuya representación JSON segura exceda el límite se sustituye por un resumen de omisión. Ninguna de estas transformaciones altera `traza`.

## Lógica clave

```text
al iniciar procesar_turno o aprobar_plan:
    sesion = SesionDepuracion()              # memoria local; nunca EstadoGrafo
    si la fachada rechaza la llamada:
        devolver resultado con sesion.control(motivo)

    activar(sesion) durante la invocación del grafo
    emitir el grafo en modos values + updates + tasks
    conservar el primer values como estado_anterior

    por cada evento del grafo:
        si tasks identifica comienzo o final de un nodo:
            asociar su nombre, su estado y su posible error seguro
        si updates identifica la actualización de un nodo:
            conservar el nodo pendiente
        si values trae el estado combinado posterior:
            añadir sesion.nodo(nodo_pendiente,
                                sanear(estado_anterior),
                                sanear(values),
                                resultado y detalle)
            si nodo_pendiente es supervisor y contexto.diagnostico_supervisor
               indica fallback:
                añadir sesion.control("supervisor", rechazado,
                                      entrada=null, salida=null,
                                      detalle=categoria y resumen seguros)
            estado_anterior = values

    durante una tool invocada por el ejecutor transversal:
        añadir sesion.tool(nombre, sanear(args), sanear(resultado), estado)

    desactivar(sesion) incluso si falla la invocación
    proyectar las seis claves con sesion.entradas, no con estado["log"]

sanear(valor, nombre_campo):
    si nombre_campo es credencial o contraseña conocida, prompt completo o cuerpo externo:
        devolver marcador seguro
    si valor es primitivo, lista o dict:
        sanear recursivamente
    si no es JSON:
        devolver {"tipo": tipo(valor), "resumen": resumen_seguro(valor)}
    si su JSON seguro supera el límite configurado:
        devolver resumen de omisión con el nombre del campo
    devolver valor saneado
```

La sesión de depuración se propaga como contexto temporal de ejecución, nunca por `EstadoGrafo`, reducers, historial ni checkpointer. La reanudación HITL crea una sesión nueva antes de invocar `Command(resume=...)`.

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Usar los eventos locales `values`, `updates` y `tasks` de LangGraph para observar la ejecución. | Instrumentar por separado todos los especialistas y nodos. | El stream entrega el estado combinado tras reducers y cubre todos los nodos declarados sin duplicar lógica de negocio. |
| Mantener una sesión efímera por invocación. | Añadir `log` al estado persistente. | Cumple RF-2, RF-14 y RF-15: no mezcla turnos ni se guarda en el checkpoint. |
| Registrar las tools desde el ejecutor transversal compartido. | Reconstruir tools solo desde `traza` al final del especialista. | Conserva el orden temporal, los argumentos y el resultado completo antes de truncar el `preview`; `traza` sigue intacta. |
| Centralizar saneado y serialización en `src/depuracion.py`. | Repetir filtros en grafo, tools y clientes. | Un único criterio comprobable evita filtraciones divergentes. |
| Representar valores no JSON con tipo y resumen seguro. | Usar `str()` o `repr()` sin límites. | Las representaciones crudas pueden fallar o contener secretos. |
| Cambiar solo el contenido de `log`, no sus seis claves superiores ni `traza`. | Añadir un séptimo campo público de auditoría. | Respeta el contrato de la spec 005 y evita bifurcar a los clientes. |
| Panel de Streamlit sin filtro; chat y «Pasos seguidos» con filtro. | Mostrar todo el log en cada burbuja de chat. | Cumple la sustitución limitada aprobada en la spec y mantiene la conversación legible. |
| Proyectar el diagnóstico de fallback como `control` rechazado del Supervisor. | Añadir `detalle` al nodo `supervisor` completado o persistir el contexto. | Distingue el fallo de la decisión primaria del fallback que permite completar el nodo, respeta `detalle: null` para nodos completados y conserva el diagnóstico solo en la llamada actual. |

## Estrategia de tests

Todas las pruebas usan `monkeypatch`, modelos falsos y ejecutores falsos ya presentes (`LLMFalso`, `EjecutorFalso`); no llaman a LLM, RAG, embeddings, ChromaDB, APIs ni Streamlit real.

| Alcance | Prueba | Dobles / comprobación |
|---|---|---|
| Esquema y secuencia | `test_depuracion.py::test_entrada_*` | Sesión de depuración pura: campos obligatorios, tipos permitidos y pasos consecutivos. |
| Nodos y estado combinado | `test_depuracion.py::test_nodo_registra_snapshot_previo_y_posterior` | Grafo con Supervisor y especialista falsos; verifica input anterior y salida tras reducer. |
| Tools | `test_depuracion.py::test_tool_registra_args_y_resultado_en_orden` | Ejecutor falso; verifica que herramienta y nodo aparecen y `traza` mantiene sus cuatro claves. |
| Fallos | `test_depuracion.py::test_fallo_*` | Nodo y ejecutor falsos que devuelven error o lanzan; salida nula cuando procede, categoría y resumen seguros. |
| Saneado | `test_depuracion.py::test_saneado_*` | Centinelas para credenciales, cabeceras, prompt, cuerpo externo, objetos no JSON y 10.000/10.001 caracteres. |
| Fachada y control | `test_agent_contrato.py::test_*control*` | Grafo espía que no debe invocarse; `thread_id`, estado, mensaje, plan ausente y selección inválida devuelven la entrada `fachada`. |
| No persistencia e HITL | `test_grafo_persistencia.py::test_*log*` | Grafo con ruta falsa y `InMemorySaver`; pausa y reanudación entregan logs distintos y checkpoint sin `log`. |
| Contrato | `test_estado_grafo.py::test_proyeccion_*` y `test_agent_contrato.py::_comprobar_contrato` | Comprueba seis claves, `log` estructurado y `traza` idéntica. |
| CLI | `test_presentacion.py` y `test_cli.py` | Estado sintético con nodo, tool y diagnóstico de Supervisor; el formato muestra todas las entradas. |
| Streamlit | `test_presentacion.py` y `test_app_streamlit.py` | Estado sintético; panel completo y burbuja / «Pasos seguidos» sin diagnóstico técnico. |
| Fallback real del Supervisor | `test_clientes_grafo_real.py::test_*fallback*` y pruebas de clientes | El modelo falso devuelve una decisión inválida; verifica la entrada `control` real en CLI y panel, y el filtrado del chat. |
| Final por llamada | `test_agent_contrato.py::test_*log_por_llamada` | Doble de grafo que produce varios pasos; no se recibe ningún evento parcial antes del resultado final. |

No hay comprobaciones manuales necesarias: CLI y Streamlit se prueban con entradas y estados simulados, y todo comportamiento es determinista.

## Riesgos

- La versión instalada de LangGraph debe mantener el orden y forma de sus eventos `values`, `updates` y `tasks`; los tests del adaptador aislarán esa dependencia.
- Los snapshots completos pueden ser voluminosos. El límite individual, el saneado recursivo y la no persistencia limitan el impacto, pero no se establece un tope global porque la spec exige el estado completo por paso.
- Un saneado incompleto podría revelar un secreto; las pruebas usarán credenciales centinela en claves, cabeceras, prompts y errores.
- Cambiar `log` de textos a objetos requiere actualizar todos los consumidores y sus pruebas en el mismo cambio.
- La suite actual tiene fallos ajenos de BiciMAD/clima que gestiona otro equipo. La constitución exige que la suite quede verde antes de cerrar cada tarea de implementación.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Contrato, `src/estado.py`, `src/agent.py` | `test_agent_contrato.py::test_fachada_*` |
| RF-2 a RF-4 | `src/depuracion.py`, contrato | `test_depuracion.py::test_entrada_*` |
| RF-5, RF-7, RF-8 | Observación de nodos en `src/graph.py` | `test_depuracion.py::test_nodo_registra_snapshot_previo_y_posterior` |
| RF-6, RF-9 | Ejecutor transversal en `src/agents/base.py` | `test_depuracion.py::test_tool_registra_args_y_resultado_en_orden` |
| RF-10 | Sesión de depuración | `test_depuracion.py::test_entrada_completada_no_lleva_detalle` |
| RF-11 | Eventos `tasks` y sesión de depuración | `test_depuracion.py::test_fallo_*` |
| RF-12 | Controles de `src/agent.py` | `test_agent_contrato.py::test_*control*` |
| RF-13 a RF-15 | `src/graph.py`, `src/agent.py`, `src/estado.py` | `test_grafo_persistencia.py::test_*log*` |
| RF-16 | Saneado recursivo | `test_depuracion.py::test_snapshot_conserva_campos_no_sensibles` |
| RF-17 a RF-19 | Catálogo de saneado | `test_depuracion.py::test_saneado_credenciales_y_contenido_sensible` |
| RF-20 | Límite configurado | `test_depuracion.py::test_limite_10000_caracteres` |
| RF-21 | Serialización segura | `test_depuracion.py::test_valor_no_json_tiene_tipo_y_resumen` |
| RF-22 | Proyección saneada | `test_depuracion.py::test_log_no_filtra_secretos` |
| RF-23 | Formato CLI | `test_cli.py::test_el_cli_muestra_*` |
| RF-24 | Panel de Streamlit | `test_app_streamlit.py::test_*depuracion*` |
| RF-25 | Presentación filtrada del chat | `test_presentacion.py::test_pasos_ocultan_*` |
| RF-23 a RF-25 (fallback real) | Proyección del diagnóstico desde el contexto efímero | `test_clientes_grafo_real.py::test_*fallback*` y pruebas de CLI/Streamlit con el grafo real |
| RF-26 | Proyección de traza | `test_estado_grafo.py::test_proyeccion_*` |
| RF-27 | Fachada tras ejecución completa | `test_agent_contrato.py::test_*log_por_llamada` |
