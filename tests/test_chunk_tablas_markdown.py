"""Tests de tablas Markdown indivisibles (spec 003, T1)."""

from langchain_core.documents import Document

import rag.chunk as chunk


def _documento_markdown(texto: str) -> Document:
    """Crea un documento Markdown en memoria para no depender del corpus real."""
    return Document(page_content=texto, metadata={"source": "data/tarifas.md"})


def test_reconoce_tabla_markdown_valida():
    """RF-1: reconoce título, encabezado, separador y fila de contenido."""
    contenido = (
        "TARIFAS 2026\n\n"
        "| Zona | Precio |\n"
        "| :--- | ---: |\n"
        "| FILA-VALIDA | 32,70 € |"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert len(chunks) == 1
    assert chunks[0].page_content == contenido
    assert chunks[0].metadata["chunk_strategy"] == "tabla_markdown"


def test_tabla_con_titulo_y_filas_completas():
    """RF-2: un único chunk conserva el título y todas las filas de una tabla."""
    contenido = (
        "PRECIOS POR ZONA\n\n"
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| FILA-UNO | 32,70 € |\n"
        "| FILA-DOS | 38,20 € |"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert [item.page_content for item in chunks] == [contenido]
    assert chunks[0].metadata["chunk_strategy"] == "tabla_markdown"


def test_tabla_mayor_que_limite_permanece_en_un_chunk(monkeypatch):
    """RF-3: el límite ordinario no divide una tabla reconocida."""
    monkeypatch.setattr(chunk, "CHUNK_SIZE", 80)
    monkeypatch.setattr(chunk, "CHUNK_OVERLAP", 10)
    fila_larga = "TEXTO-LARGO-" * 12
    contenido = (
        "TABLA LARGA\n\n"
        "| Concepto | Importe |\n"
        "| :--- | ---: |\n"
        f"| {fila_larga} | 99,99 € |"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert len(contenido) > chunk.CHUNK_SIZE
    assert [item.page_content for item in chunks] == [contenido]
    assert chunks[0].metadata["chunk_strategy"] == "tabla_markdown"


def test_tablas_consecutivas_con_titulo_repetido_son_chunks_independientes():
    """RF-2: títulos repetidos identifican ocurrencias distintas, no una sola tabla."""
    primera = (
        "TARIFAS 2026\n\n"
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| FILA-A-UNICA | 32,70 € |"
    )
    segunda = (
        "TARIFAS 2026\n\n"
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| FILA-B-UNICA | 38,20 € |"
    )

    chunks = chunk.fragmentar_documentos(
        [_documento_markdown(f"{primera}\n\n{segunda}")]
    )

    assert [item.page_content for item in chunks] == [primera, segunda]
    assert [item.metadata["chunk_strategy"] for item in chunks] == [
        "tabla_markdown",
        "tabla_markdown",
    ]


def test_ocurrencia_de_tabla_y_titulo_no_se_duplican_fuera_de_su_chunk(monkeypatch):
    """RF-4: el splitter ordinario no reproduce filas ni título de una ocurrencia."""
    monkeypatch.setattr(chunk, "CHUNK_SIZE", 60)
    monkeypatch.setattr(chunk, "CHUNK_OVERLAP", 10)
    contenido = (
        f"{'PREFACIO ' * 12}\n\n"
        "TITULO-UNICO-DE-TABLA\n\n"
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| FILA-EXCLUSIVA-DE-TABLA | 32,70 € |\n\n"
        f"{'EPILOGO ' * 12}"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])
    textos = [item.page_content for item in chunks]

    assert sum("TITULO-UNICO-DE-TABLA" in texto for texto in textos) == 1
    assert sum("FILA-EXCLUSIVA-DE-TABLA" in texto for texto in textos) == 1
    assert next(
        item for item in chunks if item.metadata["chunk_strategy"] == "tabla_markdown"
    ).page_content.startswith("TITULO-UNICO-DE-TABLA")


def test_tabla_sin_titulo_se_trata_como_texto():
    """RF-5: sin una línea de título anterior no hay tabla reconocida."""
    contenido = (
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| SIN-TITULO | 32,70 € |"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert all(item.metadata["chunk_strategy"] == "recursive_character" for item in chunks)
    assert "SIN-TITULO" in "\n".join(item.page_content for item in chunks)


def test_tabla_con_separador_invalido_se_trata_como_texto():
    """RF-5: una segunda fila que no es separadora no activa la estrategia especial."""
    contenido = (
        "TITULO CON SEPARADOR INVALIDO\n\n"
        "| Zona | Precio |\n"
        "| no-separador | tampoco |\n"
        "| FILA-SEPARADOR-INVALIDO | 32,70 € |"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert all(item.metadata["chunk_strategy"] == "recursive_character" for item in chunks)


def test_tabla_sin_encabezado_se_trata_como_texto():
    """RF-5: una fila separadora no puede sustituir a la fila de encabezados."""
    contenido = (
        "TITULO SIN ENCABEZADO\n\n"
        "| :--- | :--- |\n"
        "| :--- | :--- |\n"
        "| FILA-SIN-ENCABEZADO | 32,70 € |"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert all(item.metadata["chunk_strategy"] == "recursive_character" for item in chunks)


def test_texto_alrededor_de_tabla_usa_fragmentacion_ordinaria():
    """RF-6: solo la tabla reconocida se marca como indivisible."""
    contenido = (
        "INTRODUCCION ORDINARIA\n\n"
        "TABLA CENTRAL\n\n"
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| FILA-CENTRAL | 32,70 € |\n\n"
        "CIERRE ORDINARIO"
    )

    chunks = chunk.fragmentar_documentos([_documento_markdown(contenido)])

    assert [item.metadata["chunk_strategy"] for item in chunks] == [
        "recursive_character",
        "tabla_markdown",
        "recursive_character",
    ]
    assert chunks[0].page_content == "INTRODUCCION ORDINARIA"
    assert chunks[2].page_content == "CIERRE ORDINARIO"


def test_documento_no_markdown_mantiene_estrategia_ordinaria():
    """RF-7: una fuente no Markdown no activa la detección de tablas."""
    contenido = (
        "TITULO PDF\n\n"
        "| Zona | Precio |\n"
        "| :--- | :--- |\n"
        "| FILA-DE-PDF | 32,70 € |"
    )
    documento = Document(page_content=contenido, metadata={"source": "data/tarifas.pdf"})

    chunks = chunk.fragmentar_documentos([documento])

    assert len(chunks) == 1
    assert chunks[0].metadata["chunk_strategy"] == "recursive_character"
    assert chunks[0].page_content == contenido


def test_bloque_csv_mantiene_estrategia_actual():
    """RF-7: los bloques de paradas CSV siguen siendo unidades finales."""
    documento = Document(
        page_content="Tipo de transporte: Metro\nZona tarifaria: A",
        metadata={"source": "data/Paradas CRTM.csv", "tipo": "paradas_crtm_bloque"},
    )

    chunks = chunk.fragmentar_documentos([documento])

    assert len(chunks) == 1
    assert chunks[0].page_content == documento.page_content
    assert chunks[0].metadata["chunk_strategy"] == "bloque_csv"
