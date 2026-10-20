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
# Espera (en segundos) antes del único reintento de describir_imagen ante un error temporal del modelo.
IMAGEN_REINTENTO_ESPERA_S = 2.0

# --- Tool calculadora ---
CALC_MAX_CARACTERES = 200

# --- Clientes CLI y Streamlit (spec 008) ---
# Pedidos fijos de `python main.py --demo`: horarios, ruta (la única que pausa para HITL) y fuera de corpus.
PEDIDOS_DEMO = (
    "¿Hasta qué hora hay metro hoy?",
    "¿Cómo puedo ir desde la Puerta del Sol hasta la Estación de Atocha?",
    "¿Cuál es la capital de Francia?",
)

# Entradas técnicas del supervisor en el log del grafo: el CLI las muestra y la web las oculta.
PREFIJOS_DIAGNOSTICO_SUPERVISOR = (
    "Supervisor: categoria=",
    "Supervisor: correccion_semantica=",
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
# Caja aproximada de la Comunidad de Madrid; en los bordes puede incluir algún trozo de provincias vecinas.
# Comprobada en T16 (2026-10-16) con Nominatim real: Sol, Bernabéu y Segovia-Guiomar dentro; Barcelona y Toledo fuera.
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
# Verificado en T16 (2026-10-16) con respuestas reales: con esta máscara llegan los tramos y, con arrivalTime,
# también stopDetails.departureTime del primer tramo de transporte (transitDetails va entero). No se ajusta.
# La facturación puede depender de los campos pedidos: se revisa en la consola de Google.
GOOGLE_FIELD_MASK = (
    "routes.duration,routes.legs.steps.travelMode,"
    "routes.legs.steps.staticDuration,routes.legs.steps.transitDetails"
)
# Modos de la red CRTM que se piden: metro, metro ligero/tranvía, autobús y Cercanías.
MODOS_GOOGLE = ["SUBWAY", "LIGHT_RAIL", "BUS", "TRAIN"]
# Tipos de vehículo de cada tramo que se aceptan al verificar la respuesta.
# Vistos en T16: SUBWAY (metro) y HEAVY_RAIL (Cercanías C4b/C10 y también Renfe Avant). Google NO distingue Cercanías
# de Avant por tipo de vehículo: se acepta HEAVY_RAIL, por lo que la media distancia (Avant) también se admite.
# Limitación conocida (RF-12). Sin comprobar: TRAM, LIGHT_RAIL, BUS, TROLLEYBUS, COMMUTER_TRAIN, METRO_RAIL y RAIL.
TIPOS_VEHICULO_ACEPTADOS = {
    "SUBWAY", "METRO_RAIL", "TRAM", "BUS", "TROLLEYBUS", "COMMUTER_TRAIN", "HEAVY_RAIL", "RAIL",
}

# --- Alternativa en bici con BiciMAD (spec 009) ---
# Regla de oferta (RF-2): distancia en línea recta entre origen y destino, radio máximo a una estación y mínimos.
BICI_DISTANCIA_MIN_M = 1000
BICI_DISTANCIA_MAX_M = 6000
BICI_ESTACION_RADIO_MAX_M = 500
BICI_MIN_BICIS = 1
BICI_MIN_HUECOS = 1

# API de la EMT (rutas y campos verificados en T1, 2026-10-20). Las credenciales solo se leen del entorno.
EMT_LOGIN_URL = "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/"
EMT_ESTACIONES_URL = "https://openapi.emtmadrid.es/v1/transport/bicimad/stations/"
EMT_TIMEOUT_S = 10
EMT_CLIENT_ID = os.getenv("EMT_CLIENT_ID")
EMT_PASS_KEY = os.getenv("EMT_PASS_KEY")

# Google Routes para los tramos en bici y a pie: duración, distancia y avisos (el aviso de beta, RF-12) (la facturación depende de los campos).
GOOGLE_FIELD_MASK_BICI = "routes.duration,routes.distanceMeters,routes.warnings"
# Texto de respaldo del aviso de beta que exige Google para rutas a pie y en bici (RF-12).
BICI_AVISO_GOOGLE = ("Las rutas a pie y en bici están en fase beta y pueden carecer de aceras, caminos peatonales "
                     "o carriles bici claros.")

# Hora de salida pedida: antelación máxima en días (valor provisional).
ANTELACION_MAX_DIAS = 7

# Título de transporte que se aplica si no se indica ninguno. Cualquier otro título es texto libre
# (no hay lista cerrada): el RAG es la fuente y se abstiene si no lo conoce.
TITULO_POR_DEFECTO = "billete sencillo"
# Longitud máxima (caracteres, ya sin saltos de línea) de un título para interpretarlo y preguntarlo al RAG.
TITULO_LONGITUD_MAX = 60
# Longitud máxima (caracteres, ya sin saltos de línea) del texto de zona del RAG que se pasa entero a la pregunta de
# precio. Distinta de TITULO_LONGITUD_MAX. Nunca se corta: si lo supera, no se consulta el precio.
# A COMPROBAR en T17 con el RAG real: el valor 200 y si pasar la frase entera empeora la respuesta del precio.
ZONA_LONGITUD_MAX = 200

# Preguntas al RAG, construidas con datos de la ruta (paradas o municipios).
PREGUNTA_ZONA = "¿Qué zona tarifaria corresponde a un trayecto entre {origen} y {destino}?"
# El precio se pregunta con la zona que devolvió el RAG (los abonos se pagan por zona, no por trayecto).
# Importante: no debe contener "zona tarifaria", fragmento con el que los dobles de test identifican la pregunta de zona.
PREGUNTA_PRECIO = "¿Cuál es el precio del {titulo} en la zona indicada a continuación? {zona}"
# Frase con la que el RAG se abstiene (definida en rag/prompt.py; un test vigila que coincida).
FRASE_ABSTENCION = "No lo sé, no está en los documentos."
