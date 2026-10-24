# Plan técnico — Spec 012

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento que no esté en la spec.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `specs/012-guardas-semanticas-rutas-tarifas-zonas/spec.md` | Modificar | Marca la spec como aprobada al iniciar la planificación. | Gobernanza SDD |
| `src/catalogo_roles.py` | Modificar | Incorpora el significado tarifario de los códigos A, B1, B2, B3, C1, C2, E1 y E2 en las instrucciones compartidas del Supervisor y centraliza la detección determinista de una consulta textual de tarifa entre dos zonas. | RF-1 a RF-5, RF-14 y RF-15 |
| `src/supervisor.py` | Modificar | Aplica la nueva corrección a una cola LLM ya validada, conserva posiciones y repeticiones, y transporta el contador efímero de correcciones de `rutas` hacia el diagnóstico. | RF-6 a RF-10, RF-13 y RF-16 |
| `src/agent.py` | Modificar | Inicializa el dato efímero de la corrección de rutas junto al contexto existente de una sola llamada pública. | RF-9 a RF-12 |
| `src/graph.py` | Modificar | Registra una entrada técnica de control para la corrección semántica de rutas, independiente del fallback, segura y no persistida. | RF-8 a RF-12 |
| `tests/test_catalogo_roles.py` | Modificar | Añade pruebas unitarias de pares de zonas, conectores admitidos, términos tarifarios, una zona aislada, imagen válida y petición de ruta física. | RF-1 a RF-5 y RF-14 a RF-16 |
| `tests/test_supervisor_grafo.py` | Modificar | Prueba con modelo simulado la sustitución de `rutas` por `rag`, el orden, las repeticiones y la conservación de `sin_fallback`. | RF-6 a RF-10, RF-15 y RF-16 |
| `tests/test_grafo_enrutamiento.py` | Modificar | Comprueba el recorrido resultante hacia RAG, su traza documental y que una ruta física no se redirige. | RF-5, RF-6, RF-7, RF-13 y RF-16 |
| `tests/test_agent_contrato.py` | Modificar | Verifica, desde la fachada pública, el diagnóstico técnico seguro y efímero separado del fallback, sin cambios de contrato. | RF-8 a RF-12 |

## Contrato

Las firmas públicas `procesar_turno(estado, mensaje, thread_id)` y `aprobar_plan(estado, thread_id, aprobado)` no cambian. El resultado conserva exactamente las seis claves públicas: `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done`.

La nueva información existe solo durante la invocación interna: el Supervisor comunica el número de apariciones de `rutas` corregidas y el registro incorpora una entrada técnica estructurada. No se añade ningún campo al resultado, a la traza de tools ni al checkpoint por `thread_id`. Como ya ocurre con los diagnósticos técnicos del Supervisor, la CLI y el panel de depuración pueden ver esa entrada de `log`; el chat y «Pasos seguidos» de Streamlit la filtran mediante su categoría técnica existente.

Ejemplo de entrada pública:

```text
procesar_turno({}, "Precio del abono A-B2", "hilo-zonas")
```

Ejemplo de salida relevante, sin cambiar su forma pública:

```json
{
  "respuesta": "…respuesta anclada al corpus CRTM…",
  "plan": [],
  "log": [
    {
      "paso": 2,
      "tipo": "control",
      "nodo": "supervisor",
      "entrada": null,
      "salida": null,
      "resultado": "completado",
      "detalle": {
        "categoria": "correccion_semantica",
        "resumen": "Se redirigió 1 aparición de rutas a rag por una consulta tarifaria entre zonas."
      }
    }
  ],
  "traza": [{"tool": "rag_ask", "args": {"consulta": "Precio del abono A-B2"}, "status": "ok", "preview": "…"}],
  "hitl_pendiente": false,
  "done": true
}
```

El ejemplo representa solo las entradas relevantes del registro: la llamada real conserva sus entradas de nodo y sus números de paso consecutivos. La respuesta cruda del LLM no se incluye.

## Lógica clave

