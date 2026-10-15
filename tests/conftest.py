"""Configuración común de los tests: ninguno puede hacer una petición HTTP real."""
import urllib.request

import pytest


@pytest.fixture(autouse=True)
def sin_peticiones_reales(monkeypatch):
    # Red de seguridad: si algún test llega a urlopen sin su propio doble, falla en vez de salir a internet.
    def bloqueado(*args, **kwargs):
        raise AssertionError("petición HTTP real en un test: usa un doble de prueba")

    monkeypatch.setattr(urllib.request, "urlopen", bloqueado)
