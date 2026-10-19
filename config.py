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

MAX_FILAS_CSV = None  # : int | None
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
GENERATION_MODEL = "gemini-3.5-flash-lite" # "gemini-3.5-flash-lite" | "gemini-3.6-flash"
TEMPERATURE = 0.0


# --- Tools auxiliares y especialistas (PB2) ---
# Zona horaria que usa la tool hora_actual.
ZONA_HORARIA = "Europe/Madrid"

# Tope de llamadas a tools por turno de un especialista (límite decidido en Python).
MAX_STEPS_ESPECIALISTA = 3

# Límites transversales del grafo multiagente por conversación y turno lógico.
MAX_TURNOS_CONVERSACION = 10
MAX_CICLOS_TOOLS = 8

# Allowlist de tools que puede pedir cada especialista.
TOOLS_POR_ESPECIALISTA = {
    "rag": ["rag_ask"],
    "horarios": ["hora_actual", "rag_ask"],
    "auxiliar": ["hora_actual", "calculadora"],
    # El RAG no se expone al especialista de rutas: lo llama la propia tool (spec 004, RF-19).
    "rutas": ["planificar_ruta"],
    "tarifas": ["describir_imagen"],
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

# --- Tool planificar_ruta (spec 004) ---
# Ámbito de cobertura (territorio del corpus CRTM) como (lat_min, lon_min, lat_max, lon_max).
# A VERIFICAR sobre el mapa: caja aproximada de la Comunidad de Madrid; en los bordes
# puede incluir algún trozo de provincias vecinas.
AMBITO_COBERTURA = (39.88, -4.58, 41.17, -3.05)

# Geocodificación con Nominatim (política de uso: 1 petición/s e identificación de la app).
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_PAIS = "es"
NOMINATIM_LIMIT = 10
NOMINATIM_TIMEOUT_S = 10
NOMINATIM_INTERVALO_S = 1.0
# El contacto se lee del .env (NOMINATIM_CONTACTO); nunca se escribe en el código.
_NOMINATIM_CONTACTO = os.getenv("NOMINATIM_CONTACTO")
NOMINATIM_USER_AGENT = "MadridRumbo/1.0" + (f" ({_NOMINATIM_CONTACTO})" if _NOMINATIM_CONTACTO else "")

# Candidatos mostrados al pedir una aclaración y radio (m) bajo el cual dos puntos son el mismo lugar.
MAX_CANDIDATOS_MOSTRAR = 3
RADIO_MISMA_UBICACION_M = 100

# Google Routes. La clave solo se lee del entorno.
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_ROUTES_API_KEY = os.getenv("GOOGLE_ROUTES_API_KEY")
GOOGLE_TIMEOUT_S = 10
# A VERIFICAR con una respuesta real; la facturación puede depender de los campos pedidos.
GOOGLE_FIELD_MASK = (
    "routes.duration,routes.legs.steps.travelMode,"
    "routes.legs.steps.staticDuration,routes.legs.steps.transitDetails"
)
# Modos de la red CRTM que se piden: metro, metro ligero/tranvía, autobús y Cercanías.
MODOS_GOOGLE = ["SUBWAY", "LIGHT_RAIL", "BUS", "TRAIN"]
# Tipos de vehículo de cada tramo que se aceptan al verificar la respuesta.
# A VERIFICAR con una respuesta real: los trenes de larga distancia y alta velocidad quedan excluidos.
TIPOS_VEHICULO_ACEPTADOS = {
    "SUBWAY", "METRO_RAIL", "TRAM", "BUS", "TROLLEYBUS", "COMMUTER_TRAIN", "HEAVY_RAIL", "RAIL",
}

# Hora de salida pedida: antelación máxima en días (valor provisional).
ANTELACION_MAX_DIAS = 7

# Títulos de transporte admitidos (lista cerrada) y el que se aplica si no se indica ninguno.
TITULOS_TRANSPORTE = ("billete sencillo", "billete de 10 viajes")
TITULO_POR_DEFECTO = "billete sencillo"

# Preguntas al RAG, construidas con datos de la ruta (paradas o municipios).
PREGUNTA_ZONA = "¿Qué zona tarifaria corresponde a un trayecto entre {origen} y {destino}?"
PREGUNTA_PRECIO = "¿Cuál es el precio del {titulo} para un trayecto entre {origen} y {destino}?"
# Frase con la que el RAG se abstiene (definida en rag/prompt.py; un test vigila que coincida).
FRASE_ABSTENCION = "No lo sé, no está en los documentos."
