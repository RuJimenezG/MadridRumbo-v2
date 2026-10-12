"""
index.py — Indexación de chunks en ChromaDB persistente.

index_chunks() trabaja directamente con Document:
  - doc.page_content -> texto del chunk
  - doc.metadata["source"]        -> fuente (rellenada por src/load.py)
  - doc.metadata["chunk_index"]   -> índice (rellenado por src/chunk.py)

Durante la indexación, ChoromaDB almacena los embeddings junto con los 
metadatos "source" y "chunk_id", permitiendo identificar la procedencia de
los chunks recuperados.

Los embeddings previamente calculados pueden reutilizarse desde
el fichero JSON configurado, evitando llamadas innecesarias a la
API durante nuevas indexaciones. Si no existe un fichero válido,
los embeddings se calculan nuevamente.

La opción --recreate-index permite eliminar y regenerar la colección
completa cuando cambian el modelo de embeddings, MAX_CHUNKS o el corpus.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import chromadb
from langchain_core.documents import Document
from config import CHROMA_DIR, COLLECTION_NAME, MAX_CHUNKS
from src.embed import embeddear_textos

import json
from config import EMBEDDINGS_JSON, EMBEDDING_MODEL

#Reutiliza embeddings ya calculados en output/ (JSON) en vez de volver a llamar a la API cada vez que se indexa.
#Solo se usa si el JSON existe, es del proveedor activo (EMBEDDING_PROVIDER)
#y tiene el mismo número de chunks que el corpus actual. Si algo no cuadra
#(corpus cambiado, otro modelo, provider distinto), se ignora y se calcula
#en vivo como hasta ahora. No cambia nada para quien no tenga ese JSON.

def _cargar_embeddings_json(texts) -> list[list[float]] | None:
    modelo = EMBEDDING_MODEL
    ruta = EMBEDDINGS_JSON

    if not ruta.exists():
        return None  # no hay JSON para este proveedor, seguir como antes

    with open(ruta, encoding="utf-8") as f:
        data = json.load(f)
    if (data.get("embedding_model") != modelo) or (len(data["items"]) != len(texts)):
        return None  # JSON no coincide con la config/corpus actual, no fiable
    return [item["vector"] for item in data["items"]]

def get_client():
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_or_create_collection(client, recreate: bool = False):
    if recreate:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"[index] Colección '{COLLECTION_NAME}' eliminada.")
        except Exception as e:
            print(f"[index] No se pudo eliminar la colección: {e}")
            raise
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={
            "hnsw": {
                "batch_size": 500,
                "sync_threshold": 20000,
            }
        },
    )


def _nombre_fuente(metadata: dict) -> str:
    """Extrae solo el nombre de fichero de metadata['source'] (puede venir con ruta completa)."""
    source = metadata.get("source", "desconocido")
    return Path(str(source)).name


def index_chunks(chunks: list[Document], recreate: bool = False) -> int:
    """Indexa una lista de Document (de src/chunk.py) en ChromaDB. Devuelve el número de chunks indexados."""
    if len(chunks) > MAX_CHUNKS:
        from collections import Counter
        perdidos = Counter(_nombre_fuente(c.metadata) for c in chunks[MAX_CHUNKS:])
        print(
            f"[index] AVISO: {len(chunks)} chunks superan MAX_CHUNKS={MAX_CHUNKS}. "
            f"Se van a DESCARTAR {len(chunks) - MAX_CHUNKS} chunks, de estas fuentes: "
            f"{dict(perdidos)}. Sube MAX_CHUNKS en config.py/.env si no quieres perder "
            f"contenido de estos documentos, o revisa con el equipo si ese corpus (p. ej. "
            f"un CSV muy grande) necesita filtrarse/agregarse antes de indexar."
        )
        chunks = chunks[:MAX_CHUNKS]

    client = get_client()
    collection = get_or_create_collection(client, recreate=recreate)

    ids = [f"{_nombre_fuente(c.metadata)}::{c.metadata.get('chunk_index', i)}" for i, c in enumerate(chunks)]
    texts = [c.page_content for c in chunks]
    metadatas = [
        {"source": _nombre_fuente(c.metadata), "chunk_id": c.metadata.get("chunk_index", i)}
        for i, c in enumerate(chunks)
    ]

    # AÑADIDO (Guzmán): usa el JSON precalculado si sirve; si no, calcula
    # los embeddings como siempre. Ahorra llamadas a la API al reindexar.
    embeddings = _cargar_embeddings_json(texts)
    if embeddings is None:
        print("No hay fichero local de embeddings.json o devuelve None")
        print(f"VARIABLE ---> {EMBEDDINGS_JSON}")
        embeddings = embeddear_textos(texts)

    # Indexar por lotes para evitar problemas de memoria en corpus grandes.
    batch_size = 64
    for i in range(0, len(ids), batch_size):
        collection.upsert(
            ids=ids[i:i + batch_size],
            documents=texts[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
            embeddings=embeddings[i:i + batch_size],
        )
        
    print("\n[index] Upserts terminados.")
    print(f"[index] Verificando colección...")

    count = collection.count()

    print(f"[index] Chroma confirma {count} registros.")

    resultado = collection.query(
        query_embeddings=[embeddings[0]],
        n_results=3,
    )

    print("[index] Query de comprobación OK.")
    print(f"[index] IDs recuperados: {resultado['ids']}")
    print(f"IDs totales: {len(ids)}")
    print(f"IDs únicos: {len(set(ids))}")
    print(f"Chunks recibidos: {len(chunks)}")
    print(f"IDs generados: {len(ids)}")
    print(f"IDs únicos: {len(set(ids))}")
    print(f"Embeddings: {len(embeddings)}")
    return len(ids)
    

if __name__ == "__main__":
    import argparse
    from src.pipeline import ejecutar_ingesta

    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate-index", action="store_true", help="Borra y recrea la colección desde cero")
    args = parser.parse_args()

    chunks, _, _ = ejecutar_ingesta()
    n = index_chunks(chunks, recreate=args.recreate_index)
    print(f"[index] Indexados {n} chunks en la colección '{COLLECTION_NAME}'.")
