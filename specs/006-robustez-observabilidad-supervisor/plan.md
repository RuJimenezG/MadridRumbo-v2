# Plan técnico — Spec 006: Robustez y observabilidad de decisiones LLM del Supervisor

> Basado en `spec.md` (estado: Aprobada). No añade dependencias, no modifica las firmas de `procesar_turno` ni `aprobar_plan`, y mantiene la traza reservada exclusivamente para tools.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/modelos.py` | Modificar | Separar el adaptador estructurado del Supervisor del usado por especialistas; pedir `application/json` solo al primero, conservar el texto crudo y distinguir fallo de proveedor de fallo JSON. | RF-5 a RF-8, RF-24 |
| `src/supervisor.py` | Modificar | Corregir el prompt, normalizar fences permitidos, validar estrictamente el objeto de roles, clasificar el resultado y escribir un diagnóstico saneado en el contexto efímero de ejecución. | RF-1 a RF-14 |
| `src/graph.py` | Modificar | Declarar un `context_schema` de LangGraph, entregar su `Runtime.context` al nodo Supervisor y permitir que la invocación reciba un contexto efímero por turno. | RF-10 a RF-14, RF-25 |
| `src/estado.py` | Modificar | Extender la proyección pública para añadir a la copia de `log` la entrada técnica ya saneada, sin tocar las seis claves públicas ni `traza`; será el punto de consumo de futuros clientes. | RF-10 a RF-16, RF-25 |
| `src/agent.py` | Modificar | Crear el contexto efímero por llamada a `procesar_turno`, pasarlo al grafo y proyectarlo solo en el resultado de ese turno. | RF-10 a RF-16, RF-25 |
| `src/supervisor_reglas.py` | Modificar | Reconocer explícitamente las tres formulaciones de rutas tras normalizar mayúsculas, tildes, puntuación y espacios. | RF-17 a RF-19 |
| `src/agents/rutas.py` | Modificar | Detectar una formulación explícita de ruta incompleta antes de llamar al modelo o a una tool y devolver la aclaración controlada. | RF-20, RF-21 |
| `specs/006-robustez-observabilidad-supervisor/validacion.md` | Crear | Documentar la comprobación manual con Gemini real y una llamada de desarrollo a la fachada pública; explicará el consumo futuro seguro desde CLI y Streamlit sin implementar ninguno. | RF-22, RF-23 |
| `tests/test_modelos_grafo.py` | Modificar | Probar la configuración JSON del cliente Gemini con un doble que captura la llamada, sin red. | RF-5 a RF-8, RF-24 |
| `tests/test_supervisor_grafo.py` | Modificar | Cubrir prompt, normalización, categorías, validación estricta, fallback y ausencia de datos sensibles. | RF-1 a RF-14 |
| `tests/test_grafo_enrutamiento.py` y `tests/test_especialista_rutas.py` | Modificar | Cubrir fallback de rutas hasta `planificar_ruta`, variaciones textuales y aclaraciones sin tool. | RF-17 a RF-21 |
| `tests/test_agent_contrato.py`, `tests/test_grafo_persistencia.py` y `tests/test_estado_grafo.py` | Modificar | Verificar contrato inalterado, registro técnico seguro disponible solo en el resultado actual y ausencia de diagnóstico en `traza`, checkpoint e invocaciones posteriores. | RF-10 a RF-16, RF-25 |
| `tests/test_agent_contrato.py` | Modificar | Inyectar especialistas falsos en la regresión del fallback público para impedir que el recorrido por `auxiliar` alcance Gemini; comprobar que el doble se ejecuta. | RF-10 a RF-14; coste |

No se modificarán `main.py`, `app.py`, `requirements.txt`, `rag/rag_cli.py`, contratos de tools ni los archivos de configuración existentes. La CLI y la integración de Streamlit serán objeto de especificaciones futuras; esta entrega deja el resultado público que ambas consumirán.

## Contrato

Las firmas y las seis claves de las operaciones públicas no cambian:

```text
procesar_turno(estado, mensaje, thread_id) -> dict
aprobar_plan(estado, thread_id, aprobado) -> dict
```

El único enriquecimiento es una entrada canónica, segura y de tipo texto dentro de la lista pública ya existente `log` cuando se ejecuta el Supervisor. Ejemplo de una decisión válida:

```python
{
    "respuesta": "Son las 18:00.",
    "plan": [],
    "log": [
        "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada."
    ],
    "traza": [],
    "hitl_pendiente": False,
    "done": True,
}
```

Ejemplo de fallback por JSON inválido:

```python
{
    "respuesta": "…",
    "plan": [],
    "log": [
        "Supervisor: categoria=json_invalido; resumen=La decisión no contiene JSON válido; se aplicó el fallback."
    ],
    "traza": [],
    "hitl_pendiente": False,
    "done": True,
}
```

Las únicas categorías serán `sin_fallback`, `proveedor`, `json_invalido` y `roles_invalidos`. Los resúmenes saldrán de un catálogo fijo; nunca contendrán la respuesta cruda, una excepción, una clave, el prompt o una configuración sensible. Si el Supervisor no se ejecuta —por ejemplo, en una validación de entrada, un límite o una reanudación HITL— no se añadirá una categoría artificial.

El resultado ya deja preparado el límite de integración: un cliente técnico futuro, incluida una CLI, podrá leer la entrada segura de `log`; un cliente de chat futuro, incluido Streamlit, recibirá ese mismo resultado pero deberá ignorar `log` y `traza` al renderizar y al guardar su historial. Esta spec no crea ni modifica esos clientes.

## Lógica clave

```text
procesar_turno(estado, mensaje, thread_id):
    validar la entrada con las reglas actuales
    crear contexto_efimero = {diagnostico_supervisor: nulo}
    estado_final = invocar_grafo(..., contexto=contexto_efimero)
    devolver proyectar_resultado(estado_final, diagnostico=contexto_efimero.diagnostico_supervisor)

