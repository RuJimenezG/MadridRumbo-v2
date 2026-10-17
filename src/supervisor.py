"""Decisión segura del supervisor para la futura ejecución con LangGraph.

El supervisor admite solamente una estructura con una lista de roles. La
validación queda en Python para que una respuesta libre, inválida o fallida del
modelo no pueda activar una arista que el grafo no haya declarado.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Callable, Mapping, MutableMapping

from src.modelos import ErrorProveedorModelo, crear_modelo_supervisor
from src.supervisor_reglas import MENSAJE_REFORMULACION, elegir_roles_por_reglas


# Los nombres coinciden con los nodos que declarará el grafo en T12.
ROLES_ADMITIDOS = ("rag", "horarios", "rutas", "auxiliar", "tarifas")
MAX_ROLES_POR_DECISION = 20
CATEGORIAS_DIAGNOSTICO = frozenset(
    {"proveedor", "json_invalido", "roles_invalidos", "sin_fallback"}
)
RESUMENES_DIAGNOSTICO = {
    "proveedor": "El proveedor no entregó una respuesta utilizable.",
    "json_invalido": "La decisión no contiene JSON válido; se aplicó el fallback.",
    "roles_invalidos": "La decisión JSON contiene roles no válidos; se aplicó el fallback.",
    "sin_fallback": "Decisión estructurada validada.",
}

ModeloSupervisor = Callable[[list[dict[str, str]]], Mapping[str, Any] | Any]

_FENCE_JSON = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n(?P<contenido>.*?)\r?\n?```\Z",
    re.IGNORECASE | re.DOTALL,
)


class DecisionInvalida(ValueError):
    """Indica que una respuesta del modelo no puede convertirse en una cola segura."""


class JsonInvalido(DecisionInvalida):
    """Indica que el texto del modelo no es JSON recuperable."""


class RolesInvalidos(DecisionInvalida):
    """Indica que el objeto JSON no cumple el contrato de roles."""


@dataclass(frozen=True)
class DecisionSupervisor:
    """Resultado interno preparado para la observabilidad efímera del Supervisor."""

    roles: list[str]
    uso_fallback: bool
    categoria: str
    resumen: str


def _mensajes_para_modelo(estado: Mapping[str, Any]) -> list[dict[str, str]]:
    """Construye una entrada mínima sin mutar el historial persistido."""
    mensajes: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Decide los especialistas necesarios. Responde exclusivamente con "
                "JSON válido, sin Markdown ni texto envolvente. Ejemplo: "
                '{"roles": ["auxiliar"]}. El campo roles usa solamente rag, horarios, '
                "rutas, auxiliar o tarifas. Usa una lista vacía para finalizar."
            ),
        }
    ]
    historial = estado.get("historial", [])
    if isinstance(historial, list):
        for entrada in historial:
            if not isinstance(entrada, Mapping):
                continue
            rol = entrada.get("role")
            contenido = entrada.get("content")
            if isinstance(rol, str) and isinstance(contenido, str):
                mensajes.append({"role": rol, "content": contenido})

    mensaje = estado.get("mensaje", "")
    mensajes.append({"role": "user", "content": mensaje if isinstance(mensaje, str) else ""})
    return mensajes


def _normalizar_decision_json(respuesta: object) -> object:
    """Acepta JSON puro o un único fence Markdown JSON completo."""
    if isinstance(respuesta, Mapping):
        return respuesta
    if not isinstance(respuesta, str):
        raise ErrorProveedorModelo("El proveedor no devolvió texto utilizable.")

    texto = respuesta.strip()
    if not texto:
        raise ErrorProveedorModelo("El proveedor no devolvió texto utilizable.")
    if texto.startswith("```"):
        coincidencia = _FENCE_JSON.fullmatch(texto)
        if coincidencia is None:
            raise JsonInvalido("La decisión del supervisor no contiene JSON válido.")
        texto = coincidencia.group("contenido").strip()

    try:
        return json.loads(texto)
    except json.JSONDecodeError as exc:
        raise JsonInvalido("La decisión del supervisor no contiene JSON válido.") from exc


def validar_decision(respuesta: object) -> list[str]:
    """Convierte una respuesta estructurada en una cola finita y permitida."""
    if not isinstance(respuesta, Mapping):
        raise RolesInvalidos("La decisión del supervisor no es un objeto.")
    if set(respuesta) != {"roles"}:
        raise RolesInvalidos("La decisión del supervisor debe contener solo roles.")

    roles = respuesta.get("roles")
    if not isinstance(roles, list):
        raise RolesInvalidos("La decisión del supervisor debe incluir una lista de roles.")
    if len(roles) > MAX_ROLES_POR_DECISION:
        raise RolesInvalidos("La decisión del supervisor supera el máximo de roles.")
    if any(not isinstance(rol, str) or rol not in ROLES_ADMITIDOS for rol in roles):
        raise RolesInvalidos("La decisión del supervisor incluye un rol no permitido.")

    # Una lista vacía representa finish; las repeticiones son válidas por diseño.
    return list(roles)


def _decision_fallback(
    estado: Mapping[str, Any],
    categoria: str,
) -> DecisionSupervisor:
    """Construye un fallback con un motivo seguro de catálogo fijo."""
    mensaje = estado.get("mensaje", "")
    texto = mensaje if isinstance(mensaje, str) else ""
    return DecisionSupervisor(
        roles=elegir_roles_por_reglas(texto),
        uso_fallback=True,
        categoria=categoria,
        resumen=RESUMENES_DIAGNOSTICO[categoria],
    )


def decidir_decision_supervisor(
    estado: Mapping[str, Any],
    modelo: ModeloSupervisor | None = None,
) -> DecisionSupervisor:
    """Clasifica la decisión del Supervisor antes de usar el fallback seguro."""
    try:
        modelo_efectivo = modelo or crear_modelo_supervisor()
        respuesta = modelo_efectivo(_mensajes_para_modelo(estado))
        return DecisionSupervisor(
            roles=validar_decision(_normalizar_decision_json(respuesta)),
            uso_fallback=False,
            categoria="sin_fallback",
            resumen=RESUMENES_DIAGNOSTICO["sin_fallback"],
        )
    except ErrorProveedorModelo:
        return _decision_fallback(estado, "proveedor")
    except JsonInvalido:
        return _decision_fallback(estado, "json_invalido")
    except RolesInvalidos:
        return _decision_fallback(estado, "roles_invalidos")
    except Exception:
        return _decision_fallback(estado, "proveedor")


def decidir_roles(
    estado: Mapping[str, Any],
    modelo: ModeloSupervisor | None = None,
) -> tuple[list[str], bool]:
    """Mantiene la cola y la marca de fallback para consumidores internos previos."""
    decision = decidir_decision_supervisor(estado, modelo=modelo)
    return decision.roles, decision.uso_fallback


def nodo_supervisor(
    estado: Mapping[str, Any],
    modelo: ModeloSupervisor | None = None,
    contexto: MutableMapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Prepara la cola del turno o solicita una reformulación si no hay ámbito."""
    decision = decidir_decision_supervisor(estado, modelo=modelo)
    roles = decision.roles
    if contexto is not None:
        contexto["diagnostico_supervisor"] = {
            "categoria": decision.categoria,
            "resumen": decision.resumen,
        }

    actualizacion: dict[str, Any] = {"cola_roles": roles}

    if decision.uso_fallback:
        if not roles:
            actualizacion["respuesta"] = MENSAJE_REFORMULACION

    return actualizacion
