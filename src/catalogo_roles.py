"""Catálogo único de capacidades y límites semánticos de los roles."""
from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Mapping, Sequence
import unicodedata


@dataclass(frozen=True)
class FichaRol:
    """Responsabilidad y límite que comparten el prompt y las guardas."""

    responsabilidad: str
    limites: tuple[str, ...] = ()


# El orden es deliberado: también determina el orden de presentación al modelo.
ROLES_CATALOGO = ("rag", "tarifas", "horarios", "rutas", "auxiliar")

CATALOGO_ROLES: Mapping[str, FichaRol] = MappingProxyType(
    {
        "rag": FichaRol(
            "consultas textuales sobre normativa, tarifas, billetes, abonos y "
            "documentos del CRTM",
            ("Atiende consultas tarifarias textuales sin imagen válida.",),
        ),
        "tarifas": FichaRol(
            "interpretación de una imagen, foto o cartel aportado, con lectura de "
            "los datos que contenga",
            ("Requiere una imagen aportada válida.",),
        ),
        "horarios": FichaRol("horarios y frecuencias de transporte"),
        "rutas": FichaRol(
            "planificación de desplazamientos entre un origen y un destino",
            (
                "Incluye la zona y el precio del trayecto, también para un título concreto (p. ej. abono joven).",
                "Las preguntas de precio de seguimiento sobre una ruta ya planificada "
                "(«¿y cuánto cuesta?») van a rutas, no a rag.",
            ),
        ),
        "auxiliar": FichaRol("hora actual y cálculos"),
    }
)

# Se preservan los términos aprobados y sus flexiones simples, no sinónimos nuevos.
TERMINOS_TARIFARIOS = frozenset(
    {"tarifa", "precio", "billete", "abono", "dinero", "gastar", "costar"}
)
_VARIANTES_TARIFARIAS = MappingProxyType(
    {
        "tarifa": frozenset({"tarifa", "tarifas"}),
        "precio": frozenset({"precio", "precios"}),
        "billete": frozenset({"billete", "billetes"}),
        "abono": frozenset({"abono", "abonos"}),
        "dinero": frozenset({"dinero", "dineros"}),
        "gastar": frozenset(
            {
                "gastar",
                "gasta",
                "gastas",
                "gastamos",
                "gastan",
                "gastando",
                "gaste",
                "gastes",
                "gastemos",
                "gasto",
                "gastaria",
                "gastarias",
                "gastariamos",
                "gastarian",
            }
        ),
        "costar": frozenset(
            {
                "costar",
                "cuesta",
                "cuestan",
                "coste",
                "costes",
                "costo",
                "costos",
                "costaba",
                "costaban",
                "costaria",
                "costarias",
                "costariamos",
                "costarian",
            }
        ),
    }
)


# Catálogo cerrado: estos códigos se refieren a ámbitos tarifarios, no a lugares.
ZONAS_TARIFARIAS = frozenset({"a", "b1", "b2", "b3", "c1", "c2", "e1", "e2"})
_CODIGO_ZONA = r"(?:a|b[123]|c[12]|e[12])"
_PREFIJO_ZONA = r"(?:(?:la|las)\s+)?(?:zona(?:s)?\s+)?"
_PATRONES_PARES_ZONA = (
    re.compile(
        rf"\bentre\s+{_PREFIJO_ZONA}(?P<origen>{_CODIGO_ZONA})\s+y\s+"
        rf"{_PREFIJO_ZONA}(?P<destino>{_CODIGO_ZONA})\b"
    ),
    re.compile(
        rf"\bde\s+{_PREFIJO_ZONA}(?P<origen>{_CODIGO_ZONA})\s+a\s+"
        rf"{_PREFIJO_ZONA}(?P<destino>{_CODIGO_ZONA})\b"
    ),
    re.compile(
        rf"(?<![a-z0-9])(?P<origen>{_CODIGO_ZONA})\s*[-–—]\s*"
        rf"(?P<destino>{_CODIGO_ZONA})(?![a-z0-9])"
    ),
)
_PATRON_RUTA_CON_DOS_LUGARES = re.compile(
    r"\b(?:como\s+(?:voy|llego)|ruta|itinerario)\b.*?\bdesde\s+"
    r"(?P<origen>[a-z][a-z0-9 ]*?)\s+(?:hasta|a)\s+"
    r"(?P<destino>[a-z][a-z0-9 ]*?)(?=\s+(?:y\s+)?(?:cuanto|que|precio|"
    r"costar|cuesta|abono)\b|[?.!]|$)"
)


