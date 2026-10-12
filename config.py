import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Ingesta y chunking ---
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma"
COLLECTION_NAME = "madridrumbo_transporte"
QUERIES_DIR = BASE_DIR / "queries"

OUTPUT_DIR = BASE_DIR / "output"
CHUNKS_JSON = OUTPUT_DIR / "chunks.json"

MAX_FILAS_CSV = None  # : int | None = 40
CSV_PARADAS = "Paradas CRTM.csv"

EXTENSIONES_TEXTO = {".txt", ".md"}
EXTENSIONES_PDF = {".pdf"}
EXTENSIONES_CSV = {".csv"}

# --- Embeddings OpenAI/Gemini ---
EMBEDDING_PROVIDER = "gemini" # "openai" | "gemini"
if EMBEDDING_PROVIDER == "openai":
    EMBEDDING_MODEL = "text-embedding-3-small" 
elif EMBEDDING_PROVIDER == "gemini":
    EMBEDDING_MODEL = "gemini-embedding-2"

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

EMBED_BATCH_SIZE = 100
EMBEDDINGS_JSON = OUTPUT_DIR / "embeddings.json"
MAX_CHUNKS_EMBED: int | None = None  # None = todos; 50 puede dejar fuera FAQ/PDF

EMBED_RPM_LIMIT = 2000  # La cuota gratuita de gemini-embedding-2 es de 100 RPM en free tier y 3000 RPM en Tier 1.

# Configuración de las claves API utilizadas por los proveedores de embeddings.
# GEMINI_API_KEY permite utilizar Gemini desde las funciones de embeddings.


# --- Retrieval ---
TOP_K = 4
# Límite máximo de chunks que se pueden indexar en ChromaDB.
# Se establece un valor suficientemente alto para cubrir el corpus actual
# y evitar que documentos completos queden fuera de la indexación.


MAX_CHUNKS = 25000

# --- Generación (Gemini) ---
GENERATION_MODEL = "gemini-3.6-flash" # "gemini-3.1-flash-lite" | "gemini-3.6-flash"
TEMPERATURE = 0.0
