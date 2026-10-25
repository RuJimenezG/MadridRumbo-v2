"""Tests de la tool describir_imagen (spec 002, RF-1 a RF-8). No llaman a ningún modelo."""
import pytest

import config
from src.tools.describir_imagen import describir_imagen

SIN_TEXTO = "No hay texto legible en la imagen."


class ClienteFalso:
    """Sustituye al cliente de visión: devuelve un texto fijo y cuenta las llamadas."""

    def __init__(self, respuesta="Cartel: Billete sencillo 1,50 €", error=None):
        self.respuesta = respuesta
        self.error = error
        self.llamadas = []

    def generar(self, imagen_bytes, mime, prompt):
        self.llamadas.append({"bytes": imagen_bytes, "mime": mime, "prompt": prompt})
        if self.error:
            raise self.error
        return self.respuesta


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    """Carpeta de imágenes autorizada temporal, con una imagen demo mínima."""
    imagenes = tmp_path / "assets"
    imagenes.mkdir()
    (imagenes / "imagen_demo.jpg").write_bytes(b"\xff\xd8\xff fake jpg")
    monkeypatch.setattr(config, "IMAGENES_DIR", imagenes)
    monkeypatch.setattr(config, "IMAGEN_DEMO", "imagen_demo.jpg")
    return imagenes


def test_describe_imagen(carpeta):
    # RF-1: devuelve el texto del modelo y le pasa los bytes y el tipo de la imagen.
    cliente = ClienteFalso()
    (carpeta / "cartel.png").write_bytes(b"\x89PNG fake")
    texto = describir_imagen("cartel.png", cliente=cliente)
    assert texto == "Cartel: Billete sencillo 1,50 €"
    assert cliente.llamadas[0]["bytes"] == b"\x89PNG fake"
    assert cliente.llamadas[0]["mime"] == "image/png"
    # El prompt manda transcribir solo lo visible (RF-1 y RF-8).
    assert "no inventes" in cliente.llamadas[0]["prompt"].lower()


def test_pregunta_en_prompt(carpeta):
    # RF-2: la pregunta opcional llega al modelo.
    cliente = ClienteFalso()
    describir_imagen("imagen_demo.jpg", "¿Cuánto cuesta el abono joven?", cliente=cliente)
    assert "¿Cuánto cuesta el abono joven?" in cliente.llamadas[0]["prompt"]


def test_imagen_por_defecto(carpeta):
    # RF-3: sin ruta se usa la imagen demo configurada.
    cliente = ClienteFalso()
    describir_imagen(cliente=cliente)
    assert cliente.llamadas[0]["bytes"] == b"\xff\xd8\xff fake jpg"
    assert cliente.llamadas[0]["mime"] == "image/jpeg"


def test_no_existe(carpeta):
    # RF-4: archivo inexistente -> error y sin llamar al modelo.
    cliente = ClienteFalso()
    texto = describir_imagen("no_existe.png", cliente=cliente)
    assert texto.startswith("ERROR:") and "no existe" in texto
    assert cliente.llamadas == []


def test_formato_no_admitido(carpeta):
    # RF-4: solo JPG, JPEG y PNG.
    (carpeta / "animacion.gif").write_bytes(b"GIF89a")
    cliente = ClienteFalso()
    texto = describir_imagen("animacion.gif", cliente=cliente)
    assert texto.startswith("ERROR:") and "formato" in texto
    assert cliente.llamadas == []


def test_imagen_grande(carpeta, monkeypatch):
    # RF-5: por encima del tamaño máximo -> error y sin llamar al modelo.
    monkeypatch.setattr(config, "IMAGEN_MAX_MB", 0.001)  # unos 1000 bytes
    (carpeta / "grande.png").write_bytes(b"0" * 5000)
    cliente = ClienteFalso()
    texto = describir_imagen("grande.png", cliente=cliente)
    assert texto.startswith("ERROR:") and "grande" in texto
    assert cliente.llamadas == []


def test_ruta_fuera_de_carpeta(carpeta, tmp_path):
    # RF-6: ni rutas relativas con ".." ni absolutas pueden salir de la carpeta autorizada.
    (tmp_path / "secreto.png").write_bytes(b"\x89PNG secreto")
    cliente = ClienteFalso()
    for ruta in ["../secreto.png", str(tmp_path / "secreto.png")]:
        texto = describir_imagen(ruta, cliente=cliente)
        assert texto.startswith("ERROR:") and "no permitida" in texto
    assert cliente.llamadas == []


def test_modelo_falla(carpeta):
    # RF-7: excepción o respuesta vacía del modelo -> error controlado, sin excepción.
    assert describir_imagen(cliente=ClienteFalso(error=RuntimeError("sin red"))).startswith("ERROR:")
    assert describir_imagen(cliente=ClienteFalso(respuesta="  ")).startswith("ERROR:")


def test_sin_texto_legible(carpeta):
    # RF-8: si el modelo indica que no hay texto legible, la tool lo propaga sin inventar cifras.
    assert describir_imagen(cliente=ClienteFalso(respuesta=SIN_TEXTO)) == SIN_TEXTO


# --- Fallos temporales del modelo: reintento y registro de la causa (spec 002, RF-24 a RF-27) ---

