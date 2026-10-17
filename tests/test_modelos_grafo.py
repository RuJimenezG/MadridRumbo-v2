"""Adaptadores de modelo perezosos e inyectables (spec 005, T3)."""
import importlib
import sys
from types import SimpleNamespace

import model_auth
import pytest


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
    """RF-6: los especialistas conservan el rechazo de JSON no interpretable."""
    from src.modelos import crear_modelo_especialista

    especialista = crear_modelo_especialista(generar=lambda prompt: "no es JSON")

    try:
        especialista("Consulta")
    except ValueError as error:
        assert "interpretable" in str(error)
    else:
        raise AssertionError("Una respuesta no estructurada debe fallar de forma controlada.")


def test_generador_del_supervisor_pide_application_json_al_proveedor():
    """RF-24: la decisión del Supervisor pide JSON nativo a Gemini."""
    from src.modelos import GeneradorGemini

    llamadas = []

    class ClienteFalso:
        models = SimpleNamespace(
            generate_content=lambda **kwargs: llamadas.append(kwargs)
            or SimpleNamespace(text='{"roles": ["auxiliar"]}')
        )

    generador = GeneradorGemini(
        crear_cliente=ClienteFalso,
        solicitar_json=True,
    )

    assert generador("Decide el rol.") == '{"roles": ["auxiliar"]}'
    assert llamadas[0]["config"].response_mime_type == "application/json"


def test_solo_el_adaptador_del_supervisor_solicita_json(monkeypatch):
    """RF-1 y RF-24: especialistas y sintetizador conservan texto libre."""
    import src.modelos as modelos

    solicitudes_json = []

    class GeneradorFalso:
        def __init__(self, *, solicitar_json=False):
            solicitudes_json.append(solicitar_json)

        def __call__(self, prompt):
            return "Respuesta falsa."

    monkeypatch.setattr(modelos, "GeneradorGemini", GeneradorFalso)

    modelos.crear_modelo_supervisor()
    modelos.crear_modelo_especialista()
    modelos.crear_modelo_sintetizador()

    assert solicitudes_json == [True, False, False]


@pytest.mark.parametrize(
    "respuesta, error",
    [
        (None, RuntimeError("TOKEN_DE_PRUEBA_NO_EXPOSABLE")),
        (SimpleNamespace(text=""), None),
        (SimpleNamespace(text={"no": "texto"}), None),
        (
            SimpleNamespace(
                text=None,
                prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
            ),
            None,
        ),
    ],
)
def test_incidencias_del_proveedor_se_traducen_sin_exponer_detalles(respuesta, error):
    """RF-8: error, vacío, no texto y bloqueo cruzan una frontera uniforme."""
    from src.modelos import ErrorProveedorModelo, GeneradorGemini

    class ClienteFalso:
        def generar(self, **kwargs):
            if error is not None:
                raise error
            return respuesta

        models = property(lambda self: SimpleNamespace(generate_content=self.generar))

    generador = GeneradorGemini(crear_cliente=ClienteFalso)

    with pytest.raises(ErrorProveedorModelo) as capturada:
        generador("Decide el rol.")

    assert "TOKEN_DE_PRUEBA_NO_EXPOSABLE" not in str(capturada.value)
