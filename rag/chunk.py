"""Fragmentación (chunking) de documentos"""

import re
from pathlib import Path

# Clase Document de langchain
from langchain_core.documents import Document
# Fragmentador de texto de LangChain.
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Importamos desde config.py los parámetros que controlan el chunking:
from config import CHUNK_OVERLAP, CHUNK_SIZE


def _crear_splitter() -> RecursiveCharacterTextSplitter:
    # Creamos y devolvemos el objeto encargado de fragmentar los textos.
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )


def _es_markdown(documento: Document) -> bool:
    """Indica si la fuente del documento corresponde a un archivo Markdown."""
    source = documento.metadata.get("source", "")
    return Path(str(source)).suffix.lower() == ".md"


def _celdas_de_fila_markdown(linea: str) -> list[str] | None:
    """Devuelve las celdas de una fila delimitada por barras, o ``None``."""
    fila = linea.strip()
    if not fila.startswith("|") or not fila.endswith("|"):
        return None

    return [celda.strip() for celda in fila[1:-1].split("|")]


def _es_fila_separadora_markdown(linea: str) -> bool:
    """Comprueba el formato Markdown de la fila que separa encabezado y datos."""
    celdas = _celdas_de_fila_markdown(linea)
    return bool(celdas) and all(
        re.fullmatch(r":?-{3,}:?", celda) for celda in celdas
    )


def _es_inicio_tabla_markdown(lineas: list[str], indice: int) -> bool:
    """Valida encabezado, separador y primera fila de contenido de una tabla."""
    if indice + 2 >= len(lineas):
        return False

    encabezados = _celdas_de_fila_markdown(lineas[indice])
    separador = _celdas_de_fila_markdown(lineas[indice + 1])
    primera_fila = _celdas_de_fila_markdown(lineas[indice + 2])

    return (
        bool(encabezados)
        and bool(separador)
        and len(encabezados) == len(separador)
        and not _es_fila_separadora_markdown(lineas[indice])
        and _es_fila_separadora_markdown(lineas[indice + 1])
        and primera_fila is not None
    )


def _fragmentar_markdown_con_tablas(
    documento: Document,
    splitter: RecursiveCharacterTextSplitter,
) -> list[Document]:
    """Separa las tablas Markdown válidas sin enviar sus filas al splitter."""
    lineas = documento.page_content.split("\n")
    chunks: list[Document] = []
    inicio_texto_ordinario = 0
    indice = 0

    while indice < len(lineas):
        if not _es_inicio_tabla_markdown(lineas, indice):
            indice += 1
            continue

        # El título es la última línea no vacía que precede inmediatamente a la tabla.
        indice_titulo = indice - 1
        while indice_titulo >= inicio_texto_ordinario and not lineas[indice_titulo].strip():
            indice_titulo -= 1
        if indice_titulo < inicio_texto_ordinario:
            indice += 1
            continue

        # La tabla abarca todas las filas consecutivas delimitadas por barras.
        fin_tabla = indice + 2
        while fin_tabla < len(lineas) and _celdas_de_fila_markdown(lineas[fin_tabla]) is not None:
            fin_tabla += 1

        texto_ordinario = "\n".join(lineas[inicio_texto_ordinario:indice_titulo])
        if texto_ordinario.strip():
            segmento = Document(
                page_content=texto_ordinario,
                metadata=dict(documento.metadata),
            )
            chunks.extend(splitter.split_documents([segmento]))

        # La tabla se añade directamente para que no se divida aunque exceda CHUNK_SIZE.
        metadata_tabla = dict(documento.metadata)
        metadata_tabla["chunk_strategy"] = "tabla_markdown"
        chunks.append(
            Document(
                page_content="\n".join(lineas[indice_titulo:fin_tabla]),
                metadata=metadata_tabla,
            )
        )

        inicio_texto_ordinario = fin_tabla
        indice = fin_tabla

    texto_restante = "\n".join(lineas[inicio_texto_ordinario:])
    if texto_restante.strip():
        segmento = Document(
            page_content=texto_restante,
            metadata=dict(documento.metadata),
        )
        chunks.extend(splitter.split_documents([segmento]))

    return chunks


def fragmentar_documentos(documentos: list[Document]) -> list[Document]:
    """Fragmenta los documentos según su tipo y añade metadata útil para depurar.

    Los documentos de paradas CRTM ya llegan agrupados desde load.py en bloques de hasta 6 paradas, por lo que se consideran chunks finales y no vuelven a pasar por el splitter.

    El resto de documentos se fragmenta mediante RecursiveCharacterTextSplitter.
    """
    # Si la lista recibida está vacía, devolvemos inmediatamente otra lista vacía. Esto evita crear el splitter y realizar operaciones innecesarias.
    if not documentos:
        return []
    # Creamos el fragmentador que utilizaremos para PDF, Markdown y otros documentos de texto. Los bloques de paradas CRTM no pasarán por este splitter porque ya se han construido como unidades finales durante la carga.
    splitter = _crear_splitter()
    
    chunks: list[Document] = []

    for documento in documentos:

        # Los bloques de paradas ya han sido construidos en load.py como unidades semánticas de hasta 6 paradas.No debemos volver a fragmentarlos.
        if documento.metadata.get("tipo") == "paradas_crtm_bloque":
            chunks.append(documento)
            continue

        # Las tablas Markdown válidas conservan título y filas en una única unidad.
        if _es_markdown(documento):
            chunks.extend(_fragmentar_markdown_con_tablas(documento, splitter))
            continue

        # El resto de documentos sí se fragmenta normalmente.
        chunks.extend(splitter.split_documents([documento]))

    # Creamos una nueva lista donde guardaremos los chunks después de añadirles metadatos adicionales.
    enriquecidos: list[Document] = []

    # Recorremos todos los chunks generados con un enumerate() para tener i: posición global del chunk dentro de la lista y chunk: objeto Document correspondiente.
    for i, chunk in enumerate(chunks):

        # Copiamos los metadatos del chunk en un nuevo diccionario para evitar modificar directamente el diccionario original.
        meta = dict(chunk.metadata)

        # Añadimos el índice global del chunk, útil para depuración, inspección y trazabilidad, ya que permite saber en qué posición quedó cada fragmento dentro del conjunto total de chunks.
        meta["chunk_index"] = i
        # Añadimos también el tamaño real del contenido del chunk (número de caracteres que contiene page_content)
        meta["chunk_size"] = len(chunk.page_content)
        # Añadimos un metadato sobre la estrategia de chunk seguida.
        if meta.get("chunk_strategy") == "tabla_markdown":
            meta["chunk_strategy"] = "tabla_markdown"
        elif meta.get("tipo") == "paradas_crtm_bloque":
            meta["chunk_strategy"] = "bloque_csv"
        else:
            meta["chunk_strategy"] = "recursive_character"
        # Creamos un nuevo Document conservando exactamente el mismo texto del chunk generado por el splitter, pero utilizando los metadatos enriquecidos con chunk_index y chunk_size.
        enriquecidos.append(
            Document(page_content=chunk.page_content, metadata=meta)
        )

    # Devolvemos la lista completa de chunks enriquecidos.
    return enriquecidos