nodo_supervisor(estado, runtime):
    solicitar al adaptador del Supervisor una única respuesta JSON
    si falla el proveedor, la salida está vacía/no textual o está bloqueada:
        contexto.diagnostico = categoria "proveedor" + resumen fijo
        usar fallback determinista
    si la respuesta es texto:
        recortar solo espacios exteriores
        si coincide exactamente con un fence Markdown sin etiqueta o etiqueta json/JSON:
            extraer únicamente el cuerpo del fence
        intentar json.loads; si falla o hay texto envolvente:
            contexto.diagnostico = categoria "json_invalido" + resumen fijo
            usar fallback determinista
    validar: objeto con la única clave roles, lista ordenada de 0 a 20 cadenas admitidas
    si la validación falla:
        contexto.diagnostico = categoria "roles_invalidos" + resumen fijo
        usar fallback determinista
    si es válida:
        contexto.diagnostico = categoria "sin_fallback" + resumen fijo
        devolver la cola de roles intacta

fallback de rutas:
    normalizar texto sin distinguir mayúsculas, tildes o puntuación
    reconocer "quiero ir de", "necesito ir de" y "voy de"
    derivar a rutas; si la formulación explícita carece de origen o destino,
        devolver aclaración antes de invocar LLM, planificar_ruta o HITL

frontera de clientes futuros:
    la fachada pública devuelve la entrada segura de log solo en el resultado actual
    una CLI futura podrá mostrar esa entrada bajo una opción de diagnóstico
    Streamlit futuro debe omitir log y traza al renderizar y al guardar historial
