"""
retrieve.py — Recuperación de los top-k chunks más relevantes para una pregunta.
"""
import sys
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOP_K
from src.index import get_client, get_or_create_collection
from src.embed import embeddear_textos


@dataclass
class RetrievedChunk:
    text: str
    source: str
    chunk_id: int
    distance: float


def retrieve(query: str, k: int = TOP_K) -> list[RetrievedChunk]:
    """Recupera los k chunks más cercanos semánticamente a la pregunta."""
    client = get_client()
    collection = get_or_create_collection(client)

    if collection.count() == 0:
        raise RuntimeError(
            "El índice está vacío. Ejecuta primero: python main.py --index"
        )

    query_embedding = embeddear_textos([query])[0]
    results = collection.query(query_embeddings=[query_embedding], n_results=k)

    retrieved = []
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    dists = results["distances"][0]
    for text, meta, dist in zip(docs, metas, dists):
        retrieved.append(RetrievedChunk(
            text=text,
            source=meta.get("source", "desconocido"),
            chunk_id=meta.get("chunk_id", -1),
            distance=dist,
        ))
    return retrieved


def format_context(chunks: list[RetrievedChunk]) -> str:
    """Formatea los chunks recuperados en un bloque de contexto legible para el prompt."""
    parts = []
    for i, c in enumerate(chunks, start=1):
        parts.append(f"[Fragmento {i} | fuente: {c.source}]\n{c.text}")
    return "\n\n".join(parts)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Pregunta a buscar (solo retrieval, sin generación)")
    parser.add_argument("--k", type=int, default=TOP_K)
    args = parser.parse_args()

    chunks = retrieve(args.query, k=args.k)
    print(f"[retrieve] Top-{args.k} chunks para: {args.query!r}\n")
    for i, c in enumerate(chunks, start=1):
        print(f"#{i} | fuente={c.source} | distancia={c.distance:.4f}")
        print(c.text[:300].replace("\n", " "), "...\n")
