"""Fragmentación (chunking) de documentos"""

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

        # El resto de documentos sí se fragmenta normalmente.
        chunks.extend(
            splitter.split_documents([documento])
        )    

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
        if meta.get("tipo") == "paradas_crtm_bloque":
            meta["chunk_strategy"] = "bloque_csv"
        else:
            meta["chunk_strategy"] = "recursive_character"
        # Creamos un nuevo Document conservando exactamente el mismo texto del chunk generado por el splitter, pero utilizando los metadatos enriquecidos con chunk_index y chunk_size.
        enriquecidos.append(
            Document(page_content=chunk.page_content, metadata=meta)
        )

    # Devolvemos la lista completa de chunks enriquecidos.
    return enriquecidos
