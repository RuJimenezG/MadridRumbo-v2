"""Recorridos del StateGraph multiagente con dobles, sin APIs externas."""
import json

import pytest

from src.estado import crear_estado_inicial
from src.graph import (
    ROLES_GRAFO,
    configuracion_hilo,
    crear_grafo,
    invocar_grafo,
    recuperar_estado,
    siguiente_destino,
)
from tests.dobles_grafo import EjecutorFalso, LLMFalso


def _especialistas_falsos(llamadas):
    """Crea nodos que registran el orden y no dependen de tools ni modelos reales."""
    def crear(rol):
        def nodo(estado):
            llamadas.append(rol)
            return {"notas": [f"[{rol}] resultado falso"]}
        return nodo

    return {rol: crear(rol) for rol in ROLES_GRAFO}


def _grafo_con_roles(roles, llamadas):
    """Compila un grafo con el supervisor y sintetizador completamente inyectados."""
    return crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": roles},
        especialistas=_especialistas_falsos(llamadas),
        modelo_sintetizador=lambda contexto: "Resumen sencillo de los resultados.",
    )


def test_grafo_declara_supervisor_cinco_especialistas_y_sintetizador():
    """RF-1: todos los nodos estáticos se compilan antes de procesar un turno."""
    grafo = _grafo_con_roles([], [])
    nombres = set(grafo.get_graph().nodes)

    assert {
        "supervisor",
        "nodo_rag",
        "nodo_horarios",
        "nodo_rutas",
        "nodo_auxiliar",
        "nodo_tarifas",
        "sintetizador",
    } <= nombres


def test_grafo_recorre_un_especialista_y_luego_sintetiza():
    """RF-2 y RF-5: una decisión válida consume su cola antes de la síntesis."""
    llamadas = []
    salida = invocar_grafo(
        _grafo_con_roles(["rag"], llamadas),
        crear_estado_inicial("Consulta documental CRTM."),
        "recorrido-un-especialista",
    )

    assert llamadas == ["rag"]
    assert salida["cola_roles"] == []
    assert salida["respuesta"] == "Resumen sencillo de los resultados."


def test_grafo_encadena_y_repite_el_mismo_especialista_en_orden():
    """RF-3: la cola permite cadenas y repeticiones sin crear aristas dinámicas."""
    llamadas = []
    salida = invocar_grafo(
        _grafo_con_roles(["rag", "auxiliar", "rag"], llamadas),
        crear_estado_inicial("Consulta compuesta."),
        "recorrido-repetido",
    )

    assert llamadas == ["rag", "auxiliar", "rag"]
    assert salida["notas"] == [
        "[rag] resultado falso",
        "[auxiliar] resultado falso",
        "[rag] resultado falso",
    ]


def test_grafo_acepta_finish_sin_ejecutar_especialistas():
    """RF-2: una cola vacía termina en el sintetizador sin llamar a una tool."""
    llamadas = []
    salida = invocar_grafo(
        _grafo_con_roles([], llamadas),
        crear_estado_inicial("Saluda."),
        "recorrido-finish",
    )

    assert llamadas == []
    assert salida["respuesta"] == "Resumen sencillo de los resultados."


@pytest.mark.parametrize(
    "modelo, categoria",
    [
        (lambda mensajes: {"roles": []}, "sin_fallback"),
        (lambda mensajes: "no es JSON", "json_invalido"),
    ],
)
def test_grafo_transporta_diagnostico_por_contexto_sin_persistirlo(modelo, categoria):
    """RF-10, RF-11 y RF-25: el contexto no entra en la salida ni checkpoint."""
    grafo = crear_grafo(
        modelo_supervisor=modelo,
        modelo_sintetizador=lambda contexto: "Resumen sencillo de los resultados.",
    )
    contexto = {"diagnostico_supervisor": None}

    salida = invocar_grafo(
        grafo,
        crear_estado_inicial("Consulta documental."),
        f"contexto-{categoria}",
        contexto=contexto,
    )

    assert contexto["diagnostico_supervisor"]["categoria"] == categoria
    assert "diagnostico_supervisor" not in salida
    assert salida["log"] == []
    assert "diagnostico_supervisor" not in recuperar_estado(grafo, f"contexto-{categoria}")


def test_selector_rechaza_un_rol_sin_arista_declarada():
    """RF-4: ningún nombre ajeno puede llegar a una arista del StateGraph."""
    with pytest.raises(ValueError, match="no permitido"):
        siguiente_destino({"cola_roles": ["borrar_todo"]})


def _grafo_con_tools(roles, modelos, ejecutor):
    """Crea el grafo real con dependencias de especialistas totalmente inyectadas."""
    return crear_grafo(
        modelo_supervisor=lambda mensajes: {"roles": roles},
        modelos_especialistas=modelos,
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Resumen de pruebas.",
    )


def test_grafo_encadena_rag_y_auxiliar_con_una_traza_por_tool():
    """RF-18 y RF-45: RAG precede a auxiliar y cada llamada se agrega una sola vez."""
    ejecutor = EjecutorFalso({"rag_ask": "Zona B1 según CRTM.", "hora_actual": "Son las 17:58."})
    modelos = {
        "rag": LLMFalso([
            {"tool": "rag_ask", "args": {"consulta": "zona CRTM"}},
            {"final": "La zona es B1."},
        ]),
        "auxiliar": LLMFalso([
            {"tool": "hora_actual", "args": {}},
            {"final": "Son las 17:58."},
        ]),
    }

    salida = invocar_grafo(
        _grafo_con_tools(["rag", "auxiliar"], modelos, ejecutor),
        crear_estado_inicial("¿Qué zona CRTM corresponde y qué hora es?"),
        "recorrido-rag-auxiliar",
    )

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["rag_ask", "hora_actual"]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["rag_ask", "hora_actual"]
    assert all(set(entrada) == {"tool", "args", "status", "preview"} for entrada in salida["traza"])
    assert [resultado["especialista"] for resultado in salida["resultados"]] == ["rag", "auxiliar"]


