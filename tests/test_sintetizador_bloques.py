"""Tests de T4 (spec 010, RF-13 a RF-16): el sintetizador añade los `bloques` de `planificar_ruta` que el LLM omita.

Sin LLM ni red: el modelo es un doble. Los avisos de la spec 009 siguen cubiertos en `test_sintetizador_avisos.py`.
"""
import json
import logging

from src.sintetizador import nodo_sintetizador, renderizar_respaldo
from tests.test_sintetizador_avisos import (
    ATRIBUCION, AVISO, BICI_OK, CLIMA_OK, estado, modelo_que_omite, resultado_ruta, sintetizar,
)

TEXTO_MODELO = "Tienes ruta en metro de unos 22 minutos."
OPCIONES = ("La dirección de origen «Legazpi» es ambigua. Opciones: 1) Legazpi, Plaza de Legazpi, Arganzuela; "
            "2) Legazpi, Arganzuela. Indica cuál es o concreta más.")
LINEA_CLIMA = f"Tiempo en el origen ahora: 16 °C, sin precipitación, viento 11 km/h (apto para exterior). {ATRIBUCION}"
PARRAFO_BICI = f"Alternativa en bici (BiciMAD): 18 min en total (Google Routes). Aviso: {AVISO}"
MOTIVO = "La alternativa en bici no se ofrece con mal tiempo (lluvia)."


def test_ambigua_opciones_visibles_aunque_el_modelo_las_omita():
    respuesta = sintetizar(resultado_ruta(estado="ambigua", bloques=[OPCIONES]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{OPCIONES}"                  # el texto del modelo primero, las opciones después


def test_bici_ok_bloque_visible():
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, bloques=[PARRAFO_BICI]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{PARRAFO_BICI}"
    assert respuesta.count(AVISO) == 1                                   # el aviso va dentro del bloque: no se repite


def test_motivo_visible():
    assert sintetizar(resultado_ruta(bloques=[MOTIVO])).endswith(f"\n\n{MOTIVO}")


def test_linea_de_clima_visible():
    respuesta = sintetizar(resultado_ruta(clima=CLIMA_OK, bloques=[LINEA_CLIMA]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{LINEA_CLIMA}"
    assert respuesta.count(ATRIBUCION) == 1


def test_varios_bloques_en_orden_y_despues_los_avisos():
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK, bloques=[LINEA_CLIMA, PARRAFO_BICI]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{LINEA_CLIMA}\n\n{PARRAFO_BICI}"   # los avisos ya estaban dentro de los bloques


def test_no_duplica_si_el_modelo_ya_lo_incluye():
    modelo = lambda contexto: f"Ruta de 22 min. {OPCIONES}"
    assert sintetizar(resultado_ruta(bloques=[OPCIONES]), modelo=modelo) == f"Ruta de 22 min. {OPCIONES}"
    solo_uno = sintetizar(resultado_ruta(bloques=[MOTIVO, OPCIONES]), modelo=lambda c: f"Ruta. {MOTIVO}")
    assert solo_uno == f"Ruta. {MOTIVO}\n\n{OPCIONES}"                   # solo se añade lo que falta


def test_aviso_dentro_del_bloque_no_se_repite():
    # El modelo omite todo: el bloque de bici ya trae el aviso de Google; no se añade otra vez.
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, bloques=[PARRAFO_BICI]))
    assert respuesta.count(AVISO) == 1
    # Si el modelo incluyó el aviso suelto, el bloque sí se añade (es otro texto), con el aviso dentro.
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, bloques=[PARRAFO_BICI]), modelo=lambda c: f"Ruta. {AVISO}")
    assert respuesta.endswith(PARRAFO_BICI)


def test_varias_rutas_sin_repetir_bloques():
    respuesta = sintetizar(resultado_ruta(bloques=[MOTIVO]), resultado_ruta(bloques=[MOTIVO, OPCIONES]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{MOTIVO}\n\n{OPCIONES}"


def test_resultado_ilegible_no_rompe_y_se_registra(caplog):
    caplog.set_level(logging.DEBUG)
    ilegible = {"especialista": "rutas", "tool": "planificar_ruta", "status": "error",
                "resultado": "ERROR: no se pudo ejecutar planificar_ruta. secreto-xyz", "args": {}}
    lista = {**ilegible, "resultado": json.dumps(["no", "es", "un", "objeto"])}
    respuesta = sintetizar(ilegible, lista, resultado_ruta(bloques=[MOTIVO]))
    assert respuesta == f"{TEXTO_MODELO}\n\n{MOTIVO}"                    # los demás resultados siguen funcionando
    assert "JSONDecodeError" in caplog.text and "TypeError" in caplog.text
    assert "secreto-xyz" not in caplog.text                              # solo el tipo del error, nunca el contenido


def test_bloques_mal_formados_se_ignoran():
    for bloques in ("texto suelto", 5, [None, 3, "", "  ", {"x": 1}], None):
        assert sintetizar(resultado_ruta(bloques=bloques)) == TEXTO_MODELO
    assert sintetizar(resultado_ruta(bloques=[None, MOTIVO])) == f"{TEXTO_MODELO}\n\n{MOTIVO}"


def test_lee_resultados_y_no_las_notas():
    bruto = json.dumps({"estado": "ambigua", "bloques": [OPCIONES]}, ensure_ascii=False)
    contexto = {"notas": [f"[rutas] {bruto}"], "resultados": [], "traza": []}
    assert nodo_sintetizador(contexto, modelo_que_omite)["respuesta"] == TEXTO_MODELO


def test_otras_herramientas_no_aportan_bloques():
    otro = {"especialista": "rag", "tool": "rag_ask", "status": "ok",
            "resultado": json.dumps({"bloques": [OPCIONES]}), "args": {}}
    assert sintetizar(otro) == TEXTO_MODELO


def test_respaldo_intacto():
    def modelo_roto(contexto):
        raise RuntimeError("proveedor caído")

    entrada = estado(resultado_ruta(estado="ambigua", bloques=[OPCIONES]))
    salida = nodo_sintetizador(entrada, modelo_roto)
    assert salida["respuesta"] == renderizar_respaldo(entrada)           # el respaldo vuelca los resultados, sin añadidos
    assert salida["respuesta"].startswith("No se ha podido sintetizar la respuesta automáticamente.")
    assert salida["log"] == ["Sintetizador: se ha usado el respaldo determinista."]
