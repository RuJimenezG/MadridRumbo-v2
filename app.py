"""
app.py — Cliente Streamlit del grafo multiagente (spec 008).

Capa fina: toda la lógica de la conversación vive en `src/clientes/sesion.py`, igual que en el CLI.
Aquí solo se dibuja el chat, la barra lateral con el plan y los botones Aprobar y Rechazar,
y el panel de depuración.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import streamlit as st

from src.clientes.cargar import GrafoNoDisponible, cargar_agente
from src.clientes.planes import ids_de_planes, resumir_plan
from src.clientes.presentacion import datos_depuracion, pasos_del_turno
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
    ids_planes = ids_de_planes(sesion.planes)
    plan_elegido = None
    if sesion.puede_decidir:
        # Cada plan con su resumen legible; con varios hay que elegir cuál se decide (RF-31).
        for plan in sesion.planes:
            st.text(resumir_plan(plan))
        if len(ids_planes) > 1:
            plan_elegido = st.radio("Plan a decidir", ids_planes, key="plan_elegido")
    elif sesion.estado["done"]:
        st.success("Conversación terminada.")
    else:
        st.caption("No hay ningún plan pendiente de decisión.")

    # Los botones solo están activos con un plan pendiente (RF-22).
    columna_aprobar, columna_rechazar = st.columns(2)
    aprobar = columna_aprobar.button("Aprobar", type="primary", disabled=not sesion.puede_decidir)
    rechazar = columna_rechazar.button("Rechazar", disabled=not sesion.puede_decidir)
    if aprobar or rechazar:
        sesion.decidir(aprobado=aprobar, plan_id=plan_elegido)
        st.rerun()

    if st.button("Nueva conversación"):
        sesion.nueva_conversacion()
        st.rerun()

    # La web no muestra los diagnósticos técnicos del supervisor (RF-35); el CLI sí.
    with st.expander("Depuración"):
        st.json(datos_depuracion(sesion.estado, sesion.thread_id, ocultar_tecnicas=True))

# --- Chat ---
st.title("MadridRumbo — Asistente de transporte de Madrid")

for entrada in sesion.historial:
    if entrada["rol"] == "error":
        st.error(entrada["texto"])
    else:
        with st.chat_message("user" if entrada["rol"] == "usuario" else "assistant"):
            st.write(entrada["texto"])
            if entrada["rol"] == "asistente":
                # Pasos de ese turno: tools y registro visible, sin los diagnósticos del supervisor (RF-39 a RF-41).
                pasos = pasos_del_turno(entrada.get("log", []), entrada.get("traza", []), ocultar_tecnicas=True)
                if pasos:
                    with st.expander("Pasos seguidos"):
                        for linea in pasos:
                            st.text(linea)

# Con un plan pendiente el cuadro de mensaje queda bloqueado hasta aprobar o rechazar (RF-22b).
mensaje = st.chat_input(
    "Escribe tu pregunta sobre transporte en Madrid...",
    disabled=not sesion.puede_escribir,
)
if sesion.puede_decidir:
    st.info("Hay un plan pendiente: apruébalo o recházalo en la barra lateral para continuar.")

if mensaje:
    # El historial se dibuja antes de llamar al grafo: sin esto la pregunta no aparecería hasta recibir la
    # respuesta. Se dibuja la burbuja de la persona y un indicador de espera mientras responde (RF-38).
    with st.chat_message("user"):
        st.write(mensaje)
    with st.chat_message("assistant"), st.spinner("Consultando al asistente..."):
        sesion.enviar(mensaje)
    st.rerun()
