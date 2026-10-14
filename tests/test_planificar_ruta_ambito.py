"""Tests del ámbito de cobertura de planificar_ruta (spec 004, RF-2 y RF-3). No usan API."""
import config

# Coordenadas (lat, lon) de referencia para comprobar la caja del ámbito.
PUERTA_DEL_SOL = (40.4169, -3.7035)
BARCELONA = (41.3874, 2.1686)


def test_ambito_definido_en_config():
    # RF-2: el ámbito vive en un único punto de configuración, como (lat_min, lon_min, lat_max, lon_max).
    lat_min, lon_min, lat_max, lon_max = config.AMBITO_COBERTURA
    assert lat_min < lat_max and lon_min < lon_max
    assert -90 <= lat_min and lat_max <= 90 and -180 <= lon_min and lon_max <= 180
    # Sanidad de la caja: contiene Puerta del Sol y no contiene otra ciudad española.
    assert lat_min <= PUERTA_DEL_SOL[0] <= lat_max and lon_min <= PUERTA_DEL_SOL[1] <= lon_max
    assert not (lat_min <= BARCELONA[0] <= lat_max and lon_min <= BARCELONA[1] <= lon_max)