import logging  # noqa: E402

from google.genai import errors as errores_google  # noqa: E402

ERROR_GENERICO = "ERROR: el modelo no pudo describir la imagen"


def error_de_google(codigo, estado, mensaje="mensaje del servidor"):
    """Un error real de google-genai (ServerError para 5xx, ClientError para 4xx)."""
    clase = errores_google.ServerError if codigo >= 500 else errores_google.ClientError
    return clase(codigo, {"error": {"code": codigo, "message": mensaje, "status": estado}})


class ClienteQueFalla:
    """Cliente de visión que lanza los errores indicados, uno por llamada, y después responde."""

    def __init__(self, errores, respuesta="Cartel: Billete sencillo 1,50 €"):
        self.errores = list(errores)
        self.respuesta = respuesta
        self.llamadas = 0

    def generar(self, imagen_bytes, mime, prompt):
        self.llamadas += 1
        if self.errores:
            raise self.errores.pop(0)
        return self.respuesta


@pytest.fixture
def esperas(monkeypatch):
    """Sustituye time.sleep para no esperar de verdad y anota cuánto se pidió esperar."""
    pedidas = []
    monkeypatch.setattr("time.sleep", lambda segundos: pedidas.append(segundos))
    return pedidas


@pytest.mark.parametrize("error", [
    error_de_google(503, "UNAVAILABLE"),
    error_de_google(429, "RESOURCE_EXHAUSTED"),
    error_de_google(500, "INTERNAL"),
    error_de_google(504, "DEADLINE_EXCEEDED"),
    TimeoutError("tiempo agotado"),
    ConnectionError("sin conexión"),
], ids=["503", "429", "500", "504", "timeout", "conexion"])
def test_reintenta_ante_un_error_temporal(carpeta, esperas, error):
    # RF-24: un fallo temporal se reintenta una vez, tras la espera configurada.
    cliente = ClienteQueFalla([error])
    assert describir_imagen(cliente=cliente) == "Cartel: Billete sencillo 1,50 €"
    assert cliente.llamadas == 2
    assert esperas == [config.IMAGEN_REINTENTO_ESPERA_S]


def test_dos_fallos_temporales_dan_error_controlado(carpeta, esperas):
    # RF-25: si el segundo intento también falla, el mismo error controlado y sin más reintentos.
    cliente = ClienteQueFalla([error_de_google(503, "UNAVAILABLE"), error_de_google(503, "UNAVAILABLE")])
    assert describir_imagen(cliente=cliente) == ERROR_GENERICO
    assert cliente.llamadas == 2
    assert len(esperas) == 1


@pytest.mark.parametrize("error", [
    error_de_google(400, "INVALID_ARGUMENT"),
    error_de_google(401, "UNAUTHENTICATED"),
    error_de_google(403, "PERMISSION_DENIED"),
    error_de_google(404, "NOT_FOUND"),
    RuntimeError("error sin código"),
], ids=["400", "401", "403", "404", "sin_codigo"])
def test_un_error_no_temporal_no_se_reintenta(carpeta, esperas, error):
    # RF-26: clave inválida, modelo retirado o petición mala no se arreglan esperando.
    cliente = ClienteQueFalla([error])
    assert describir_imagen(cliente=cliente) == ERROR_GENERICO
    assert cliente.llamadas == 1
    assert esperas == []


def test_registra_la_causa_sin_datos_sensibles(carpeta, esperas, caplog):
    # RF-27: queda el tipo, el código y el estado, y nunca el mensaje completo ni la clave.
    secreto = "AIzaSyCLAVE-SECRETA-123"
    error = error_de_google(503, "UNAVAILABLE", mensaje=f"fallo con {secreto} en E:/privado/imagen.jpg")
    with caplog.at_level(logging.WARNING):
        resultado = describir_imagen(cliente=ClienteQueFalla([error, error]))
    registro = caplog.text
    assert "ServerError" in registro and "503" in registro and "UNAVAILABLE" in registro
    assert secreto not in registro and "privado" not in registro
    # El agente sigue viendo solo el mensaje genérico, sin detalles internos.
    assert resultado == ERROR_GENERICO
    assert "503" not in resultado and secreto not in resultado


def test_el_registro_indica_el_numero_de_intento(carpeta, esperas, caplog):
    error = error_de_google(503, "UNAVAILABLE")
    with caplog.at_level(logging.WARNING):
        describir_imagen(cliente=ClienteQueFalla([error, error]))
    assert "intento 1" in caplog.text and "intento 2" in caplog.text


def test_un_error_no_temporal_tambien_se_registra(carpeta, esperas, caplog):
    with caplog.at_level(logging.WARNING):
        describir_imagen(cliente=ClienteQueFalla([error_de_google(404, "NOT_FOUND")]))
    assert "ClientError" in caplog.text and "404" in caplog.text and "NOT_FOUND" in caplog.text


def test_el_exito_a_la_primera_no_espera_ni_registra(carpeta, esperas, caplog):
    cliente = ClienteQueFalla([])
    with caplog.at_level(logging.WARNING):
        assert describir_imagen(cliente=cliente) == "Cartel: Billete sencillo 1,50 €"
    assert cliente.llamadas == 1 and esperas == [] and caplog.text == ""
