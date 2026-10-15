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


def test_hora_llegada_no_calcula(ahora_invierno):
    # RF-39: si se pide hora de llegada no se calcula nada, aunque la hora de salida sea válida o no.
    assert pr.validar_hora(None, "2026-01-12T09:00")["estado"] == "hora_llegada_no_admitida"
    assert pr.validar_hora("2026-01-12T08:30", "2026-01-12T09:00")["estado"] == "hora_llegada_no_admitida"
    assert pr.validar_hora("rara", "9:00")["estado"] == "hora_llegada_no_admitida"
    # Una hora de llegada vacía equivale a no haberla pedido.
    assert pr.validar_hora("2026-01-12T08:30", "  ")["estado"] == "ok"


def test_titulo_vacio_aplica_billete_sencillo():
    # RF-19: si no se indica título se considera el billete sencillo.
    for vacio in (None, "", "   "):
        assert pr.resolver_titulo(vacio) == (config.TITULO_POR_DEFECTO, True)
    assert config.TITULO_POR_DEFECTO == "billete sencillo"


def test_titulo_de_la_lista_se_normaliza_a_su_valor_canonico():
    # RF-35: los títulos de la lista cerrada se reconocen sin importar mayúsculas ni espacios.
    assert pr.resolver_titulo("Billete de 10 viajes ") == ("billete de 10 viajes", True)
    assert pr.resolver_titulo("BILLETE   SENCILLO") == ("billete sencillo", True)


def test_titulo_fuera_de_lista_no_esta_disponible():
    # RF-36: un título fuera de la lista (p. ej. un abono) se conserva tal cual y se marca no disponible.
    assert pr.resolver_titulo("abono mensual") == ("abono mensual", False)
    assert pr.resolver_titulo(123) == ("123", False)


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
    "hora_llegada_no_admitida": (_con(), {"hora_llegada": "2026-10-15T09:00"}),
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


@pytest.mark.parametrize("estado", ["hora_llegada_no_admitida", "hora_no_interpretable", "hora_pasada",
                                    "hora_demasiado_lejana", "faltan_datos"])
def test_validaciones_de_entrada_no_usan_la_red(esc, estado):
    # Orden: las validaciones baratas van primero; con una entrada rechazada no se llama a nada externo.
    configurar, args = ESTADOS[estado]
    pr.planificar_ruta(**{"origen": "Sol", "destino": "Bernabéu", **args})
    assert esc.orden == []


def test_la_hora_actual_solo_sale_de_reloj_ahora():
    # La herramienta no lee el reloj del sistema por su cuenta: toda hora pasa por `ahora()` (src/reloj.py).
    codigo = open(pr.__file__, encoding="utf-8").read()
    assert "datetime.now" not in codigo and "time.time(" not in codigo and "date.today" not in codigo
    assert "from src.reloj import ahora" in codigo


def test_titulo_no_disponible_lista_los_disponibles(esc):
    # RF-36: ruta y zona sí; el precio se omite y se muestran los títulos disponibles.
    r = pr.planificar_ruta("Sol", "Bernabéu", titulo="abono joven")
    assert r["estado"] == "ok" and r["precio"]["estado"] == "omitida" and r["zona"]["estado"] == "ok"
    assert "abono joven" in r["mensaje"] and "no está disponible" in r["mensaje"]
    assert all(t in r["mensaje"] for t in config.TITULOS_TRANSPORTE)
    assert esc.cuantas("rag") == 1
