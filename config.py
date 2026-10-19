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

MAX_FILAS_CSV = 40  # : int | None
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

EMBED_RPM_LIMIT = 80 # 2000  # La cuota gratuita de gemini-embedding-2 es de 100 RPM en free tier y 3000 RPM en Tier 1.

# Configuración de las claves API utilizadas por los proveedores de embeddings.
# GEMINI_API_KEY permite utilizar Gemini desde las funciones de embeddings.


# --- Retrieval ---
TOP_K = 4
# Límite máximo de chunks que se pueden indexar en ChromaDB.
# Se establece un valor suficientemente alto para cubrir el corpus actual
# y evitar que documentos completos queden fuera de la indexación.


MAX_CHUNKS = 25000

# --- Generación (Gemini) ---
GENERATION_MODEL = "gemini-3.5-flash-lite" # "gemini-3.5-flash-lite" | "gemini-3.6-flash"
TEMPERATURE = 0.0


# --- Tools auxiliares y especialistas (PB2) ---
# Zona horaria que usa la tool hora_actual.
ZONA_HORARIA = "Europe/Madrid"

# Tope de llamadas a tools por turno de un especialista (límite decidido en Python).
MAX_STEPS_ESPECIALISTA = 3

# Allowlist de tools que puede pedir cada especialista.
TOOLS_POR_ESPECIALISTA = {
    "horarios": ["hora_actual", "rag_ask"],
    "tarifas": ["describir_imagen", "calculadora", "rag_ask"],
}

# --- Tool multimodal describir_imagen ---
# Carpeta autorizada: la tool no lee imágenes fuera de ella.
IMAGENES_DIR = BASE_DIR / "assets"
# Imagen que se usa cuando no se indica ruta (nombre relativo a IMAGENES_DIR).
IMAGEN_DEMO = "imagen_demo.jpg"
IMAGEN_MAX_MB = 4
EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png"}
# Modelo propio de la tool de imagen: gemini-3.6-flash (GENERATION_MODEL) devolvió 503 por demanda alta en las pruebas.
MODELO_VISION = "gemini-3.8-flash"

# --- Tool calculadora ---
CALC_MAX_CARACTERES = 200

# --- Clientes CLI y Streamlit (spec 005) ---
# Pedidos fijos de `python main.py --demo`: horarios, tarifas con imagen y fuera de corpus.
PEDIDOS_DEMO = (
    "¿Hasta qué hora hay metro hoy?",
    "Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?",
    "¿Cuál es la capital de Francia?",
)

# Respuestas reconocidas en el chat (se comparan en minúsculas y sin espacios sobrantes).
PALABRAS_SALIR = {"salir", "exit", "quit"}
PALABRAS_APROBAR = {"s", "si", "sí", "a", "aprobar"}
PALABRAS_RECHAZAR = {"n", "no", "r", "rechazar"}

# Variable de entorno que activa el grafo simulado y valor que lo activa.
VARIABLE_MODO_SIMULADO = "MADRIDRUMBO_GRAFO"
VALOR_MODO_SIMULADO = "falso"

# Módulo del grafo real que usan los clientes (debe exponer procesar_turno y aprobar_plan).
MODULO_GRAFO_REAL = "src.agent"
