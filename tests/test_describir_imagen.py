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
