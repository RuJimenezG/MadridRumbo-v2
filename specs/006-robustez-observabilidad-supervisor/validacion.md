# Comprobación manual segura con Gemini real

Esta guía es manual y opcional. No forma parte de `pytest`: cada escenario puede
contactar con Gemini y consumir cuota. No ejecutar estos comandos durante una
validación automática ni si no se dispone de autorización para usar el
proveedor.

## Preparación y límites

- Ejecutar cada escenario desde la raíz del repositorio, en una consola nueva.
- Usar un `thread_id` nuevo en cada ejecución para no reutilizar un checkpoint.
- No abrir, imprimir, copiar ni modificar `.env`; tampoco incluir claves reales
  en comandos, resultados, incidencias o capturas.
- Para el diagnóstico, imprimir únicamente `resultado["log"]`. No imprimir el
  resultado completo, los prompts, la respuesta cruda del modelo ni la traza.
- La categoría del Supervisor solo puede ser `sin_fallback`, `proveedor`,
  `json_invalido` o `roles_invalidos`. El resumen que aparece en `log` procede
  de un catálogo fijo y no contiene detalles del proveedor.

Las pruebas automáticas ya verifican este límite con dobles y sin credenciales,
red, embeddings ni bases de datos reales: `test_modelos_grafo.py`,
`test_supervisor_grafo.py`, `test_grafo_enrutamiento.py`,
`test_especialista_rutas.py`, `test_agent_contrato.py`,
`test_estado_grafo.py` y `test_grafo_persistencia.py`.

## Regresión de tests sin Gemini

Comprobación realizada el 19/10/2026:

- `python -m pytest tests/test_agent_contrato.py::test_fallback_publico_solo_expone_categoria_y_resumen_canonicos -q`: **1 passed**.
- `python -m pytest -q`: **100 % completado, código de salida 0**.

El test de fallback público inyecta los cinco especialistas, registra que la
consulta «¿Qué hora es?» alcanza el doble `auxiliar` y sustituye la creación
del cliente Gemini por un centinela que falla si se invoca. Por tanto, cubre
RF-10 a RF-14 sin pedir credenciales ni abrir conexiones de red.

## Registro de ejecución manual

Comprobaciones realizadas el 17/10/2026 por la persona validadora:

- Escenario 1: la salida de `log` incluyó la categoría y el resumen esperados
  para `sin_fallback`.
- Escenario 2: la salida de `log` incluyó la categoría y el resumen esperados
  para `proveedor`.

La ejecución confirma la observabilidad segura de la decisión del Supervisor.
No valida la continuidad de los especialistas ante una caída total del
proveedor: por ejemplo, `auxiliar` necesita hoy al LLM para decidir que debe
invocar `hora_actual`. Esa mejora requeriría una spec distinta.

## Escenario 1: decisión válida del Supervisor

Con Gemini configurado de forma habitual para el proceso, ejecutar una consulta
ligera que no active rutas ni RAG:

```powershell
python -c "from src.agent import procesar_turno; resultado = procesar_turno({}, '¿Qué hora es?', 'manual-supervisor-valido-006'); print(resultado['log'])"
```

Si Gemini responde y su decisión cumple el contrato, la salida de `log` incluye
exactamente esta entrada de diagnóstico:

```text
Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada.
```

Esa categoría acredita que la decisión del Supervisor fue JSON válido y no se
usó el fallback. Una incidencia posterior de otro especialista no cambia ese
diagnóstico del turno.

## Escenario 2: fallback reproducible por proveedor

Abrir una consola PowerShell nueva e independiente. En ella, establecer una
clave deliberadamente inválida solo para ese proceso, sin consultar ni tocar
`.env`, y ejecutar el mismo tipo de consulta:

```powershell
$env:GEMINI_API_KEY = 'clave-invalida-solo-proceso-006'
python -c "from src.agent import procesar_turno; resultado = procesar_turno({}, '¿Qué hora es?', 'manual-supervisor-proveedor-006'); print(resultado['log'])"
```

La variable de entorno del proceso prevalece sobre la configuración habitual.
La llamada puede alcanzar el proveedor, pero no debe revelar el valor de esa
clave. El resultado esperado es:

```text
Supervisor: categoria=proveedor; resumen=El proveedor no entregó una respuesta utilizable.
```

Cerrar esa consola al terminar el escenario. Así se descarta la variable
temporal sin modificar archivos ni afectar a otras sesiones.

## Revisión segura y clientes futuros

Para diagnosticar un turno, revisar exclusivamente la entrada canónica de
`log` con el prefijo `Supervisor:`. No usar `traza`, excepciones, prompts ni
salidas sin filtrar como fuente del diagnóstico.

La fachada pública devuelve seis claves: `respuesta`, `plan`, `log`, `traza`,
`hitl_pendiente` y `done`. El diagnóstico se entrega únicamente en el resultado
del turno que ejecutó el Supervisor; no se guarda en su historial ni en el
checkpoint, y no reaparece al aprobar un plan.

No se implementa aquí ningún cliente. Una CLI futura podrá ofrecer una opción
técnica para presentar la entrada segura de `log`. Un Streamlit futuro deberá
renderizar la respuesta y el plan, pero no podrá mostrar ni conservar `log` o
`traza` en el historial de chat. Esa integración queda para una spec posterior;
`main.py` y `app.py` no forman parte de esta validación.

