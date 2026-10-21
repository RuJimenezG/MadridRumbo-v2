"""Spec 010, T14 (RF-39 y RF-40): el LLM del sintetizador no ve los textos de los `bloques` que luego se añaden
literales, recibe una nota que lo avisa y solo ve los resultados del turno actual. Sin LLM ni red."""
import json

from src.graph import crear_grafo, invocar_grafo
from src.sintetizador import nodo_sintetizador, renderizar_respaldo
from tests.dobles_grafo import EjecutorFalso, LLMFalso
from tests.test_sintetizador_avisos import AVISO, BICI_OK, resultado_ruta
from tests.test_sintetizador_bloques import MOTIVO, OPCIONES, PARRAFO_BICI

NOTA = "Zona, precio, clima, bici y opciones se añaden después de forma automática; no los repitas ni los resumas."
CABECERA = "Salida: ahora · Título: billete sencillo."
TEXTO_MODELO = "Tienes ruta en metro de unos 22 minutos."


class Modelo:
    """Modelo falso: guarda el contexto recibido y responde un texto fijo que no repite los bloques."""

    def __init__(self, texto=TEXTO_MODELO):
        self.texto, self.contextos = texto, []

    def __call__(self, contexto):
        self.contextos.append(json.loads(json.dumps(contexto)))
        return self.texto


def estado(*resultados, notas=None, historial=None):
    e = {"notas": notas or [], "resultados": list(resultados), "traza": []}
    if historial is not None:
        e["historial"] = historial
    return e


def con_bloques(**campos):
    return resultado_ruta(mensaje=f"{CABECERA} {OPCIONES} {MOTIVO}", bloques=[OPCIONES, MOTIVO], **campos)


# --- RF-39: sin los textos de los bloques y con la nota ---

def test_el_contexto_no_lleva_los_textos_de_los_bloques_y_si_la_nota():
    modelo = Modelo()
    nodo_sintetizador(estado(con_bloques(), notas=[f"[rutas] {OPCIONES}", "[rag] Otra nota."]), modelo)
    contexto = modelo.contextos[0]
    texto = json.dumps(contexto, ensure_ascii=False)
    assert OPCIONES not in texto and MOTIVO not in texto                       # ni en `resultado` ni en `notas`
    assert contexto["nota"] == NOTA
    assert CABECERA in texto and "[rag] Otra nota." in texto                    # lo demás se conserva
    datos = json.loads(contexto["resultados"][0]["resultado"])
    assert "bloques" not in datos and datos["estado"] == "ok" and datos["mensaje"].strip() == CABECERA


def test_la_respuesta_lleva_cada_texto_una_sola_vez():
    respuesta = nodo_sintetizador(estado(con_bloques()), Modelo())["respuesta"]
    assert respuesta == f"{TEXTO_MODELO}\n\n{OPCIONES}\n\n{MOTIVO}"
    assert respuesta.count(OPCIONES) == 1 and respuesta.count(MOTIVO) == 1


def test_los_avisos_y_el_aviso_dentro_del_bloque_siguen_funcionando():
    resultado = resultado_ruta(mensaje=f"{CABECERA} {PARRAFO_BICI}", bloques=[PARRAFO_BICI], bici=BICI_OK)
    modelo = Modelo()
    respuesta = nodo_sintetizador(estado(resultado), modelo)["respuesta"]
    assert respuesta == f"{TEXTO_MODELO}\n\n{PARRAFO_BICI}" and respuesta.count(AVISO) == 1
    assert PARRAFO_BICI not in json.dumps(modelo.contextos[0], ensure_ascii=False)


def test_sin_bloques_el_contexto_no_cambia():
    modelo = Modelo()
    entrada = estado(resultado_ruta(), notas=["[rutas] Ruta."])
    nodo_sintetizador(entrada, modelo)
    contexto = modelo.contextos[0]
    assert set(contexto) == {"notas", "resultados", "traza"} and "nota" not in contexto
    assert contexto["resultados"] == entrada["resultados"] and contexto["notas"] == entrada["notas"]