```text
al construir las instrucciones del Supervisor:
    declarar que A, B1, B2, B3, C1, C2, E1 y E2 son zonas tarifarias, no lugares

al recibir una cola de roles ya validada del LLM:
    detectar si el mensaje no tiene imagen válida
    detectar un término tarifario aprobado
    detectar un par de zonas admitidas unido por «entre … y …», «de … a …» o guion
    detectar si la misma consulta pide una ruta entre dos lugares físicos

    si es tarifa entre zonas y no es ruta física:
        reemplazar cada "rutas" por "rag" sin reordenar ni eliminar otras entradas
        guardar solo el número de reemplazos como corrección semántica efímera

    completar las reglas vigentes de ruta real y continuar el grafo normalmente

al terminar el nodo Supervisor dentro de una llamada instrumentada:
    registrar su nodo normal
    si hubo fallback: registrar su diagnóstico de fallback existente
    si hubo corrección de rutas: registrar un control técnico "correccion_semantica"
        con un resumen fijo que solo contiene el contador
    no persistir ninguno de los datos de diagnóstico
```

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Centralizar los códigos de zona, sus conectores y la guarda en el catálogo de roles. | Añadir expresiones regulares independientes al prompt o al nodo de rutas. | El catálogo ya es la fuente compartida entre las instrucciones y las guardas semánticas; evita reglas divergentes y permite pruebas puras sin LLM. |
| Aplicar la guarda solo después de validar formalmente la cola LLM y antes de continuar las reglas de ruta vigentes. | Rechazar o modificar la respuesta LLM antes de validarla, o sustituir el fallback determinista. | La spec exige corregir una decisión válida, conservar el fallback de la spec 006 y no alterar las garantías de allowlist. |
| Reconocer únicamente pares de códigos de la lista cerrada con los tres conectores especificados y un término tarifario. | Interpretar cualquier letra/número o cualquier frase «de … a …» como zonas. | Limita falsos positivos; una sola «zona A» y los recorridos ordinarios conservan su comportamiento actual. |
| Excluir de la guarda una petición de desplazamiento con dos extremos que no sean ambos códigos de zona. | Eliminar `rutas` siempre que se detecten dos zonas y una palabra tarifaria. | Mantiene la ruta física y su tratamiento documental/tarifario cuando una consulta combina ambos fines. |
| Transportar solamente un contador de correcciones en un contexto efímero y generar el diagnóstico desde el registro estructurado. | Añadir campos públicos, escribir el diagnóstico en el estado persistente o guardar la salida LLM. | Respeta el contrato de seis claves, el aislamiento por turno de las specs 006 y 011, y las restricciones de seguridad. |
| Reutilizar la categoría técnica existente `correccion_semantica` con un resumen fijo y contador. | Crear una categoría pública nueva o reutilizar una categoría de fallback. | Los clientes ya filtran los diagnósticos semánticos con esa categoría; mantenerla separada de `sin_fallback` y de los fallbacks evita cambios de presentación. |

## Estrategia de tests

Todos los tests usan `pytest`, funciones puras, modelos falsos y ejecutores falsos ya presentes en `tests/dobles_grafo.py`. No se crea un cliente Gemini, no se ejecuta `rag_ask` real, no se generan embeddings y no se abre ChromaDB.

| Área | Prueba | Dobles y comprobaciones |
|---|---|---|
| Detección de zonas | Parametrizar A–B2, A a B1, B3–C1 y variantes de mayúsculas; comprobar «entre», «de … a …» y guion. | Sin dobles; función pura. Verifica que ambos códigos pertenezcan al catálogo permitido. |
| Límites de detección | Probar un solo código, ausencia de término tarifario, imagen válida y «¿Cómo llego desde la zona A a Sol?». | Sin dobles; debe devolver que no corresponde la guarda. |
| Prompt compartido | Comprobar que las instrucciones del Supervisor declaran las zonas como tarifarias y no como origen/destino. | Sin dobles; inspección de la cadena generada por el catálogo. |
| Corrección de decisión válida | Simular `{"roles": ["rutas"]}` para las tres consultas de aceptación y comprobar `roles == ["rag"]`, `uso_fallback == false` y categoría `sin_fallback`. | Lambda de modelo que devuelve el diccionario validado; nunca se llama a proveedor. |
| Orden y repeticiones | Simular una cola con `rutas` repetido e intercalado con otros roles. | Modelo falso; comprobar sustituciones posicionales y que las demás entradas no cambian. |
| Ruta física | Simular una solicitud Sol–Atocha con precio y una cola que contiene o necesita `rutas`. | Modelo falso y, para el grafo, especialista de rutas falso; comprobar que la guarda no elimina `rutas`. |
| Evidencia documental | Recorrer el grafo con modelo Supervisor falso que devuelve `rutas`, especialista RAG falso y ejecutor falso de `rag_ask`. | `LLMFalso` y `EjecutorFalso`; comprobar una única traza de RAG y cero ejecución de rutas para A–B2. |
| Imagen | Recorrer el Supervisor con `imagen_valida=True`. | Modelo falso; comprobar que no aplica la guarda textual y se conserva el flujo multimodal vigente. |
| Diagnóstico | Invocar la fachada con un grafo y Supervisor falsos que provoquen la corrección. | Comprobar una entrada `control` de `supervisor` con `correccion_semantica`, el contador en el resumen, ausencia de una entrada de fallback y ausencia del texto crudo de prueba; confirmar que ni checkpoint ni traza contienen el dato efímero. |
| Presentación | No se requieren pruebas nuevas de CLI ni Streamlit. | La categoría técnica ya se reconoce y filtra en las pruebas existentes de presentación; la prueba de contrato demuestra que el registro conserva su forma. |