## Validación final RF por RF

La evidencia automática se ejecuta con dobles y no usa credenciales, red,
embeddings ni bases de datos reales. Los escenarios de Gemini de esta guía se
ejecutaron manualmente el 17/10/2026 y no forman parte de `pytest` porque
pueden consumir cuota.

| RF | Veredicto | Evidencia | Tipo / estado |
| --- | --- | --- | --- |
| RF-1 | Sí | `test_prompt_del_supervisor_exige_json_sin_envoltorios` y `test_decision_de_roles_valida_conserva_orden_y_sin_fallback` | Automatizada |
| RF-2 | Sí | `test_prompt_del_supervisor_exige_json_sin_envoltorios` comprueba `{"roles": ["auxiliar"]}` | Automatizada |
| RF-3 | Sí | `test_prompt_del_supervisor_exige_json_sin_envoltorios` comprueba la instrucción JSON sin Markdown ni texto envolvente | Automatizada |
| RF-4 | Sí | `test_decision_de_roles_valida_conserva_orden_y_sin_fallback` cubre lista vacía, repetición y veinte roles | Automatizada |
| RF-5 | Sí | `test_supervisor_acepta_json_y_fences_markdown_recuperables` cubre fence vacío, `json`, `JSON` y espacios exteriores | Automatizada |
| RF-6 | Sí | `test_json_no_valido_activa_fallback_clasificado` rechaza comillas simples como `json_invalido` | Automatizada |
| RF-7 | Sí | `test_supervisor_rechaza_json_con_formato_no_recuperable` y `test_json_no_valido_activa_fallback_clasificado` rechazan prosa y contenido exterior | Automatizada |
| RF-8 | Sí | `test_incidencias_del_proveedor_se_traducen_sin_exponer_detalles` y `test_incidencias_de_proveedor_activan_fallback_sin_filtrar_detalles` | Automatizada |
| RF-9 | Sí | `test_roles_fuera_del_contrato_activan_fallback_clasificado` cubre forma, tamaño y allowlist | Automatizada |
| RF-10 | Sí | `test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` y `test_proyeccion_anade_diagnostico_canonico_sin_mutar_estado_ni_filtrar_texto` | Automatizada |
| RF-11 | Sí | `test_decision_de_roles_valida_conserva_orden_y_sin_fallback` y `test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo` | Automatizada |
| RF-12 | Sí | Casos de `proveedor`, `json_invalido`, `roles_invalidos` y `sin_fallback` en `test_supervisor_grafo.py` | Automatizada |
| RF-13 | Sí | `test_proyeccion_anade_diagnostico_canonico_sin_mutar_estado_ni_filtrar_texto` usa el catálogo fijo | Automatizada |
| RF-14 | Sí | `test_incidencias_de_proveedor_activan_fallback_sin_filtrar_detalles` y `test_fallback_publico_solo_expone_categoria_y_resumen_canonicos` usan centinelas no filtrados | Automatizada |
| RF-15 | Sí, frontera preparada | `test_fachada_expone_las_dos_firmas_y_las_seis_claves` y la sección «Revisión segura y clientes futuros» | Automatizada y documentada; CLI diferida por alcance |
| RF-16 | Sí, frontera preparada | Separación de `log`/`traza` en `test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo` y esta guía | Automatizada y documentada; Streamlit diferido por alcance |
| RF-17 | Sí | `test_reglas_reconocen_formulaciones_equivalentes_de_ruta` y `test_fallback_de_ruta_valida_planifica_y_se_pausa_para_hitl` | Automatizada |
| RF-18 | Sí | `test_reglas_reconocen_formulaciones_equivalentes_de_ruta` y `test_fallback_de_ruta_valida_planifica_y_se_pausa_para_hitl` | Automatizada |
| RF-19 | Sí | `test_reglas_reconocen_formulaciones_equivalentes_de_ruta` y `test_fallback_de_ruta_valida_planifica_y_se_pausa_para_hitl` | Automatizada |
| RF-20 | Sí | `test_fallback_de_ruta_valida_planifica_y_se_pausa_para_hitl` verifica tool, plan normalizado y pausa HITL | Automatizada |
| RF-21 | Sí | `test_formulacion_incompleta_pide_aclaracion_antes_de_llm_tool_y_hitl` deja LLM, tool, traza y plan en cero | Automatizada |
| RF-22 | Sí | Escenarios «decisión válida» y «fallback reproducible por proveedor» de este documento | Manual ejecutada el 17/10/2026 |
| RF-23 | Sí | Secciones «Preparación y límites» y «Revisión segura y clientes futuros» de este documento | Manual ejecutada el 17/10/2026 |
| RF-24 | Sí | `test_generador_del_supervisor_pide_application_json_al_proveedor` y `test_solo_el_adaptador_del_supervisor_solicita_json` | Automatizada |
| RF-25 | Sí | `test_grafo_transporta_diagnostico_por_contexto_sin_persistirlo`, `test_resultado_del_turno_expone_diagnostico_seguro_sin_persistirlo` y `test_reanudacion_hitl_no_reproyecta_el_diagnostico_del_turno_inicial` | Automatizada |

Resultado de la regresión final: todos los RF tienen evidencia automatizada o
una comprobación manual documentada y realizada. La ejecución manual de Gemini
quedó limitada a los dos escenarios seguros descritos en esta guía.
