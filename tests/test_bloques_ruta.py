"""Tests de T2 y T3 (spec 010, RF-4 a RF-12): campo `bloques` de `planificar_ruta` y política del clima. Sin red.

`Escenario` simula Nominatim, Google, RAG, EMT y Open-Meteo; la alternativa real en bici se activa con `bici_real()`.
"""
import pytest

import config
from src.tools import bicimad, planificar_ruta as pr
from tests.dobles_ruta import (
    ATOCHA, BARCELONA, BERNABEU, EMT_ESTACIONES_OK, METEO_LLUVIA, SOL, Escenario, estacion_emt, nominatim,
)

PLAZA_MAYOR = nominatim("Plaza Mayor, Madrid", 40.4155, -3.7074)     # a unos 365 m de Sol: por debajo del mínimo de bici
NO_MADRID = nominatim("Calle X, Madrid", 40.41, -3.70, "Madrid", "ES-CT")   # dentro del ámbito, sin Madrid verificado
HORA_PEDIDA = "2026-10-15T09:00"                                      # posterior a la hora fija del Escenario


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def estaciones(*lista):
    return (200, {"code": "00", "description": "x", "datetime": "x", "data": list(lista)})


def ruta(**kw):
    return pr.planificar_ruta("Sol", "Bernabéu", **kw)


# --- T2: dirección problemática ---

def test_ambigua_lleva_las_opciones_en_bloques(esc):
    esc.nominatim = [[SOL, ATOCHA], [BERNABEU]]
    r = ruta()
    assert r["estado"] == "ambigua"
    assert len(r["bloques"]) == 1
    frase = r["bloques"][0]
    assert "es ambigua. Opciones: 1) Puerta del Sol, Madrid; 2) Estación de Atocha, Madrid." in frase
    assert frase in r["mensaje"] and "Salida" not in frase and "Título" not in frase      # sin la cabecera


def test_direccion_no_encontrada_y_fuera_cobertura_en_bloques(esc):
    esc.nominatim = [[], [BERNABEU]]
    r = ruta()
    assert r["estado"] == "direccion_no_encontrada"
    assert r["bloques"] == ["No he encontrado la dirección de origen «Sol». Indica una más precisa."]
    esc.nominatim = [[BARCELONA], [BERNABEU]]
    r = ruta()
    assert r["estado"] == "fuera_cobertura"
    assert r["bloques"] == ["La dirección de origen «Sol» está fuera de la cobertura de MadridRumbo."]
    # Dos extremos con problema: una frase por extremo, en orden.
    esc.nominatim = [[], [BARCELONA]]
    assert len(ruta()["bloques"]) == 2
    # Madrid sin verificar (RF-55 de la spec 004): también direccion_no_encontrada con su frase.
    esc.nominatim = [[NO_MADRID], [BERNABEU]]
    r = ruta()
    assert r["estado"] == "direccion_no_encontrada"
    assert len(r["bloques"]) == 1 and "No se pudo verificar que la dirección de origen" in r["bloques"][0]
    assert r["bloques"][0] in r["mensaje"]


# --- T2: ruta ok, bici y clima ---

def test_bici_ok_lleva_su_parrafo_y_el_clima(esc):
    esc.bici_real()
    r = ruta()
    assert r["bici"]["estado"] == "ok"
    clima, bici = r["bloques"]
    assert clima.startswith("Tiempo en el origen ahora:") and clima.endswith(f"{config.CLIMA_ATRIBUCION}.")
    assert bici.startswith("Alternativa en bici (BiciMAD):") and r["bici"]["aviso"] in bici
    assert clima in r["mensaje"] and r["mensaje"].endswith(bici)          # son los mismos textos del mensaje


FRASE_R1 = ("La alternativa en bici no se ofrece con hora de salida o de llegada pedida: "
            "la disponibilidad de bicis es la de ahora.")
FRASE_R2 = "La alternativa en bici no se ofrece: la distancia entre origen y destino queda fuera del rango de 1 a 6 km."


