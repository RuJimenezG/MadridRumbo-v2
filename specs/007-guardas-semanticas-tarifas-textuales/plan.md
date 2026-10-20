# Plan técnico — Spec 007: Guardas semánticas para consultas textuales de tarifas

> Basado en `spec.md` (estado: Aprobada). No añade dependencias, no cambia las firmas públicas de `procesar_turno`, `aprobar_plan`, `rag_ask` o `describir_imagen`, ni modifica la allowlist de tools.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/catalogo_roles.py` | Crear | Centralizar el catálogo ordenado de roles, sus responsabilidades, sus restricciones semánticas, los términos tarifarios explícitos y los textos reutilizables para el Supervisor. Expondrá predicados puros para identificar una consulta tarifaria textual y corregir una cola validada. | RF-1 a RF-10 |
| `src/supervisor.py` | Modificar | Generar las instrucciones desde el catálogo, aplicar la guarda solo después de validar una decisión LLM, preservar orden y repeticiones al sustituir `tarifas` por `rag`, y transportar el número seguro de sustituciones dentro de la decisión válida. | RF-1 a RF-10, RF-14 a RF-17 |
| `src/graph.py` | Modificar | Ampliar el contexto interno y efímero con una señal de imagen válida, entregarlo al Supervisor y a `tarifas`, y reconocer la redirección defensiva de `tarifas` a `rag` sin invocar visión ni alterar la allowlist. | RF-11 a RF-13, RF-15 |
| `src/agents/tarifas.py` | Modificar | Comprobar el contexto de imagen antes de llamar al bucle del especialista; con imagen válida mantendrá la lectura visual de la ruta seleccionada y sin ella devolverá una señal interna de redirección controlada. | RF-3, RF-11, RF-12 |
| `src/estado.py` | Modificar | Proyectar, junto al diagnóstico canónico existente, una segunda línea canónica de corrección semántica en la copia pública de `log`, sin añadir claves ni persistir datos. | RF-14 a RF-17 |
| `src/agent.py` | Modificar | Crear el contexto efímero de cada turno con imagen ausente por defecto y mantener intactas las seis claves públicas. | RF-11, RF-14 a RF-19 |
| `specs/007-guardas-semanticas-tarifas-textuales/validacion.md` | Crear | Documentar la diferencia entre fallback y corrección semántica y el contrato que deberán consumir la CLI técnica y Streamlit en specs futuras. | RF-18 a RF-20 |
| `tests/test_catalogo_roles.py` | Crear | Probar catálogo único, responsabilidades, límites y normalización de términos tarifarios sin proveedores. | RF-1 a RF-10 |
| `tests/test_supervisor_grafo.py` | Modificar | Cubrir prompt generado, decisión válida incompatible, términos tarifarios, repeticiones, imagen válida y conservación de `sin_fallback` sin datos crudos. | RF-1 a RF-11, RF-14 a RF-17 |
| `tests/test_grafo_enrutamiento.py` | Modificar | Comprobar el recorrido completo de Combinado Metro a `rag_ask`, la traza RAG, cero llamadas a `describir_imagen`, la redirección defensiva y el recorrido visual con imagen válida. | RF-9 a RF-13 |
| `tests/test_flujo_imagen_calculo.py` | Modificar | Declarar explícitamente una imagen válida en los escenarios visuales actuales y comprobar que la ausencia de imagen no inicia el LLM ni la tool de visión. | RF-11, RF-12 |
| `tests/test_estado_grafo.py` y `tests/test_agent_contrato.py` | Modificar | Verificar la proyección segura, el contrato inalterado y la ausencia del indicador en checkpoint, historial, reanudaciones y turnos posteriores. | RF-14 a RF-17 |

No se modificarán `main.py`, `app.py`, `rag/responder.py`, `rag/rag_cli.py`, `src/tools/describir_imagen.py`, la allowlist de `config.py`, `src/supervisor_reglas.py` ni los documentos del corpus. La CLI y Streamlit son trabajo de specs futuras. El fallback ya existente conservará sus reglas; la defensa de ejecución cubrirá sus posibles llegadas a `tarifas` sin imagen.

## Contrato

Se conservan las firmas y las seis claves públicas:

```text
procesar_turno(estado, mensaje, thread_id) -> dict
aprobar_plan(estado, thread_id, aprobado) -> dict
respuesta, plan, log, traza, hitl_pendiente, done
```

No se añade ninguna clave pública de entrada o salida para las imágenes. El contexto interno del grafo empieza cada turno sin imagen y solo una integración interna o un cliente futuro podrá inyectar una señal de imagen ya validada. La demo configurada contará como aportada únicamente si esa futura integración la selecciona de forma explícita; su valor por defecto en `describir_imagen` no constituye contexto de imagen.

Ejemplo de consulta textual corregida, con una decisión LLM válida pero incompatible:

```python
entrada = {}
mensaje = "¿Cuánto cuesta el Combinado Metro?"
# El LLM devuelve {"roles": ["tarifas"]}.

