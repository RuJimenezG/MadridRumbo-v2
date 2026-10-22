"""Tests de T7 (spec 010, RF-22 a RF-24): reglas de la capa 2 en `PROMPT_RUTAS` y paso de sus argumentos. Sin API ni red."""
import json

from src.agents.rutas import PROMPT_RUTAS, nodo_rutas
from tests.dobles_grafo import EjecutorFalso, LLMFalso
from tests.test_especialista_rutas import RUTA_OK, _estado

# El prompt se compara sin saltos de línea: las frases pueden partirse al envolver el texto.
PROMPT = " ".join(PROMPT_RUTAS.split())


def test_la_firma_de_la_tool_lista_los_parametros_de_la_capa_2():
    for parametro in ("texto_alternativo_origen?", "texto_alternativo_destino?", "probable_origen?", "probable_destino?"):
        assert parametro in PROMPT


def test_solo_cuando_el_turno_anterior_ya_fue_no_valido_y_la_nueva_entrada_tampoco_resuelve():
    assert "solo cuando el turno anterior ya dejó ese extremo sin resolver" in PROMPT
    assert "la nueva entrada de la persona tampoco lo resuelve" in PROMPT
    assert "una sola vez por extremo" in PROMPT


def test_elige_solo_entre_candidatos_mostrados_y_con_confianza_baja_pregunta():
    assert "elige solo entre las opciones que la tool mostró" in PROMPT
    assert "probable_origen=true" in PROMPT and "probable_destino=true" in PROMPT
    assert "Si tu confianza es baja, no elijas: vuelve a preguntar" in PROMPT


def test_con_cero_candidatos_propone_un_unico_texto_alternativo_por_extremo():
    assert "0 candidatos" in PROMPT
    assert "un único texto alternativo por extremo" in PROMPT


def test_el_prompt_sigue_sin_listas_ni_ejemplos_de_titulos():
    # Mismo criterio que `test_prompt_sin_lista_de_titulos` (spec 004, RF-35 y RF-50).
    for texto in ("billete de 10 viajes", "billete sencillo", "abono", "títulos disponibles", "lista cerrada"):
        assert texto not in PROMPT.lower()


def test_el_especialista_pasa_los_argumentos_de_la_capa_2_a_la_tool():
    args = {"origen": "xyz", "destino": "Sol", "texto_alternativo_origen": "Atocha", "probable_destino": True,
            "opcion_destino": 2}
    llm = LLMFalso([{"tool": "planificar_ruta", "args": args}, {"final": "Ruta propuesta."}])
    ejecutor = EjecutorFalso({"planificar_ruta": json.dumps(RUTA_OK, ensure_ascii=False)})
    salida = nodo_rutas(_estado("quiero ir de xyz a Sol"), llm, ejecutor)
    assert ejecutor.llamadas == [("planificar_ruta", args)]
    assert salida["notas"][-1].endswith("Ruta propuesta.")
