# Validación — Spec 007

> Fecha: 2026-10-18 · Resultado de `python -m pytest -ra`: **450 passed en 11,21 s**.
>
> La ejecución usa dobles de prueba; no invoca proveedores, APIs, embeddings ni
> ChromaDB reales.

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_catalogo_roles.py::test_catalogo_declara_roles_y_responsabilidades` | Sí |
| RF-2 | Automático | `tests/test_catalogo_roles.py::test_instrucciones_reutilizan_catalogo_y_exclusiones_de_tarifas` | Sí |
| RF-3 | Automático | `tests/test_catalogo_roles.py::test_instrucciones_reutilizan_catalogo_y_exclusiones_de_tarifas` | Sí |
| RF-4 | Automático | `tests/test_catalogo_roles.py::test_catalogo_declara_roles_y_responsabilidades` | Sí |
| RF-5 | Automático | `tests/test_catalogo_roles.py::test_catalogo_declara_roles_y_responsabilidades` | Sí |
| RF-6 | Automático | `tests/test_catalogo_roles.py::test_catalogo_declara_roles_y_responsabilidades` | Sí |
| RF-7 | Automático | `tests/test_catalogo_roles.py::test_detecta_terminos_tarifarios_con_normalizacion_y_flexiones_simples` y `tests/test_supervisor_grafo.py::test_decision_tarifas_textual_valida_se_corrige_a_rag` | Sí |
| RF-8 | Automático | `tests/test_catalogo_roles.py::test_instrucciones_reutilizan_catalogo_y_exclusiones_de_tarifas` y `tests/test_agent_contrato.py::test_procesar_turno_inicializa_el_contexto_sin_imagen_valida` | Sí |
| RF-9 | Automático | `tests/test_catalogo_roles.py::test_corrige_tarifas_sin_imagen_y_conserva_orden_y_repeticiones` y `tests/test_supervisor_grafo.py::test_repeticiones_tarifas_informan_contador_seguro_y_conservan_orden` | Sí |
| RF-10 | Automático | `tests/test_catalogo_roles.py::test_referencia_a_cartel_sin_archivo_sigue_siendo_consulta_textual` y `tests/test_supervisor_grafo.py::test_referencia_textual_a_cartel_sin_imagen_va_a_rag` | Sí |
| RF-11 | Automático | `tests/test_supervisor_grafo.py::test_imagen_valida_conserva_tarifas_en_una_decision_valida` y `tests/test_flujo_imagen_calculo.py::test_contexto_de_imagen_demo_explicita_conserva_tarifas_sin_persistirla` | Sí |
| RF-12 | Automático | `tests/test_flujo_imagen_calculo.py::test_tarifas_sin_imagen_no_inicia_llm_ni_vision_y_pide_redireccion` y `tests/test_grafo_enrutamiento.py::test_tarifas_sin_imagen_redirige_a_rag_sin_vision` | Sí |
| RF-13 | Automático | `tests/test_grafo_enrutamiento.py::test_combinado_metro_corregido_llama_rag_ask_y_conserva_traza` | Sí |
| RF-14 | Automático | `tests/test_estado_grafo.py::test_proyeccion_anade_indicador_de_correccion_semantica_seguro_y_separado` | Sí |
| RF-15 | Automático | `tests/test_supervisor_grafo.py::test_fallback_valido_se_conserva_sin_correccion_semantica` y `tests/test_agent_contrato.py::test_correccion_semantica_se_expone_solo_en_el_turno_que_la_origina` | Sí |
| RF-16 | Automático | `tests/test_estado_grafo.py::test_proyeccion_anade_indicador_de_correccion_semantica_seguro_y_separado` y `tests/test_supervisor_grafo.py::test_repeticiones_tarifas_informan_contador_seguro_y_conservan_orden` | Sí |
| RF-17 | Automático | `tests/test_agent_contrato.py::test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo` y `tests/test_agent_contrato.py::test_correccion_semantica_se_expone_solo_en_el_turno_que_la_origina` | Sí |
| RF-18 | Contrato y documentación | La proyección pública conserva seis claves y sitúa el diagnóstico seguro en `log`: `tests/test_estado_grafo.py::test_proyeccion_publica_tiene_solo_las_seis_claves_y_traza_normalizada`. La integración de clientes se describe en «Consumo por clientes futuros». | Sí |
| RF-19 | Contrato y documentación | El mismo contrato no añade campos públicos técnicos y el contexto no persiste: `tests/test_agent_contrato.py::test_correccion_semantica_se_expone_solo_en_el_turno_que_la_origina`. La pauta de Streamlit en «Consumo por clientes futuros» excluye esas líneas de su UI. | Sí |
| RF-20 | Documentación | Secciones «Diagnóstico seguro» y «Consumo por clientes futuros» de este documento. | Sí |

## Diagnóstico seguro

Una corrección semántica no es un fallback. El fallback es una decisión de
contingencia del Supervisor, clasificada únicamente por el valor canónico
`sin_fallback` o por su categoría de fallo correspondiente. Una corrección se
produce después de que el JSON y los roles del modelo ya sean válidos: Python
sustituye las apariciones incompatibles de `tarifas` por `rag`.

En el resultado del turno, ambas señales están separadas en líneas canónicas
de `log`:

```text
Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada.
Supervisor: correccion_semantica=aplicada; resumen=Se redirigieron N derivaciones incompatibles de tarifas a rag.
```

La segunda línea solo aparece en el turno que aplicó la corrección. `N` es el
contador seguro de roles sustituidos. No contiene la respuesta cruda del LLM,
el JSON original, prompts, claves ni otro contenido sensible. La `traza`
continúa siendo la traza normalizada de tools; para una tarifa textual
redirigida permite comprobar la llamada a `rag_ask` y su evidencia anclada al
corpus CRTM.

## Pruebas manuales con LLM real

Estas comprobaciones complementan la suite automática; no se ejecutan con
`pytest`. Requieren que el entorno ya disponga de las credenciales autorizadas
y del índice RAG preparado, por lo que pueden consumir llamadas de proveedor.
Usar identificadores de hilo nuevos para no reutilizar un checkpoint previo.

### 1. Precio de un billete sin imagen: debe usar RAG

En una consola Python del entorno configurado, ejecutar:

```python
from src.agent import procesar_turno

