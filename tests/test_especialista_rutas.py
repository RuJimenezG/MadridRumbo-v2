"""Tests del especialista de rutas (spec 004, RF-25 a RF-29). No usan API."""
import config


def test_config_allowlist_rutas():
    # RF-25: el especialista "rutas" solo puede pedir planificar_ruta; el RAG lo llama la herramienta (RF-19).
    assert config.TOOLS_POR_ESPECIALISTA["rutas"] == ["planificar_ruta"]