resultado = {
    "respuesta": "...respuesta basada en el corpus CRTM...",
    "plan": [],
    "log": [
        "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada.",
        "Supervisor: correccion_semantica=aplicada; resumen=Se redirigieron 1 derivaciones incompatibles de tarifas a rag.",
    ],
    "traza": [
        {
            "tool": "rag_ask",
            "args": {"consulta": "¿Cuánto cuesta el Combinado Metro?"},
            "status": "ok",
            "preview": "...evidencia del corpus...",
        }
    ],
    "hitl_pendiente": False,
    "done": True,
}
```

La lista `log` conserva la categoría de fallback de cuatro valores de la spec 006; la corrección no introduce una quinta categoría ni una respuesta cruda del LLM. La traza continúa teniendo exclusivamente las cuatro claves de tools y prueba la llamada a `rag_ask`, cuyo contrato permanece como texto. No se promete una lista independiente de fuentes.

Esta spec no crea ni modifica clientes. El resultado público actual deja preparada la frontera: una CLI técnica futura podrá mostrar exclusivamente las líneas seguras de `log` que empiezan por `Supervisor:`, y Streamlit futuro deberá ignorar `log` y `traza` al renderizar o guardar el historial. `main.py`, `app.py` y `rag/rag_cli.py` permanecen fuera de alcance.

## Lógica clave

```text
procesar_turno(estado, mensaje, thread_id):
    validar los argumentos con las reglas actuales
    crear contexto efímero con diagnóstico nulo e imagen no válida por defecto
    invocar el grafo con ese contexto, sin escribirlo en EstadoGrafo
    proyectar solo el diagnóstico seguro del contexto en el resultado actual

integración interna o cliente futuro con una imagen previamente validada:
    marcar el contexto efímero como imagen válida para ese turno
    si se selecciona la imagen demo, marcarla explícitamente

supervisor(estado, contexto):
    construir el prompt desde CATALOGO_ROLES:
        responsabilidades de rag, tarifas, horarios, rutas y auxiliar
        tarifa textual sin imagen -> rag
        tarifas requiere imagen válida
    pedir y validar JSON exactamente como en la spec 006
    si hay proveedor, JSON o roles inválidos:
        conservar el fallback y su categoría actual, sin corrección semántica
    si la decisión LLM es válida:
        roles = cola validada
        si no hay imagen válida y la consulta contiene un término tarifario:
            reemplazar cada "tarifas" por "rag" en su misma posición
            contar los reemplazos
        conservar categoria=sin_fallback y uso_fallback=falso
        guardar en contexto solo el contador positivo y un resumen fijo
        devolver la cola corregida

nodo_tarifas(estado, contexto_imagen):
    si no hay imagen válida:
        devolver una señal interna de "redirigir a rag" y una nota controlada
        no llamar al LLM visual ni a describir_imagen
    ejecutar el especialista con describir_imagen

envoltorio del especialista tarifas:
    si recibe la señal interna de redirección:
        reemplazar el primer rol de [tarifas, resto] por [rag, resto]
    en cualquier otro caso:
        consumir el rol normalmente
    nunca invocar rag_ask dentro de tarifas

proyectar_resultado(estado, diagnóstico):
    copiar log existente
    añadir línea canónica categoría/resumen de la spec 006
    si el contador seguro de correcciones es entero positivo:
        añadir una segunda línea canónica de corrección con ese número
    no copiar al resultado respuesta del LLM, prompt, pregunta original,
    ruta de imagen ni datos del checkpoint
