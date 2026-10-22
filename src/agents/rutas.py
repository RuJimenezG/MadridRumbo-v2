"""Especialista de rutas que delega el cálculo en planificar_ruta.

La tool conserva internamente sus consultas RAG de zona y precio. Este nodo solo
realiza la llamada exterior, conserva su resultado y nunca duplica esa consulta
dentro del mismo procesamiento.
"""
from __future__ import annotations


from datetime import datetime
import re
import unicodedata
from typing import Any, Callable, Mapping

from src.reloj import ahora
from src.supervisor_reglas import eleccion_tras_ambigua
from src.tools.hora_actual import hora_actual


PROMPT_RUTAS = """Eres el especialista de rutas de MadridRumbo.
Ayudas a planificar desplazamientos en transporte público entre un origen y un
destino. Usa el historial de la conversación para recuperar un extremo aportado
en un turno anterior.

Tool disponible únicamente:
- planificar_ruta(origen, destino, hora_salida?, hora_llegada?, titulo?, opcion_origen?, opcion_destino?,
  texto_alternativo_origen?, texto_alternativo_destino?, probable_origen?, probable_destino?):
  calcula la ruta y consulta internamente el RAG para zona y precio.
  `titulo` es el título de transporte que pide la persona, tal como lo escribe (texto libre).

Reglas:
- No inventes ni supongas origen o destino. Si falta alguno, responde con una
  nota que pida exactamente el dato pendiente y no pidas la tool.
- Para una ruta con ambos extremos, solicita planificar_ruta una sola vez.
- Las horas (hora_salida y hora_llegada) se pasan a la tool en ISO 8601 con hora, por
  ejemplo 2026-10-17T08:00; la tool rechaza cualquier otro formato. Usa la fecha y hora
  actuales indicadas abajo para convertir "mañana" o "dentro de una hora".
- Si la tool devuelve un extremo ambiguo y la persona responde con un número, vuelve a pedir
  planificar_ruta repitiendo el texto ORIGINAL de ese extremo (el de la primera petición,
  no la respuesta) y añade opcion_origen u opcion_destino con ese número (entero desde 1).
  Si en lugar de un número escribe una dirección, envíala como texto nuevo de ese extremo
  con opcion 1 (opcion_origen=1 u opcion_destino=1).
- Si la persona menciona un título de transporte o pregunta por su precio, pásalo en `titulo`;
  si no pide ninguno, no envíes `titulo`.
- Si la tool devuelve un extremo ambiguo (estado "ambigua"), tu "final" debe copiar literalmente las
  opciones numeradas del `mensaje` de la tool y pedir que elija una.
- Si la tool devuelve "ruta_no_calculada", no reescribas el resultado: copia el `mensaje` de la tool tal cual.
- Si la persona pregunta después «¿y cuánto cuesta?» (o por otro título), vuelve a pedir planificar_ruta
  con los mismos origen y destino del historial y el `titulo` pedido.
- Si la persona pide ir en bici (o en BiciMAD) con origen y destino, solicita planificar_ruta igualmente:
  la tool devuelve la ruta en transporte público y la alternativa en BiciMAD si procede o el motivo por el
  que no se ofrece. Tu "final" debe copiar lo que devuelva la tool y no rechaces la petición por ser en bici.
- Segunda capa (solo cuando el turno anterior ya dejó ese extremo sin resolver, ambiguo o no encontrado, y la
  nueva entrada de la persona tampoco lo resuelve): actúa una sola vez por extremo y nunca en el primer intento.
  - Si la tool mostró opciones, elige solo entre las opciones que la tool mostró, con opcion_origen u
    opcion_destino y probable_origen=true o probable_destino=true. Si tu confianza es baja, no elijas:
    vuelve a preguntar a la persona con las opciones.
  - Si hubo 0 candidatos, propone un único texto alternativo por extremo en texto_alternativo_origen o
    texto_alternativo_destino (el nombre del lugar sin prefijos como «metro»); no encadenes más intentos.
  - La respuesta de la tool indica qué dirección se usó y cómo corregirla: conserva esa frase.
- En una pregunta de seguimiento sobre la misma ruta (por ejemplo «¿y cómo puedo ir en bici?»), pide
  planificar_ruta con los mismos textos de origen y destino, las mismas opciones elegidas (opcion_origen u
  opcion_destino, si la persona eligió con un número) y el mismo `titulo` del historial; no los sustituyas
  por valores por defecto.
- Conserva el JSON, las aclaraciones y los errores que devuelva la tool.
- No consultes directamente el RAG ni otra tool.
- Responde SOLO con un JSON por mensaje:
  {"tool": "planificar_ruta", "args": {...}} para pedir la tool, o
  {"final": "<nota en español>"} cuando tengas la respuesta.
"""

PATRON_FORMULACION_RUTA = re.compile(
    r"\b(?:quiero\W+ir\W+de|necesito\W+ir\W+de|voy\W+de)\b(?P<resto>.*)"
)


SEPARADORES_DESTINO = {"a", "al", "hasta"}


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

    # Separador del destino: la primera «a», «al» o «hasta» (spec 010); con la última, «de Sol a Moncloa a las 8» se parte mal.
    separador = next((i for i, token in enumerate(extremos) if token in SEPARADORES_DESTINO), None)
    if separador is None:
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


def construir_prompt(ahora_dt: datetime) -> str:
    """Prompt del especialista con la fecha y hora actuales, que se recalculan en cada llamada (RF-50)."""
    return f"{PROMPT_RUTAS}\n{hora_actual(ahora_dt)}\n"


def _mensajes_rutas(estado: Mapping[str, Any]) -> list[dict[str, str]]:
    """Copia el historial textual válido y añade el mensaje del turno actual."""
    mensajes: list[dict[str, str]] = [{"role": "system", "content": construir_prompt(ahora())}]
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

    # Spec 010, RF-46: respuesta solo con números tras una ambigua → misma llamada con las opciones, sin LLM.
    args_eleccion = eleccion_tras_ambigua(estado)
    if args_eleccion is not None:
        try:
            resultado = str(ejecutar("planificar_ruta", args_eleccion, traza))
        except Exception:
            resultado = "ERROR: no se pudo ejecutar planificar_ruta."
            traza.append({"tool": "planificar_ruta", "args": args_eleccion, "status": "error", "preview": resultado})
        resultado_ruta = (resultado, args_eleccion)
        return terminar("Se ha planificado la ruta con las opciones elegidas.")

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
