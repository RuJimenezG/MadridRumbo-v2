"""Especialista de rutas que delega el cálculo en planificar_ruta.

La tool conserva internamente sus consultas RAG de zona y precio. Este nodo solo
realiza la llamada exterior, conserva su resultado y nunca duplica esa consulta
dentro del mismo procesamiento.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable, Mapping


PROMPT_RUTAS = """Eres el especialista de rutas de MadridRumbo.
Ayudas a planificar desplazamientos en transporte público entre un origen y un
destino. Usa el historial de la conversación para recuperar un extremo aportado
en un turno anterior.

Tool disponible únicamente:
- planificar_ruta(origen, destino, hora_salida?, hora_llegada?, titulo?):
  calcula la ruta y consulta internamente el RAG para zona y precio.

Reglas:
- No inventes ni supongas origen o destino. Si falta alguno, responde con una
  nota que pida exactamente el dato pendiente y no pidas la tool.
- Para una ruta con ambos extremos, solicita planificar_ruta una sola vez.
- Conserva el JSON, las aclaraciones y los errores que devuelva la tool.
- No consultes directamente el RAG ni otra tool.
- Responde SOLO con un JSON por mensaje:
  {"tool": "planificar_ruta", "args": {...}} para pedir la tool, o
  {"final": "<nota en español>"} cuando tengas la respuesta.
"""

PATRON_FORMULACION_RUTA = re.compile(
    r"\b(?:quiero\W+ir\W+de|necesito\W+ir\W+de|voy\W+de)\b(?P<resto>.*)"
)


def _aclaracion_formulacion_incompleta(mensaje: Any) -> str | None:
    """Detecta solo las tres formulaciones aprobadas cuando les falta un extremo."""
    if not isinstance(mensaje, str):
        return None

    sin_acentos = unicodedata.normalize("NFD", mensaje.lower())
    sin_acentos = "".join(
        caracter for caracter in sin_acentos if unicodedata.category(caracter) != "Mn"
    )
    coincidencia = PATRON_FORMULACION_RUTA.search(sin_acentos)
    if coincidencia is None:
        return None

    # Los tokens eliminan puntuación para distinguir el separador «a» de extremos vacíos.
    extremos = re.findall(r"[a-zñ0-9]+", coincidencia.group("resto"))
    if not extremos:
        return "Falta indicar el origen y el destino para planificar la ruta."

    try:
        separador = len(extremos) - 1 - extremos[::-1].index("a")
    except ValueError:
        return "Falta indicar el destino para planificar la ruta."

    tiene_origen = separador > 0
    tiene_destino = separador < len(extremos) - 1
    if not tiene_origen and not tiene_destino:
        return "Falta indicar el origen y el destino para planificar la ruta."
    if not tiene_origen:
        return "Falta indicar el origen para planificar la ruta."
    if not tiene_destino:
        return "Falta indicar el destino para planificar la ruta."
    return None


def _mensajes_rutas(estado: Mapping[str, Any]) -> list[dict[str, str]]:
    """Copia el historial textual válido y añade el mensaje del turno actual."""
    mensajes: list[dict[str, str]] = [{"role": "system", "content": PROMPT_RUTAS}]
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


def _extremos_validos(args: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Devuelve argumentos copiables y los extremos ausentes sin invocar la tool."""
    datos = dict(args)
    faltan = [
        extremo
        for extremo in ("origen", "destino")
        if not isinstance(datos.get(extremo), str) or not datos[extremo].strip()
    ]
    return datos, faltan


def nodo_rutas(
    estado: Mapping[str, Any],
    llm: Callable[[list[dict[str, str]]], Any],
    ejecutar: Callable[[str, dict[str, Any], list[dict[str, Any]]], str],
) -> dict[str, Any]:
    """Planifica una única ruta exterior o solicita los extremos que faltan."""
    notas = list(estado.get("notas", []))
    traza = list(estado.get("traza", []))
    resultados = list(estado.get("resultados", []))
    resultado_ruta: tuple[str, dict[str, Any]] | None = None

    def terminar(texto: str) -> dict[str, Any]:
        salida: dict[str, Any] = {"notas": notas + [f"[rutas] {texto}"], "traza": traza}
        if resultado_ruta is not None:
            bruto, args_ruta = resultado_ruta
            estado_tool = "ok"
            if traza and isinstance(traza[-1], Mapping):
                estado_tool = str(traza[-1].get("status", "ok"))
            # Conserva el JSON completo: la traza solo tiene un extracto auditable.
            salida["resultados"] = resultados + [{
                "especialista": "rutas",
                "tool": "planificar_ruta",
                "status": estado_tool,
                "resultado": bruto,
                "args": dict(args_ruta),
            }]
        return salida

    aclaracion = _aclaracion_formulacion_incompleta(estado.get("mensaje"))
    if aclaracion is not None:
        return terminar(aclaracion)

    args_replanificar = estado.get("replanificar_args")
    if isinstance(args_replanificar, Mapping):
        args, faltan = _extremos_validos(args_replanificar)
        if not faltan:
            try:
                resultado = str(ejecutar("planificar_ruta", args, traza))
            except Exception:
                resultado = "ERROR: no se pudo ejecutar planificar_ruta."
                traza.append({"tool": "planificar_ruta", "args": args, "status": "error", "preview": resultado})
            resultado_ruta = (resultado, args)
            return terminar("Se ha solicitado una ruta alternativa con los datos anteriores.")

    mensajes = _mensajes_rutas(estado)
    try:
        propuesta = llm(mensajes)
    except Exception:
        return terminar("ERROR: el modelo no respondió al preparar la ruta.")

    if not isinstance(propuesta, Mapping):
        return terminar("ERROR: respuesta del modelo no interpretable para rutas.")
    if isinstance(propuesta.get("final"), str):
        return terminar(propuesta["final"])
    if propuesta.get("tool") != "planificar_ruta":
        tool = propuesta.get("tool")
        nombre = tool if isinstance(tool, str) else "desconocida"
        aviso = f"ERROR: tool no permitida: {nombre}"
        args_bloqueados = propuesta.get("args") if isinstance(propuesta.get("args"), Mapping) else {}
        traza.append({"tool": nombre, "args": dict(args_bloqueados), "status": "bloqueada", "preview": aviso})
        return terminar(aviso)

    args_propuestos = propuesta.get("args")
    args, faltan = _extremos_validos(args_propuestos if isinstance(args_propuestos, Mapping) else {})
    if faltan:
        datos = " y ".join(f"el {extremo}" for extremo in faltan)
        return terminar(f"Falta indicar {datos} para planificar la ruta.")

    try:
        resultado = str(ejecutar("planificar_ruta", args, traza))
    except Exception:
        resultado = "ERROR: no se pudo ejecutar planificar_ruta."
        traza.append({"tool": "planificar_ruta", "args": args, "status": "error", "preview": resultado})
    resultado_ruta = (resultado, args)

    mensajes.append({"role": "tool", "content": f"planificar_ruta: {resultado}"})
    try:
        cierre = llm(mensajes)
    except Exception:
        return terminar(f"Resultado de planificar_ruta: {resultado}")

    if isinstance(cierre, Mapping) and isinstance(cierre.get("final"), str):
        return terminar(cierre["final"])
    if isinstance(cierre, Mapping) and cierre.get("tool") == "planificar_ruta":
        return terminar("La ruta ya se ha planificado una sola vez en este turno.")
    return terminar(f"Resultado de planificar_ruta: {resultado}")
