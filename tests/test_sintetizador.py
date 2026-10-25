"""Pruebas del sintetizador anclado del grafo, sin proveedores externos."""
from src.sintetizador import nodo_sintetizador, renderizar_respaldo
from tests.dobles_grafo import SintetizadorFalso


def _estado(notas=None, resultados=None, traza=None):
    """Crea un estado mínimo con información ya obtenida por especialistas."""
    return {
        "notas": notas or [],
        "resultados": resultados or [],
        "traza": traza or [],
        "mensaje": "dato que no debe necesitar el sintetizador",
    }


def test_sintetizador_devuelve_una_respuesta_sencilla_en_espanol():
    """RF-5 y RF-20: integra resultados disponibles mediante el modelo inyectado."""
    modelo = SintetizadorFalso(["La línea 1 tiene servicio hasta la hora indicada."])

    salida = nodo_sintetizador(_estado(notas=["[horarios] Cierre: 01:30."]), modelo=modelo)

    assert salida == {"respuesta": "La línea 1 tiene servicio hasta la hora indicada."}
    assert modelo.llamadas == [
        {"notas": ["[horarios] Cierre: 01:30."], "resultados": [], "traza": []}
    ]


def test_sintetizador_recibe_la_informacion_parcial_y_sus_limitaciones():
    """RF-21 y RF-22: las fuentes obtenidas y la parte no disponible llegan ancladas."""
    modelo = SintetizadorFalso([
        "La zona está disponible, pero no se pudo obtener el precio del billete."
    ])
    estado = _estado(
        notas=["[rutas] Zona (RAG): B1."],
        traza=[
            {
                "tool": "planificar_ruta",
                "args": {},
                "status": "error",
                "preview": "ERROR: no se pudo determinar el precio.",
            }
        ],
    )

    salida = nodo_sintetizador(estado, modelo=modelo)

    assert "zona" in salida["respuesta"].lower()
    assert "no se pudo obtener el precio" in salida["respuesta"].lower()
    assert modelo.llamadas[0]["notas"] == estado["notas"]
    assert modelo.llamadas[0]["traza"] == estado["traza"]


def test_respaldo_conserva_abstencion_y_error_de_los_especialistas():
    """RF-17, RF-19 y RF-22: el texto determinista no pierde información disponible."""
    estado = _estado(
        notas=["[rag] No lo sé, no está en los documentos."],
        resultados=[{"especialista": "tarifas", "resultado": "Importe visible: 1,50 €."}],
        traza=[
            {
                "tool": "hora_actual",
                "args": {},
                "status": "error",
                "preview": "ERROR: no se pudo obtener la hora.",
            }
        ],
    )

    respuesta = renderizar_respaldo(estado)

    assert "No lo sé, no está en los documentos." in respuesta
    assert "Importe visible: 1,50 €." in respuesta
    assert "ERROR: no se pudo obtener la hora." in respuesta
    assert "parcial" in respuesta.lower()


def test_fallo_del_modelo_devuelve_aviso_y_el_respaldo_disponible():
    """RF-56: un error de síntesis no elimina los datos reunidos previamente."""
    estado = _estado(notas=["[auxiliar] Son las 17:58."], resultados=[])
    modelo = SintetizadorFalso([RuntimeError("fallo simulado")])

    salida = nodo_sintetizador(estado, modelo=modelo)

    assert "No se ha podido sintetizar" in salida["respuesta"]
    assert "Son las 17:58." in salida["respuesta"]
    assert "log" not in salida