def _caso_r1(esc, monkeypatch):
    return ruta(hora_salida=HORA_PEDIDA), FRASE_R1


def _caso_r2(esc, monkeypatch):
    esc.nominatim = [[SOL], [PLAZA_MAYOR]]
    return ruta(), FRASE_R2


def _caso_mal_tiempo(esc, monkeypatch):
    esc.meteo = (200, METEO_LLUVIA)
    return ruta(), "La alternativa en bici no se ofrece con mal tiempo (lluvia)."


def _caso_sin_bicis(esc, monkeypatch):
    esc.emt_estaciones = estaciones(estacion_emt(2, "2 - Bernabeu", 40.4528, -3.6880, 1, 9))
    return ruta(), bicimad.FRASES_NO_OFRECIDA["sin_bicis_origen"]


def _caso_sin_huecos(esc, monkeypatch):
    esc.emt_estaciones = estaciones(estacion_emt(1, "1 - Sol", 40.4172, -3.7030, 6, 2),
                                    estacion_emt(2, "2 - Bernabeu", 40.4528, -3.6880, 1, 0))
    return ruta(), bicimad.FRASES_NO_OFRECIDA["sin_huecos_destino"]


def _caso_misma_estacion(esc, monkeypatch):
    monkeypatch.setattr(config, "BICI_ESTACION_RADIO_MAX_M", 10_000)
    esc.emt_estaciones = estaciones(estacion_emt(1, "1 - Medio", 40.4350, -3.6959, 3, 3))
    return ruta(), bicimad.FRASES_NO_OFRECIDA["misma_estacion"]


def _caso_emt_caida(esc, monkeypatch):
    esc.emt_login = TimeoutError("t")
    return ruta(), bicimad.FRASE_NO_DISPONIBLE


def _caso_google_bici_caido(esc, monkeypatch):
    esc.tramos_bici = [TimeoutError("t")]
    return ruta(), bicimad.FRASE_NO_DISPONIBLE


CASOS_MOTIVO = [_caso_r1, _caso_r2, _caso_mal_tiempo, _caso_sin_bicis, _caso_sin_huecos, _caso_misma_estacion,
                _caso_emt_caida, _caso_google_bici_caido]


@pytest.mark.parametrize("caso", CASOS_MOTIVO, ids=lambda c: c.__name__[6:])
def test_motivo_de_cada_causa_en_bloques(esc, monkeypatch, caso):
    esc.bici_real()
    r, frase = caso(esc, monkeypatch)
    assert r["estado"] == "ok" and r["bici"]["estado"] in ("no_ofrecida", "no_disponible")
    assert r["bloques"][-1] == frase                    # la línea de motivo cierra los bloques
    assert "Alternativa en bici (BiciMAD)" not in "".join(r["bloques"])


def test_mensaje_y_campos_existentes_no_cambian(monkeypatch):
    # R1/R2/R0: el motivo viaja solo en `bloques`; el `mensaje` y `bici` son los de siempre (spec 009).
    for caso in (_caso_r1, _caso_r2, _caso_mal_tiempo):
        esc = Escenario(monkeypatch)
        esc.bici_real()
        r, frase_caso = caso(esc, monkeypatch)
        assert r["bici"] == {"estado": "no_ofrecida", "motivo": None}
        assert frase_caso not in r["mensaje"] and "bici" not in r["mensaje"].lower().replace("bicis", "")
        assert set(r) - {"bloques", "clima"} == {"estado", "mensaje", "hora_salida", "titulo", "hora_llegada",
                                                 "salida_resultante", "origen", "destino", "ruta", "zona", "precio",
                                                 "bici"}
    # R3/R4 y no disponible: la frase sigue al final del `mensaje`, como hasta ahora.
    for caso in (_caso_sin_bicis, _caso_emt_caida):
        esc = Escenario(monkeypatch)
        esc.bici_real()
        r, frase = caso(esc, monkeypatch)
        assert r["mensaje"].endswith(frase)


