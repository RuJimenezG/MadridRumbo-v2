# Validación — Spec 002

> Fecha: 2026-10-14 · Resultado de `pytest`: 75 passed, 0 failed

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_describir_imagen.py::test_describe_imagen` | ✅ |
| RF-2 | Automático | `tests/test_describir_imagen.py::test_pregunta_en_prompt` | ✅ |
| RF-3 | Automático | `tests/test_describir_imagen.py::test_imagen_por_defecto` | ✅ |
| RF-4 | Automático | `tests/test_describir_imagen.py::test_no_existe`, `::test_formato_no_admitido` | ✅ |
| RF-5 | Automático | `tests/test_describir_imagen.py::test_imagen_grande` | ✅ |
| RF-6 | Automático | `tests/test_describir_imagen.py::test_ruta_fuera_de_carpeta` | ✅ |
| RF-7 | Automático | `tests/test_describir_imagen.py::test_modelo_falla` | ✅ |
| RF-8 | Automático | `tests/test_describir_imagen.py::test_sin_texto_legible` | ✅ |
| RF-9 | Automático | `tests/test_allowlist_multimodal.py::test_imagen_en_allowlist` | ✅ |
| RF-10 | Automático | `tests/test_allowlist_multimodal.py::test_traza_imagen` | ✅ |
| RF-11 | Automático + manual | `tests/test_allowlist_multimodal.py::test_imagen_demo_existe` y lectura visual | ✅ (imagen revisada a simple vista el 2026-10-14) |
| RF-12–14 | Automático | `tests/test_calculadora.py::test_operaciones`, `::test_decimales_coma`, `::test_formato_resultado` | ✅ |
| RF-15 | Automático | `tests/test_calculadora.py::test_expresion_no_permitida` | ✅ |
| RF-16 | Automático | `tests/test_calculadora.py::test_division_cero` | ✅ |
| RF-17 | Automático | `tests/test_calculadora.py::test_expresion_vacia_o_larga` | ✅ |
| RF-18 | Automático | `tests/test_calculadora.py::test_sin_red` | ✅ |
| RF-19 | Automático | `tests/test_allowlist_multimodal.py::test_calculadora_en_allowlist` | ✅ |
| RF-20 | Automático | `tests/test_allowlist_multimodal.py::test_traza_calculadora` | ✅ |
| RF-21 | Automático | `tests/test_flujo_imagen_calculo.py::test_imagen_luego_calculo`, `::test_flujo_con_tools_reales`, `::test_tool_ajena_bloqueada` | ✅ |
| RF-22 | Automático | `tests/test_flujo_imagen_calculo.py::test_nota_muestra_importes_y_operacion` | ✅ |
| RF-23 | Automático | `tests/test_flujo_imagen_calculo.py::test_sin_importes_no_calcula` | ✅ |
| Demo | Manual ⚠️ API | `describir_imagen` + `calculadora` sobre la imagen demo con `gemini-3.8-flash` → 4 precios leídos y total 9,50 | ✅ (a nivel de tools; sin LLM de especialista) |

## Criterios de finalización
- [x] Todos los RF con test en verde (`pytest`) sin API.
- [x] Demo manual de las tools realizada con la API real y resultado guardado en el informe.

## Fuera de spec
- Especialista `tarifas` (`src/agents/tarifas.py`) y su entrada en `TOOLS_POR_ESPECIALISTA`. La spec dejaba abierto qué especialista usa las tools; se creó uno para dar dueño al flujo (RF-21 a RF-23). Está pendiente de confirmar con quien lleve el grafo.
- Mini-bucle común en `src/agents/base.py`, compartido con el especialista de horarios.
- Estado «error» en la traza para errores controlados de las tools (`ERROR: ...`).
- Imagen demo: captura de la sección «Billetes de autobuses EMT» de RedTransporte (800 x 260 px). No es un cartel oficial; la fuente y la fecha están en el README.

## Veredicto
**Parcial.** Los 23 RF tienen test en verde y la suite completa pasa (75 passed). Además, el 2026-10-14 se ejecutó la demo real de las dos tools con `gemini-3.8-flash`: `describir_imagen` leyó los cuatro precios de la imagen (RF-1, RF-3, RF-11) y `calculadora` dio 9,50 para `3*1,50+5,00`, con las dos llamadas en la traza (RF-9, RF-10, RF-19, RF-20). Queda sin probar el flujo del especialista `tarifas` con un LLM real, que necesita el grafo integrado (RF-21 a RF-23 solo están cubiertos con LLM falso). El modelo configurado por defecto (`gemini-3.6-flash`) devolvió un 503 por demanda alta durante la prueba. T11 queda hecha a nivel de tools; T12 sigue abierta hasta probar el flujo con el grafo.
