"""
app.py — Interfaz Streamlit: chat + contexto recuperado + tabla de métricas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st
from src.responder import responder
from config import GENERATION_MODEL

st.set_page_config(page_title="MadridRumbo", page_icon="assets/icono.png")
st.image("assets/icono.png", width=120)
st.title("MadridRumbo — Asistente de transporte de Madrid")

if "historial" not in st.session_state:
    st.session_state.historial = []

pregunta = st.chat_input("Escribe tu pregunta sobre transporte en Madrid...")

for turno in st.session_state.historial:
    with st.chat_message("user"):
        st.write(turno["pregunta"])
    with st.chat_message("assistant"):
        st.write(turno["respuesta"])
        with st.expander("Contexto usado"):
            st.write(", ".join(turno["fuentes"]))
            st.text(turno["contexto"])
        st.caption(f"k={turno['k']} · chunks={turno['num_chunks']} · tiempo={turno['tiempo']}s · modelo={GENERATION_MODEL}")

if pregunta:
    with st.chat_message("user"):
        st.write(pregunta)

    resultado = responder(pregunta)

    with st.chat_message("assistant"):
        st.write(resultado["respuesta"])
        with st.expander("Contexto usado"):
            st.write(", ".join(resultado["fuentes"]))
            st.text(resultado["contexto"])
        st.caption(f"k={resultado['k']} · chunks={resultado['num_chunks']} · tiempo={resultado['tiempo']}s · modelo={GENERATION_MODEL}")

    st.session_state.historial.append(resultado)

if st.session_state.historial:
    st.divider()
    st.subheader("Métricas")
    tabla = [
        {
            "Pregunta": t["pregunta"],
            "K": t["k"],
            "Chunks": t["num_chunks"],
            "Tiempo (s)": t["tiempo"],
            "Modelo": GENERATION_MODEL,
        }
        for t in st.session_state.historial
    ]
    st.table(tabla)