"""
responder.py — Une retrieve() + generate() en una única función reutilizable,
sin depender de si la usa el CLI o Streamlit.
"""
import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TOP_K, GENERATION_MODEL
from src.retrieve import retrieve, format_context
from src.generate import generate

logging.basicConfig(
    filename="rag.log",
    level=logging.INFO,
    format="%(asctime)s | %(message)s",
)


def responder(pregunta: str, k: int = TOP_K) -> dict:
    """Responde una pregunta usando el corpus. Devuelve texto + fuentes usadas."""
    inicio = time.time()
    chunks = retrieve(pregunta, k=k)
    respuesta = generate(pregunta, chunks)
    tiempo = round(time.time() - inicio, 2)
    fuentes = sorted(set(c.source for c in chunks))
    contexto = format_context(chunks)

    logging.info(
        f"pregunta='{pregunta}' | k={k} | chunks={len(chunks)} | "
        f"tiempo={tiempo}s | modelo={GENERATION_MODEL}"
    )

    return {
        "pregunta": pregunta,
        "respuesta": respuesta,
        "fuentes": fuentes,
        "k": k,
        "num_chunks": len(chunks),
        "tiempo": tiempo,
        "contexto": contexto,
    }


def rag_ask(consulta: str) -> str:
    """Versión simplificada para el futuro proyecto de Agentes: solo el texto."""
    return responder(consulta)["respuesta"]