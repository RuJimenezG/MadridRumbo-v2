"""Fábrica del StateGraph de MadridRumbo con auditoría transversal.

Las aristas son estáticas y el supervisor solo llena una cola validada. Todos
los especialistas reciben el mismo ejecutor inyectado; el envoltorio del grafo
agrega exclusivamente los deltas de notas, trazas y resultados de cada nodo.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Callable, Mapping, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

import config
from src.agents.auxiliar import nodo_auxiliar
from src.agents.base import (
    EjecutorTool,
    crear_ejecutor_acotado,
    crear_ejecutor_transversal,
    sesion_depuracion_activa,
)
from src.agents.horarios import nodo_horarios
from src.agents.rag import nodo_rag
from src.agents.rutas import nodo_rutas
from src.agents.tarifas import (
    MARCADOR_REDIRECCION_A_RAG,
    nodo_tarifas,
    redireccionar_tarifas_sin_imagen,
)
from src.depuracion import SesionDepuracion
from src.estado import EstadoGrafo, crear_plan
from src.modelos import crear_modelo_especialista
from src.sintetizador import nodo_sintetizador, renderizar_respaldo, turno_actual
from src.supervisor import nodo_supervisor
from src.tools import ejecutar_tool


ROLES_GRAFO = ("rag", "horarios", "rutas", "auxiliar", "tarifas")
NodoEspecialista = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_CLAVE_IMAGEN_VALIDA_INTERNA = "_imagen_valida_contexto"


class ContextoEjecucion(TypedDict, total=False):
    """Datos de una invocación que no deben llegar al checkpointer."""

    diagnostico_supervisor: dict[str, str] | None
    correcciones_tarifas: int
    imagen_valida: bool


def configuracion_hilo(thread_id: str) -> dict[str, dict[str, str]]:
    """Crea la configuración que LangGraph usa para aislar un checkpoint."""
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("thread_id debe ser un texto no vacío.")
    return {"configurable": {"thread_id": thread_id}}


def invocar_grafo(
    grafo: Any,
    estado: Mapping[str, Any],
    thread_id: str,
    *,
    contexto: ContextoEjecucion | None = None,
    sesion: SesionDepuracion | None = None,
) -> dict[str, Any]:
    """Invoca un grafo siempre con el identificador de conversación requerido."""
    configuracion = configuracion_hilo(thread_id)
    if sesion is not None:
        with sesion_depuracion_activa(sesion):
            return _consumir_eventos_grafo(
                grafo.stream(
                    dict(estado),
                    config=configuracion,
                    context=contexto,
                    stream_mode=["values", "updates", "tasks"],
                ),
                sesion,
                estado_inicial=estado,
                contexto=contexto,
            )
    return dict(
        grafo.invoke(
            dict(estado),
            config=configuracion,
            context=contexto,
        )
    )


def reanudar_grafo(
    grafo: Any,
    decision: Mapping[str, Any],
    thread_id: str,
    *,
    sesion: SesionDepuracion | None = None,
) -> dict[str, Any]:
    """Reanuda una interrupciÃ³n del hilo sin crear una conversaciÃ³n nueva."""
    configuracion = configuracion_hilo(thread_id)
    comando = Command(resume=dict(decision))
    if sesion is not None:
        with sesion_depuracion_activa(sesion):
            return _consumir_eventos_grafo(
                grafo.stream(
                    comando,
                    config=configuracion,
                    stream_mode=["values", "updates", "tasks"],
                ),
                sesion,
            )
    return dict(grafo.invoke(comando, config=configuracion))


def _registrar_nodo_fallido(sesion: SesionDepuracion, nombre: object, entrada: object) -> None:
    """Añade un fallo de nodo sin exponer la excepción ni datos de proveedor."""
    sesion.registrar(
        "nodo",
        nombre if isinstance(nombre, str) and nombre else "desconocido",
        entrada,
        None,
        resultado="fallido",
        detalle={
            "categoria": "nodo",
            "resumen": "El nodo no pudo completarse.",
        },
    )


def _registrar_fallback_supervisor(
    sesion: SesionDepuracion,
    contexto: Mapping[str, Any] | None,
) -> bool:
    """Proyecta el diagnóstico efímero tras un fallback, sin añadirlo al estado.

    El nodo del Supervisor termina correctamente porque aplica una alternativa
    segura. La entrada ``control`` separa el rechazo de su decisión primaria
    de ese nodo completado, que por contrato debe conservar ``detalle`` nulo.
    """
    if not isinstance(contexto, Mapping):
        return False
    diagnostico = contexto.get("diagnostico_supervisor")
    if not isinstance(diagnostico, Mapping):
        return False
    categoria = diagnostico.get("categoria")
    if not isinstance(categoria, str) or not categoria or categoria == "sin_fallback":
        return False
    resumen = diagnostico.get("resumen")
    sesion.registrar(
        "control",
        "supervisor",
        None,
        None,
        resultado="rechazado",
        detalle={
            "categoria": categoria,
            "resumen": resumen if isinstance(resumen, str) else "El Supervisor aplicó un fallback seguro.",
        },
    )
    return True


def _consumir_eventos_grafo(
    eventos: Any,
    sesion: SesionDepuracion,
    *,
    estado_inicial: Mapping[str, Any] | None = None,
    contexto: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convierte eventos locales de LangGraph en snapshots completos por nodo.

    ``tasks`` entrega el estado de entrada y el fin de cada nodo; ``values``
    entrega el estado ya combinado por los reducers. Las entradas completadas
    se dejan pendientes hasta recibir ese valor combinado. Si un nodo no
    cambia el estado, la entrada del siguiente nodo aporta el mismo snapshot.
    """
    ultimo_estado = dict(estado_inicial or {})
    tareas_en_curso: dict[object, dict[str, Any]] = {}
    nodos_pendientes: list[dict[str, Any]] = []
    actualizaciones: dict[str, Any] = {}
    diagnostico_supervisor_registrado = False

    def completar_pendientes(salida: object) -> None:
        nonlocal diagnostico_supervisor_registrado
        while nodos_pendientes:
            nodo = nodos_pendientes.pop(0)
            # La actualización asocia los tres modos del stream; el snapshot
            # final siempre procede de values, tras aplicar los reducers.
            actualizaciones.pop(nodo["nodo"], None)
            sesion.registrar("nodo", nodo["nodo"], nodo["entrada"], salida)
            if nodo["nodo"] == "supervisor" and not diagnostico_supervisor_registrado:
                diagnostico_supervisor_registrado = _registrar_fallback_supervisor(sesion, contexto)

    try:
        for evento in eventos:
            if not isinstance(evento, tuple) or len(evento) != 2:
                continue
            modo, carga = evento
            if modo == "values" and isinstance(carga, Mapping):
                ultimo_estado = dict(carga)
                completar_pendientes(ultimo_estado)
                continue
            if modo == "updates" and isinstance(carga, Mapping):
                for nombre, actualizacion in carga.items():
                    if isinstance(nombre, str):
                        actualizaciones[nombre] = actualizacion
                continue
            if modo != "tasks" or not isinstance(carga, Mapping):
                continue

            identificador = carga.get("id")
            if "input" in carga:
                # Sin un nuevo values, el input del nodo siguiente es el estado
                # combinado que necesitaba el nodo previo sin actualización.
                completar_pendientes(carga["input"])
                tareas_en_curso[identificador] = {
                    "nodo": carga.get("name"),
                    "entrada": carga["input"],
                }
                continue

            if "error" not in carga and "result" not in carga:
                continue
            tarea = tareas_en_curso.pop(identificador, None)
            if tarea is None:
                tarea = {"nodo": carga.get("name"), "entrada": None}
            if carga.get("error") is not None:
                _registrar_nodo_fallido(sesion, tarea["nodo"], tarea["entrada"])
            else:
                nombre = tarea["nodo"]
                if isinstance(nombre, str) and nombre:
                    nodos_pendientes.append(tarea)
                else:
                    _registrar_nodo_fallido(sesion, nombre, tarea["entrada"])
    except Exception:
        completar_pendientes(ultimo_estado)
        for tarea in tareas_en_curso.values():
            _registrar_nodo_fallido(sesion, tarea["nodo"], tarea["entrada"])
        raise

    completar_pendientes(ultimo_estado)
    return ultimo_estado


