"""Tool multimodal: lee una imagen (p. ej. un cartel de tarifas) y devuelve su contenido en texto."""
import os
from pathlib import Path

import config

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

    try:
        texto = (cliente or ClienteGemini()).generar(archivo.read_bytes(), MIMES[sufijo], prompt)
    except Exception:  # red, cuota, clave ausente...
        return "ERROR: el modelo no pudo describir la imagen"
    if not texto or not texto.strip():
        return "ERROR: el modelo no pudo describir la imagen"
    return texto.strip()
