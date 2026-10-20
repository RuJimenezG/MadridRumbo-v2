"""Tests de hora de salida y título de planificar_ruta (spec 004). No usan API.

La hora actual se fija parcheando `ahora` en el módulo que la usa.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import config
from src.tools import planificar_ruta as pr
from tests.dobles_ruta import ATOCHA, BARCELONA, BERNABEU, SOL, Escenario

MADRID = ZoneInfo("Europe/Madrid")


def fijar_ahora(monkeypatch, *args):
    """Fija el instante actual (hora de Madrid) que ven las funciones del módulo."""
    instante = datetime(*args, tzinfo=MADRID)
    monkeypatch.setattr(pr, "ahora", lambda: instante)
    return instante


@pytest.fixture
def ahora_invierno(monkeypatch):
    # Sábado 10/01/2026 10:00:45 (con segundos para comprobar que se compara a nivel de minuto).
    return fijar_ahora(monkeypatch, 2026, 1, 10, 10, 0, 45)


def test_sin_hora_usa_momento_de_consulta(ahora_invierno):
    # RF-14: sin hora de salida, la hora considerada es la de la consulta y no se envía departureTime.
    for vacia in (None, "", "   "):
        r = pr.validar_hora(vacia)
        assert r["estado"] == "ok"
        assert r["considerada"] == ahora_invierno
        assert r["salida_rfc3339"] is None


def test_hora_pedida_se_acepta_como_hora_considerada(ahora_invierno):
    # RF-31: la hora pedida es la considerada para calcular la ruta.
    r = pr.validar_hora("2026-01-12T08:30")
    assert r["estado"] == "ok"
    assert r["considerada"] == datetime(2026, 1, 12, 8, 30, tzinfo=MADRID)


def test_hora_rfc3339_con_desplazamiento_de_madrid(monkeypatch):
    # RF-31: la hora se envía a Google en RFC 3339 con el desplazamiento real de Madrid en esa fecha.
    fijar_ahora(monkeypatch, 2026, 1, 10, 10, 0)
    assert pr.validar_hora("2026-01-15T08:30")["salida_rfc3339"] == "2026-01-15T08:30:00+01:00"
    # Una hora con otro desplazamiento se convierte a hora de Madrid.
    assert pr.validar_hora("2026-01-15T07:30:00+00:00")["salida_rfc3339"] == "2026-01-15T08:30:00+01:00"

    fijar_ahora(monkeypatch, 2026, 7, 10, 10, 0)
    assert pr.validar_hora("2026-07-15T08:30")["salida_rfc3339"] == "2026-07-15T08:30:00+02:00"

    # Cambio a horario de verano (domingo 29/03/2026, las 02:00 pasan a ser las 03:00).
    fijar_ahora(monkeypatch, 2026, 3, 28, 12, 0)
    assert pr.validar_hora("2026-03-29T01:30")["salida_rfc3339"] == "2026-03-29T01:30:00+01:00"
    assert pr.validar_hora("2026-03-29T03:30")["salida_rfc3339"] == "2026-03-29T03:30:00+02:00"
    # La hora que no existe ese día no se puede interpretar.
    assert pr.validar_hora("2026-03-29T02:30")["estado"] == "hora_no_interpretable"

    # Cambio a horario de invierno (domingo 25/10/2026, las 03:00 pasan a ser las 02:00).
    fijar_ahora(monkeypatch, 2026, 10, 24, 12, 0)
    assert pr.validar_hora("2026-10-25T01:30")["salida_rfc3339"] == "2026-10-25T01:30:00+02:00"
    assert pr.validar_hora("2026-10-25T03:30")["salida_rfc3339"] == "2026-10-25T03:30:00+01:00"
    # La hora repetida se toma en su primera aparición (horario de verano).
    assert pr.validar_hora("2026-10-25T02:30")["salida_rfc3339"] == "2026-10-25T02:30:00+02:00"


def test_hora_pasada_no_calcula(ahora_invierno):
    # RF-32: una hora anterior al momento de la consulta se rechaza; la del minuto actual no.
    assert pr.validar_hora("2026-01-10T09:59")["estado"] == "hora_pasada"
    assert pr.validar_hora("2026-01-09T23:00")["estado"] == "hora_pasada"
    assert pr.validar_hora("2026-01-10T10:00")["estado"] == "ok"


def test_hora_no_interpretable_no_calcula(ahora_invierno):
    # RF-33: lo que no es una fecha y hora ISO 8601 no se interpreta ni se corrige.
    for rara in ("mañana a las 8", "2026-01-12T25:99", "2026-01-12", "08:30", 830, ["2026-01-12T08:30"]):
        assert pr.validar_hora(rara)["estado"] == "hora_no_interpretable", rara


def test_hora_demasiado_lejana(ahora_invierno):
    # RF-34: pasada la antelación máxima configurada se rechaza; justo en el límite se acepta.
    limite = ahora_invierno.replace(second=0) + timedelta(days=config.ANTELACION_MAX_DIAS)
    assert pr.validar_hora(limite.strftime("%Y-%m-%dT%H:%M"))["estado"] == "ok"
    mas_alla = limite + timedelta(minutes=1)
    assert pr.validar_hora(mas_alla.strftime("%Y-%m-%dT%H:%M"))["estado"] == "hora_demasiado_lejana"


def test_hora_llegada_valida_se_acepta(ahora_invierno):
    # RF-39: la hora de llegada se admite; es la hora considerada y se envía a Google en RFC 3339 (no como salida).
    r = pr.validar_hora(None, "2026-01-15T09:00")
    assert r["estado"] == "ok" and r["tipo"] == "llegada"
    assert r["considerada"] == datetime(2026, 1, 15, 9, 0, tzinfo=MADRID)
    assert r["llegada_rfc3339"] == "2026-01-15T09:00:00+01:00"
    assert r["salida_rfc3339"] is None
    # Una hora de llegada vacía equivale a no haberla pedido.
    assert pr.validar_hora("2026-01-12T08:30", "  ")["tipo"] == "salida"
    assert pr.validar_hora(None, "")["llegada_rfc3339"] is None


def test_salida_y_llegada_a_la_vez_no_calcula(ahora_invierno):
    # RF-43: con salida y llegada a la vez se rechaza, sea cual sea su validez.
    assert pr.validar_hora("2026-01-12T08:30", "2026-01-12T09:00")["estado"] == "horas_incompatibles"
    assert pr.validar_hora("rara", "9:00")["estado"] == "horas_incompatibles"


@pytest.mark.parametrize("llegada, estado", [
    ("2026-01-10T09:59", "hora_pasada"),                 # RF-32
    ("mañana a las 8", "hora_no_interpretable"),         # RF-33
    ("2026-01-12", "hora_no_interpretable"),             # RF-33: falta la hora
    ("2027-01-01T08:00", "hora_demasiado_lejana"),       # RF-34
])
def test_llegada_rechazada_con_las_mismas_reglas_que_la_salida(ahora_invierno, llegada, estado):
    # RF-32, RF-33, RF-34: la hora de llegada se valida igual que la de salida (misma función, mismos estados).
    assert pr.validar_hora(None, llegada)["estado"] == estado
    assert pr.validar_hora(llegada)["estado"] == estado
    assert pr.validar_hora(None, llegada)["llegada_rfc3339"] is None


def test_titulo_vacio_aplica_billete_sencillo():
    # RF-19: si no se indica título se considera el billete sencillo.
    for vacio in (None, "", "   "):
        assert pr.resolver_titulo(vacio) == (config.TITULO_POR_DEFECTO, True)
    assert config.TITULO_POR_DEFECTO == "billete sencillo"


def test_titulo_libre_se_acepta_sin_lista_cerrada():
    # RF-35: cualquier título (abonos, billete sencillo, otros) se acepta tal cual, sin lista cerrada ni forma canónica.
    assert pr.resolver_titulo("Abono mensual") == ("Abono mensual", True)
    assert pr.resolver_titulo("Billete de 10 viajes ") == ("Billete de 10 viajes", True)
    assert pr.resolver_titulo(123) == ("123", True)
    assert not hasattr(config, "TITULOS_TRANSPORTE")      # RF-36 obsoleto: la lista ya no existe


def test_titulo_sin_saltos_de_linea(esc):
    # RF-47: el título saneado no contiene saltos de línea, ni en la cabecera ni en la pregunta al RAG.
    titulo, interpretable = pr.resolver_titulo("abono\njoven\r\nmensual\u2028")
    assert titulo == "abono joven mensual" and interpretable
    assert not any(c in titulo for c in "\r\n\u2028\u2029")
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo="abono\njoven\r\nmensual")
    assert r["titulo"] == "abono joven mensual" and "Título: abono joven mensual." in r["mensaje"]
    assert all("\n" not in p and "\r" not in p for p in esc.preguntas)
    assert "abono joven mensual" in esc.preguntas[1]


def test_titulo_respeta_longitud_maxima():
    # RF-48: hasta TITULO_LONGITUD_MAX se interpreta; un carácter más, no. La longitud se mide ya saneado.
    assert config.TITULO_LONGITUD_MAX == 60
    justo = "a" * config.TITULO_LONGITUD_MAX
    assert pr.resolver_titulo(justo) == (justo, True)
    assert pr.resolver_titulo(f"\n{justo}\n") == (justo, True)
    largo = justo + "a"
    assert pr.resolver_titulo(largo) == (largo, False)


def test_titulo_demasiado_largo_no_consulta_el_precio(esc):
    # RF-48: sin precio, se informa de que no se pudo interpretar el título y se entregan ruta y zona.
    largo = "abono " + "x" * config.TITULO_LONGITUD_MAX
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo=largo)
    assert r["estado"] == "ok" and r["ruta"]["duracion_min"] == 22 and r["zona"]["estado"] == "ok"
    assert r["precio"] == {"estado": "omitida", "texto": None, "fuente": "RAG"}
    assert "no se pudo interpretar el título" in r["mensaje"] and "Zona (RAG)" in r["mensaje"]
    assert esc.cuantas("rag") == 1 and largo not in esc.preguntas[0]      # solo la zona; el título no entra en la pregunta
    # RF-38: la cabecera muestra el título cortado al máximo más «…», nunca entero (tampoco en el campo `titulo`).
    cortado = largo[:config.TITULO_LONGITUD_MAX] + "…"
    assert f"Título: {cortado}." in r["mensaje"] and r["titulo"] == cortado
    assert largo not in r["mensaje"] and largo not in repr(r)


def test_titulo_en_el_limite_no_se_corta(esc):
    # RF-38: un título que no supera el máximo se muestra entero, sin «…».
    justo = "a" * config.TITULO_LONGITUD_MAX
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo=justo)
    assert f"Título: {justo}." in r["mensaje"] and r["titulo"] == justo


def test_titulo_vacio_tras_sanear_usa_sencillo_y_lo_indica(esc):
    # RF-51: un título que queda vacío al sanearlo equivale a no haberlo indicado; la cabecera (RF-38) lo indica.
    for vacio in ("\n", " \r\n ", "\u2028"):
        assert pr.resolver_titulo(vacio) == (config.TITULO_POR_DEFECTO, True)
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo=" \r\n ")
    assert r["titulo"] == "billete sencillo" and "Título: billete sencillo." in r["mensaje"]
    assert "billete sencillo" in esc.preguntas[1]


def test_cabecera_con_hora_pedida_incluye_hora_y_titulo():
    # RF-38: la cabecera de todo mensaje lleva la hora de salida y el título considerados.
    hora = datetime(2026, 1, 15, 8, 30, tzinfo=MADRID)
    assert pr.cabecera(hora, "billete de 10 viajes") == "Salida: 15/01/2026 08:30 · Título: billete de 10 viajes."


def test_cabecera_sin_hora_pedida_indica_ahora():
    # RF-38, RF-14: sin hora de salida se muestra la hora actual marcada como "ahora".
    hora = datetime(2026, 1, 10, 10, 0, tzinfo=MADRID)
    assert pr.cabecera(hora, "billete sencillo", es_ahora=True) == (
        "Salida: ahora (10/01/2026 10:00) · Título: billete sencillo."
    )


def test_cabecera_con_hora_no_interpretable_muestra_el_texto_recibido():
    # RF-38: si la hora no se pudo interpretar, se muestra lo que llegó.
    assert pr.cabecera("mañana a las 8", "billete sencillo") == (
        "Salida: «mañana a las 8» · Título: billete sencillo."
    )


# --- T12: orquestación, hora y título en todos los mensajes (RF-14, RF-32 a RF-34, RF-38, RF-39) ---

@pytest.fixture
def esc(monkeypatch):
    return Escenario(monkeypatch)


def _con(**cambios):
    """Configura el escenario con los atributos indicados (p. ej. nominatim=..., google=...)."""
    # Las listas se copian: el escenario las consume y la tabla ESTADOS se reutiliza en cada caso.
    return lambda esc: [setattr(esc, k, list(v) if isinstance(v, list) else v) for k, v in cambios.items()]


# estado esperado: (configuración del escenario, argumentos de planificar_ruta)
ESTADOS = {
    "ok": (_con(), {}),
    "faltan_datos": (_con(), {"origen": "", "destino": "  "}),
    "horas_incompatibles": (_con(), {"hora_salida": "2026-10-15T09:00", "hora_llegada": "2026-10-15T10:00"}),
    "hora_no_interpretable": (_con(), {"hora_salida": "mañana por la tarde"}),
    "hora_pasada": (_con(), {"hora_salida": "2026-10-15T07:00"}),
    "hora_demasiado_lejana": (_con(), {"hora_salida": "2027-01-01T08:00"}),
    "geocodificacion_fallida": (_con(nominatim=[TimeoutError("t")]), {}),
    "direccion_no_encontrada": (_con(nominatim=[[], [BERNABEU]]), {}),
    "fuera_cobertura": (_con(nominatim=[[BARCELONA], [BERNABEU]]), {}),
    "ambigua": (_con(nominatim=[[SOL, ATOCHA], [BERNABEU]]), {}),
    "misma_ubicacion": (_con(nominatim=[[SOL], [SOL]]), {}),
    "ruta_no_calculada": (_con(google=TimeoutError("t")), {}),
    "sin_ruta": (_con(google={}), {}),
}


@pytest.mark.parametrize("estado", ESTADOS)
@pytest.mark.parametrize("titulo", [None, "billete de 10 viajes", "abono joven"])
def test_todos_los_estados_incluyen_hora_y_titulo(esc, estado, titulo):
    # RF-38: en toda respuesta, `estado` es la primera clave y el mensaje empieza por «Salida: … · Título: …».
    configurar, args = ESTADOS[estado]
    configurar(esc)
    r = pr.planificar_ruta(**{"origen": "Sol", "destino": "Bernabéu", "titulo": titulo, **args})
    assert r["estado"] == estado and list(r)[0] == "estado"
    assert r["mensaje"].startswith("Salida: ") and " · Título: " in r["mensaje"]
    assert r["titulo"] == (titulo or "billete sencillo")
    assert f"Título: {r['titulo']}." in r["mensaje"]
    assert isinstance(r["hora_salida"], str)


def test_cabecera_con_hora_actual_y_con_hora_pedida(esc):
    # RF-14: sin hora se indica «ahora» con la hora de reloj.ahora(); con hora pedida, esa hora.
    assert pr.planificar_ruta("Sol", "Bernabéu")["mensaje"].startswith("Salida: ahora (15/10/2026 08:12) · ")
    esc.nominatim = [[SOL], [BERNABEU]]
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_salida="2026-10-16T09:30")
    assert r["mensaje"].startswith("Salida: 16/10/2026 09:30 · ") and r["hora_salida"] == "2026-10-16T09:30+02:00"


def test_hora_no_interpretable_muestra_el_texto_recibido(esc):
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_salida="cuando salga el sol")
    assert "«cuando salga el sol»" in r["mensaje"]


@pytest.mark.parametrize("estado", ["horas_incompatibles", "hora_no_interpretable", "hora_pasada",
                                    "hora_demasiado_lejana", "faltan_datos"])
def test_validaciones_de_entrada_no_usan_la_red(esc, estado):
    # Orden: las validaciones baratas van primero; con una entrada rechazada no se llama a nada externo.
    configurar, args = ESTADOS[estado]
    pr.planificar_ruta(**{"origen": "Sol", "destino": "Bernabéu", **args})
    assert esc.orden == []


def test_salida_y_llegada_a_la_vez_rechaza_sin_llamar_a_nada(esc):
    # RF-43: informa de que no se pueden combinar y pide elegir una; ni Nominatim ni Google ni el RAG.
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_salida="2026-10-16T08:00", hora_llegada="2026-10-16T09:00")
    assert r["estado"] == "horas_incompatibles" and list(r)[0] == "estado"
    assert "no se pueden combinar" in r["mensaje"].lower() and "elige una" in r["mensaje"].lower()
    assert r["mensaje"].startswith("Salida: ") and " · Título: billete sencillo." in r["mensaje"]
    assert r["ruta"] is None and esc.orden == []


@pytest.mark.parametrize("llegada, estado", [
    ("2026-10-15T07:00", "hora_pasada"),
    ("cuando salga el sol", "hora_no_interpretable"),
    ("2027-01-01T08:00", "hora_demasiado_lejana"),
])
def test_llegada_rechazada_no_usa_la_red_y_lleva_cabecera(esc, llegada, estado):
    # RF-32, RF-33, RF-34 con hora de llegada: no se llama a nada y el mensaje lleva la hora de llegada y el título.
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_llegada=llegada)
    assert r["estado"] == estado and esc.orden == []
    assert r["mensaje"].startswith("Llegada: ") and " · Título: billete sencillo." in r["mensaje"]
    assert "llegada" in r["mensaje"].split(". ", 1)[1]        # el rechazo habla de la hora de llegada
    assert r["hora_llegada"] is not None and r["salida_resultante"] is None


def test_cabecera_de_llegada_indica_la_hora_de_llegada_considerada(esc):
    # RF-38: con hora de llegada la cabecera lleva la hora considerada (de llegada) y el título.
    esc.nominatim = [[SOL], [BERNABEU]]
    r = pr.planificar_ruta("Sol", "Bernabéu", hora_llegada="2026-10-16T09:30")
    assert r["estado"] == "ok"
    assert r["mensaje"].startswith("Llegada: 16/10/2026 09:30 · Título: billete sencillo. ")
    assert r["hora_llegada"] == "2026-10-16T09:30+02:00"


def test_la_hora_actual_solo_sale_de_reloj_ahora():
    # La herramienta no lee el reloj del sistema por su cuenta: toda hora pasa por `ahora()` (src/reloj.py).
    codigo = open(pr.__file__, encoding="utf-8").read()
    assert "datetime.now" not in codigo and "time.time(" not in codigo and "date.today" not in codigo
    assert "from src.reloj import ahora" in codigo


def test_titulo_libre_nunca_supera_dos_llamadas_al_rag(esc):
    # RF-35 y RNF Coste: cualquier título, incluso uno raro, hace como mucho 2 llamadas al RAG (zona y precio).
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo="abono joven")
    assert r["estado"] == "ok" and r["precio"]["estado"] == "ok" and "abono joven" in r["mensaje"]
    assert "no está disponible" not in r["mensaje"] and esc.cuantas("rag") == 2