def recuperar_estado(grafo: Any, thread_id: str) -> dict[str, Any]:
    """Recupera el último estado persistido del hilo, o un diccionario vacío."""
    snapshot = grafo.get_state(configuracion_hilo(thread_id))
    return dict(snapshot.values) if snapshot and snapshot.values else {}


def _registrar_mensaje(estado: Mapping[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Añade el mensaje entrante al historial que conservará el checkpointer."""
    mensaje = estado.get("mensaje", "")
    if not isinstance(mensaje, str) or not mensaje.strip():
        return {}
    return {"historial": [{"role": "user", "content": mensaje}]}


def _nodo_supervisor_con_contexto(
    estado: Mapping[str, Any],
    runtime: Runtime[ContextoEjecucion],
    modelo: Callable[..., Any] | None,
) -> dict[str, Any]:
    """Entrega el diagnóstico seguro al contexto efímero de esta invocación."""
    return nodo_supervisor(estado, modelo=modelo, contexto=runtime.context)


def _destino_entrada(estado: Mapping[str, Any]) -> str:
    """Evita el supervisor cuando la fachada detectó el máximo de turnos."""
    return "limite_turnos" if estado.get("limite_turnos") else "supervisor"


def _actualizacion_turno(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Cuenta una sola respuesta para cada mensaje válido, incluso si deja HITL."""
    if estado.get("turno_contabilizado"):
        return {}
    anteriores = estado.get("turnos_completados", 0)
    total = anteriores if isinstance(anteriores, int) and anteriores >= 0 else 0
    return {"turnos_completados": total + 1, "turno_contabilizado": True}


def _registrar_turno(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Nodo que registra el par mensaje/respuesta antes de terminar o pausar."""
    return _actualizacion_turno(estado)


def _resumen_disponible(estado: Mapping[str, Any]) -> str:
    """Mantiene la última respuesta o el respaldo determinista al cortar el flujo."""
    respuesta = estado.get("respuesta")
    if isinstance(respuesta, str) and respuesta.strip():
        return respuesta
    return renderizar_respaldo(estado)


def _limite_turnos(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Termina sin especialistas cuando la conversación agotó sus turnos."""
    return {
        "respuesta": f"{_resumen_disponible(estado)}\nSe ha alcanzado el máximo de turnos de conversación.",
        "hitl_pendiente": False,
        "done": True,
        "limite_turnos": True,
    }


def _limite_tools(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Termina con lo obtenido cuando no queda presupuesto de tools directas."""
    salida = _actualizacion_turno(estado)
    salida.update(
        {
            "respuesta": f"{_resumen_disponible(estado)}\nSe ha alcanzado el máximo de tools permitido para este turno.",
            "hitl_pendiente": False,
            "done": True,
            "planes_pendientes": [],
            "limite_tools_alcanzado": True,
        }
    )
    return salida


def _como_dict(resultado: object) -> dict[str, Any] | None:
    """Acepta el dict de la tool o su representaciÃ³n JSON, sin lanzar excepciones."""
    if isinstance(resultado, Mapping):
        return deepcopy(dict(resultado))
    if not isinstance(resultado, str):
        return None
    try:
        cargado = json.loads(resultado)
    except (TypeError, ValueError):
        return None
    return deepcopy(dict(cargado)) if isinstance(cargado, Mapping) else None


def _candidatos_rutas(estado: Mapping[str, Any]) -> list[tuple[object, dict[str, Any]]]:
    """Extrae resultados completos de rutas y usa la traza solo como respaldo."""
    candidatos: list[tuple[object, dict[str, Any]]] = []
    resultados = estado.get("resultados", [])
    if isinstance(resultados, list):
        for entrada in resultados:
            if not isinstance(entrada, Mapping) or entrada.get("tool") != "planificar_ruta":
                continue
            args = entrada.get("args")
            candidatos.append((entrada.get("resultado"), dict(args) if isinstance(args, Mapping) else {}))
    if candidatos:
        return candidatos

    traza = estado.get("traza", [])
    if not isinstance(traza, list):
        return []
    for entrada in traza:
        if not isinstance(entrada, Mapping) or entrada.get("tool") != "planificar_ruta":
            continue
        args = entrada.get("args")
        candidatos.append((entrada.get("preview"), dict(args) if isinstance(args, Mapping) else {}))
    return candidatos


def normalizar_planes_rutas(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Convierte solo rutas completas y correctas en planes persistibles con ID."""
    pendientes = estado.get("planes_pendientes", [])
    planes = list(pendientes) if isinstance(pendientes, list) else []
    replanificar_args = estado.get("replanificar_args")
    es_replanificacion = isinstance(replanificar_args, Mapping)
    if planes and not es_replanificacion:
        # El nodo puede reanudarse: no regenera IDs de planes ya persistidos.
        return {}

    candidatos = _candidatos_rutas(estado)
    if es_replanificacion:
        # Los resultados anteriores permanecen auditables; solo el Ãºltimo es la nueva propuesta.
        candidatos = candidatos[-1:]

    siguiente = 1
    desde_id = estado.get("replanificar_desde_id")
    if isinstance(desde_id, str) and desde_id.startswith("ruta-"):
        try:
            siguiente = int(desde_id.removeprefix("ruta-")) + 1
        except ValueError:
            pass
    for plan in planes:
        if isinstance(plan, Mapping) and isinstance(plan.get("id"), str) and plan["id"].startswith("ruta-"):
            try:
                siguiente = max(siguiente, int(plan["id"].removeprefix("ruta-")) + 1)
            except ValueError:
                pass

    nuevos_planes = []
    for resultado_bruto, args in candidatos:
        resultado = _como_dict(resultado_bruto)
        if resultado is None or resultado.get("estado") != "ok":
            continue
        ruta = resultado.get("ruta")
        if not isinstance(ruta, Mapping):
            continue
        nuevos_planes.append(crear_plan(f"ruta-{siguiente}", resultado, args))
        siguiente += 1

    if not nuevos_planes:
        if es_replanificacion:
            return {"replanificar_args": None, "replanificar_desde_id": None}
        return {}
    salida: dict[str, Any] = {
        "planes_pendientes": planes + nuevos_planes,
        "hitl_pendiente": True,
        "done": False,
    }
    if es_replanificacion:
        salida.update({"replanificar_args": None, "replanificar_desde_id": None})
    return salida


def _debe_pausar(estado: Mapping[str, Any]) -> str:
    """Dirige al interrupt Ãºnicamente cuando hay una propuesta pendiente vÃ¡lida."""
    planes = estado.get("planes_pendientes", [])
    if estado.get("hitl_pendiente") and isinstance(planes, list) and planes:
        return "pausa_hitl"
    return "finalizar_turno"


def _nodo_pausa_hitl(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Interrumpe tras el checkpoint que ya contiene plan, respuesta y done falso."""
    planes = estado.get("planes_pendientes", [])
    resumen = [
        {"id": plan.get("id"), "resultado": plan.get("resultado")}
        for plan in planes
        if isinstance(plan, Mapping)
    ] if isinstance(planes, list) else []
    decision = interrupt({"motivo": "aprobar_plan", "plan": resumen})
    if not isinstance(decision, Mapping):
        return {}
    seleccionado = decision.get("plan_id_seleccionado")
    if not isinstance(seleccionado, str) or not isinstance(decision.get("aprobado"), bool):
        return {}
    return {"plan_id_seleccionado": seleccionado, "decision_hitl": dict(decision)}


def _destino_decision_hitl(estado: Mapping[str, Any]) -> str:
    """Separa la aprobaciÃ³n de la replanificaciÃ³n sin confiar en texto libre."""
    decision = estado.get("decision_hitl")
    if isinstance(decision, Mapping) and decision.get("aprobado") is True:
        return "aceptar_plan"
    if isinstance(decision, Mapping) and decision.get("aprobado") is False:
        return "rechazar_plan"
    return "pausa_hitl"


def _aceptar_plan(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Cierra las propuestas pendientes y conserva el plan elegido para sintetizar."""
    seleccionado = estado.get("plan_id_seleccionado")
    planes = estado.get("planes_pendientes", [])
    if not isinstance(seleccionado, str) or not isinstance(planes, list):
        return {"hitl_pendiente": True, "done": False}

    plan = next(
        (candidato for candidato in planes if isinstance(candidato, Mapping) and candidato.get("id") == seleccionado),
        None,
    )
    if plan is None:
        return {"hitl_pendiente": True, "done": False}

    aprobado = deepcopy(dict(plan))
    resumen = json.dumps(aprobado.get("resultado", {}), ensure_ascii=False, default=str)
    return {
        "planes_pendientes": [],
        "plan_aprobado": aprobado,
        "hitl_pendiente": False,
        "done": False,
        "notas": [f"[rutas] Plan aprobado {seleccionado}: {resumen}"],
    }


def _rechazar_plan(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Descarta solo el plan elegido y prepara una nueva llamada de rutas con sus args."""
    seleccionado = estado.get("plan_id_seleccionado")
    planes = estado.get("planes_pendientes", [])
    if not isinstance(seleccionado, str) or not isinstance(planes, list):
        return {"hitl_pendiente": True, "done": False}

    plan = next(
        (candidato for candidato in planes if isinstance(candidato, Mapping) and candidato.get("id") == seleccionado),
        None,
    )
    if plan is None:
        return {"hitl_pendiente": True, "done": False}

    args = plan.get("args")
    restantes = [dict(candidato) for candidato in planes if isinstance(candidato, Mapping) and candidato.get("id") != seleccionado]
    return {
        "planes_pendientes": restantes,
        "cola_roles": ["rutas"],
        "plan_id_seleccionado": None,
        "replanificar_args": deepcopy(dict(args)) if isinstance(args, Mapping) else {},
        "replanificar_desde_id": seleccionado,
        "decision_hitl": None,
        "hitl_pendiente": False,
        "done": False,
        "notas": [f"[rutas] Plan rechazado {seleccionado}; se solicitará una alternativa."],
    }


def _finalizar_turno(_: Mapping[str, Any]) -> dict[str, bool]:
    """Cierra los recorridos que no requieren aprobaciÃ³n humana."""
    return {"hitl_pendiente": False, "done": True}


def siguiente_destino(estado: Mapping[str, Any]) -> str:
    """Devuelve un nodo declarado o sintetizador; rechaza cualquier rol ajeno."""
    usadas = estado.get("tools_turno", 0)
    if estado.get("limite_tools_alcanzado") or (isinstance(usadas, int) and usadas >= config.MAX_CICLOS_TOOLS):
        return "limite_tools"
    cola = estado.get("cola_roles", [])
    if not isinstance(cola, list) or not cola:
        return "sintetizador"

    rol = cola[0]
    if not isinstance(rol, str) or rol not in ROLES_GRAFO:
        raise ValueError(f"Rol no permitido en la cola del grafo: {rol!r}")
    return f"nodo_{rol}"


def _especialistas_predeterminados(
    modelos: Mapping[str, Callable[..., Any]] | None,
    ejecutar: EjecutorTool,
) -> dict[str, NodoEspecialista]:
    """Crea nodos con modelos perezosos y un ejecutor común para todo el turno."""
    modelos = modelos or {}
    modelos_efectivos = {
        rol: modelos.get(rol) or crear_modelo_especialista()
        for rol in ROLES_GRAFO
    }

    def ejecutor_para(estado: Mapping[str, Any]) -> EjecutorTool:
        return crear_ejecutor_acotado(ejecutar, estado.get("tools_turno", 0))

    return {
        "rag": lambda estado: nodo_rag(dict(estado), modelos_efectivos["rag"], ejecutor_para(estado)),
        "horarios": lambda estado: nodo_horarios(dict(estado), modelos_efectivos["horarios"], ejecutor_para(estado)),
        "rutas": lambda estado: nodo_rutas(estado, modelos_efectivos["rutas"], ejecutor_para(estado)),
        "auxiliar": lambda estado: nodo_auxiliar(dict(estado), modelos_efectivos["auxiliar"], ejecutor_para(estado)),
        "tarifas": lambda estado: nodo_tarifas(
            dict(estado),
            modelos_efectivos["tarifas"],
            ejecutor_para(estado),
            tiene_imagen_valida=estado.get(_CLAVE_IMAGEN_VALIDA_INTERNA) is True,
        ),
    }


def _delta(anterior: object, nuevo: object) -> list[Any]:
    """Extrae el tramo añadido por un nodo que recibe las listas acumuladas."""
    if not isinstance(nuevo, list):
        return []
    if isinstance(anterior, list) and nuevo[:len(anterior)] == anterior:
        return list(nuevo[len(anterior):])
    return list(nuevo)


def _resultados_desde_traza(rol: str, traza: list[Any]) -> list[dict[str, Any]]:
    """Convierte cada llamada directa en un resultado resumido para la síntesis."""
    resultados: list[dict[str, Any]] = []
    for entrada in traza:
        if not isinstance(entrada, Mapping):
            continue
        resultados.append(
            {
                "especialista": rol,
                "tool": str(entrada.get("tool", "")),
                "status": str(entrada.get("status", "")),
                "resultado": str(entrada.get("preview", "")),
            }
        )
    return resultados


def _envolver_especialista(
    rol: str,
    nodo: NodoEspecialista,
) -> Callable[..., dict[str, Any]]:
    """Ejecuta un especialista, agrega sus deltas y consume el primer rol de cola."""
    def ejecutar_nodo(
        estado: Mapping[str, Any],
        runtime: Runtime[ContextoEjecucion],
    ) -> dict[str, Any]:
        cola = estado.get("cola_roles", [])
        if not isinstance(cola, list) or not cola or cola[0] != rol:
            raise ValueError(f"La cola no permite ejecutar el nodo {rol!r}.")

        imagen_valida = (
            isinstance(runtime.context, Mapping)
            and runtime.context.get("imagen_valida") is True
        )
        if rol == "tarifas" and not imagen_valida:
            actualizacion = redireccionar_tarifas_sin_imagen()
        else:
            estado_para_nodo = dict(estado)
            if rol == "tarifas":
                estado_para_nodo[_CLAVE_IMAGEN_VALIDA_INTERNA] = True
            actualizacion = nodo(estado_para_nodo)
        if not isinstance(actualizacion, Mapping):
            raise ValueError(f"El nodo {rol!r} no devolvió una actualización válida.")

        notas = _delta(estado.get("notas", []), actualizacion.get("notas", []))
        traza = _delta(estado.get("traza", []), actualizacion.get("traza", []))
        resultados = _delta(estado.get("resultados", []), actualizacion.get("resultados", []))
        if rol == "tarifas" and actualizacion.get(MARCADOR_REDIRECCION_A_RAG) is True:
            salida_redireccion = {"cola_roles": ["rag", *cola[1:]]}
            if notas:
                salida_redireccion["notas"] = notas
            return salida_redireccion
        if not resultados:
            resultados = _resultados_desde_traza(rol, traza)
        # Cada resultado lleva el turno en que se produjo: `resultados` acumula toda la conversación y el sintetizador
        # solo fuerza los bloques del turno actual.
        turno = turno_actual(estado)
        if turno is not None:
            resultados = [{**r, "turno": turno} if isinstance(r, Mapping) else r for r in resultados]

        salida = {
            clave: valor
            for clave, valor in actualizacion.items()
            if clave not in {"notas", "traza", "resultados", "cola_roles"}
        }
        if notas:
            salida["notas"] = notas
        if traza:
            salida["traza"] = traza
        if resultados:
            salida["resultados"] = resultados
        ejecutadas = sum(
            1
            for entrada in traza
            if isinstance(entrada, Mapping) and entrada.get("status") in {"ok", "error"}
        )
        if ejecutadas:
            previas = estado.get("tools_turno", 0)
            usadas = previas if isinstance(previas, int) and previas >= 0 else 0
            total = usadas + ejecutadas
            salida["tools_turno"] = total
            if total >= config.MAX_CICLOS_TOOLS:
                salida["limite_tools_alcanzado"] = True
        salida["cola_roles"] = list(cola[1:])
        return salida

    return ejecutar_nodo


def crear_grafo(
    *,
    modelo_supervisor: Callable[..., Any] | None = None,
    modelos_especialistas: Mapping[str, Callable[..., Any]] | None = None,
    especialistas: Mapping[str, NodoEspecialista] | None = None,
    modelo_sintetizador: Callable[..., str] | None = None,
    ejecutar: EjecutorTool = ejecutar_tool,
    checkpointer: Any | None = None,
) -> Any:
    """Construye un grafo inyectable con un saver aislado por ``thread_id``."""
    desconocidos_modelos = set(modelos_especialistas or {}) - set(ROLES_GRAFO)
    if desconocidos_modelos:
        raise ValueError(f"Modelos de especialistas no permitidos: {sorted(desconocidos_modelos)!r}")

    ejecutor_compartido = crear_ejecutor_transversal(ejecutar)
    nodos_especialistas = _especialistas_predeterminados(modelos_especialistas, ejecutor_compartido)
    if especialistas:
        desconocidos = set(especialistas) - set(ROLES_GRAFO)
        if desconocidos:
            raise ValueError(f"Especialistas no permitidos: {sorted(desconocidos)!r}")
        nodos_especialistas.update(especialistas)

    grafo = StateGraph(EstadoGrafo, context_schema=ContextoEjecucion)
    grafo.add_node("entrada", _registrar_mensaje)
    grafo.add_node("limite_turnos", _limite_turnos)
    grafo.add_node(
        "supervisor",
        lambda estado, runtime: _nodo_supervisor_con_contexto(
            estado,
            runtime,
            modelo_supervisor,
        ),
    )
    for rol in ROLES_GRAFO:
        grafo.add_node(f"nodo_{rol}", _envolver_especialista(rol, nodos_especialistas[rol]))
    grafo.add_node("normalizar_rutas", normalizar_planes_rutas)
    grafo.add_node("sintetizador", lambda estado: nodo_sintetizador(estado, modelo=modelo_sintetizador))
    grafo.add_node("registrar_turno", _registrar_turno)
    grafo.add_node("limite_tools", _limite_tools)
    grafo.add_node("pausa_hitl", _nodo_pausa_hitl)
    grafo.add_node("aceptar_plan", _aceptar_plan)
    grafo.add_node("rechazar_plan", _rechazar_plan)
    grafo.add_node(
        "sintetizador_aprobacion",
        lambda estado: nodo_sintetizador(estado, modelo=modelo_sintetizador, tras_aprobacion=True),
    )
    grafo.add_node("finalizar_turno", _finalizar_turno)

    destinos = {f"nodo_{rol}": f"nodo_{rol}" for rol in ROLES_GRAFO}
    destinos["sintetizador"] = "normalizar_rutas"
    destinos["limite_tools"] = "limite_tools"
    grafo.add_edge(START, "entrada")
    grafo.add_conditional_edges(
        "entrada",
        _destino_entrada,
        {"supervisor": "supervisor", "limite_turnos": "limite_turnos"},
    )
    grafo.add_conditional_edges("supervisor", siguiente_destino, destinos)
    for rol in ROLES_GRAFO:
        grafo.add_conditional_edges(f"nodo_{rol}", siguiente_destino, destinos)
    grafo.add_edge("normalizar_rutas", "sintetizador")
    grafo.add_edge("sintetizador", "registrar_turno")
    grafo.add_conditional_edges(
        "registrar_turno",
        _debe_pausar,
        {"pausa_hitl": "pausa_hitl", "finalizar_turno": "finalizar_turno"},
    )
    grafo.add_conditional_edges(
        "pausa_hitl",
        _destino_decision_hitl,
        {"aceptar_plan": "aceptar_plan", "rechazar_plan": "rechazar_plan", "pausa_hitl": "pausa_hitl"},
    )
    grafo.add_edge("aceptar_plan", "sintetizador_aprobacion")
    grafo.add_edge("sintetizador_aprobacion", "finalizar_turno")
    grafo.add_edge("rechazar_plan", "nodo_rutas")
    grafo.add_edge("finalizar_turno", END)
    grafo.add_edge("limite_turnos", END)
    grafo.add_edge("limite_tools", END)

    saver = checkpointer if checkpointer is not None else InMemorySaver()
    return grafo.compile(checkpointer=saver)
