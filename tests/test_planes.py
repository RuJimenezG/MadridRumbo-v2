"""Tests de las funciones puras de planes de los clientes (spec 008, RF-30, RF-33 y RF-35).

Un plan del grafo real es `{"id": "ruta-1", "resultado": {...}}`. No usan grafo, red ni API.
"""
import config
from src.clientes.planes import es_entrada_tecnica_supervisor, ids_de_planes, resumir_plan

RUTA = {
    "estado": "ok",
    "mensaje": "Ruta calculada",
    "hora_salida": None,
    "titulo": "billete sencillo",
    "origen": {"direccion": "Puerta del Sol, Madrid"},
    "destino": {"direccion": "Estación de Atocha, Madrid"},
    "ruta": {
        "duracion_min": 12,
        "tramos": [
            {"modo": "A pie", "linea": None, "desde": None, "hasta": None, "duracion_min": 3},
            {"modo": "SUBWAY", "linea": "1", "desde": "Sol", "hasta": "Atocha", "duracion_min": 9},
        ],
        "fuente": "Google Routes",
    },
    "zona": {"estado": "ok", "texto": "Zona A según la tabla tarifaria.", "fuente": "RAG"},
    "precio": {"estado": "ok", "texto": "El billete sencillo cuesta 1,50 €.", "fuente": "RAG"},
}
PLAN = {"id": "ruta-1", "resultado": RUTA}


# --- Resumen de un plan (RF-30) ---

def test_resumen_de_ruta_completo():
    texto = resumir_plan(PLAN)
    assert "ruta-1" in texto
    assert "Origen: Puerta del Sol, Madrid" in texto
    assert "Destino: Estación de Atocha, Madrid" in texto
    assert "12 min" in texto
    assert "A pie" in texto and "3 min" in texto
    assert "SUBWAY" in texto and "línea 1" in texto
    assert "Sol" in texto and "Atocha" in texto and "9 min" in texto
    assert "Zona A según la tabla tarifaria." in texto
    assert "1,50 €" in texto
    assert "billete sencillo" in texto


def test_los_tramos_salen_en_orden():
    texto = resumir_plan(PLAN)
    assert texto.index("A pie") < texto.index("SUBWAY")


def test_resumen_sin_tramos():
    ruta = {**RUTA, "ruta": {"duracion_min": 12, "tramos": [], "fuente": "Google Routes"}}
    texto = resumir_plan({"id": "ruta-2", "resultado": ruta})
    assert "12 min" in texto
    assert "Tramos" not in texto


def test_resumen_sin_zona_ni_precio():
    ruta = {k: v for k, v in RUTA.items() if k not in ("zona", "precio")}
    texto = resumir_plan({"id": "ruta-3", "resultado": ruta})
    assert "Origen" in texto and "12 min" in texto
    assert "Zona" not in texto and "Precio" not in texto


def test_zona_o_precio_sin_evidencia_se_marcan_como_no_disponibles():
    ruta = {
        **RUTA,
        "zona": {"estado": "sin_evidencia", "texto": None, "fuente": "RAG"},
        "precio": {"estado": "error", "texto": None, "fuente": "RAG"},
    }
    texto = resumir_plan({"id": "ruta-4", "resultado": ruta})
    assert "Zona: no disponible" in texto
    assert "Precio: no disponible" in texto


# --- Formato desconocido (RF-33) ---

def test_plan_de_formato_desconocido():
    # Un resultado sin las claves de una ruta se muestra como clave: valor, sin fallar.
    texto = resumir_plan({"id": "otro-1", "resultado": {"cosa": 1, "otra": {"a": 2}}})
    assert "otro-1" in texto
    assert "cosa: 1" in texto
    assert "otra" in texto and "a" in texto


def test_resultado_que_no_es_un_diccionario():
    for resultado in ("texto suelto", None, 42, ["lista"]):
        texto = resumir_plan({"id": "raro-1", "resultado": resultado})
        assert "raro-1" in texto


def test_plan_que_no_es_un_diccionario():
    assert "texto" in resumir_plan("texto")
    assert isinstance(resumir_plan(None), str)


def test_ruta_con_campos_de_otro_tipo_no_falla():
    ruta = {"origen": "Sol", "destino": None, "ruta": {"duracion_min": "mucho", "tramos": "no es lista"}}
    texto = resumir_plan({"id": "ruta-5", "resultado": ruta})
    assert "ruta-5" in texto


# --- Identificadores (RF-31) ---

def test_ids_de_planes():
    planes = [{"id": "ruta-1", "resultado": {}}, {"id": "ruta-2", "resultado": {}}]
    assert ids_de_planes(planes) == ["ruta-1", "ruta-2"]


def test_ids_ignora_entradas_invalidas():
    planes = [{"id": "ruta-1"}, {"resultado": {}}, "texto", None, {"id": 7}, {"id": ""}]
    assert ids_de_planes(planes) == ["ruta-1"]


def test_ids_de_lo_que_no_es_una_lista():
    assert ids_de_planes([]) == []
    assert ids_de_planes(None) == []
    assert ids_de_planes("ruta-1") == []


# --- Entradas técnicas del supervisor (RF-35) ---

def test_entradas_tecnicas():
    assert es_entrada_tecnica_supervisor(
        {"nodo": "supervisor", "detalle": {"categoria": "json_invalido", "resumen": "Fallback aplicado."}}
    )


def test_cada_diagnostico_estructurado_del_supervisor_se_reconoce():
    for categoria in ("json_invalido", "correccion_semantica"):
        assert es_entrada_tecnica_supervisor(
            {"nodo": "supervisor", "detalle": {"categoria": categoria, "resumen": "Resumen seguro."}}
        )


def test_otras_entradas_del_log_no_son_tecnicas():
    for linea in [
        {"nodo": "supervisor", "detalle": None},
        {"nodo": "rutas", "detalle": {"categoria": "ok", "resumen": "Correcto."}},
        {"nodo": "fachada", "detalle": {"categoria": "plan_pendiente", "resumen": "Pendiente."}},
    ]:
        assert es_entrada_tecnica_supervisor(linea) is False


def test_entrada_tecnica_con_valores_que_no_son_texto():
    for valor in (None, 5, [{"nodo": "supervisor"}]):
        assert es_entrada_tecnica_supervisor(valor) is False
