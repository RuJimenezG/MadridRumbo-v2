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
            "planificación de desplazamientos entre un origen y un destino"
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
            "Una consulta textual de tarifa sin imagen debe seleccionar rag.",
            "No selecciones tarifas salvo que exista una imagen aportada válida.",
            "Referirse solo a una imagen, foto o cartel no constituye una imagen aportada.",
        )
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
