"""Tests de T9 (spec 009, RF-12 y RF-24): el aviso de Google de la bici y la atribución a Open-Meteo sobreviven a la
síntesis, que es un LLM y puede omitirlos. Sin LLM ni red: el modelo es un doble. Archivo propio (no toca los tests de
`test_sintetizador.py`); el cambio en `src/sintetizador.py` pendiente de la confirmación de quien mantiene el grafo.
"""
import json

import pytest

import config
from src.sintetizador import nodo_sintetizador

AVISO = "Las rutas a pie y en bici están en fase beta y pueden carecer de aceras o carriles bici claros."
ATRIBUCION = f"{config.CLIMA_ATRIBUCION}."
CLIMA_OK = {"estado": "ok", "temperatura_c": 16.1, "precipitacion_mm": 0.0, "codigo": 3, "viento_kmh": 11.2,
            "apto": True, "motivos": [], "fuente": "Open-Meteo", "licencia": "CC BY 4.0"}
BICI_OK = {"estado": "ok", "motivo": None, "duracion_min": 18, "aviso": AVISO,
           "fuentes": {"estaciones": "EMT BiciMAD", "tiempos": "Google Routes"}}


def resultado_ruta(**campos):
    """Entrada de `resultados` tal como la deja el especialista de rutas (el JSON de la tool, en texto)."""
    bruto = {"estado": "ok", "mensaje": "De «Sol» a «Bernabéu»: 22 min.", **campos}
    return {"especialista": "rutas", "tool": "planificar_ruta", "status": "ok",
            "resultado": json.dumps(bruto, ensure_ascii=False), "args": {"origen": "Sol", "destino": "Bernabéu"}}


def estado(*resultados):
    return {"notas": ["[rutas] Ruta calculada."], "resultados": list(resultados), "traza": []}


def modelo_que_omite(contexto):
    return "Tienes ruta en metro de unos 22 minutos."


def sintetizar(*resultados, modelo=modelo_que_omite):
    return nodo_sintetizador(estado(*resultados), modelo)["respuesta"]


def test_avisos_obligatorios_sobreviven_a_la_sintesis():
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK))
    assert respuesta.startswith("Tienes ruta en metro de unos 22 minutos.")        # el texto del modelo va primero
    assert respuesta.count(AVISO) == 1 and respuesta.count(ATRIBUCION) == 1
    assert respuesta.endswith(ATRIBUCION) and respuesta.index(AVISO) < respuesta.index(ATRIBUCION)


def test_no_se_duplican_si_el_modelo_ya_los_incluye():
    def modelo(contexto):
        return f"Ruta de 22 min. {AVISO} {ATRIBUCION}"
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK), modelo=modelo)
    assert respuesta == f"Ruta de 22 min. {AVISO} {ATRIBUCION}"
    solo_aviso = sintetizar(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK), modelo=lambda c: f"Ruta. {AVISO}")
    assert solo_aviso.count(AVISO) == 1 and solo_aviso.count(ATRIBUCION) == 1


def test_sin_bici_ni_clima_la_respuesta_no_cambia():
    for resultados in ([resultado_ruta()], [], [{"especialista": "horarios", "tool": "rag_ask", "status": "ok",
                                                  "resultado": "Horario: hasta 01:30."}]):
        assert sintetizar(*resultados) == "Tienes ruta en metro de unos 22 minutos."


def test_solo_se_anade_lo_que_corresponde():
    atribucion = sintetizar(resultado_ruta(bici={"estado": "no_ofrecida", "motivo": None}, clima=CLIMA_OK))
    assert ATRIBUCION in atribucion and AVISO not in atribucion
    aviso = sintetizar(resultado_ruta(bici=BICI_OK, clima={"estado": "no_disponible"}))
    assert AVISO in aviso and "Open-Meteo" not in aviso
    for bici in ({"estado": "no_disponible", "motivo": "x", "aviso": AVISO}, {"estado": "ok", "aviso": ""},
                 {"estado": "ok"}):
        assert sintetizar(resultado_ruta(bici=bici)) == "Tienes ruta en metro de unos 22 minutos."


def test_el_aviso_de_google_se_copia_literal():
    bici = {**BICI_OK, "aviso": "Aviso distinto que mandó Google. Otra frase."}
    assert sintetizar(resultado_ruta(bici=bici)).endswith("\n\nAviso distinto que mandó Google. Otra frase.")


def test_varias_rutas_sin_repetir_avisos():
    respuesta = sintetizar(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK), resultado_ruta(bici=BICI_OK, clima=CLIMA_OK))
    assert respuesta.count(AVISO) == 1 and respuesta.count(ATRIBUCION) == 1


def test_resultado_como_dict_y_basura_no_rompen():
    como_dict = {"especialista": "rutas", "tool": "planificar_ruta", "status": "ok",
                 "resultado": {"estado": "ok", "bici": BICI_OK, "clima": CLIMA_OK}}
    assert AVISO in sintetizar(como_dict)
    basura = [{"tool": "planificar_ruta", "resultado": "no es JSON {"}, {"tool": "planificar_ruta", "resultado": "[1, 2]"},
              {"tool": "planificar_ruta", "resultado": '{"bici": "texto", "clima": 3}'}, {"tool": "planificar_ruta"},
              "texto suelto", None, 7]
    assert sintetizar(*basura) == "Tienes ruta en metro de unos 22 minutos."


def test_no_se_toman_avisos_de_otras_tools():
    otra = {"especialista": "horarios", "tool": "rag_ask", "status": "ok",
            "resultado": json.dumps({"bici": BICI_OK, "clima": CLIMA_OK})}
    assert sintetizar(otra) == "Tienes ruta en metro de unos 22 minutos."


def test_el_respaldo_determinista_no_cambia():
    def falla(contexto):
        raise RuntimeError("sin modelo")
    salida = nodo_sintetizador(estado(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK)), falla)
    assert salida["respuesta"].startswith("No se ha podido sintetizar la respuesta automáticamente.")
    assert salida["respuesta"].count(AVISO) == 1                                   # ya vuelca el JSON completo
    assert "log" not in salida
    assert "log" not in nodo_sintetizador(estado(resultado_ruta(bici=BICI_OK)), lambda c: "   ")  # respuesta vacía → respaldo


def test_el_modelo_recibe_el_mismo_contexto():
    recibido = []

    def modelo(contexto):
        recibido.append(contexto)
        return "Respuesta."
    nodo_sintetizador(estado(resultado_ruta(bici=BICI_OK, clima=CLIMA_OK)), modelo)
    assert set(recibido[0]) == {"notas", "resultados", "traza"}
