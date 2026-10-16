"""Configuración centralizada del grafo multiagente (spec 005, T1)."""
from pathlib import Path

import config


def test_limites_de_conversacion_y_tools():
    """RF-38 y RF-39: los límites se definen en un único punto."""
    assert config.MAX_TURNOS_CONVERSACION == 10
    assert config.MAX_CICLOS_TOOLS == 8


def test_allowlists_de_los_especialistas_del_grafo():
    """RF-43, RF-44 y RF-58: cada especialista recibe solo sus tools."""
    assert config.TOOLS_POR_ESPECIALISTA == {
        "rag": ["rag_ask"],
        "horarios": ["hora_actual", "rag_ask"],
        "auxiliar": ["hora_actual", "calculadora"],
        "rutas": ["planificar_ruta"],
        "tarifas": ["describir_imagen"],
    }


def test_requirements_declara_langgraph():
    """RF-1: una instalación limpia incluye la dependencia del grafo."""
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    assert "langgraph>=1.2,<2" in requirements.read_text(encoding="utf-8").splitlines()