def test_resultado_ilegible_o_de_otra_tool_no_se_toca():
    ilegible = {**resultado_ruta(), "resultado": "ERROR: no se pudo ejecutar planificar_ruta."}
    otro = {"especialista": "rag", "tool": "rag_ask", "status": "ok", "resultado": f"{OPCIONES} (del RAG)"}
    modelo = Modelo()
    nodo_sintetizador(estado(ilegible, otro, con_bloques()), modelo)
    resultados = modelo.contextos[0]["resultados"]
    assert resultados[0] == ilegible and resultados[1] == otro                   # solo se limpian los de planificar_ruta


def test_el_respaldo_usa_el_contexto_completo():
    def roto(contexto):
        raise RuntimeError("caído")

    entrada = estado(con_bloques())
    salida = nodo_sintetizador(entrada, roto)
    assert salida["respuesta"] == renderizar_respaldo(entrada) and OPCIONES in salida["respuesta"]
    assert salida["log"] == ["Sintetizador: se ha usado el respaldo determinista."]


# --- RF-40: solo el turno actual ---

def de_turno(turno, **campos):
    return {**resultado_ruta(**campos), "turno": turno}


def usuario(n):
    return [{"role": "user", "content": f"mensaje {i}"} for i in range(1, n + 1)]


def test_el_llm_solo_ve_los_resultados_del_turno_actual():
    modelo = Modelo()
    antiguo = de_turno(1, mensaje="RESULTADO ANTIGUO")
    actual = de_turno(2, mensaje="RESULTADO ACTUAL")
    sin_marca = resultado_ruta(mensaje="SIN MARCA")
    nodo_sintetizador(estado(antiguo, actual, sin_marca, historial=usuario(2)), modelo)
    texto = json.dumps(modelo.contextos[0], ensure_ascii=False)
    assert "RESULTADO ACTUAL" in texto and "SIN MARCA" in texto and "RESULTADO ANTIGUO" not in texto


def test_sin_historial_el_llm_ve_todos_los_resultados():
    modelo = Modelo()
    nodo_sintetizador(estado(de_turno(1, mensaje="UNO"), de_turno(2, mensaje="DOS")), modelo)
    assert len(modelo.contextos[0]["resultados"]) == 2


def test_el_respaldo_sigue_viendo_toda_la_conversacion():
    def roto(contexto):
        raise RuntimeError("caído")

    entrada = estado(de_turno(1, mensaje="RESULTADO ANTIGUO"), de_turno(2, mensaje="ACTUAL"), historial=usuario(2))
    assert "RESULTADO ANTIGUO" in nodo_sintetizador(entrada, roto)["respuesta"]      # respaldo sin cambios


def test_en_el_grafo_el_llm_no_ve_el_turno_anterior_ni_los_bloques():
    def ruta(**campos):
        return json.dumps({"estado": "ruta_no_calculada", **campos}, ensure_ascii=False)

    ejecutor = EjecutorFalso({"planificar_ruta": [
        ruta(mensaje=f"{CABECERA} PRIMERO. {OPCIONES}", bloques=[OPCIONES]),
        ruta(mensaje=f"{CABECERA} SEGUNDO. {MOTIVO}", bloques=[MOTIVO]),
    ]})
    llm = LLMFalso([{"tool": "planificar_ruta", "args": {"origen": "a", "destino": "b"}}, {"final": "x"}] * 2)
    modelo = Modelo()
    grafo = crear_grafo(modelo_supervisor=lambda m: {"roles": ["rutas"]}, modelos_especialistas={"rutas": llm},
                        ejecutar=ejecutor, modelo_sintetizador=modelo)

    def turno(mensaje):
        return invocar_grafo(grafo, {"mensaje": mensaje, "tools_turno": 0, "limite_tools_alcanzado": False,
                                     "turno_contabilizado": False, "limite_turnos": False}, "ctx")

    turno("primero")
    segundo = turno("segundo")
    texto = json.dumps(modelo.contextos[1]["resultados"], ensure_ascii=False)
    assert "SEGUNDO" in texto and "PRIMERO" not in texto and MOTIVO not in texto
    assert modelo.contextos[1]["nota"] == NOTA
    assert segundo["respuesta"] == f"{TEXTO_MODELO}\n\n{MOTIVO}"