def instrucciones_para_supervisor() -> str:
    """Devuelve las responsabilidades y exclusiones desde el catálogo único."""
    lineas = ["Responsabilidades y límites de los roles:"]
    for rol in ROLES_CATALOGO:
        ficha = CATALOGO_ROLES[rol]
        lineas.append(f"- {rol}: {ficha.responsabilidad}.")
        lineas.extend(f"  Límite: {limite}" for limite in ficha.limites)

    lineas.extend(
        (
            "",
            "Reglas de exclusión:",
            "Una consulta textual de tarifa sin imagen y sin origen ni destino debe seleccionar rag; con origen y destino "
            "selecciona rutas, que incluye la zona y el precio del trayecto, también para un título concreto (p. ej. abono joven).",
            "No selecciones tarifas salvo que exista una imagen aportada válida.",
            "Referirse solo a una imagen, foto o cartel no constituye una imagen aportada.",
        )
    )
    lineas.append(
        "Los códigos A, B1, B2, B3, C1, C2, E1 y E2 son zonas tarifarias; "
        "no son origen ni destino físico."
    )
    return "\n".join(lineas)


def _tokens_normalizados(texto: str) -> set[str]:
    """Reduce mayúsculas, tildes y puntuación a palabras comparables."""
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    sin_tildes = "".join(
        caracter
        for caracter in sin_tildes
        if unicodedata.category(caracter) != "Mn"
    )
    return set(re.findall(r"[a-z]+", sin_tildes))


def es_consulta_tarifaria_textual(mensaje: object) -> bool:
    """Indica si un mensaje contiene un término tarifario explícito aprobado."""
    if not isinstance(mensaje, str):
        return False

    palabras = _tokens_normalizados(mensaje)
    return any(palabras & variantes for variantes in _VARIANTES_TARIFARIAS.values())


def _texto_normalizado(texto: str) -> str:
    """Normaliza el texto para comparar conectores y códigos sin tildes."""
    sin_tildes = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caracter
        for caracter in sin_tildes
        if unicodedata.category(caracter) != "Mn"
    )


def _es_zona_aislada(texto: str) -> bool:
    """Indica si un extremo normalizado es únicamente un código tarifario."""
    return " ".join(texto.split()) in ZONAS_TARIFARIAS


def _es_peticion_ruta_con_lugares_fisicos(texto: str) -> bool:
    """Reconoce de forma conservadora una ruta con dos extremos no tarifarios."""
    coincidencia = _PATRON_RUTA_CON_DOS_LUGARES.search(texto)
    if coincidencia is None:
        return False

    return not _es_zona_aislada(coincidencia["origen"]) and not _es_zona_aislada(
        coincidencia["destino"]
    )


def es_consulta_tarifaria_entre_zonas(
    mensaje: object,
    *,
    tiene_imagen_valida: bool,
) -> bool:
    """Detecta una tarifa textual que relaciona explícitamente dos zonas admitidas."""
    if tiene_imagen_valida or not isinstance(mensaje, str):
        return False
    if not es_consulta_tarifaria_textual(mensaje):
        return False

    texto = _texto_normalizado(mensaje)
    if _es_peticion_ruta_con_lugares_fisicos(texto):
        return False

    for patron in _PATRONES_PARES_ZONA:
        coincidencia = patron.search(texto)
        if coincidencia and {
            coincidencia["origen"],
            coincidencia["destino"],
        } <= ZONAS_TARIFARIAS:
            return True
    return False


def corregir_tarifas_textuales(
    roles: Sequence[str],
    mensaje: object,
    *,
    tiene_imagen_valida: bool,
) -> tuple[list[str], int]:
    """Sustituye ``tarifas`` por ``rag`` en una cola validada sin imagen válida."""
    cola = list(roles)
    if tiene_imagen_valida or not es_consulta_tarifaria_textual(mensaje):
        return cola, 0

    correcciones = sum(rol == "tarifas" for rol in cola)
    if not correcciones:
        return cola, 0

    return ["rag" if rol == "tarifas" else rol for rol in cola], correcciones
