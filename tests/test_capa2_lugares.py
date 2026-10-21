"""Tests de T6 (spec 010, RF-19 a RF-21): capa 2 de ambigüedad en la herramienta. Sin red.

`texto_alternativo_*` se geocodifica con Nominatim y la verificación de Madrid (+1 llamada por extremo, ≤ 4 en total);
`probable_*` marca que la `opcion_*` fue una elección automática. La «opción usada» también va en `bloques`.
"""
import json
from urllib.parse import parse_qs, urlparse

import pytest

from src.tools import planificar_ruta as pr
from tests.dobles_ruta import ATOCHA, BERNABEU, SOL, Escenario, nominatim

NO_MADRID = nominatim("Calle X, Madrid", 40.41, -3.70, "Madrid", "ES-CT")   # dentro del ámbito, sin Madrid verificado


@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def aviso_alternativo(rol, texto, alternativo, direccion):
    return (f"Para el {rol} («{texto}») no se encontró una dirección válida; se usó «{alternativo}»: {direccion}. "
            "Si no es la que querías, indica una dirección más precisa.")


# --- texto_alternativo_origen / destino ---

def test_alternativo_resuelve_un_extremo_sin_candidatos(esc):
    esc.nominatim = [[], [SOL], [BERNABEU]]              # origen sin candidatos, su alternativo y el destino
    r = pr.planificar_ruta("Sol raro", "Bernabéu", texto_alternativo_origen="Puerta del Sol")
    frase = aviso_alternativo("origen", "Sol raro", "Puerta del Sol", "Puerta del Sol, Madrid")
    assert r["estado"] == "ok" and r["origen"]["direccion"] == "Puerta del Sol, Madrid"
    assert esc.cuantas("nominatim") == 3                  # +1 llamada por el alternativo
    assert frase in r["mensaje"] and r["bloques"][-1] == frase


def test_alternativo_en_los_dos_extremos_como_mucho_4_llamadas(esc):
    esc.nominatim = [[], [SOL], [], [BERNABEU]]
    r = pr.planificar_ruta("x", "y", texto_alternativo_origen="Puerta del Sol", texto_alternativo_destino="Bernabéu")
    assert r["estado"] == "ok" and esc.cuantas("nominatim") == 4
    assert r["bloques"][-2:] == [aviso_alternativo("origen", "x", "Puerta del Sol", "Puerta del Sol, Madrid"),
                                 aviso_alternativo("destino", "y", "Bernabéu", "Estadio Santiago Bernabéu, Madrid")]


def test_si_el_alternativo_tampoco_resuelve_error_sin_mas_intentos(esc):
    esc.nominatim = [[], [], [], []]
    r = pr.planificar_ruta("x", "y", texto_alternativo_origen="a", texto_alternativo_destino="b")
    assert r["estado"] == "direccion_no_encontrada" and esc.cuantas("nominatim") == 4     # nunca más de 4
    assert esc.cuantas("google") == 0 and esc.cuantas("rag") == 0
    assert len(r["bloques"]) == 2 and "No he encontrado la dirección de origen «x»" in r["bloques"][0]


@pytest.mark.parametrize("candidatos", [[NO_MADRID], [SOL, ATOCHA]], ids=["sin_madrid_verificado", "ambiguo"])
def test_alternativo_no_verificado_se_descarta_con_el_error_original(esc, candidatos):
    esc.nominatim = [[], candidatos, [BERNABEU]]
    r = pr.planificar_ruta("x", "Bernabéu", texto_alternativo_origen="alt")
    assert r["estado"] == "direccion_no_encontrada" and esc.cuantas("nominatim") == 3
    assert r["bloques"] == ["No he encontrado la dirección de origen «x». Indica una más precisa."]
    assert esc.cuantas("google") == 0 and esc.cuantas("rag") == 0


def test_alternativo_fuera_del_ambito_se_descarta(esc):
    from tests.dobles_ruta import BARCELONA
    esc.nominatim = [[], [BARCELONA], [BERNABEU]]
    r = pr.planificar_ruta("x", "Bernabéu", texto_alternativo_origen="alt")
    assert r["estado"] == "direccion_no_encontrada" and esc.cuantas("nominatim") == 3


