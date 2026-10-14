# Plan técnico — Spec 003

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento que no esté en la spec.

## Archivos afectados

| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `rag/chunk.py` | Modificar | Detecta las tablas válidas de documentos Markdown, las emite junto con su título como chunks indivisibles y aplica el splitter ordinario únicamente a los segmentos restantes. Conserva la firma pública actual y anota la estrategia de cada chunk. | RF-1–7 |
| `tests/test_chunk_tablas_markdown.py` | Crear | Pruebas unitarias de detección, indivisibilidad, exclusión de duplicados, entradas no válidas y regresión para formatos no Markdown. | RF-1–7 |

No se modifican `config.py`, interfaces CLI, carga, índice, recuperación ni generación; tampoco se añaden dependencias.

## Contrato

No cambia ningún contrato público ni comando. La función de fragmentación conserva esta firma:

```text
fragmentar_documentos(documentos: list[Document]) -> list[Document]
```

Para un `Document` cuya fuente termine en `.md`, una secuencia válida devuelve un único `Document` de tabla, con los metadatos de origen existentes, índice y tamaño, e identificando su estrategia como tabla Markdown. Los demás segmentos del mismo documento y los documentos de otros formatos mantienen el resultado ordinario actual.

Ejemplo:

```text
Entrada Markdown:
TARIFAS 2026

| Zona | Precio |
| :--- | :--- |
| A | 32,70 € |

Salida relevante:
Document(
  page_content="TARIFAS 2026\n\n| Zona | Precio |\n| :--- | :--- |\n| A | 32,70 € |",
  metadata={..., "chunk_strategy": "tabla_markdown"}
)
```

No habrá otro chunk que contenga el título o una fila de **esa misma ocurrencia** de tabla. Si el documento tiene otra tabla con el título `TARIFAS 2026`, esta genera su propio chunk independiente y también conserva todas sus filas. Una tabla sin fila separadora se devuelve dentro de los chunks ordinarios, igual que el texto normal.

## Lógica clave

```text
para cada documento:
    si es un bloque CSV de paradas:
        conservarlo como hasta ahora
    si su fuente no termina en .md:
        aplicar el splitter ordinario
        continuar

    recorrer sus líneas en orden:
        buscar título inmediatamente anterior (ignorando solo líneas vacías)
        validar: encabezado con barras, separador Markdown y una o más filas con barras
        si no es una tabla válida:
            continuar el recorrido como texto ordinario
        enviar al splitter el texto pendiente anterior al título
        emitir un Document único con título + tabla completa y marcarlo como tabla Markdown
        reanudar tras la última fila de la tabla
    enviar al splitter el texto ordinario restante

añadir a todos los chunks sus metadatos globales actuales:
    tabla Markdown -> estrategia tabla_markdown
    bloque CSV -> estrategia bloque_csv
    resto -> estrategia recursive_character
```

## Decisiones técnicas

| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Detectar las tablas durante la fragmentación de documentos Markdown | Alterar la carga para generar documentos de tabla | La responsabilidad solicitada es de fragmentación y así se conserva el contrato de carga y sus metadatos de origen. |
| Usar un análisis lineal del formato acordado | Incorporar un parser Markdown externo | El formato está delimitado por la spec y el análisis lineal no añade dependencias al stack cerrado. |
| Considerar título la última línea no vacía inmediatamente anterior a la tabla | Exigir que el título sea un encabezado Markdown | El corpus usa títulos en texto plano y la spec no exige marcadores de encabezado. |
| Excluir título y tabla de los segmentos que pasan al splitter | Fragmentar todo y recomponer o filtrar chunks después | Evita duplicados y garantiza que ninguna fila quede en un chunk ordinario. |
| Marcar la estrategia de los chunks de tabla como `tabla_markdown` | No distinguirlos de los chunks ordinarios | Mantiene trazabilidad y permite pruebas directas sin cambiar interfaces públicas. |
| Mantener la tabla completa aunque exceda el límite ordinario | Dividirla por filas o aplicar el límite configurado | RF-3 exige que sea indivisible. |

## Estrategia de tests

Todos los tests serán unitarios y no usarán API, LLM, embeddings ni ChromaDB. Construirán `Document` en memoria; `monkeypatch` reducirá el tamaño de chunk efectivo cuando sea necesario para demostrar que una tabla larga no se divide.

- RF-1: un Markdown con título, encabezados, separador y filas produce un chunk marcado como tabla Markdown.
- RF-2: el contenido del chunk de tabla es exactamente el título y todas sus filas, en el mismo orden; dos tablas consecutivas, aunque repitan título, generan dos chunks independientes.
- RF-3: una tabla de longitud mayor que el límite ordinario sigue generando un solo chunk completo.
- RF-4: se comprueba que el título y marcadores exclusivos de cada ocurrencia de tabla aparecen una sola vez fuera de su propio chunk, sin prohibir que otra tabla independiente use el mismo texto de título.
- RF-5: se parametrizan tablas sin título y con separador inválido; ninguna se marca como tabla y su texto se somete a la estrategia ordinaria.
- RF-6: texto antes, entre y después de tablas válidas se conserva en chunks ordinarios, sin contener título ni filas de una tabla reconocida.
- RF-7: un documento con fuente `.pdf` y un bloque CSV de paradas conservan las estrategias y el comportamiento ya existentes; no se intenta reconocer tablas en ellos.

No hay validación manual obligatoria: todos los RF se pueden comprobar de forma determinista mediante `pytest`.

## Riesgos

- El formato Markdown convertido puede contener filas irregulares; el detector debe ceñirse a la forma acordada y dejar las demás como texto ordinario (RF-5).
- Un texto inmediatamente antes de una tabla puede interpretarse como título si cumple la posición definida por la spec; el corpus debe mantener el formato título + tabla acordado.
- Los chunks de tabla largos incrementan el tamaño de una entrada de embeddings, pero es un efecto explícitamente requerido por RF-3.
- Cambiar la enumeración de chunks puede invalidar artefactos de ingesta previos; al preparar de nuevo el corpus se regenerarán sus artefactos según el flujo existente.

## Trazabilidad

| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | Detección lineal en `rag/chunk.py` | `tests/test_chunk_tablas_markdown.py::test_reconoce_tabla_markdown_valida` |
| RF-2 | Emisión del chunk indivisible con título | `::test_tabla_con_titulo_y_filas_completas`, `::test_tablas_consecutivas_con_titulo_repetido_son_chunks_independientes` |
| RF-3 | Ruta de emisión directa de tabla | `::test_tabla_mayor_que_limite_permanece_en_un_chunk` |
| RF-4 | Exclusión de cada ocurrencia de tabla de los segmentos ordinarios | `::test_ocurrencia_de_tabla_y_titulo_no_se_duplican_fuera_de_su_chunk` |
| RF-5 | Validación de formato y fallback ordinario | `::test_tabla_sin_titulo_se_trata_como_texto`, `::test_tabla_con_separador_invalido_se_trata_como_texto` |
| RF-6 | Segmentación de texto no tabular | `::test_texto_alrededor_de_tabla_usa_fragmentacion_ordinaria` |
| RF-7 | Selección solo para Markdown | `::test_documento_no_markdown_mantiene_estrategia_ordinaria`, `::test_bloque_csv_mantiene_estrategia_actual` |
