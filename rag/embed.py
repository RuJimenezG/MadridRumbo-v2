"""Generación de embeddings con OpenAI o Gemini.

Lee output/chunks.json, convierte cada chunk en un vector y guarda
output/embeddings.json. Expone embeddear_consulta() para el retriever.
"""

import json
import time
from pathlib import Path
# SKU de Google Gemini
from google import genai
from google.genai import types
from google.genai.errors import APIError
from config import (
    CHUNKS_JSON,
    EMBED_BATCH_SIZE,
    EMBEDDING_MODEL,
    EMBEDDINGS_JSON,
    MAX_CHUNKS_EMBED,
    EMBED_RPM_LIMIT,
    EMBEDDING_PROVIDER,
    OPENAI_API_KEY,
    GEMINI_API_KEY,
)

from .model_auth import configurar_gemini_api_key, configurar_openai_api_key

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# =====================================================================
# Dos proveedores soportados: "openai" y "gemini".
# =====================================================================

def _extraer_vector(embedding_obj) -> list[float]:
    # Dependiendo de cómo devuelva el SDK el embedding el vector puede venir almacenado en un atributo llamado "values". Si existe ese atributo, extraemos sus valores y los convertimos explícitamente en una lista de números float.
    if hasattr(embedding_obj, "values"):
        return list(embedding_obj.values)
    # Si el objeto ya es iterable directamente, lo convertimos igualmente en una lista. Esta segunda posibilidad hace que la función sea compatible con distintas representaciones del resultado.
    return list(embedding_obj)


def cargar_chunks_json() -> list[dict]:
    """Carga desde disco los chunks generados previamente por el pipeline de ingesta."""
    # Antes de intentar leer el archivo, comprobamos que exista.
    if not CHUNKS_JSON.exists():
        raise FileNotFoundError(
            f"No existe {CHUNKS_JSON}. Ejecuta antes: python main.py --prepare"
        )

    # Leemos todo el contenido de chunks.json como texto UTF-8 y json.loads() lo convierte a estructuras normales de Python (diccionarios, listas, strings, etc.).
    data = json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))
    # El pipeline guarda los chunks dentro de la clave "chunks". get("chunks", []) devuelve: la lista de chunks si existe o una lista vacía si la clave no está presente.
    return data.get("chunks", [])


def embeddear_textos(textos: list[str]) -> list[list[float]]:
    """Envía textos a Gemini en lotes y devuelve vectores en el mismo orden."""
    # Si no recibimos ningún texto, no es necesario llamar a Gemini.
    if not textos:
        return []
    # Aquí acumularemos todos los vectores generados. Cada elemento será una lista de float.
    vectores: list[list[float]] = []
    
    if EMBEDDING_PROVIDER == "gemini":
        return _embed_gemini(textos)
    elif EMBEDDING_PROVIDER == "openai":
            return _embed_openai(textos)
    else:
        raise ValueError(
            f"EMBEDDING_PROVIDER={EMBEDDING_PROVIDER!r} no soportado. "
            f"Usa 'openai' o 'gemini' en tu .env."
        )


