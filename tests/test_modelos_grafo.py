"""Adaptadores de modelo perezosos e inyectables (spec 005, T3)."""
import importlib
import sys

import model_auth


def test_importar_y_construir_adaptadores_no_configura_claves(monkeypatch):
    """T3: no se crea cliente ni se solicita una clave durante la importación."""
    llamadas = []
    monkeypatch.setattr(
        model_auth,
        "configurar_gemini_api_key",
        lambda: llamadas.append("configurada"),
    )
    sys.modules.pop("src.modelos", None)

    modelos = importlib.import_module("src.modelos")
    modelos.crear_modelo_supervisor()
    modelos.crear_modelo_especialista()
    modelos.crear_modelo_sintetizador()

    assert llamadas == []


def test_modelos_estructurados_usan_el_generador_inyectado():
    """RF-6: los dobles inyectados sustituyen el modelo de producción."""
    from src.modelos import crear_modelo_especialista, crear_modelo_supervisor

    prompts = []

    def generar(prompt):
        prompts.append(prompt)
        return '{"tool": "hora_actual", "args": {}}'

    especialista = crear_modelo_especialista(generar=generar)
    supervisor = crear_modelo_supervisor(generar=lambda prompt: {"roles": ["rag"]})

    assert especialista([{"role": "user", "content": "¿Qué hora es?"}]) == {
        "tool": "hora_actual",
        "args": {},
    }
    assert supervisor("Consulta documental") == {"roles": ["rag"]}
    assert "¿Qué hora es?" in prompts[0]


def test_sintetizador_inyectado_recibe_estado_y_no_llama_a_un_proveedor():
    """RF-19 y RF-56: la síntesis se puede probar sin LLM real."""
    from src.modelos import crear_modelo_sintetizador

    estados = []
    sintetizador = crear_modelo_sintetizador(
        generar=lambda prompt: estados.append(prompt) or "Respuesta sencilla."
    )

    assert sintetizador({"notas": ["Dato del RAG"], "traza": []}) == "Respuesta sencilla."
    assert "Dato del RAG" in estados[0]


def test_respuesta_estructurada_invalida_se_informa_sin_ejecutar_nada_externo():
    """RF-6: el adaptador permite al supervisor aplicar su fallback controlado."""
    from src.modelos import crear_modelo_supervisor

    supervisor = crear_modelo_supervisor(generar=lambda prompt: "no es JSON")

    try:
        supervisor("Consulta")
    except ValueError as error:
        assert "interpretable" in str(error)
    else:
        raise AssertionError("Una respuesta no estructurada debe fallar de forma controlada.")