```

El `context_schema` se usará únicamente durante `invoke(..., context=...)`; no formará parte de `EstadoGrafo`, de los reducers ni del checkpointer. `proyectar_resultado` trabajará sobre una copia antes de añadir su entrada a `log`, con lo que el diagnóstico no reaparecerá en otro turno, una aprobación ni una lectura de estado persistido.

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Transportar el diagnóstico mediante `Runtime.context` de LangGraph. | Guardarlo en `EstadoGrafo.log`, `traza` o el checkpoint. | `log` se acumula actualmente y `traza` tiene un contrato exclusivo de tools; el contexto efímero cumple RF-25 sin cambiar las seis claves públicas. |
| Mantener `log` como `list[str]` y añadir una línea canónica. | Añadir claves públicas o convertir `log` en objetos. | Preserva el contrato consumible existente y permite a la CLI mostrar la categoría sin transformar datos. |
| Solicitar `response_mime_type="application/json"` solo al adaptador del Supervisor. | Confiar solo en el prompt o aplicar JSON forzado también a especialistas y sintetizador. | Refuerza la decisión objetivo sin alterar salidas estructuradas o textuales ajenas al alcance. |
| Mantener el prompt con ejemplo JSON válido y validar en Python. | Confiar únicamente en el modo JSON del proveedor. | El modo JSON reduce formatos defectuosos, pero no sustituye la allowlist, la validación ni el fallback seguro. |
| Normalizar únicamente fences completos sin etiqueta o `json` sin distinción de mayúsculas. | Extraer el primer objeto, aceptar cualquier lenguaje de fence o corregir comillas simples con `ast`/reemplazos. | Evita aceptar texto envolvente o decisiones ambiguas, tal como exigen RF-5 a RF-7. |
| Usar un catálogo fijo de cuatro categorías y resúmenes. | Serializar excepciones, respuestas, prompts o configuraciones. | Hace el diagnóstico útil y comprobable sin filtrar secretos ni detalles internos. |
| Exponer el diagnóstico exclusivamente en el resultado público actual para clientes futuros. | Crear ahora una CLI, modificar Streamlit o acoplar la observabilidad a la UI existente. | Mantiene esta spec en la capa de sistema, preserva `main.py` y `app.py`, y deja un contrato claro para que las specs de clientes apliquen RF-15 y RF-16. |
| No usar `response_schema` en esta iteración. | Duplicar la allowlist en un esquema del proveedor. | La spec exige `response_mime_type`; Python continúa siendo la autoridad única para roles y evita dos fuentes de verdad. |

## Estrategia de tests

Todos los tests usarán dobles inyectados y no inicializarán Gemini, APIs, embeddings, ChromaDB, Nominatim, Google Routes ni Vision reales.

| Área | Prueba y dobles | Cobertura |
|---|---|---|
| Prompt y JSON válido | Doble generador del Supervisor; comprobar ejemplo exacto, instrucción exclusiva JSON, lista vacía, repetición y veinte roles. | RF-1 a RF-4, RF-11 |
| Markdown recuperable | Parámetros con fence sin etiqueta, `json`, `JSON`, espacios y saltos exteriores; rechazar otros lenguajes y prosa externa. | RF-5, RF-7 |
| Fallos de parseo y roles | Doble que devuelve comillas simples, texto adicional, campos extra, falta de `roles`, tipo erróneo, más de veinte roles o rol prohibido. | RF-6, RF-7, RF-9, RF-12 |
| Fallo de proveedor | Doble que lanza excepción, devuelve vacío, valor no textual o bloqueo controlado. | RF-8 |
| Diagnóstico seguro | Centinelas que imitan clave, prompt y respuesta bruta; comprobar que las categorías y resúmenes fijos son los únicos datos expuestos. | RF-10 a RF-14 |
| Configuración Gemini | Cliente Gemini falso que registra `generate_content`; comprobar `response_mime_type="application/json"` solo en el Supervisor. | RF-24 |
| Rutas | Supervisor falso que falla, LLM de rutas y `EjecutorFalso`; comprobar las tres formulaciones con variantes textuales, una llamada a `planificar_ruta` y plan pendiente para extremos válidos. | RF-17 a RF-20 |
| Aclaración de rutas | Las tres formulaciones incompletas no invocan LLM de rutas, tool, traza de ruta ni HITL. | RF-21 |
| No persistencia | Dos turnos del mismo `thread_id`, más reanudación HITL; comprobar que el diagnóstico solo aparece en la primera proyección y no en checkpoint, historial ni resultado posterior. | RF-10, RF-11, RF-25 |
| Frontera de clientes | Verificar las mismas seis claves y `log: list[str]`; comprobar que el único dato de diagnóstico entregado está en el resultado actual, no en `traza` ni en estado persistido. | RF-15, RF-16, compatibilidad |
| Regresión sin API del fallback público | Crear el grafo con Supervisor, Sintetizador y los cinco especialistas inyectados; provocar `json_invalido` con «¿Qué hora es?» y comprobar que el doble `auxiliar` se ejecuta sin inicializar un proveedor real. | RF-10 a RF-14, coste |
| Guía manual | Revisar manualmente, mediante la fachada pública, los escenarios Gemini real y fallback; no se automatiza porque consume proveedor. | RF-22, RF-23 |

La guía manual indicará dos comprobaciones separadas mediante una llamada de desarrollo a `procesar_turno`: una consulta ligera con Gemini configurado, que debe devolver `sin_fallback` en el `log` del resultado; y un fallback reproducible en una consola nueva con una clave de proceso deliberadamente inválida, sin leer, imprimir ni modificar `.env`. La segunda debe producir `proveedor` y un resumen genérico. También indicará cerrar esa consola al acabar y no usar rutas/RAG. Incluirá el contrato que deberán respetar los clientes futuros: la CLI podrá presentar la entrada segura de `log` y Streamlit no deberá mostrar ni conservar `log` o `traza`; su comprobación de interfaz queda expresamente diferida a la spec que implemente esos clientes.

## Riesgos

- `response_mime_type` mejora el formato, pero Gemini puede seguir devolver contenido no usable; las pruebas conservan el parseo, validación y fallback como barreras obligatorias.
- El contexto de ejecución requiere la API de LangGraph instalada; la versión presente admite `context_schema` y `invoke(..., context=...)`, y se cubrirá con dobles sin red.
- La protección visual de RF-16 depende de una futura integración de Streamlit; esta entrega reduce el riesgo al dejar el diagnóstico categorizado, seguro y separado de `traza`, pero no cambia la UI existente.
- El escenario manual con una clave de proceso inválida puede consumir o contactar con Gemini, por lo que queda fuera de `pytest`, se hará en una consola aislada y no revelará ninguna clave real.
- Una prueba de contrato que omita el doble del especialista seleccionado por el fallback puede inicializar Gemini, pedir credenciales o abrir conexiones de red. La regresión inyecta los cinco especialistas para que cambios futuros de clasificación tampoco rompan la garantía de coste.
- El reconocimiento de rutas es deliberadamente acotado a las tres formulaciones aprobadas; no se convertirá en un extractor general de direcciones ni cambiará el contrato de `planificar_ruta`.
- La copia de trabajo contiene modificaciones ajenas en `config.py` y `output/chunks.json`; esta iteración no las modifica.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 a RF-4 | Prompt, parser del Supervisor y validación estricta | `tests/test_supervisor_grafo.py::test_prompt_y_decision_valida` |
| RF-5 | Normalizador de fences acotado | `tests/test_supervisor_grafo.py::test_bloques_markdown_recuperables` |
| RF-6 a RF-7 | Clasificación de parseo JSON | `tests/test_supervisor_grafo.py::test_json_invalido_activa_fallback` |
| RF-8 | Frontera de proveedor en el adaptador | `tests/test_supervisor_grafo.py::test_fallo_proveedor_activa_fallback` |
| RF-9 | Validación de forma, tamaño y allowlist | `tests/test_supervisor_grafo.py::test_roles_invalidos_activan_fallback` |
| RF-10 a RF-14 | Contexto efímero, catálogo seguro y proyección de `log` | `tests/test_supervisor_grafo.py::test_diagnostico_es_seguro` y `tests/test_grafo_persistencia.py::test_diagnostico_no_persiste` |
| RF-10 a RF-14, coste | Fallback público con todos los especialistas sustituidos por dobles | `tests/test_agent_contrato.py::test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` |
| RF-15 | Resultado público con diagnóstico técnico seguro para consumo de clientes | `tests/test_agent_contrato.py::test_resultado_expone_diagnostico_seguro` |
| RF-16 | Límite de integración documentado: diagnóstico separado de la respuesta, el plan y la traza | `tests/test_agent_contrato.py::test_resultado_separa_diagnostico_de_datos_de_chat` |
| RF-17 a RF-19 | Reglas deterministas de expresiones de ruta | `tests/test_grafo_enrutamiento.py::test_fallback_reconoce_formulaciones_de_ruta` |
| RF-20 | Recorrido fallback → rutas → planificar → HITL | `tests/test_grafo_enrutamiento.py::test_formulacion_de_ruta_valida_planifica` |
| RF-21 | Aclaración previa a LLM/tool/HITL | `tests/test_especialista_rutas.py::test_formulacion_incompleta_pide_aclaracion` |
| RF-22 a RF-23 | Guía manual Gemini segura y reproducible | `specs/006-robustez-observabilidad-supervisor/validacion.md` (manual) |
| RF-24 | Configuración JSON del cliente Supervisor | `tests/test_modelos_grafo.py::test_supervisor_pide_application_json` |
| RF-25 | Contexto no persistente ni reproyectado | `tests/test_grafo_persistencia.py::test_diagnostico_no_persiste` |