def test_fallo_de_nominatim_en_el_alternativo_detiene_todo(esc):
    esc.nominatim = [[], TimeoutError("t")]
    r = pr.planificar_ruta("x", "Bernabéu", texto_alternativo_origen="alt")
    assert r["estado"] == "geocodificacion_fallida" and esc.cuantas("nominatim") == 2


def test_el_alternativo_solo_se_usa_si_el_extremo_no_se_resolvio(esc):
    r = pr.planificar_ruta("Sol", "Bernabéu", texto_alternativo_origen="otro", texto_alternativo_destino="otro")
    assert r["estado"] == "ok" and esc.cuantas("nominatim") == 2 and "no se encontró" not in r["mensaje"]


@pytest.mark.parametrize("alternativo", ["", "   ", None, 5, ["a"]])
def test_alternativo_vacio_o_no_texto_se_ignora(esc, alternativo):
    esc.nominatim = [[], [BERNABEU]]
    r = pr.planificar_ruta("x", "Bernabéu", texto_alternativo_origen=alternativo)
    assert r["estado"] == "direccion_no_encontrada" and esc.cuantas("nominatim") == 2


def test_alternativo_pasa_por_la_normalizacion_de_prefijos(monkeypatch):
    esc = Escenario(monkeypatch)
    q = []
    original = pr._http_json

    def espia(url, **kw):
        if url.startswith("https://nominatim"):
            q.append(parse_qs(urlparse(url).query)["q"][0])
        return original(url, **kw)

    monkeypatch.setattr(pr, "_http_json", espia)
    esc.nominatim = [[], [SOL], [BERNABEU]]
    pr.planificar_ruta("x", "Bernabéu", texto_alternativo_origen="Metro Sol")
    assert q == ["x", "Sol", "Bernabéu"]


def test_los_parametros_nuevos_llegan_por_la_capa_de_la_allowlist(esc):
    esc.nominatim = [[], [SOL], [BERNABEU]]
    r = json.loads(pr.planificar_ruta_texto(origen="x", destino="Bernabéu", texto_alternativo_origen="Sol",
                                            probable_origen=True))
    assert r["estado"] == "ok" and esc.cuantas("nominatim") == 3


# --- probable_origen / probable_destino y «opción usada» en bloques ---

def test_opcion_usada_va_en_bloques(esc):
    esc.nominatim = [[SOL, ATOCHA], [BERNABEU]]
    r = pr.planificar_ruta("Sol", "Bernabéu", opcion_origen=2)
    frase = ("Para el origen («Sol») se usó la opción 2: Estación de Atocha, Madrid. "
             "Si no es la que querías, indica otra opción (1 a 2) o una dirección más precisa.")
    assert r["estado"] == "ok" and frase in r["mensaje"] and r["bloques"][-1] == frase


def test_probable_marca_la_eleccion_automatica_y_como_corregirla(esc):
    esc.nominatim = [[SOL, ATOCHA], [BERNABEU]]
    r = pr.planificar_ruta("Sol", "Bernabéu", opcion_origen=2, probable_origen=True)
    frase = ("Elección automática: para el origen («Sol») se usó la opción 2: Estación de Atocha, Madrid. "
             "Si no es la que querías, indica otra opción (1 a 2) o una dirección más precisa.")
    assert frase in r["mensaje"] and r["bloques"][-1] == frase


@pytest.mark.parametrize("probable", [None, False, "sí", 1])
def test_probable_solo_cuenta_si_es_verdadero(esc, probable):
    esc.nominatim = [[SOL, ATOCHA], [BERNABEU]]
    r = pr.planificar_ruta("Sol", "Bernabéu", opcion_origen=2, probable_origen=probable)
    assert "Elección automática" not in r["mensaje"]


def test_probable_sin_opcion_se_ignora(esc):
    r = pr.planificar_ruta("Sol", "Bernabéu", probable_origen=True, probable_destino=True)
    assert r["estado"] == "ok" and "Elección automática" not in r["mensaje"]
    assert not any("opción" in b for b in r["bloques"])


def test_la_opcion_usada_acompana_a_un_error_del_otro_extremo(esc):
    esc.nominatim = [[SOL, ATOCHA], []]
    r = pr.planificar_ruta("Sol", "nada", opcion_origen=1, probable_origen=True)
    assert r["estado"] == "direccion_no_encontrada"
    assert r["bloques"][0].startswith("No he encontrado la dirección de destino")
    assert r["bloques"][1].startswith("Elección automática: para el origen («Sol») se usó la opción 1")
