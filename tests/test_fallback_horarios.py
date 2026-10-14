"""Tests del fallback determinista del supervisor para horarios (spec 001, RF-16)."""
import pytest

from src.supervisor_reglas import PALABRAS_HORARIOS, elegir_rol_por_palabras


def test_palabras_horario():
    # RF-16: un mensaje con términos de horario se deriva a "horarios".
    assert elegir_rol_por_palabras("¿a qué hora cierra el metro?") == "horarios"
    assert elegir_rol_por_palabras("¿Cuál es el horario de la línea 1?") == "horarios"


@pytest.mark.parametrize("palabra", sorted(PALABRAS_HORARIOS))
def test_cada_palabra_clave(palabra):
    assert elegir_rol_por_palabras(f"Quiero saber {palabra} del autobús") == "horarios"


def test_sin_acentos_ni_mayusculas():
    assert elegir_rol_por_palabras("¿CUÁL ES LA ULTIMA SALIDA?") == "horarios"


def test_mensaje_sin_palabras_de_horario():
    # Otros mensajes no se derivan a horarios.
    assert elegir_rol_por_palabras("¿Qué zonas cubre el abono mensual?") is None
    assert elegir_rol_por_palabras("") is None