def test_grafo_encadena_tarifas_y_auxiliar_sin_calculadora_en_tarifas():
    """RF-43 y RF-46: describe la imagen antes de que auxiliar calcule el total."""
    ejecutor = EjecutorFalso({"describir_imagen": "Importe visible: 1,50 €.", "calculadora": "4,50"})
    modelos = {
        "tarifas": LLMFalso([
            {"tool": "describir_imagen", "args": {"pregunta": "importe"}},
            {"final": "La imagen muestra 1,50 €."},
        ]),
        "auxiliar": LLMFalso([
            {"tool": "calculadora", "args": {"expresion": "3*1,50"}},
            {"final": "El total es 4,50."},
        ]),
    }

    salida = invocar_grafo(
        _grafo_con_tools(["tarifas", "auxiliar"], modelos, ejecutor),
        crear_estado_inicial("Calcula el total de la imagen."),
        "recorrido-tarifas-auxiliar",
    )

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["describir_imagen", "calculadora"]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["describir_imagen", "calculadora"]
    assert all(resultado["especialista"] != "tarifas" or resultado["tool"] != "calculadora"
               for resultado in salida["resultados"])


def test_horarios_y_rutas_mantienen_sus_consultas_internas_sin_duplicar_rag():
    """RF-58 y RF-59: horarios usa su excepción RAG y rutas solo su tool exterior."""
    ruta = json.dumps({"estado": "ok", "ruta": {"duracion_min": 12}})
    ejecutor = EjecutorFalso(
        {"hora_actual": "Son las 17:58.", "rag_ask": "Horario: hasta 01:30.", "planificar_ruta": ruta}
    )
    modelos = {
        "horarios": LLMFalso([
            {"tool": "hora_actual", "args": {}},
            {"tool": "rag_ask", "args": {"consulta": "horario metro"}},
            {"final": "El metro cierra a la 01:30."},
        ]),
        "rutas": LLMFalso([
            {"tool": "planificar_ruta", "args": {"origen": "Atocha", "destino": "Sol"}},
            {"final": "Ruta disponible."},
        ]),
    }

    salida = invocar_grafo(
        _grafo_con_tools(["horarios", "rutas"], modelos, ejecutor),
        crear_estado_inicial("¿A qué hora cierra el metro y cómo llego de Atocha a Sol?"),
        "recorrido-horarios-rutas",
    )

    assert [nombre for nombre, _ in ejecutor.llamadas] == ["hora_actual", "rag_ask", "planificar_ruta"]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["hora_actual", "rag_ask", "planificar_ruta"]
    assert sum(nombre == "rag_ask" for nombre, _ in ejecutor.llamadas) == 1


@pytest.mark.parametrize(
    "mensaje",
    [
        "QUIERO IR DE Átocha A Sol, por favor.",
        "Necesito, ir de Atocha a Sol!!!",
        "Voy de Atocha a Sol; dime cómo.",
    ],
)
def test_fallback_de_ruta_valida_planifica_y_se_pausa_para_hitl(mensaje):
    """RF-17 a RF-20: el fallback llega a rutas, tool y pausa de aprobación."""
    ruta = {
        "estado": "ok",
        "origen": {"direccion": "Estación de Atocha, Madrid"},
        "destino": {"direccion": "Puerta del Sol, Madrid"},
        "ruta": {"duracion_min": 12, "tramos": [{"modo": "SUBWAY", "linea": "1"}]},
    }
    llm_rutas = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Atocha", "destino": "Sol"}},
        {"final": "Ruta disponible para revisión."},
    ])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(ruta, ensure_ascii=False)})

    def proveedor_no_disponible(_mensajes):
        raise RuntimeError("proveedor no disponible")

    grafo = crear_grafo(
        modelo_supervisor=proveedor_no_disponible,
        modelos_especialistas={"rutas": llm_rutas},
        ejecutar=ejecutor,
        modelo_sintetizador=lambda contexto: "Ruta preparada para aprobación.",
    )
    contexto = {"diagnostico_supervisor": None}
    thread_id = f"fallback-rutas-{mensaje[:8]}"

    salida = invocar_grafo(
        grafo,
        crear_estado_inicial(mensaje),
        thread_id,
        contexto=contexto,
    )
    snapshot = grafo.get_state(configuracion_hilo(thread_id))

    assert contexto["diagnostico_supervisor"]["categoria"] == "proveedor"
    assert len(llm_rutas.llamadas) == 2
    assert ejecutor.llamadas == [("planificar_ruta", {"origen": "Atocha", "destino": "Sol"})]
    assert [entrada["tool"] for entrada in salida["traza"]] == ["planificar_ruta"]
    assert salida["planes_pendientes"][0]["id"] == "ruta-1"
    assert salida["hitl_pendiente"] is True
    assert salida["done"] is False
    assert snapshot.next == ("pausa_hitl",)
