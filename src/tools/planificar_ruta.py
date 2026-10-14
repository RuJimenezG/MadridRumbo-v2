"""Tool planificar_ruta (spec 004): ruta en transporte público CRTM con zona y precio del RAG.

De momento solo contiene las funciones puras del ámbito de cobertura.
"""
import config


def dentro_de_ambito(lat: float, lon: float, ambito: tuple | None = None) -> bool:
    """Indica si un punto está dentro de la caja de cobertura (los límites cuentan como dentro)."""
    lat_min, lon_min, lat_max, lon_max = ambito or config.AMBITO_COBERTURA
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def viewbox_nominatim(ambito: tuple | None = None) -> str:
    """Convierte el ámbito (lat_min, lon_min, lat_max, lon_max) al `viewbox` de Nominatim.

    Nominatim espera x1,y1,x2,y2 con la longitud primero: esquina superior izquierda
    (lon_min, lat_max) e inferior derecha (lon_max, lat_min).
    """
    lat_min, lon_min, lat_max, lon_max = ambito or config.AMBITO_COBERTURA
    return f"{lon_min},{lat_max},{lon_max},{lat_min}"
