# Validación — Spec 002

> Fecha: 2026-10-14 · Actualizada el 2026-10-19 tras integrarse el grafo (specs 005 a 007) · Resultado de `pytest`: 623 passed, 0 failed (`develop`)

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
| RF-21 | Automático · **superado por la spec 005 (RF-15, RF-43, RF-46)** | El flujo ya no lo hace un solo especialista: `tarifas` lee los importes con `describir_imagen` y `auxiliar` calcula con `calculadora`. `tests/test_flujo_imagen_calculo.py::test_tarifas_extrae_importes_sin_calcular`, `::test_tarifas_bloquea_calculadora_y_rag`, `tests/test_grafo_enrutamiento.py::test_grafo_encadena_tarifas_y_auxiliar_sin_calculadora_en_tarifas` | ✅ (con dobles) |
| RF-22 | Automático · **reformulado** | La nota de `tarifas` conserva los importes y su procedencia; la operación la deja `auxiliar` en su traza. `tests/test_flujo_imagen_calculo.py::test_prompt_entrega_importes_y_delega_el_calculo_en_auxiliar` | ✅ (con dobles) |
| RF-23 | Automático | `tests/test_flujo_imagen_calculo.py::test_sin_importes_no_inventa_un_total` | ✅ |
| RF-24 | Automático | `tests/test_describir_imagen.py::test_reintenta_ante_un_error_temporal` (503, 429, 500, 504, tiempo agotado y fallo de conexión) | ✅ |
| RF-25 | Automático | `tests/test_describir_imagen.py::test_dos_fallos_temporales_dan_error_controlado` | ✅ |
| RF-26 | Automático | `tests/test_describir_imagen.py::test_un_error_no_temporal_no_se_reintenta` (400, 401, 403, 404 y error sin código) | ✅ |
| RF-27 | Automático | `tests/test_describir_imagen.py::test_registra_la_causa_sin_datos_sensibles`, `::test_el_registro_indica_el_numero_de_intento`, `::test_un_error_no_temporal_tambien_se_registra` | ✅ |
| Demo | Manual ⚠️ API | `describir_imagen` + `calculadora` sobre la imagen demo con `gemini-3.8-flash` → 4 precios leídos y total 9,50 | ✅ (a nivel de tools; sin LLM de especialista) |

## Criterios de finalización
- [x] Todos los RF con test en verde (`pytest`) sin API.
- [x] Demo manual de las tools realizada con la API real y resultado guardado en el informe.
- [ ] Flujo imagen → importes → total de punta a punta con el grafo real: **no es posible hoy** (ver «Limitaciones»).

## Fuera de spec
- Además de los tests citados, `tests/test_describir_imagen.py::test_el_exito_a_la_primera_no_espera_ni_registra` comprueba que sin fallo no se espera ni se registra nada.
- Especialista `tarifas` (`src/agents/tarifas.py`). La spec dejaba abierto qué especialista usa las tools; se creó uno para dar dueño al flujo. Quien lleva el grafo lo adoptó y lo cambió (spec 005): ahora solo lee la imagen y la cuenta la hace `auxiliar`, y la allowlist de `tarifas` quedó en `describir_imagen`.
- Mini-bucle común en `src/agents/base.py`, compartido con el especialista de horarios.
- Estado «error» en la traza para errores controlados de las tools (`ERROR: ...`).
- Imagen demo: captura de la sección «Billetes de autobuses EMT» de RedTransporte (800 x 260 px). No es un cartel oficial; la fuente y la fecha están en el README.

## Limitaciones
- **El flujo de la imagen es inalcanzable desde los clientes.** La spec 007 solo permite `tarifas` con una «imagen aportada válida», pero `src/agent.py` fija `imagen_valida=False` en cada turno y la API pública no ofrece forma de aportar una imagen. Una consulta sobre una imagen se desvía al RAG, que no ve imágenes. Pendiente de que quien lleva el grafo decida cómo se aporta.
- La demo real (2026-10-14) se hizo a nivel de tools, con un script, no a través del grafo.
- El reintento y el registro de la causa (RF-24 a RF-27) solo se han probado con clientes falsos y con los errores reales de `google.genai` construidos a mano; no se han provocado con un 503 real de Gemini.

## Veredicto
**Parcial.** Los 27 RF (RF-1 a RF-27) tienen test en verde y la suite completa pasa (623 passed en `develop`). El 2026-10-14 se ejecutó la demo real de las dos tools con `gemini-3.8-flash`: `describir_imagen` leyó los cuatro precios de la imagen (RF-1, RF-3, RF-11) y `calculadora` dio 9,50 para `3*1,50+5,00`, con las dos llamadas en la traza (RF-9, RF-10, RF-19, RF-20). RF-21 a RF-23 se reformularon cuando la spec 005 repartió el flujo entre `tarifas` y `auxiliar`; siguen cubiertos con dobles de prueba, pero no se pueden demostrar de punta a punta con el grafo real mientras no se pueda aportar una imagen. T11 quedó hecha a nivel de tools; T12 sigue abierta.

**Actualización del 2026-10-19 (RF-24 a RF-27).** Se añadieron el reintento ante errores temporales y el registro de la causa del fallo, a raíz de la demo real, donde un 503 pasajero, un modelo retirado y una clave inválida daban el mismo mensaje. Los 4 requisitos nuevos tienen test en verde (466 passed).
