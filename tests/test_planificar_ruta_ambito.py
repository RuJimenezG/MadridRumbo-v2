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


def test_sol_dentro_barcelona_fuera_y_borde():
    # RF-3: Puerta del Sol está dentro, otra ciudad española fuera, y el límite exacto de la caja cuenta como dentro.
    from src.tools.planificar_ruta import dentro_de_ambito

    lat_min, lon_min, lat_max, lon_max = config.AMBITO_COBERTURA
    assert dentro_de_ambito(*PUERTA_DEL_SOL)
    assert not dentro_de_ambito(*BARCELONA)
    # Borde: esquinas y lados exactos dentro; un paso más allá, fuera.
    assert dentro_de_ambito(lat_min, lon_min) and dentro_de_ambito(lat_max, lon_max)
    assert not dentro_de_ambito(lat_max + 0.001, lon_max)
    assert not dentro_de_ambito(lat_min, lon_min - 0.001)


def test_homonimo_fuera_se_descarta_y_el_de_dentro_se_conserva():
    # RF-3: entre dos candidatos con el mismo nombre solo queda el que está dentro del ámbito.
    from src.tools.planificar_ruta import dentro_de_ambito

    candidatos = [{"nombre": "Calle Mayor (Barcelona)", "coords": BARCELONA},
                  {"nombre": "Calle Mayor (Madrid)", "coords": PUERTA_DEL_SOL}]
    dentro = [c["nombre"] for c in candidatos if dentro_de_ambito(*c["coords"])]
    assert dentro == ["Calle Mayor (Madrid)"]


def test_viewbox_longitud_primero():
    # RF-3: Nominatim espera x1,y1,x2,y2 (longitud primero); AMBITO_COBERTURA está en (lat, lon, lat, lon).
    from src.tools.planificar_ruta import viewbox_nominatim

    assert viewbox_nominatim((1, 2, 3, 4)) == "2,3,4,1"
    # Sin argumento usa el ámbito de config.py.
    lat_min, lon_min, lat_max, lon_max = config.AMBITO_COBERTURA
    assert viewbox_nominatim() == f"{lon_min},{lat_max},{lon_max},{lat_min}"
