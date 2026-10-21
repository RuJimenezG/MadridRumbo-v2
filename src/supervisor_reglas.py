"""Reglas deterministas del supervisor: fallback por palabras clave cuando el LLM falla."""
import re
import unicodedata

# Términos que indican una pregunta de horarios (se comparan sin acentos ni mayúsculas).
PALABRAS_HORARIOS = {
    "hora", "horario", "ahora", "hoy", "noche",
    "ultima", "primera", "abre", "cierra", "frecuencia",
}

# Orden exigido para capacidades independientes del fallback multiagente.
ORDEN_FALLBACK = ("rag", "horarios", "auxiliar", "rutas", "tarifas")

# Mensaje que el futuro supervisor usará cuando ninguna regla pueda decidir.
MENSAJE_REFORMULACION = (
    "No he podido clasificar tu consulta. Reformúlala dentro del alcance de "
    "rutas, información del corpus CRTM, hora actual, cálculos o imágenes de transporte."
)

PALABRAS_RAG = {"crtm", "corpus", "documentos", "zona", "zonas", "tarifa", "tarifas", "abono", "abonos", "billete", "billetes"}
PALABRAS_IMAGEN = {"imagen", "imagenes", "foto", "fotos", "cartel", "carteles"}
PALABRAS_CALCULO = {"calcula", "calcular", "calculo", "total", "suma", "resta", "multiplica", "divide"}
PALABRAS_RUTAS = {"ruta", "rutas", "llegar", "llego", "voy", "ir", "viaje", "trayecto"}
PALABRAS_TRANSPORTE = {"metro", "autobus", "bus", "cercanias", "linea", "lineas", "tranvia"}
PALABRAS_ACCION_HORARIO = {"horario", "horarios", "frecuencia", "ultima", "primer", "primera", "abre", "cierra", "salida", "salidas"}
PATRONES_FORMULACION_RUTA = (
    r"\bquiero\W+ir\W+de\b",
    r"\bnecesito\W+ir\W+de\b",
    r"\bvoy\W+de\b",
)


def _normalizar(texto: str) -> set[str]:
    """Devuelve las palabras del texto en minúsculas y sin acentos."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return set(re.findall(r"[a-zñ]+", sin_acentos))


def _texto_normalizado(texto: str) -> str:
    """Normaliza un texto completo para reconocer expresiones de varias palabras."""
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    sin_acentos = "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin_acentos).strip()


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


def _es_hora_actual(texto: str) -> bool:
    """Reconoce peticiones de hora actual sin confundirlas con horarios de transporte."""
    return any(
        expresion in texto
        for expresion in (
            "que hora es",
            "dime la hora",
            "hora actual",
            "hora tenemos",
        )
    )


def _es_horario_transporte(palabras: set[str]) -> bool:
    """Reconoce horarios de red incluso cuando mencionan una hora concreta."""
    if palabras & PALABRAS_ACCION_HORARIO:
        return True
    return bool(
        "hora" in palabras
        and palabras & PALABRAS_TRANSPORTE
        and palabras & {"abre", "cierra", "sale", "salida", "ultima", "primera"}
    )


def _es_calculo(texto: str, palabras: set[str]) -> bool:
    """Reconoce instrucciones aritméticas o una expresión numérica sencilla."""
    if palabras & PALABRAS_CALCULO:
        return True
    return bool(re.search(r"\d+(?:[,.]\d+)?\s*[+\-*/]\s*\d+", texto))


def _es_ruta(texto: str, palabras: set[str]) -> bool:
    """Reconoce una intención de desplazamiento sin inferir origen ni destino."""
    if palabras & {"ruta", "rutas", "trayecto", "viaje"}:
        return True
    if any(re.search(patron, texto) for patron in PATRONES_FORMULACION_RUTA):
        return True
    return any(expresion in texto for expresion in ("como llegar", "como llego", "como voy", "como ir"))


# Spec 010: ruta con origen y destino = verbo de desplazamiento + «de/desde X a/al/hasta Y». Es más estricto que `_es_ruta`
# (que acepta «cómo voy» sin extremos y no conoce «desde») para no añadir `rutas` a «¿Cómo voy a pagar el abono?».
_VERBOS_DESPLAZAMIENTO = {"ir", "voy", "vamos", "llegar", "llego", "llegamos", "viajar", "viajo", "desplazarme"}
_EXTREMOS_RUTA = re.compile(r"\b(?:desde|de)\s+\S.*?\s+(?:hasta|al?)\s+\S")


def completar_rutas_con_extremos(roles: list[str], mensaje: object) -> tuple[list[str], int]:
    """Añade `rutas` al principio de la cola si el mensaje tiene forma de ruta con origen y destino.

    Devuelve `(cola, añadidos)`. Nunca quita ni reordena otros roles; si `rutas` ya está o el mensaje no tiene
    esa forma, la cola no cambia. Corrige al LLM cuando manda una consulta de ruta con precio solo a `rag`.
    """
    cola = list(roles)
    if "rutas" in cola or not isinstance(mensaje, str) or not mensaje.strip():
        return cola, 0
    if _normalizar(mensaje) & _VERBOS_DESPLAZAMIENTO and _EXTREMOS_RUTA.search(_texto_normalizado(mensaje)):
        return ["rutas", *cola], 1
    return cola, 0


def elegir_roles_por_reglas(mensaje: str) -> list[str]:
    """Devuelve los roles del fallback en orden seguro o una lista vacía si no clasifica.

    La dependencia imagen con total se trata antes del orden general: los
    importes deben obtenerse con tarifas antes de que auxiliar calcule.
    """
    if not isinstance(mensaje, str) or not mensaje.strip():
        return []

    texto = _texto_normalizado(mensaje)
    palabras = _normalizar(mensaje)
    es_imagen = bool(palabras & PALABRAS_IMAGEN)
    es_calculo = _es_calculo(texto, palabras)

    # Esta secuencia concreta prevalece sobre el orden de roles independientes.
    if es_imagen and es_calculo:
        return ["tarifas", "auxiliar"]

    roles: set[str] = set()
    if es_imagen:
        roles.add("tarifas")

    # Una imagen de tarifas no requiere RAG salvo que se mencione su fuente documental.
    fuente_documental_explicita = bool(palabras & {"crtm", "corpus", "documentos"})
    if palabras & PALABRAS_RAG and (not es_imagen or fuente_documental_explicita):
        roles.add("rag")
    if _es_horario_transporte(palabras):
        roles.add("horarios")
    if _es_hora_actual(texto) or es_calculo:
        roles.add("auxiliar")
    if _es_ruta(texto, palabras):
        roles.add("rutas")

    return [rol for rol in ORDEN_FALLBACK if rol in roles]
