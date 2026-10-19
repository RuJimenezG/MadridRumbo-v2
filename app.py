"""
app.py — Cliente Streamlit del grafo multiagente (spec 005).

Capa fina: toda la lógica de la conversación vive en `src/clientes/sesion.py`, igual que en el CLI.
Aquí solo se dibuja el chat, la barra lateral con el plan y los botones Aprobar y Rechazar,
y el panel de depuración.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st

from src.clientes.cargar import GrafoNoDisponible, cargar_agente
from src.clientes.presentacion import datos_depuracion
from src.clientes.sesion import SesionChat

st.set_page_config(page_title="MadridRumbo", page_icon="assets/icono.png")

# La sesión (identificador, estado e historial) vive en st.session_state: Streamlit vuelve a
# ejecutar este script en cada interacción y las variables normales se perderían.
if "sesion" not in st.session_state:
    try:
        agente, aviso = cargar_agente()
    except GrafoNoDisponible as error:
        st.error(str(error))
        st.stop()
    st.session_state.sesion = SesionChat(agente)
    st.session_state.aviso = aviso

sesion: SesionChat = st.session_state.sesion

# --- Barra lateral: plan pendiente, decisión, nueva conversación y depuración ---
with st.sidebar:
    st.image("assets/icono.png", width=80)
    if st.session_state.aviso:
        st.warning(st.session_state.aviso)

    st.subheader("Plan")
    if sesion.puede_decidir:
        for punto in sesion.estado["plan"]:
            st.markdown(f"- {punto}")
    elif sesion.estado["done"]:
        st.success("Conversación terminada.")
    else:
        st.caption("No hay ningún plan pendiente de decisión.")

    # Los botones solo están activos con un plan pendiente (RF-22).
    columna_aprobar, columna_rechazar = st.columns(2)
    aprobar = columna_aprobar.button("Aprobar", type="primary", disabled=not sesion.puede_decidir)
    rechazar = columna_rechazar.button("Rechazar", disabled=not sesion.puede_decidir)
    if aprobar or rechazar:
        sesion.decidir(aprobado=aprobar)
        st.rerun()

    if st.button("Nueva conversación"):
        sesion.nueva_conversacion()
        st.rerun()

    with st.expander("Depuración"):
        st.json(datos_depuracion(sesion.estado, sesion.thread_id))

# --- Chat ---
st.title("MadridRumbo — Asistente de transporte de Madrid")

for entrada in sesion.historial:
    if entrada["rol"] == "error":
        st.error(entrada["texto"])
    else:
        with st.chat_message("user" if entrada["rol"] == "usuario" else "assistant"):
            st.write(entrada["texto"])

# Con un plan pendiente el cuadro de mensaje queda bloqueado hasta aprobar o rechazar (RF-22b).
mensaje = st.chat_input(
    "Escribe tu pregunta sobre transporte en Madrid...",
    disabled=not sesion.puede_escribir,
)
if sesion.puede_decidir:
    st.info("Hay un plan pendiente: apruébalo o recházalo en la barra lateral para continuar.")

if mensaje:
    sesion.enviar(mensaje)
    st.rerun()