resultado = procesar_turno(
    {},
    "¿Cuánto cuesta un billete sencillo de Metro?",
    "validacion-manual-rag-sin-imagen",
)
print(resultado["respuesta"])
print(resultado["log"])
print(resultado["traza"])
```

Verificar que la respuesta se apoya en el corpus CRTM y que `traza` contiene
una entrada con `tool == "rag_ask"`. No debe haber ninguna entrada con
`tool == "describir_imagen"`. Si el Supervisor hubiera emitido de forma
válida `tarifas`, el `log` debe incluir además la línea canónica
`correccion_semantica=aplicada` y seguir mostrando `categoria=sin_fallback`.

**Resultado registrado (2026-10-18): Conforme.** La consulta devolvió una
respuesta apoyada en el corpus CRTM, con precios de billete sencillo entre
1,50 € y 1,90 €. La `traza` registró tres consultas `rag_ask` y ninguna llamada
a `describir_imagen`. El Supervisor produjo una decisión estructurada válida,
reflejada como `categoria=sin_fallback`; al seleccionar directamente `rag`, no
correspondía registrar una corrección semántica.

### 2. Análisis de la imagen demo: debe usar `tarifas`

La fachada pública inicializa siempre el turno sin imagen; para esta prueba la
integración interna marca explícitamente como válida la demo configurada, sin
alterar el contrato público. En una consola Python del entorno configurado,
ejecutar:

```python
from src.estado import crear_estado_inicial, proyectar_resultado
from src.graph import crear_grafo, invocar_grafo

grafo = crear_grafo()
contexto = {
    "diagnostico_supervisor": None,
    "correcciones_tarifas": 0,
    "imagen_valida": True,
}
estado_final = invocar_grafo(
    grafo,
    crear_estado_inicial("Analiza la imagen demo configurada e indica los precios visibles."),
    "validacion-manual-imagen-demo",
    contexto=contexto,
)
resultado = proyectar_resultado(
    estado_final,
    diagnostico_supervisor=contexto["diagnostico_supervisor"],
    correcciones_tarifas=contexto["correcciones_tarifas"],
)
print(resultado["respuesta"])
print(resultado["log"])
print(resultado["traza"])
```

Verificar que `traza` contiene una entrada con `tool == "describir_imagen"`,
que no se registra una corrección semántica y que el diagnóstico conserva
`categoria=sin_fallback`. La tool utiliza `config.IMAGEN_DEMO` si el especialista
no indica una ruta, por lo que la comprobación analiza la demo configurada.

**Resultado registrado (2026-10-18): Conforme.** La respuesta extrajo cuatro
tarifas visibles de la imagen demo y la `traza` contiene una única llamada
correcta a `describir_imagen`, sin llamadas RAG. El diagnóstico fue una decisión
estructurada válida (`categoria=sin_fallback`) y no registró corrección
semántica, como corresponde a una imagen marcada explícitamente como válida.

## Consumo por clientes futuros

Esta spec no modifica `main.py`, `app.py` ni `rag/rag_cli.py`, y no añade
campos al contrato público. Los clientes futuros deben usar exclusivamente el
resultado ya proyectado:

- Un cliente técnico puede inspeccionar y registrar las líneas canónicas de
  `log` y la `traza` normalizada. Debe presentar la corrección como señal
  técnica independiente y no como un fallback ni como una respuesta del
  modelo.
- Streamlit no debe mostrar la línea `correccion_semantica=aplicada`, su
  resumen ni detalles de `traza` a la persona usuaria. Solo presentará la
  respuesta de síntesis y las fuentes que correspondan al flujo normal.
- Ningún cliente debe reconstruir ni solicitar el contenido crudo de la
  decisión del LLM; el indicador y el resumen fijo son la única observabilidad
  de la corrección.

## Criterios de finalización

- [x] Todos los RF tienen evidencia de pruebas o de contrato/documentación y
  la suite está en verde.
- [x] La decisión válida pero incompatible para Combinado Metro llama una vez
  a `rag_ask`, conserva respuesta y traza ancladas y no llama a visión.
- [x] Una imagen válida, incluida la demo marcada explícitamente, conserva el
  recorrido por `tarifas` y la llamada visual.
- [x] Las apariciones repetidas de `tarifas` se sustituyen posicionalmente por
  `rag` sin alterar el orden.
- [x] La corrección queda observable con contador y resumen seguro, separada
  de `sin_fallback` y sin respuesta cruda del LLM.
- [x] Este documento explica cómo revisar la corrección y distinguirla de un
  fallback.
- [x] La suite completa se ejecuta sin APIs ni credenciales reales.

## Fuera de spec

Nada. La señal interna de imagen y la redirección defensiva del grafo son los
mecanismos necesarios para los RF-8 a RF-13; no amplían el contrato público,
la allowlist ni las herramientas RAG o de visión.

## Veredicto

**Sí.** La spec se cumple: los 20 requisitos cuentan con evidencia, la
regresión completa pasa con dobles y se mantienen fuera de alcance los
clientes públicos y los contratos de RAG y visión.