def ejecutar_embeddings() -> tuple[list[dict], Path]:
    """chunks.json → vectores → embeddings.json."""   
    # Cargamos los chunks generados previamente durante la fase de preparación del corpus.
    chunks = cargar_chunks_json()
    # Guardamos el número total de chunks disponibles antes de aplicar cualquier límite.
    total_disponibles = len(chunks)
    # Si MAX_CHUNKS_EMBED tiene un valor configurado, reducimos el conjunto de chunks a procesar. Si es None, se procesan todos.
    if MAX_CHUNKS_EMBED is not None:
        chunks = chunks[:MAX_CHUNKS_EMBED]
    # Extraemos únicamente el texto de cada chunk.
    textos = [c["text"] for c in chunks]
    # Guardamos el instante justo antes de empezar la generación para poder medir cuánto tarda la operación completa.
    inicio = time.perf_counter()
    # Enviamos los textos a Gemini y obtenemos sus vectores.
    vectores = embeddear_textos(textos)
    # Calculamos el tiempo transcurrido. perf_counter() devuelve segundos, por eso multiplicamos por 1000 para expresarlo en milisegundos.
    latencia_ms = (time.perf_counter() - inicio) * 1000
    # Mostramos en consola:
    # - número de chunks procesados;
    # - tiempo empleado;
    # - modelo utilizado.
    print(
        f"Embeddings: {len(textos)} chunks en {latencia_ms:.0f} ms ({EMBEDDING_MODEL})"
    )
    # Si hemos procesado menos chunks de los que había originalmente, informamos de ello. Esto permite detectar fácilmente que MAX_CHUNKS_EMBED está limitando el procesamiento.
    if len(textos) < total_disponibles:
        print(f"  (de {total_disponibles} en {CHUNKS_JSON.name}; ver MAX_CHUNKS_EMBED)")
    # Construiremos una lista que relacione cada chunk original con su embedding correspondiente.
    items = []
    # zip() empareja cada chunk con su vector. Esto funciona correctamente porque embeddear_textos() conserva el orden de entrada.
    for chunk, vector in zip(chunks, vectores):
        # Para cada elemento conservamos:
        # - el texto original;
        # - su embedding;
        # - los metadatos del chunk.
        items.append(
            {
                "text": chunk["text"],
                "vector": vector,
                "metadata": chunk.get("metadata", {}),
            }
        )

    # Construimos la estructura completa que se guardará en embeddings.json.
    payload = {
        "embedding_model": EMBEDDING_MODEL,
        "total": len(items),
        "total_chunks_en_origen": total_disponibles,
        "dimensions": len(vectores[0]) if vectores else 0,
        # Lista con los textos, vectores y metadatos.
        "items": items,
    }

    # Nos aseguramos de que exista el directorio donde debe guardarse embeddings.json.
    # parents=True: crea también los directorios superiores necesarios.
    # exist_ok=True: no produce error si el directorio ya existe.
    EMBEDDINGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    # Serializamos el payload como JSON y lo escribimos en disco.
    EMBEDDINGS_JSON.write_text(
        json.dumps(
            # Estructura Python que queremos convertir a JSON.
            payload,
            # Conserva directamente caracteres como ñ, á, é, etc. en lugar de convertirlos a secuencias Unicode.
            ensure_ascii=False,
            # Añade sangría para que el archivo resulte legible.
            indent=2,
        ),
        # Guardamos el fichero utilizando codificación UTF-8.
        encoding="utf-8",
    )

    # Informamos por consola de:
    # - dónde se ha guardado el archivo;
    # - cuántas dimensiones tiene cada embedding.
    print(f"  Guardado: {EMBEDDINGS_JSON} ({payload['dimensions']} dimensiones)")
    # Devolvemos:
    # 1. La lista de elementos con texto, embedding y metadata.
    # 2. La ruta del archivo embeddings.json generado.
    return items, EMBEDDINGS_JSON


def _embed_gemini(texts: list[str]) -> list[list[float]]:
    """
    Gemini para embedear_textos() (arquitectura ChromaDB), en lotes, respetando
    EMBED_RPM_LIMIT.
    """
    configurar_gemini_api_key()

    client = genai.Client(api_key=GEMINI_API_KEY)
    vectores: list[list[float]] = []

    for inicio in range(0, len(texts), EMBED_BATCH_SIZE):
        lote = texts[inicio: inicio + EMBED_BATCH_SIZE]
        contents = [types.Content(parts=[types.Part(text=t)]) for t in lote]

        for intento in range(3):
            try:
                result = client.models.embed_content(model=EMBEDDING_MODEL, contents=contents)
                break
            except APIError as e:
                if getattr(e, "code", None) == 429:
                    if "PerDay" in str(e):
                        print("   [embed] límite DIARIO alcanzado, parando (reintentar no sirve).")
                        raise
                    if intento < 2:
                        print(f"   [embed] límite por minuto, esperando 60s (lote {inicio}-{inicio + len(lote)})...")
                        time.sleep(60)
                        continue
                raise

        vectores.extend(_extraer_vector(emb) for emb in result.embeddings)
        if inicio + EMBED_BATCH_SIZE < len(texts):
            time.sleep(60 * len(lote) / EMBED_RPM_LIMIT)

    return vectores


def _embed_openai(texts: list[str]) -> list[list[float]]:
    configurar_openai_api_key()
    import openai
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    vectores: list[list[float]] = []
    for inicio in range(0, len(texts), EMBED_BATCH_SIZE):
        lote = texts[inicio: inicio + EMBED_BATCH_SIZE]
        resp = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=lote
        )
        vectores.extend(_extraer_vector(d.embedding) for d in resp.data)
    return vectores

if __name__ == "__main__":
    vecs = embeddear_textos(["¿Cuánto cuesta el Abono Joven?", "Zonas tarifarias de Madrid"])
    print(f"Generados {len(vecs)} vectores de dimensión {len(vecs[0])}")
