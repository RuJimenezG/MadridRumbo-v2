"""Funciones puras para mostrar los planes del grafo y filtrar su log (spec 008).

Un plan del grafo real es `{"id": "ruta-1", "resultado": {...}}`. Para una ruta, `resultado`
trae origen, destino, duración y tramos, y la zona y el precio que consultó el RAG. El grafo
puede añadir campos o devolver planes de otro tipo, así que nada aquí debe fallar por un
formato inesperado.
"""
from typing import Any, Mapping

import config

# Claves que identifican un resultado como ruta; sin ninguna se vuelca como clave: valor.
CLAVES_DE_RUTA = ("origen", "destino", "ruta")


def _direccion(punto: Any) -> str | None:
    """Texto de un origen o destino, que puede ser un diccionario con `direccion` o un texto."""
    if isinstance(punto, Mapping):
        punto = punto.get("direccion")
    return punto if isinstance(punto, str) and punto.strip() else None


def _es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _linea_de_tramo(numero: int, tramo: Any) -> str:
    """Una línea como `2. SUBWAY línea 1: Sol -> Atocha (9 min)`; omite lo que falte."""
    if not isinstance(tramo, Mapping):
        return f"    {numero}. {tramo}"
    modo = tramo.get("modo") if isinstance(tramo.get("modo"), str) else "Tramo"
    linea = tramo.get("linea")
    texto = f"{modo} línea {linea}" if linea else modo
    desde, hasta = tramo.get("desde"), tramo.get("hasta")
    if desde and hasta:
        texto += f": {desde} -> {hasta}"
    if _es_numero(tramo.get("duracion_min")):
        texto += f" ({tramo['duracion_min']} min)"
    return f"    {numero}. {texto}"


def _dato_del_rag(etiqueta: str, dato: Any) -> str | None:
    """Zona o precio consultados al RAG: su texto, `no disponible` si falló, o nada si no se pidió."""
    if isinstance(dato, str):
        return f"  {etiqueta}: {dato}"
    if not isinstance(dato, Mapping):
        return None
    if dato.get("estado") == "omitida":
        return None
    texto = dato.get("texto")
    if dato.get("estado") == "ok" and isinstance(texto, str) and texto.strip():
        return f"  {etiqueta}: {texto}"
    return f"  {etiqueta}: no disponible"


def _lineas_de_ruta(resultado: Mapping) -> list[str]:
    lineas = []
    for etiqueta, clave in (("Origen", "origen"), ("Destino", "destino")):
        direccion = _direccion(resultado.get(clave))
        if direccion:
            lineas.append(f"  {etiqueta}: {direccion}")
    if isinstance(resultado.get("titulo"), str):
        lineas.append(f"  Título: {resultado['titulo']}")
    if isinstance(resultado.get("hora_salida"), str):
        lineas.append(f"  Salida: {resultado['hora_salida']}")

    ruta = resultado.get("ruta")
    if isinstance(ruta, Mapping):
        if _es_numero(ruta.get("duracion_min")):
            lineas.append(f"  Duración: {ruta['duracion_min']} min")
        tramos = ruta.get("tramos")
        if isinstance(tramos, list) and tramos:
            lineas.append("  Tramos:")
            lineas += [_linea_de_tramo(i, t) for i, t in enumerate(tramos, start=1)]

    for etiqueta, clave in (("Zona", "zona"), ("Precio", "precio")):
        linea = _dato_del_rag(etiqueta, resultado.get(clave))
        if linea:
            lineas.append(linea)
    return lineas


def resumir_plan(plan: Any) -> str:
    """Resumen legible de un plan, con su identificador. Nunca lanza excepciones."""
    if not isinstance(plan, Mapping):
        return f"Plan: {plan}"

    lineas = [f"Plan {plan.get('id', '?')}"]
    resultado = plan.get("resultado")
    if not isinstance(resultado, Mapping):
        lineas.append(f"  {resultado}")
    elif any(clave in resultado for clave in CLAVES_DE_RUTA):
        lineas += _lineas_de_ruta(resultado)
    elif resultado:
        lineas += [f"  {clave}: {valor}" for clave, valor in resultado.items()]
    else:
        lineas.append("  (sin datos)")
    return "\n".join(lineas)


def ids_de_planes(planes: Any) -> list[str]:
    """Identificadores de los planes válidos, en orden; ignora todo lo que no tenga `id` de texto."""
    if not isinstance(planes, list):
        return []
    return [
        plan["id"]
        for plan in planes
        if isinstance(plan, Mapping) and isinstance(plan.get("id"), str) and plan["id"].strip()
    ]


def es_entrada_tecnica_supervisor(linea: Any) -> bool:
    """True si la entrada es un diagnóstico técnico del Supervisor, antiguo o estructurado."""
    if isinstance(linea, str):
        return linea.startswith(tuple(config.PREFIJOS_DIAGNOSTICO_SUPERVISOR))
    if not isinstance(linea, Mapping) or linea.get("nodo") != "supervisor":
        return False
    detalle = linea.get("detalle")
    return isinstance(detalle, Mapping) and isinstance(detalle.get("categoria"), str) and isinstance(
        detalle.get("resumen"), str
    )