```

El contexto de imagen y el diagnóstico usan `Runtime.context`, como la observabilidad de la spec 006. No se incorporan a `EstadoGrafo`, `historial`, reducers, `log` persistido ni `traza`, por lo que un turno posterior y una reanudación HITL no los recuperan. La adquisición, validación y presentación de imágenes por clientes quedan para specs posteriores.

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Crear un catálogo Python único para roles, descripciones y restricciones semánticas. | Repetir los roles y sus límites en el prompt, el validador y las guardas. | Evita que el LLM reciba reglas distintas de las que Python aplica y cubre RF-1 a RF-8. |
| Corregir la cola únicamente después de validar el JSON del LLM. | Confiar solo en el prompt o reemplazar el fallback actual. | Mantiene las barreras de la spec 006 y el fallback ante proveedor, JSON y roles inválidos. |
| Normalizar los términos explícitos sin distinguir mayúsculas, tildes, puntuación ni plurales o flexiones simples de las palabras aprobadas. | Buscar subcadenas crudas o ampliar la intención a cualquier consulta de transporte. | Reconoce formulaciones como «tarifas», «billetes» y «cuesta» sin sobrepasar el conjunto explícito de RF-7. |
| Transportar una señal de imagen válida únicamente por `Runtime.context` y exigir selección explícita de la demo. | Inferir imagen por las palabras «foto» o «cartel», usar siempre el valor por defecto de `describir_imagen` o persistir la imagen en el estado. | Una referencia textual no acredita una imagen, la demo implícita anularía la guarda y el contexto efímero no contamina turnos posteriores ni cambia el contrato público. |
| Redirigir desde `nodo_tarifas` mediante una señal interna consumida por el envoltorio del grafo. | Permitir a `tarifas` llamar directamente a `rag_ask` o añadir RAG a su allowlist. | Mantiene la separación de especialistas y la allowlist de la spec 005; el RAG deja su propia traza verificable. |
| Mantener `sin_fallback` y añadir una segunda línea canónica a `log`. | Crear una quinta categoría, añadir una clave pública o serializar la decisión LLM. | Distingue ambos fenómenos, mantiene las seis claves públicas y evita exponer contenido no saneado. |
| Mantener `main.py`, `app.py` y `rag/rag_cli.py` sin cambios. | Implementar ahora una CLI del grafo o migrar Streamlit. | La interfaz y la subida/presentación de imágenes pertenecen a specs futuras; esta entrega preserva el contrato público seguro que esos clientes deberán consumir. |
| Usar dobles de LLM, ejecutor y fachada para todas las pruebas automatizadas. | Ejecutar Gemini, Vision, RAG, embeddings o ChromaDB reales. | Cumple el límite de coste y hace verificables las llamadas y sus ausencias. |

## Estrategia de tests

Todas las pruebas automáticas usarán `LLMFalso`, `EjecutorFalso`, `monkeypatch`, rutas temporales y clientes/fachadas falsos. No crearán proveedores, no leerán credenciales y no llamarán a Gemini, Vision, RAG real, embeddings, ChromaDB, Nominatim ni Google Routes.

| Área | Prueba y dobles | Cobertura |
|---|---|---|
| Catálogo y prompt | Catálogo puro y doble del Supervisor que captura mensajes; comprobar las cinco responsabilidades y las dos exclusiones. | RF-1 a RF-8 |
| Términos y guardas | Decisiones válidas `{"roles": ["tarifas"]}` con cada término aprobado y variantes normalizadas; ausencia de imagen, referencia textual a cartel y Combinado Metro. | RF-7 a RF-10 |
| Orden y repeticiones | Doble LLM con `{"roles": ["auxiliar", "tarifas", "tarifas"]}`; comprobar `auxiliar`, `rag`, `rag` y contador dos. | RF-9, RF-16 |
| Contexto de imagen | Inyectar contexto efímero falso o válido en el grafo; comprobar que una demo explícitamente marcada, incluso sin tarifas legibles, sigue permitiendo visión. | RF-8, RF-10, RF-11 |
| Integración RAG | Grafo con decisión válida errónea, LLM de RAG guionizado y `EjecutorFalso`; comprobar una llamada a `rag_ask`, respuesta textual anclada simulada y traza de cuatro campos. | RF-9, RF-13 |
| Ausencia de visión | LLM de tarifas que falla si llega a invocarse y `EjecutorFalso` contador; comprobar cero llamadas a LLM visual y `describir_imagen` para Combinado Metro y para una llegada defensiva directa a `tarifas`. | RF-9, RF-10, RF-12 |
| Recorrido visual | Contexto con demo o archivo válido, LLM de tarifas y ejecutor falso; comprobar que se llama una vez a `describir_imagen`, incluso si el contenido no son tarifas. | RF-3, RF-11 |
| Observabilidad segura | Centinelas de respuesta cruda, prompt, secreto y ruta; comprobar `sin_fallback`, indicador separado, resumen fijo y contador, sin filtraciones. | RF-14 a RF-17 |
| No persistencia | Dos turnos del mismo `thread_id` y una reanudación HITL; comprobar que corrección e imagen no están en checkpoint, historial, `traza` ni resultado posterior. | RF-15, RF-17 |
| Frontera de clientes futuros | Comprobar que el resultado conserva las seis claves, que la información técnica está solo en `log` y que nunca entra en `respuesta`, `traza`, historial o checkpoint. | RF-18, RF-19 |
| Guía de operación | Matriz RF por RF que documenta cómo una CLI futura debe leer `log` y cómo Streamlit futuro debe omitir `log` y `traza`, sin implementar ninguno. | RF-18 a RF-20 |

## Riesgos

- La aplicación actual no transporta archivos adjuntos. La adquisición y validación de imágenes para clientes se definirán en una spec posterior; esta entrega solo respeta una señal interna ya validada.
- Una cola repetida puede producir varias consultas RAG porque RF-9 conserva repeticiones; el límite global de tools existente seguirá siendo la barrera de coste.
- El fallback anterior puede todavía seleccionar `tarifas` por palabras de imagen; la defensa del nodo lo redirige de forma segura sin cambiar las reglas ni categorías del fallback.
- La CLI y Streamlit actuales no consumen el grafo. Las specs futuras deberán respetar la frontera documentada de `log` y `traza`; esta entrega no las modifica.
- El directorio de trabajo ya contiene `docs/PR.md` sin seguimiento, ajeno a esta spec; no se modificará.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Catálogo único de roles | `tests/test_catalogo_roles.py::test_catalogo_declara_roles_y_responsabilidades` |
| RF-2 | Descripción de `rag` generada desde catálogo | `tests/test_supervisor_grafo.py::test_prompt_declara_rag_documental` |
| RF-3 | Descripción y ejecución visual de `tarifas` | `tests/test_supervisor_grafo.py::test_prompt_declara_tarifas_visual` y `tests/test_grafo_enrutamiento.py::test_imagen_valida_mantiene_tarifas` |
| RF-4 | Descripción de `horarios` | `tests/test_catalogo_roles.py::test_catalogo_declara_horarios` |
| RF-5 | Descripción de `rutas` | `tests/test_catalogo_roles.py::test_catalogo_declara_rutas` |
| RF-6 | Descripción de `auxiliar` | `tests/test_catalogo_roles.py::test_catalogo_declara_auxiliar` |
| RF-7 | Exclusión de tarifa textual sin imagen | `tests/test_supervisor_grafo.py::test_prompt_y_guarda_envian_tarifa_textual_a_rag` |
| RF-8 | Exclusión de `tarifas` sin contexto visual | `tests/test_supervisor_grafo.py::test_prompt_y_guarda_envian_tarifa_textual_a_rag` |
| RF-9 | Sustitución posicional tras JSON válido | `tests/test_supervisor_grafo.py::test_decision_tarifas_textual_valida_se_corrige_a_rag` |
| RF-10 | Referencia a cartel sin imagen | `tests/test_supervisor_grafo.py::test_referencia_textual_a_cartel_sin_imagen_va_a_rag` |
| RF-11 | Contexto de imagen válida y demo explícita | `tests/test_grafo_enrutamiento.py::test_imagen_demo_valida_mantiene_tarifas` |
| RF-12 | Defensa del nodo de tarifas | `tests/test_grafo_enrutamiento.py::test_tarifas_sin_imagen_redirige_a_rag_sin_vision` |
| RF-13 | Respuesta anclada y traza RAG | `tests/test_grafo_enrutamiento.py::test_combinado_metro_corregido_llama_rag_ask_y_conserva_traza` |
| RF-14 | Indicador independiente | `tests/test_estado_grafo.py::test_proyeccion_anade_indicador_de_correccion_semantica` |
| RF-15 | `sin_fallback` efímero | `tests/test_agent_contrato.py::test_correccion_semantica_no_persiste_ni_cambia_categoria` |
| RF-16 | Resumen fijo con contador | `tests/test_supervisor_grafo.py::test_repeticiones_tarifas_informan_contador_seguro` |
| RF-17 | No filtración de contenido crudo | `tests/test_agent_contrato.py::test_correccion_semantica_no_expone_respuesta_cruda` |
| RF-18 | Resultado público y frontera de CLI futura | `tests/test_agent_contrato.py::test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo` y `validacion.md` |
| RF-19 | Separación para Streamlit futuro | `tests/test_agent_contrato.py::test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo` y `validacion.md` |
| RF-20 | Guía de observabilidad | `specs/007-guardas-semanticas-tarifas-textuales/validacion.md` |

## Cambio aprobado 2026-10-19: selección explícita de la imagen demo

Este complemento sustituye, para la imagen demo configurada, la limitación
anterior que dejaba su selección exclusivamente en una integración interna. No
incorpora subida de archivos ni rutas elegidas por la persona usuaria.

### Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/agent.py` | Modificar | Reconocer la referencia literal `assets/imagen_demo.jpg`, validar localmente la demo configurada y trasladar el resultado exclusivamente al contexto efímero del turno. | RF-21 a RF-24 |
| `tests/test_agent_contrato.py` | Modificar | Cubrir la selección desde la fachada pública, la conservación de sus seis claves, el rechazo seguro de una demo inválida y que la señal no se hereda entre turnos. | RF-21 a RF-24 |
| `tests/test_flujo_imagen_calculo.py` | Modificar | Reutilizar el recorrido visual existente para comprobar, con modelo y ejecutor falsos, que una demo seleccionada desde la fachada alcanza `tarifas` y la tool permitida. | RF-21, RF-22 |
| `specs/007-guardas-semanticas-tarifas-textuales/validacion.md` | Modificar | Añadir la matriz de evidencia de los RF-21 a RF-24 y registrar la suite sin API. | RF-21 a RF-24 |

