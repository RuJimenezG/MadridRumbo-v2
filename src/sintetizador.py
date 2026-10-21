"""Síntesis anclada de los resultados del grafo multiagente.

El modelo recibe únicamente datos ya producidos por especialistas. Si no puede
responder, un renderizado determinista conserva la información disponible y
explica que la síntesis automática ha fallado.
"""
from __future__ import annotations

from copy import deepcopy
import json
import logging
from typing import Any, Callable, Mapping

import config
from src.modelos import crear_modelo_sintetizador

logger = logging.getLogger(__name__)

ModeloSintetizador = Callable[[Mapping[str, Any]], str]


def contexto_anclado(estado: Mapping[str, Any]) -> dict[str, list[Any]]:
    """Selecciona las únicas fuentes que el modelo puede usar para sintetizar."""
    notas = estado.get("notas", [])
    resultados = estado.get("resultados", [])
    traza = estado.get("traza", [])
    return {
        "notas": deepcopy(notas) if isinstance(notas, list) else [],
        "resultados": deepcopy(resultados) if isinstance(resultados, list) else [],
        "traza": deepcopy(traza) if isinstance(traza, list) else [],
    }


def _avisos_obligatorios(contexto: Mapping[str, Any]) -> list[str]:
    """Textos que el LLM no puede omitir: los `bloques` de planificar_ruta (spec 010) y luego sus avisos (spec 009).

    Los avisos son el de Google de la bici (RF-12) y la atribución a Open-Meteo. Se leen de `resultados[].resultado`
    (el JSON completo de la tool), no de las notas, que el especialista puede haber reescrito.
    """
    bloques: list[str] = []
    avisos: list[str] = []
    for resultado in contexto.get("resultados", []):
        if not isinstance(resultado, Mapping) or resultado.get("tool") != "planificar_ruta":
            continue
        try:  # un resultado ilegible solo se omite: no debe activar el respaldo ni tapar los demás
            bruto = resultado.get("resultado")
            datos = json.loads(bruto) if isinstance(bruto, str) else bruto
            if not isinstance(datos, Mapping):
                raise TypeError("el resultado no es un objeto")
            if isinstance(datos.get("bloques"), list):
                bloques += [b.strip() for b in datos["bloques"] if isinstance(b, str) and b.strip()]
            bici, clima = datos.get("bici"), datos.get("clima")
            if isinstance(bici, Mapping) and bici.get("estado") == "ok" and isinstance(bici.get("aviso"), str):
                avisos.append(bici["aviso"].strip())
            if isinstance(clima, Mapping) and clima.get("estado") == "ok":
                avisos.append(f"{config.CLIMA_ATRIBUCION}.")
        except Exception as e:  # noqa: BLE001 - solo el tipo del error: el contenido puede ser sensible
            logger.warning("Resultado de planificar_ruta ilegible: %s", type(e).__name__)
    return [a for a in dict.fromkeys([*bloques, *avisos]) if a]


def _lineas_respaldo(contexto: Mapping[str, Any]) -> tuple[list[str], bool]:
    """Recoge texto literal y señala si alguna fuente comunica una limitación."""
    lineas: list[str] = []
    hay_limitacion = False

    for nota in contexto.get("notas", []):
        if isinstance(nota, str) and nota.strip():
            lineas.append(nota)
            normalizada = nota.lower()
            hay_limitacion = hay_limitacion or "error" in normalizada or "no lo sé" in normalizada

    for resultado in contexto.get("resultados", []):
        if isinstance(resultado, Mapping):
            lineas.append(json.dumps(dict(resultado), ensure_ascii=False, default=str))
        elif isinstance(resultado, str) and resultado.strip():
            lineas.append(resultado)

    for entrada in contexto.get("traza", []):
        if not isinstance(entrada, Mapping):
            continue
        status = entrada.get("status")
        preview = entrada.get("preview")
        if status != "ok" or (isinstance(preview, str) and "no lo sé" in preview.lower()):
            if isinstance(preview, str) and preview.strip():
                lineas.append(preview)
            hay_limitacion = True

    return lineas, hay_limitacion


def renderizar_respaldo(estado: Mapping[str, Any]) -> str:
    """Devuelve una respuesta sencilla sin transformar ni inventar los datos reunidos."""
    contexto = contexto_anclado(estado)
    lineas, hay_limitacion = _lineas_respaldo(contexto)
    cabecera = "No se ha podido sintetizar la respuesta automáticamente."
    if not lineas:
        return f"{cabecera} No se ha obtenido información de los especialistas."

    etiqueta = "Información disponible (puede ser parcial):" if hay_limitacion else "Información obtenida:"
    return "\n".join([cabecera, etiqueta, *[f"- {linea}" for linea in lineas]])


def nodo_sintetizador(
    estado: Mapping[str, Any],
    modelo: ModeloSintetizador | None = None,
) -> dict[str, Any]:
    """Genera una síntesis sencilla o activa el respaldo si el modelo falla."""
    contexto = contexto_anclado(estado)
    try:
        modelo_efectivo = modelo or crear_modelo_sintetizador()
        respuesta = modelo_efectivo(contexto)
        if not isinstance(respuesta, str) or not respuesta.strip():
            raise ValueError("Respuesta del sintetizador no interpretable.")
        # Se compara con el texto ya acumulado: el bloque de bici lleva dentro el aviso de Google y el de clima la atribución.
        texto = respuesta
        for obligatorio in _avisos_obligatorios(contexto):
            if obligatorio not in texto:
                texto = f"{texto}\n\n{obligatorio}"
        return {"respuesta": texto}
    except Exception:
        return {
            "respuesta": renderizar_respaldo(contexto),
            "log": ["Sintetizador: se ha usado el respaldo determinista."],
        }