@pytest.mark.parametrize("kw", [{"hora_salida": "ayer"}, {"hora_salida": "2026-10-14T09:00"}, {"origen": ""}])
def test_sin_bloques_no_hay_clave(esc, kw):
    args = {"origen": "Sol", "destino": "Bernabéu", **kw}
    r = pr.planificar_ruta(**args)
    assert r["estado"] != "ok" and "bloques" not in r


def test_sin_bloques_en_otros_estados_de_ruta(esc):
    esc.google = TimeoutError("t")
    r = ruta()
    assert r["estado"] == "ruta_no_calculada" and "bloques" not in r
    esc.nominatim = [[SOL], [SOL]]
    r = pr.planificar_ruta("Sol", "Sol")
    assert r["estado"] == "misma_ubicacion" and "bloques" not in r


# --- T3: política del clima (RF-9 a RF-12; revisa RF-23 y RF-25 de la spec 009) ---

AVISO_SIN_CLIMA = "No se pudo comprobar el tiempo; la alternativa en bici se ofrece sin esa comprobación."


def test_clima_caido_ofrece_bici_con_aviso(esc):
    esc.bici_real()
    esc.meteo = TimeoutError("t")
    r = ruta()
    assert config.CLIMA_SIN_DATO_AVISO == AVISO_SIN_CLIMA
    assert r["clima"] == {"estado": "no_disponible"} and r["bici"]["estado"] == "ok"
    aviso, bici = r["bloques"]
    assert aviso == AVISO_SIN_CLIMA and bici.startswith("Alternativa en bici (BiciMAD):")
    assert aviso not in r["mensaje"] and bici in r["mensaje"]            # el `mensaje` sigue sin línea de clima


def test_clima_caido_sin_less_walking(esc):
    esc.meteo = TimeoutError("t")
    ruta()
    assert esc.cuantas("google") == 1
    assert "routingPreference" not in esc.cuerpos_google[0]["transitPreferences"]


def test_clima_caido_y_bici_no_disponible_conviven_en_bloques(esc):
    esc.bici_real()
    esc.meteo, esc.emt_login = TimeoutError("t"), TimeoutError("t")
    assert ruta()["bloques"] == [AVISO_SIN_CLIMA, bicimad.FRASE_NO_DISPONIBLE]


def test_mal_tiempo_sigue_sin_bici(esc):
    esc.bici_real()
    esc.meteo = (200, METEO_LLUVIA)
    r = ruta()
    assert r["bici"] == {"estado": "no_ofrecida", "motivo": None} and esc.llamadas_bici == []
    assert esc.cuerpos_google[0]["transitPreferences"]["routingPreference"] == "LESS_WALKING"
    assert AVISO_SIN_CLIMA not in r["bloques"]


def test_hora_pedida_sin_clima_y_con_motivo(esc):
    esc.bici_real()
    r = ruta(hora_salida=HORA_PEDIDA)
    assert esc.llamadas_meteo == [] and "clima" not in r and esc.llamadas_bici == []
    assert r["bloques"] == [FRASE_R1]                                    # sin línea de clima ni aviso de clima caído


def test_log_de_clima_solo_tipo_y_reason(esc, caplog):
    import logging
    import urllib.error
    caplog.set_level(logging.DEBUG)
    esc.meteo = urllib.error.URLError("[Errno 11001] getaddrinfo failed")
    ruta()
    log = caplog.text
    assert "URLError" in log and "getaddrinfo failed" in log
    assert "CLAVE-DE-TEST" not in log and "latitude" not in log          # ni la clave ni la URL de la consulta
    caplog.clear()
    esc.nominatim, esc.meteo = [[SOL], [BERNABEU]], RuntimeError("secreto-xyz")
    ruta()
    assert "RuntimeError" in caplog.text and "secreto-xyz" not in caplog.text    # otras excepciones: solo el tipo


