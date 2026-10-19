"""Tests de la fuente de hora (spec 004, RF-14). No usan API."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
from src.reloj import ahora


def test_ahora_en_zona_madrid():
    # RF-14: ahora() devuelve un datetime con la zona horaria configurada y es el instante actual.
    antes = datetime.now(ZoneInfo(config.ZONA_HORARIA))
    valor = ahora()
    assert valor.tzinfo is not None
    assert valor.tzinfo.key == config.ZONA_HORARIA == "Europe/Madrid"
    assert abs(valor - antes) < timedelta(seconds=5)
