"""Spec 010 (corrección): el sintetizador solo fuerza los `bloques` y avisos de los resultados del turno actual.

`resultados` acumula todos los turnos de la conversación; cada entrada lleva `turno` (nº de mensajes de la persona
en `historial` cuando se produjo). Sin red ni LLM: modelo falso y grafo con dobles.
"""
import json

from src.graph import configuracion_hilo, crear_grafo, invocar_grafo
from src.sintetizador import nodo_sintetizador
from tests.dobles_grafo import EjecutorFalso, LLMFalso
from tests.test_sintetizador_avisos import AVISO, BICI_OK, modelo_que_omite, resultado_ruta
from tests.test_sintetizador_bloques import MOTIVO, OPCIONES, PARRAFO_BICI, TEXTO_MODELO


def usuario(n):
    return [{"role": "user", "content": f"mensaje {i}"} for i in range(1, n + 1)]


def sintetizar(historial, *resultados):
    estado = {"notas": [], "traza": [], "historial": historial, "resultados": list(resultados)}
    return nodo_sintetizador(estado, modelo_que_omite)["respuesta"]


def de_turno(turno, **campos):
    return {**resultado_ruta(**campos), "turno": turno}


def test_ambigua_resuelta_en_el_turno_anterior_no_reaparece():
    respuesta = sintetizar(usuario(2), de_turno(1, estado="ambigua", bloques=[OPCIONES]), de_turno(2, bloques=[MOTIVO]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{MOTIVO}" and OPCIONES not in respuesta


def test_dos_resultados_del_mismo_turno_se_incluyen_los_dos():
    respuesta = sintetizar(usuario(2), de_turno(1, bloques=[OPCIONES]),
                           de_turno(2, bloques=[MOTIVO]), de_turno(2, bloques=[PARRAFO_BICI], bici=BICI_OK))
    assert respuesta == f"{TEXTO_MODELO}\n\n{MOTIVO}\n\n{PARRAFO_BICI}"


def test_resultado_antiguo_con_bici_no_se_repite():
    antiguo = de_turno(1, bici=BICI_OK, bloques=[PARRAFO_BICI])
    respuesta = sintetizar(usuario(2), antiguo, de_turno(2, bloques=[MOTIVO]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{MOTIVO}" and AVISO not in respuesta     # ni el bloque ni el aviso de Google


def test_el_turno_actual_se_cuenta_por_mensajes_de_la_persona():
    # Las respuestas del asistente en `historial` (si las hubiera) no cuentan como turno.
    historial = usuario(1) + [{"role": "assistant", "content": "hola"}] + usuario(1)
    assert sintetizar(historial, de_turno(1, bloques=[OPCIONES]), de_turno(2, bloques=[MOTIVO])).endswith(f"\n\n{MOTIVO}")


def test_sin_marca_de_turno_se_incluye_como_hasta_ahora():
    # Resultados sin `turno` (conversaciones guardadas antes de este cambio, dobles de otros tests) no se filtran.
    assert sintetizar(usuario(2), resultado_ruta(bloques=[MOTIVO])).endswith(f"\n\n{MOTIVO}")


def test_sin_historial_no_se_filtra_nada():
    estado = {"notas": [], "traza": [], "resultados": [de_turno(1, bloques=[OPCIONES])]}
    assert nodo_sintetizador(estado, modelo_que_omite)["respuesta"].endswith(f"\n\n{OPCIONES}")


# --- grafo completo: dos turnos de la misma conversación ---

def _ruta(estado, **campos):
    return json.dumps({"estado": estado, "mensaje": estado, **campos}, ensure_ascii=False)


def test_en_el_grafo_las_opciones_del_primer_turno_no_salen_en_el_segundo():
    ejecutor = EjecutorFalso({"planificar_ruta": [
        _ruta("ambigua", bloques=[OPCIONES]),
        _ruta("ruta_no_calculada", bloques=["No se pudo calcular la ruta."]),
    ]})
    llm = LLMFalso([
        {"tool": "planificar_ruta", "args": {"origen": "Sol", "destino": "Bernabéu"}}, {"final": "Elige una opción."},
        {"tool": "planificar_ruta", "args": {"origen": "Sol", "destino": "Bernabéu", "opcion_origen": 2}},
        {"final": "Sin ruta."},
    ])
    grafo = crear_grafo(modelo_supervisor=lambda m: {"roles": ["rutas"]}, modelos_especialistas={"rutas": llm},
                        ejecutar=ejecutor, modelo_sintetizador=lambda estado: "Resumen.")

    def turno(mensaje):
        return invocar_grafo(grafo, {"mensaje": mensaje, "tools_turno": 0, "limite_tools_alcanzado": False,
                                     "turno_contabilizado": False, "limite_turnos": False}, "dos-turnos")

    primero = turno("De Sol a Bernabéu")
    assert primero["respuesta"] == f"Resumen.\n\n{OPCIONES}"
    segundo = turno("La opción 2")
    assert segundo["respuesta"] == "Resumen.\n\nNo se pudo calcular la ruta."
    assert OPCIONES not in segundo["respuesta"]
    assert [r["turno"] for r in segundo["resultados"]] == [1, 2]                  # cada resultado lleva su turno
    assert grafo.get_state(configuracion_hilo("dos-turnos")).values["respuesta"] == segundo["respuesta"]
