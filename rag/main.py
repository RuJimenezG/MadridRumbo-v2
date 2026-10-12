"""Punto de entrada por línea de comandos de MadridRumbo.

Uso:
  python main.py --prepare              -> carga, limpia y fragmenta el corpus (chunks.json)
  python main.py --index                -> (re)indexa el corpus en ChromaDB (offline)
  python main.py --index --recreate-index  -> borra y recrea la colección desde cero
  python main.py --query "..."          -> solo retrieval (sin LLM), muestra el contexto
  python main.py --ask "..."            -> RAG completo: retrieval + generación (Gemini)
  python main.py --ask "..." --k 6

Los comandos disponibles permiten preparar el corpus, indexarlo en
ChromaDB, consultar el contexto recuperado y ejecutar el flujo RAG
completo. --prepare prepara el corpus y genera los embeddings,
--index almacena los chunks en ChromaDB, --query permite comprobar
el retrieval y --ask ejecuta la generación de respuestas.
"""
import argparse

import json
from langchain_core.documents import Document
from config import CHUNKS_JSON

from src.pipeline import ejecutar_ingesta
from src.embed import ejecutar_embeddings
from src.index import index_chunks
from src.retrieve import retrieve, format_context
# El módulo de generación se importa únicamente cuando se ejecuta --ask.
# De esta forma, los comandos --prepare, --index y --query pueden
# utilizarse sin necesidad de inicializar el cliente de Gemini.


def _cmd_prepare() -> None:
    """Ingesta (load->clean->chunk->chunks.json) + pipeline de embeddings.json de Gemini."""
    ejecutar_ingesta()
    print()
    ejecutar_embeddings()

def cargar_chunks_json() -> list[Document]:
    """Carga los chunks guardados en output/chunks.json como Documents."""
    data = json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))

    return [
        Document(
            page_content=chunk["text"],
            metadata=chunk["metadata"],
        )
        for chunk in data["chunks"]
    ]

def _cmd_index(recreate: bool) -> None:
    """Indexa los chunks guardados o ejecuta la ingesta si no existe el JSON."""
    if CHUNKS_JSON.exists():
        print(f"[main] Cargando chunks desde {CHUNKS_JSON} ...")
        chunks = cargar_chunks_json()
    else:
        print("[main] No existe chunks.json. Ejecutando ingesta...")
        chunks, _, _ = ejecutar_ingesta()

    print()
    n = index_chunks(chunks, recreate=recreate)
    print(f"[main] Indexados {n} chunks en ChromaDB.")


def _cmd_query(pregunta: str, k: int) -> None:
    """Solo retrieval: muestra el contexto recuperado, sin llamar al LLM."""
    chunks = retrieve(pregunta, k=k)
    print(f"\nPREGUNTA: {pregunta}")
    print(f"\n--- CONTEXTO RECUPERADO (top-{k}) ---\n")
    print(format_context(chunks))
    print("\nFUENTES:", sorted({c.source for c in chunks}))


def _cmd_ask(pregunta: str, k: int) -> None:
    """RAG completo: retrieval (ChromaDB) + generación (Gemini), con abstención si no hay evidencia."""
    from src.responder import responder
    resultado = responder(pregunta, k=k)
    print(f"\nPREGUNTA: {pregunta}\n")
    print(f"RESPUESTA:\n{resultado['respuesta']}\n")
    print("FUENTES:", resultado["fuentes"])


def main() -> None:
    """Ejecuta el comando solicitado desde la línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="MadridRumbo",
        description="Asistente RAG sobre transporte público de Madrid.",
    )
    parser.add_argument("--prepare", action="store_true", help="Ingesta + embeddings.json (Gemini)")
    parser.add_argument("--index", action="store_true", help="Indexa el corpus en ChromaDB (offline)")
    parser.add_argument("--recreate-index", action="store_true", help="Borra y recrea la colección al indexar")
    parser.add_argument("--query", type=str, help="Solo retrieval: muestra el contexto recuperado")
    parser.add_argument("--ask", type=str, help="RAG completo: retrieval + generación")
    parser.add_argument("--k", type=int, default=4, help="Número de chunks a recuperar (default=4)")

    args = parser.parse_args()

    if not any([args.prepare, args.index, args.query, args.ask]):
        parser.print_help()
        return

    if args.prepare:
        _cmd_prepare()

    if args.index:
        _cmd_index(recreate=args.recreate_index)

    if args.query:
        _cmd_query(args.query, k=args.k)

    if args.ask:
        _cmd_ask(args.ask, k=args.k)


if __name__ == "__main__":
    main()
