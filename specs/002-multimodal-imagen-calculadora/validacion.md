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
| Demo | Manual ⚠️ API | «Según la imagen, ¿cuánto cuestan 3 billetes sencillos y 2 abonos?» → traza `describir_imagen` + `calculadora`, total correcto | ⏭ Omitida (ver «Veredicto») |

## Criterios de finalización
- [x] Todos los RF con test en verde (`pytest`) sin API.
- [ ] Demo manual realizada y resultado guardado para el informe.

## Fuera de spec
- Especialista `tarifas` (`src/agents/tarifas.py`) y su entrada en `TOOLS_POR_ESPECIALISTA`. La spec dejaba abierto qué especialista usa las tools; se creó uno para dar dueño al flujo (RF-21 a RF-23). Está pendiente de confirmar con quien lleve el grafo.
- Mini-bucle común en `src/agents/base.py`, compartido con el especialista de horarios.
- Estado «error» en la traza para errores controlados de las tools (`ERROR: ...`).
- Imagen demo: captura de la sección «Billetes de autobuses EMT» de RedTransporte (800 x 260 px). No es un cartel oficial; la fuente y la fecha están en el README.

## Veredicto
**Parcial.** Los 23 RF tienen test en verde y la suite completa pasa (75 passed). No se ha verificado con la API real: la lectura de la imagen por Gemini (RF-1, RF-8) y la demo «3 billetes sencillos EMT y 1 Exprés Aeropuerto → 9,50 €» no se han ejecutado. Los tests usan un cliente falso, así que no prueban que el modelo lea bien las cifras. T11 y T12 quedan abiertas hasta hacer esa demo.