No se modificarán `src/graph.py`, `src/agents/tarifas.py`, `src/tools/describir_imagen.py`, `config.py`, `main.py` ni `app.py`: el grafo ya consume `imagen_valida` desde su contexto efímero y la tool ya usa la demo configurada cuando no recibe ruta. La comprobación de que CLI y Streamlit preservan el mensaje se planificará en la spec 008 (RF-37).

### Contrato

Las firmas y las seis claves públicas permanecen intactas:

```text
procesar_turno(estado, mensaje, thread_id) -> dict
aprobar_plan(estado, thread_id, aprobado) -> dict
```

El campo `estado` no incorpora una imagen ni una ruta. La selección se expresa
solo en el texto de `mensaje` y no aparece en el resultado ni en el
checkpoint.

```python
procesar_turno(
    {},
    "Analiza assets/imagen_demo.jpg e indica los precios visibles.",
    "hilo-demo",
)
# Devuelve las mismas seis claves públicas; el grafo puede derivar a tarifas.
```

Un mensaje como `"Analiza esta imagen"`, una referencia distinta o un turno
posterior sin la referencia literal no seleccionan la demo y conservan las
guardas vigentes de tarifas textuales.

### Lógica clave

```text
imagen_demo_valida_para(mensaje):
    si mensaje no contiene exactamente "assets/imagen_demo.jpg":
        devolver falso
    directorio = resolver IMAGENES_DIR
    archivo = resolver directorio / IMAGEN_DEMO
    si archivo queda fuera de directorio, no es fichero, su extensión no está
       permitida o supera el tamaño máximo configurado:
        devolver falso
    devolver verdadero

invocar_turno_con_diagnostico(grafo, estado, thread_id):
    contexto = diagnóstico vacío + contador de correcciones
    contexto.imagen_valida = imagen_demo_valida_para(estado.mensaje)
    invocar el grafo con ese contexto únicamente para este turno
    proyectar el resultado con las seis claves públicas existentes

siguiente turno del mismo hilo:
    reconstruir el contexto desde su nuevo mensaje
    no leer ni persistir la selección del turno anterior
```

### Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Activar la demo solo mediante la cadena literal aprobada. | Inferirla por «imagen», «foto» o «cartel». | Evita que una referencia textual sin archivo anule las guardas de RF-9, RF-10 y RF-12. |
| Validar localmente la demo configurada antes de activar la señal. | Llamar a `describir_imagen` para comprobarla. | La selección no debe consumir Vision ni depender de credenciales; la tool seguirá aplicando su propia defensa antes de leer el archivo. |
| Calcular `imagen_valida` a partir de `mensaje` en la fachada. | Añadir `estado["imagen"]`, una clave pública o una ruta nueva. | Mantiene firmas, seis claves de salida y aislamiento del checkpoint. |
| Reutilizar el contexto efímero y el valor por defecto de la tool. | Cambiar el grafo, el especialista o pasar una ruta controlada por el LLM. | El contexto ya llega al Supervisor y a `tarifas`; la tool ya abre exclusivamente `IMAGEN_DEMO`. |
| No modificar CLI ni Streamlit. | Añadir selector, uploader o lógica visual específica. | Ambos clientes ya reenvían el mensaje a la misma fachada; la comprobación contractual de ese límite pertenece a RF-37 de la spec 008. |

### Estrategia de tests

Todos los casos nuevos usarán un grafo real con Supervisor, especialistas,
modelo y ejecutor falsos, o bien rutas temporales mediante `monkeypatch`. No
invocarán Gemini, Vision, RAG, embeddings ni ChromaDB.

