"""Tests de allowlist y traza de las tools multimodal y calculadora (spec 002, RF-9, RF-10, RF-11, RF-19, RF-20)."""
import importlib

import pytest

import config
from src.tools import TOOLS_PERMITIDAS, ejecutar_tool


class ClienteFalso:
    """Cliente de visión falso: sustituye a ClienteGemini para no llamar a la API."""

    def generar(self, imagen_bytes, mime, prompt):
        return "Cartel: Billete sencillo 1,50 €"


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    """Carpeta de imágenes temporal y cliente de visión falso."""
    imagenes = tmp_path / "assets"
    imagenes.mkdir()
    (imagenes / "imagen_demo.jpg").write_bytes(b"\xff\xd8\xff fake jpg")
    monkeypatch.setattr(config, "IMAGENES_DIR", imagenes)
    monkeypatch.setattr(config, "IMAGEN_DEMO", "imagen_demo.jpg")
    # No se usa `import src.tools.describir_imagen` porque en el paquete ese nombre es la función.
    modulo = importlib.import_module("src.tools.describir_imagen")
    monkeypatch.setattr(modulo, "ClienteGemini", ClienteFalso)
    return imagenes


def test_imagen_en_allowlist():
    # RF-15 y RF-44: tarifas solo recibe la tool de imagen en el grafo.
    assert callable(TOOLS_PERMITIDAS.get("describir_imagen"))
    assert config.TOOLS_POR_ESPECIALISTA["tarifas"] == ["describir_imagen"]


def test_tarifas_no_recibe_calculadora_ni_rag_directo():
    """RF-44: calcular y consultar el corpus pertenecen a otros especialistas."""
    permitidas = config.TOOLS_POR_ESPECIALISTA["tarifas"]
    assert "calculadora" not in permitidas
    assert "rag_ask" not in permitidas


def test_traza_imagen(carpeta):
    # RF-10: la traza guarda nombre, argumentos, estado y extracto del resultado.
    traza = []
    args = {"ruta": "imagen_demo.jpg", "pregunta": "¿Qué precios hay?"}
    resultado = ejecutar_tool("describir_imagen", args, traza)
    assert resultado == "Cartel: Billete sencillo 1,50 €"
    assert traza == [
        {"tool": "describir_imagen", "args": args, "status": "ok", "preview": resultado[:120]}
    ]


def test_imagen_con_error_en_traza(carpeta):
    # RF-10: un error controlado de la tool se refleja como estado "error".
    traza = []
    resultado = ejecutar_tool("describir_imagen", {"ruta": "../.env"}, traza)
    assert resultado.startswith("ERROR:")
    assert traza[0]["status"] == "error"


def test_imagen_demo_existe():
    # RF-11: la imagen demo configurada existe y no está vacía (que se lea bien se valida a mano).
    demo = config.IMAGENES_DIR / config.IMAGEN_DEMO
    assert demo.is_file() and demo.stat().st_size > 0


def test_calculadora_en_allowlist():
    # RF-19
    assert callable(TOOLS_PERMITIDAS.get("calculadora"))


def test_traza_calculadora():
    # RF-20: la traza guarda nombre, argumentos, estado y resultado.
    traza = []
    resultado = ejecutar_tool("calculadora", {"expresion": "3*2,40"}, traza)
    assert resultado == "7,20"
    assert traza == [
        {"tool": "calculadora", "args": {"expresion": "3*2,40"}, "status": "ok", "preview": "7,20"}
    ]
    ejecutar_tool("calculadora", {"expresion": "1/0"}, traza)
    assert traza[1]["status"] == "error"
