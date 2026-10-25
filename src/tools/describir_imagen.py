"""Tool multimodal: lee una imagen (p. ej. un cartel de tarifas) y devuelve su contenido en texto."""
import logging
import os
import time
from pathlib import Path

import config

registro = logging.getLogger(__name__)

# Códigos de error del servicio que se arreglan esperando: límite de peticiones y fallos del servidor.
CODIGOS_TEMPORALES = {429, 500, 502, 503, 504}
ERROR_DEL_MODELO = "ERROR: el modelo no pudo describir la imagen"

MIMES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

INSTRUCCION_BASE = (
    "Eres un asistente de transporte público de Madrid. Transcribe en español el texto y las "
    "cifras que se ven en la imagen (precios, zonas, horarios, nombres). Describe solo lo visible: "
    "no inventes ni completes datos. Si no hay texto legible, responde exactamente: "
    "No hay texto legible en la imagen."
)


class ClienteGemini:
    """Cliente real de visión. Se crea solo si no se inyecta otro (los tests inyectan uno falso)."""

    def generar(self, imagen_bytes: bytes, mime: str, prompt: str) -> str:
        # no se carga google.genai ni se pide la clave hasta usar la tool.
        from google import genai
        from google.genai import types

        from model_auth import configurar_gemini_api_key

        configurar_gemini_api_key()
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        respuesta = client.models.generate_content(
            model=config.MODELO_VISION,
            contents=[types.Part.from_bytes(data=imagen_bytes, mime_type=mime), prompt],
            config=types.GenerateContentConfig(temperature=config.TEMPERATURE),
        )
        return respuesta.text or ""


def describir_imagen(ruta: str | None = None, pregunta: str | None = None, cliente=None) -> str:
    """Devuelve el contenido visible de una imagen de la carpeta autorizada.

    `ruta` es relativa a `config.IMAGENES_DIR`; sin ruta se usa la imagen demo.
    `cliente` solo se inyecta en tests. Nunca lanza excepciones: los fallos
    devuelven un texto que empieza por "ERROR:".
    """
    base = Path(config.IMAGENES_DIR).resolve()
    ruta = ruta or config.IMAGEN_DEMO
    # Un nombre absoluto sustituye a `base` en la unión, pero el resolve() posterior lo detecta.
    archivo = (base / ruta).resolve()

    # Solo se leen archivos dentro de la carpeta autorizada (evita rutas como ../.env).
    if archivo != base and base not in archivo.parents:
        return "ERROR: ruta no permitida"
    if not archivo.is_file():
        return f"ERROR: la imagen no existe: {ruta}"
    sufijo = archivo.suffix.lower()
    if sufijo not in config.EXTENSIONES_IMAGEN or sufijo not in MIMES:
        return f"ERROR: formato no admitido ({sufijo or 'sin extensión'})"
    if archivo.stat().st_size > config.IMAGEN_MAX_MB * 1024 * 1024:
        return f"ERROR: imagen demasiado grande (límite {config.IMAGEN_MAX_MB} MB)"

    prompt = INSTRUCCION_BASE
    if pregunta:
        prompt += f"\nCéntrate en esta pregunta: {pregunta}"

    texto = _generar_con_un_reintento(cliente or ClienteGemini(), archivo.read_bytes(), MIMES[sufijo], prompt)
    if not texto or not texto.strip():
        return ERROR_DEL_MODELO
    return texto.strip()


def _es_error_temporal(error: Exception) -> bool:
    """True si esperar puede arreglarlo: límite de peticiones, fallo del servidor o fallo de red.

    Se clasifica por el atributo `code` y no por la clase, que puede variar entre versiones de la librería.
    """
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    return getattr(error, "code", None) in CODIGOS_TEMPORALES


def _registrar_causa(error: Exception, intento: int) -> None:
    """Deja en el registro de qué fallo se trata, sin el mensaje completo, la clave ni la imagen."""
    registro.warning(
        "describir_imagen falló (intento %d): tipo=%s código=%s estado=%s",
        intento,
        type(error).__name__,
        getattr(error, "code", None),
        getattr(error, "status", None),
    )


def _generar_con_un_reintento(cliente, imagen_bytes: bytes, mime: str, prompt: str) -> str | None:
    """Llama al modelo; ante un error temporal espera y reintenta una sola vez.

    Devuelve el texto, o None si el modelo falla (la causa queda en el registro).
    """
    for intento in (1, 2):
        try:
            return cliente.generar(imagen_bytes, mime, prompt)
        except Exception as error:  # red, cuota, clave ausente...
            _registrar_causa(error, intento)
            if intento == 2 or not _es_error_temporal(error):
                return None
            time.sleep(config.IMAGEN_REINTENTO_ESPERA_S)
    return None