| Área | Prueba y dobles | Cobertura |
|---|---|---|
| Selección pública | `procesar_turno` con un Supervisor falso que selecciona `tarifas`, especialista falso contador y mensaje con la referencia literal; comprobar contexto válido, recorrido por tarifas y seis claves públicas. | RF-21, RF-22 |
| Validación local | Sustituir temporalmente directorio, nombre, extensión o tamaño de la demo; comprobar que una configuración inválida no activa tarifas, no llama a visión y se redirige a RAG. | RF-22, RF-23 |
| No persistencia | Dos llamadas de fachada con el mismo `thread_id`: la primera contiene la referencia y la segunda no; comprobar `tarifas` y después `rag`, sin señal visual en checkpoint ni resultado público. | RF-24 |
| Recorrido de tool | Modelo de tarifas y ejecutor falsos; comprobar que la demo seleccionada conserva la única llamada permitida a `describir_imagen`, sin red. | RF-21, RF-22 |
| Regresión existente | Mantener los escenarios de tarjeta, cartel o imagen sin referencia literal como consultas sin imagen válida. | RF-9, RF-10, RF-12 |

La prueba de CLI y Streamlit no se añade a esta spec porque no cambia sus
archivos ni su contrato: se cubrirá al planificar RF-37 en la spec 008.

### Riesgos

- La referencia es deliberadamente literal y sensible a cambios en su texto;
  una variante como `imagen_demo.jpg` sin `assets/` no seleccionará la demo.
- Un error de configuración de la demo debe resultar en redirección segura a
  RAG, nunca en una lectura de una ruta alternativa.
- El modo simulado de clientes no sustituye la comprobación del grafo real;
  la evidencia de la propagación de mensajes de ambos clientes se mantiene en
  la spec 008.
- La validación local duplica la decisión de admisibilidad antes de la defensa
  final de la tool; ambas deben seguir basándose en los límites centralizados
  de `config.py`.

### Trazabilidad del cambio

| RF | Parte del plan | Test |
|---|---|---|
| RF-21 | Detección literal y contexto efímero en la fachada | `tests/test_agent_contrato.py::test_referencia_literal_de_demo_habilita_tarifas` |
| RF-22 | Validación local y recorrido visual falso | `tests/test_agent_contrato.py::test_demo_configurada_valida_habilita_tarifas` y `tests/test_flujo_imagen_calculo.py::test_demo_seleccionada_describe_imagen` |
| RF-23 | Configuración de demo inválida | `tests/test_agent_contrato.py::test_demo_invalida_se_redirige_a_rag_sin_vision` |
| RF-24 | Contexto reconstruido en el siguiente turno | `tests/test_agent_contrato.py::test_demo_no_se_hereda_entre_turnos_de_la_fachada` |
