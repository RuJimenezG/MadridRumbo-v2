"""Reglas deterministas del supervisor: fallback por palabras clave cuando el LLM falla."""
import re
import unicodedata

# Términos que indican una pregunta de horarios (se comparan sin acentos ni mayúsculas).
PALABRAS_HORARIOS = {
    "hora", "horario", "ahora", "hoy", "noche",
    "ultima", "primera", "abre", "cierra", "frecuencia",
}


def _normalizar(texto: str) -> set[str]:
    """Devuelve las palabras del texto en minúsculas y sin acentos."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return set(re.findall(r"[a-zñ]+", sin_acentos))


def elegir_rol_por_palabras(mensaje: str) -> str | None:
    """Devuelve "horarios" si el mensaje trae términos de horario; si no, None.

    None significa que estas reglas no deciden y manda el siguiente criterio del supervisor.
    """
    palabras = _normalizar(mensaje)
    # Se aceptan plurales simples: "horas", "horarios", "noches"...
    for clave in PALABRAS_HORARIOS:
        if clave in palabras or f"{clave}s" in palabras:
            return "horarios"
    return None