La validación automatizada final será `python -m pytest`. No se necesita comprobación manual porque todo el comportamiento de la spec puede ejercerse con dobles deterministas.

## Riesgos

- La heurística para reconocer extremos físicos puede confundir una formulación poco habitual; se limita a actuar cuando hay simultáneamente un par tarifario explícito y una intención tarifaria, y se cubren las regresiones de ruta.
- El orden de aplicación de la nueva guarda y de la regla existente que completa rutas es sensible: una implementación en orden distinto podría reinsertar `rutas` tras corregirla. Los tests de decisión y recorrido fijarán el orden esperado.
- El contexto de ejecución es efímero y varios tests construyen contextos explícitos; habrá que actualizar sus fixtures mínimos para incorporar el nuevo contador sin aceptar datos públicos ni persistidos.
- El diagnóstico debe mantenerse como entrada técnica de control, no como una entrada de nodo fallido ni como fallback, para que la UI actual lo filtre correctamente.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Instrucciones compartidas en catálogo | `tests/test_catalogo_roles.py::test_instrucciones_identifican_las_zonas_tarifarias` |
| RF-2 | Detector textual de tarifa entre zonas | `tests/test_catalogo_roles.py::test_detecta_consultas_tarifarias_entre_zonas` |
| RF-3 | Conectores admitidos del detector | `tests/test_catalogo_roles.py::test_detecta_pares_de_zonas_con_cada_conector` |
| RF-4 | Límite de una sola zona | `tests/test_catalogo_roles.py::test_una_sola_zona_no_activa_la_guarda_de_rutas` |
| RF-5 | Exclusión de ruta física | `tests/test_supervisor_grafo.py::test_ruta_fisica_con_precio_conserva_rutas` |
| RF-6 | Sustitución validada de `rutas` por `rag` | `tests/test_supervisor_grafo.py::test_llm_valido_rutas_para_a_b2_se_corrige_a_rag` |
| RF-7 | Conservación de posiciones y repeticiones | `tests/test_supervisor_grafo.py::test_correccion_de_rutas_conserva_orden_y_repeticiones` |
| RF-8 | Categoría de fallback intacta | `tests/test_supervisor_grafo.py::test_correccion_de_rutas_mantiene_sin_fallback` |
| RF-9 | Diagnóstico técnico de corrección | `tests/test_agent_contrato.py::test_correccion_de_rutas_registra_diagnostico_tecnico_separado` |
| RF-10 | Diagnóstico sin salida LLM cruda | `tests/test_agent_contrato.py::test_diagnostico_de_correccion_de_rutas_no_expone_respuesta_cruda` |
| RF-11 | Registro público técnico y separado | `tests/test_agent_contrato.py::test_correccion_de_rutas_registra_diagnostico_tecnico_separado` |
| RF-12 | Filtrado existente de diagnósticos en web | `tests/test_presentacion.py::test_formatear_turno_oculta_diagnosticos_tecnicos` |
| RF-13 | Recorrido hacia RAG y traza | `tests/test_grafo_enrutamiento.py::test_consulta_de_zonas_corregida_llama_rag_ask_y_conserva_traza` |
| RF-14 | Exclusión por imagen válida | `tests/test_supervisor_grafo.py::test_imagen_valida_no_aplica_guarda_de_zonas` |
| RF-15 | No regresión fuera del patrón | `tests/test_catalogo_roles.py::test_consulta_sin_par_de_zonas_conserva_el_comportamiento` |
| RF-16 | Ruta física más atención documental | `tests/test_grafo_enrutamiento.py::test_ruta_fisica_con_precio_conserva_rutas_y_rag` |