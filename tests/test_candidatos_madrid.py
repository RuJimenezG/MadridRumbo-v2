"""Spec 010 (corrección): las opciones de una ambigua y la elección solo incluyen candidatos de la Comunidad de Madrid.

Caso real: «Puerta del Sol» ofrecía como opción 2 «Puerta del Sol, Galápagos, Guadalajara»: está dentro de la caja de
cobertura (`dentro_de_ambito`) pero no en la Comunidad de Madrid, y elegirla acababa en «no se pudo verificar». Sin red.
"""
import pytest

from src.tools import planificar_ruta as pr
from tests.dobles_ruta import ATOCHA, BERNABEU, SOL, Escenario, nominatim

GALAPAGOS = nominatim("Puerta del Sol, Galápagos, Guadalajara, Castilla-La Mancha", 40.84, -3.15, "Galápagos", "ES-CM")
TOLEDO = nominatim("Puerta del Sol, Toledo, Castilla-La Mancha", 39.86, -4.02, "Toledo", "ES-CM")
SIN_DATOS = {"display_name": "Sitio sin comunidad", "lat": "40.5", "lon": "-3.5", "address": {"city": "Algo"}}


def cand(raw):
    """Candidato tal como lo deja `geocodificar` (sin red ni esperas)."""
    lugar = raw["address"]
    return {"direccion": raw["display_name"], "lat": float(raw["lat"]), "lon": float(raw["lon"]),
            "municipio": lugar.get("city"), "region": lugar.get("state"), "iso": lugar.get("ISO3166-2-lvl4")}


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def test_el_candidato_de_otra_comunidad_no_entra_en_la_lista():
    c = pr.clasificar_candidatos([cand(SOL), cand(GALAPAGOS), cand(ATOCHA)])
    assert c["estado"] == "ambigua"
    assert [x["direccion"] for x in c["candidatos"]] == ["Puerta del Sol, Madrid", "Estación de Atocha, Madrid"]


def test_un_solo_candidato_de_madrid_se_elige_sin_preguntar():
    c = pr.clasificar_candidatos([cand(GALAPAGOS), cand(SOL), cand(TOLEDO)])
    assert c["estado"] == "ok" and c["elegido"]["direccion"] == "Puerta del Sol, Madrid"


def test_un_unico_candidato_fuera_de_madrid_sigue_dando_el_error_de_verificacion(esc):
    # RF-55 de la spec 004: no se descarta antes; lo rechaza la verificación con su mensaje.
    esc.nominatim = [[GALAPAGOS], [BERNABEU]]
    r = pr.planificar_ruta("Puerta del Sol", "Bernabéu")
    assert r["estado"] == "direccion_no_encontrada" and "No se pudo verificar que la dirección de origen" in r["mensaje"]


def test_sin_ningun_candidato_verificable_la_lista_no_cambia():
    # Sin datos de comunidad en ninguno no hay con qué filtrar: se conserva el comportamiento anterior.
    c = pr.clasificar_candidatos([cand(SIN_DATOS), cand(GALAPAGOS)])
    assert c["estado"] == "ambigua" and len(c["candidatos"]) == 2


def test_la_ambigua_del_flujo_no_muestra_candidatos_de_fuera(esc):
    esc.nominatim = [[SOL, GALAPAGOS, ATOCHA], [BERNABEU]]
    r = pr.planificar_ruta("Puerta del Sol", "Bernabéu")
    assert r["estado"] == "ambigua"
    assert "Galápagos" not in r["mensaje"] and all("Galápagos" not in b for b in r["bloques"])
    assert r["candidatos"]["origen"] == [{"direccion": "Puerta del Sol, Madrid"}, {"direccion": "Estación de Atocha, Madrid"}]


def test_elegir_la_opcion_2_da_un_candidato_de_madrid(esc):
    esc.nominatim = [[SOL, GALAPAGOS, ATOCHA], [BERNABEU]]
    r = pr.planificar_ruta("Puerta del Sol", "Bernabéu", opcion_origen=2)
    assert r["estado"] == "ok" and r["origen"]["direccion"] == "Estación de Atocha, Madrid"


def test_antes_elegir_la_opcion_de_fuera_acababa_en_error(esc):
    # Con un solo candidato de Madrid y otro de fuera, ya no hay opción 2: se resuelve a Madrid directamente.
    esc.nominatim = [[GALAPAGOS, SOL], [BERNABEU]]
    r = pr.planificar_ruta("Puerta del Sol", "Bernabéu", opcion_origen=2)
    assert r["estado"] == "ok" and r["origen"]["direccion"] == "Puerta del Sol, Madrid"
    assert "se usó la opción" not in r["mensaje"]          # no hubo ambigüedad que resolver
