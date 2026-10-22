"""Spec 010, T16 (RF-44): candidatos que son el mismo lugar con otra etiqueta no hacen ambigua la dirección. Sin red.

Casos reales: «Sol» devolvía dos «Puerta del Sol» idénticas (a más de 100 m) y «Rivas» devolvía «Rivas» y
«Rivas-Vaciamadrid» (el mismo municipio).
"""
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import ATOCHA, SOL, nominatim
from tests.test_candidatos_madrid import GALAPAGOS, cand

SOL_LEJOS = nominatim("Puerta del Sol, Madrid", 40.4180, -3.7060)            # mismo texto, a unos 250 m
SOL_MAYUS = nominatim("PUERTA  DEL SOL, Madrid", 40.4190, -3.7080)           # mismo texto salvo mayúsculas y espacios
RIVAS = nominatim("Rivas, Rivas-Vaciamadrid, Comunidad de Madrid, España", 40.3530, -3.5400, "Rivas-Vaciamadrid")
RIVAS_VACIA = nominatim("Rivas-Vaciamadrid, Comunidad de Madrid, España", 40.3260, -3.5180, "Rivas-Vaciamadrid")
CALLE_RIVAS = nominatim("Calle de Rivas, Rivas-Vaciamadrid, España", 40.3400, -3.5300, "Rivas-Vaciamadrid")
RIVAS_OTRO = nominatim("Rivas, Otro Pueblo, España", 40.5, -3.6, "Otro Pueblo")


def test_direcciones_identicas_son_un_lugar_aunque_esten_lejos():
    c = pr.clasificar_candidatos([cand(SOL), cand(SOL_LEJOS), cand(SOL_MAYUS)])
    assert c["estado"] == "ok" and c["elegido"]["lat"] == 40.4169       # se queda el primero (mejor clasificado)


def test_la_etiqueta_corta_del_mismo_municipio_es_el_mismo_lugar():
    c = pr.clasificar_candidatos([cand(RIVAS), cand(RIVAS_VACIA)])
    assert c["estado"] == "ok" and c["elegido"]["direccion"].startswith("Rivas, ")


def test_una_calle_del_municipio_no_es_el_municipio():
    c = pr.clasificar_candidatos([cand(RIVAS_VACIA), cand(CALLE_RIVAS)])
    assert c["estado"] == "ambigua" and len(c["candidatos"]) == 2


def test_mismo_nombre_en_otro_municipio_no_se_fusiona():
    a, b = cand(RIVAS_VACIA), cand(RIVAS_OTRO)
    assert not pr.mismo_lugar(a, b) and not pr.mismo_lugar(b, a)


def test_lugares_distintos_siguen_siendo_ambiguos():
    c = pr.clasificar_candidatos([cand(SOL), cand(SOL_LEJOS), cand(ATOCHA)])
    assert c["estado"] == "ambigua"
    assert [x["direccion"] for x in c["candidatos"]] == ["Puerta del Sol, Madrid", "Estación de Atocha, Madrid"]


def test_tras_filtrar_madrid_y_deduplicar_queda_uno_y_no_es_ambigua():
    c = pr.clasificar_candidatos([cand(GALAPAGOS), cand(SOL), cand(SOL_LEJOS)])
    assert c["estado"] == "ok" and c["elegido"]["direccion"] == "Puerta del Sol, Madrid"
