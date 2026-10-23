"""Tests del cliente Streamlit con `AppTest` (spec 008, RF-38 a RF-41).

No usan red ni API: el grafo se sustituye por un agente de prueba y no se arranca ningún servidor.
"""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import src.agent as agent
from src.clientes.contrato import estado_vacio
from src.graph import crear_grafo

APP = str(Path(__file__).resolve().parent.parent / "app.py")
DIAGNOSTICO = {
    "paso": 1,
    "tipo": "nodo",
    "nodo": "supervisor",
    "entrada": {"mensaje": "consulta"},
    "salida": None,
    "resultado": "fallido",
    "detalle": {"categoria": "json_invalido", "resumen": "Se aplicó el fallback del Supervisor."},
}


class AgenteDePrueba:
    """Agente que responde a cada mensaje con su propio registro y su propia traza, y anota cuándo lo llaman."""

    def __init__(self, eventos, con_pasos=True):
        self.eventos = eventos
        self.con_pasos = con_pasos

    def procesar_turno(self, estado, mensaje, thread_id):
        self.eventos.append("grafo")
        respuesta = {**estado_vacio(), "respuesta": f"Respuesta a {mensaje}"}
        if self.con_pasos:
            respuesta["log"] = [
                DIAGNOSTICO,
                {
                    "paso": 2,
                    "tipo": "nodo",
                    "nodo": "horarios",
                    "entrada": {"mensaje": mensaje},
                    "salida": {"nota": f"nota de {mensaje}"},
                    "resultado": "completado",
                    "detalle": None,
                },
            ]
            respuesta["traza"] = [{"tool": "hora_actual", "args": {}, "status": "ok", "preview": f"hora de {mensaje}"}]
        return respuesta

    def aprobar_plan(self, estado, thread_id, aprobado):
        return estado_vacio()


@pytest.fixture
def eventos(monkeypatch):
    """Lista donde se anota el orden de lo que ocurre: burbujas, indicador de espera y llamadas al grafo."""
    anotados = []
    original_burbuja, original_espera = st.chat_message, st.spinner

    def burbuja(nombre, *args, **kwargs):
        anotados.append(f"burbuja:{nombre}")
        return original_burbuja(nombre, *args, **kwargs)

    def espera(*args, **kwargs):
        anotados.append("espera")
        return original_espera(*args, **kwargs)

    monkeypatch.setattr(st, "chat_message", burbuja)
    monkeypatch.setattr(st, "spinner", espera)
    return anotados


def _abrir_app(monkeypatch, eventos, con_pasos=True, agente=None):
    agente = agente or AgenteDePrueba(eventos, con_pasos)
    monkeypatch.setattr("src.clientes.cargar.cargar_agente", lambda *args, **kwargs: (agente, None))
    return AppTest.from_file(APP, default_timeout=30).run()


def _pasos(at):
    return [e for e in at.expander if e.label == "Pasos seguidos"]


def test_el_mensaje_se_dibuja_antes_de_llamar_al_grafo(monkeypatch, eventos):
    # RF-38: la pregunta aparece en el chat sin esperar a la respuesta.
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("¿Hasta qué hora hay metro?").run()
    assert not at.exception
    assert "burbuja:user" in eventos and "grafo" in eventos
    assert eventos.index("burbuja:user") < eventos.index("grafo")


def test_hay_indicador_de_espera_mientras_el_grafo_responde(monkeypatch, eventos):
    # RF-38: se muestra un indicador de espera antes de llamar al grafo.
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("hola").run()
    assert "espera" in eventos and "grafo" in eventos
    assert eventos.index("espera") < eventos.index("grafo")


def test_la_respuesta_muestra_los_pasos_seguidos(monkeypatch, eventos):
    # RF-39: bajo la respuesta hay un desplegable con las tools y el registro visible.
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("uno").run()
    (desplegable,) = _pasos(at)
    lineas = [t.value for t in desplegable.text]
    assert "Flujo: horarios" in lineas
    assert "1. hora_actual [ok] hora de uno" in lineas


def test_los_pasos_no_muestran_el_diagnostico_del_supervisor(monkeypatch, eventos):
    # RF-39 y RF-35: la web no enseña los diagnósticos técnicos del supervisor.
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("uno").run()
    (desplegable,) = _pasos(at)
    assert not any("json_invalido" in t.value for t in desplegable.text)


def test_el_panel_depuracion_muestra_el_diagnostico_estructurado(monkeypatch, eventos):
    """RF-24: el panel lateral no aplica el filtro que usa el chat."""
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("uno").run()
    assert any("json_invalido" in str(elemento.value) for elemento in at.json)


def test_el_panel_muestra_el_fallback_real_del_supervisor_y_el_chat_lo_filtra(monkeypatch, eventos):
    """RF-23 a RF-25: la UI recibe el diagnóstico generado por el grafo real."""
    grafo = crear_grafo(
        modelo_supervisor=lambda mensajes: "RESPUESTA_CRUDA_QUE_NO_ES_JSON",
        especialistas={
            rol: lambda estado, rol=rol: {
                "notas": [f"[{rol}] resultado de prueba"],
                "traza": [],
                "resultados": [],
            }
            for rol in ("rag", "horarios", "rutas", "auxiliar", "tarifas")
        },
        modelo_sintetizador=lambda contexto: "Respuesta de prueba.",
    )
    monkeypatch.setattr(agent, "_GRAFO", grafo)

    at = _abrir_app(monkeypatch, eventos, agente=agent)
    at.chat_input[0].set_value("¿Qué hora es?").run()

    assert not at.exception
    assert any("json_invalido" in str(elemento.value) for elemento in at.json)
    (desplegable,) = _pasos(at)
    assert not any("json_invalido" in texto.value for texto in desplegable.text)


def test_cada_respuesta_conserva_sus_propios_pasos(monkeypatch, eventos):
    # RF-40: el desplegable de la primera respuesta no cambia al llegar la segunda.
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("uno").run()
    at.chat_input[0].set_value("dos").run()
    primero, segundo = _pasos(at)
    assert "1. hora_actual [ok] hora de uno" in [t.value for t in primero.text]
    assert "1. hora_actual [ok] hora de dos" in [t.value for t in segundo.text]


def test_sin_pasos_no_hay_desplegable(monkeypatch, eventos):
    # RF-41: una respuesta sin tools ni registro visible no lleva desplegable.
    at = _abrir_app(monkeypatch, eventos, con_pasos=False)
    at.chat_input[0].set_value("uno").run()
    assert not _pasos(at)


def test_los_pasos_del_chat_no_vuelcan_la_entrada_ni_la_salida_de_cada_paso(monkeypatch, eventos):
    # RF-39: el chat muestra un resumen; la entrada y la salida completas de cada paso son del panel de depuración.
    at = _abrir_app(monkeypatch, eventos)
    at.chat_input[0].set_value("uno").run()
    (desplegable,) = _pasos(at)
    texto = "\n".join(t.value for t in desplegable.text)
    assert "entrada:" not in texto and "salida:" not in texto
    assert any("nota de uno" in str(elemento.value) for elemento in at.json)
