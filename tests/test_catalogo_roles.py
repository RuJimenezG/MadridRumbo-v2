"""Pruebas unitarias del catálogo semántico de roles de la spec 007."""

import pytest

from src.catalogo_roles import (
    CATALOGO_ROLES,
    ROLES_CATALOGO,
    corregir_tarifas_textuales,
    es_consulta_tarifaria_textual,
    instrucciones_para_supervisor,
)


def test_catalogo_declara_roles_y_responsabilidades():
    """RF-1 a RF-6: un único catálogo conserva las cinco responsabilidades."""
    assert ROLES_CATALOGO == ("rag", "tarifas", "horarios", "rutas", "auxiliar")
    assert tuple(CATALOGO_ROLES) == ROLES_CATALOGO
    assert CATALOGO_ROLES["rag"].responsabilidad == (
        "consultas textuales sobre normativa, tarifas, billetes, abonos y "
        "documentos del CRTM"
    )
    assert CATALOGO_ROLES["tarifas"].responsabilidad == (
        "interpretación de una imagen, foto o cartel aportado, con lectura de "
        "los datos que contenga"
    )
    assert CATALOGO_ROLES["horarios"].responsabilidad == (
        "horarios y frecuencias de transporte"
    )
    assert CATALOGO_ROLES["rutas"].responsabilidad == (
        "planificación de desplazamientos entre un origen y un destino"
    )
    assert CATALOGO_ROLES["auxiliar"].responsabilidad == "hora actual y cálculos"


def test_instrucciones_reutilizan_catalogo_y_exclusiones_de_tarifas():
    """RF-1, RF-7 y RF-8: el prompt se deriva del catálogo y sus límites."""
    instrucciones = instrucciones_para_supervisor()

    for rol, capacidad in CATALOGO_ROLES.items():
        assert f"- {rol}: {capacidad.responsabilidad}." in instrucciones
    assert "Una consulta textual de tarifa sin imagen debe seleccionar rag." in instrucciones
    assert "No selecciones tarifas salvo que exista una imagen aportada válida." in instrucciones
    assert "Referirse solo a una imagen, foto o cartel no constituye una imagen aportada." in instrucciones


@pytest.mark.parametrize(
    "mensaje",
    [
        "¿Cuál es la TARIFA?",
        "¿Qué PRECIO tienen los abonos?",
        "¿Dónde compro BILLETES?",
        "¿Qué ABONOS hay?",
        "¿Cuánto DINERO necesito?",
        "¿Cuánto GASTARÍA al mes?",
        "¿Cuánto CUESTA el Combinado Metro?",
        "¿Cuál es el precio, del billete?",
    ],
)
def test_detecta_terminos_tarifarios_con_normalizacion_y_flexiones_simples(mensaje):
    """RF-7: se ignoran mayúsculas, tildes y puntuación sin ampliar el ámbito."""
    assert es_consulta_tarifaria_textual(mensaje) is True


@pytest.mark.parametrize(
    "mensaje",
    [
        "¿Cuál es la frecuencia de la línea 1?",
        "¿Cómo llego a Sol?",
        "¿Qué hora es?",
        "¿Dónde está la oficina de turismo?",
        "", 
    ],
)
def test_no_clasifica_como_tarifaria_una_consulta_fuera_de_los_terminos_explicitos(mensaje):
    """RF-7: la guarda no infiere una intención tarifaria sin término aprobado."""
    assert es_consulta_tarifaria_textual(mensaje) is False


def test_referencia_a_cartel_sin_archivo_sigue_siendo_consulta_textual():
    """RF-10: mencionar una foto o cartel no acredita una imagen aportada."""
    mensaje = "En la foto del cartel, ¿cuánto cuesta el abono?"

    assert es_consulta_tarifaria_textual(mensaje) is True


def test_corrige_tarifas_sin_imagen_y_conserva_orden_y_repeticiones():
    """RF-9 y RF-16: toda aparición se sustituye en la misma posición."""
    original = ["auxiliar", "tarifas", "tarifas", "horarios"]

    roles, correcciones = corregir_tarifas_textuales(
        original,
        "¿Cuánto cuesta el Combinado Metro?",
        tiene_imagen_valida=False,
    )

    assert roles == ["auxiliar", "rag", "rag", "horarios"]
    assert correcciones == 2
    assert original == ["auxiliar", "tarifas", "tarifas", "horarios"]


def test_no_corrige_tarifas_si_hay_una_imagen_valida():
    """RF-11: una imagen válida habilita el especialista visual aunque no sea tarifa."""
    roles, correcciones = corregir_tarifas_textuales(
        ["tarifas"],
        "¿Cuánto cuesta el Combinado Metro?",
        tiene_imagen_valida=True,
    )

    assert roles == ["tarifas"]
    assert correcciones == 0


def test_no_corrige_si_la_consulta_no_contiene_termino_tarifario_explicito():
    """RF-9: la corrección queda limitada al alcance semántico aprobado."""
    roles, correcciones = corregir_tarifas_textuales(
        ["tarifas", "horarios"],
        "Describe este aviso del Metro.",
        tiene_imagen_valida=False,
    )

    assert roles == ["tarifas", "horarios"]
    assert correcciones == 0


def test_ficha_de_rutas_incluye_zona_y_precio_y_las_preguntas_de_seguimiento():
    """Spec 010, T5b (c): la ficha de `rutas` dice que incluye zona y precio y que el precio de seguimiento va a rutas."""
    ficha = CATALOGO_ROLES["rutas"]
    limites = " ".join(ficha.limites)
    assert "zona y el precio del trayecto" in limites
    assert "seguimiento" in limites and "van a rutas" in limites
    assert "Límite: " + ficha.limites[0] in instrucciones_para_supervisor()      # llega al prompt del supervisor
