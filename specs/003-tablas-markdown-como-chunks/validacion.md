# Validación — Spec 003

> Fecha: 2026-10-14 · Resultado de `pytest`: 86 passed in 5.51s

| RF | Cómo se comprueba | Test o comprobación manual | Resultado |
|---|---|---|---|
| RF-1 | Automático | `tests/test_chunk_tablas_markdown.py::test_reconoce_tabla_markdown_valida` | ✅ |
| RF-2 | Automático | `::test_tabla_con_titulo_y_filas_completas`, `::test_tablas_consecutivas_con_titulo_repetido_son_chunks_independientes` | ✅ |
| RF-3 | Automático | `::test_tabla_mayor_que_limite_permanece_en_un_chunk` | ✅ |
| RF-4 | Automático | `::test_ocurrencia_de_tabla_y_titulo_no_se_duplican_fuera_de_su_chunk` | ✅ |
| RF-5 | Automático | `::test_tabla_sin_titulo_se_trata_como_texto`, `::test_tabla_con_separador_invalido_se_trata_como_texto`, `::test_tabla_sin_encabezado_se_trata_como_texto` | ✅ |
| RF-6 | Automático | `::test_texto_alrededor_de_tabla_usa_fragmentacion_ordinaria` | ✅ |
| RF-7 | Automático | `::test_documento_no_markdown_mantiene_estrategia_ordinaria`, `::test_bloque_csv_mantiene_estrategia_actual` | ✅ |

## Criterios de finalización

- [x] Todos los RF tienen tests automatizados en verde con `pytest`, sin API.
- [x] Las pruebas de fragmentación con tablas del formato acordado demuestran que cada ocurrencia se conserva en un único chunk con su título y sin fragmentos duplicados en otros chunks.

## Fuera de spec

Nada. El metadato `chunk_strategy: tabla_markdown` se usa únicamente para mantener la trazabilidad de la estrategia de fragmentación, exigida por los requisitos no funcionales.

## Veredicto

Sí — se cumplen RF-1 a RF-7 y los criterios de finalización mediante pruebas deterministas sin API.
