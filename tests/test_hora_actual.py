"""Tests de la tool hora_actual (spec 001, RF-1 a RF-5). No usan red ni API."""
import socket
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config
from src.tools.hora_actual import hora_actual

MADRID = ZoneInfo("Europe/Madrid")


def test_formato_laborable():
    # RF-1: fecha, hora, día de la semana y tipo de día (martes = laborable).
    texto = hora_actual(datetime(2026, 10, 13, 17, 58, tzinfo=MADRID))
    assert "martes" in texto
    assert "13/10/2026" in texto
    assert "17:58" in texto
    assert "laborable" in texto


def test_sabado_domingo():
    # RF-1: el sábado y el domingo se distinguen del día laborable.
    sabado = hora_actual(datetime(2026, 10, 17, 9, 5, tzinfo=MADRID))
    domingo = hora_actual(datetime(2026, 10, 18, 9, 5, tzinfo=MADRID))
    assert "sábado" in sabado and "laborable" not in sabado
    assert "domingo" in domingo and "laborable" not in domingo


def test_sin_argumentos():
    # RF-2: se puede ejecutar sin ningún argumento y devuelve texto.
    texto = hora_actual()
    assert isinstance(texto, str) and texto
    assert not texto.startswith("ERROR")


def test_sin_red(monkeypatch):
    # RF-3: no abre ninguna conexión de red.
    def sin_red(*args, **kwargs):
        raise AssertionError("hora_actual no debe usar la red")

    monkeypatch.setattr(socket, "socket", sin_red)
    assert not hora_actual(datetime(2026, 10, 13, 17, 58, tzinfo=MADRID)).startswith("ERROR")


def test_zona_horaria_configurable(monkeypatch):
    # RF-4: la zona horaria sale de config.ZONA_HORARIA.
    instante = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    assert "14:00" in hora_actual(instante)  # Madrid en octubre = UTC+2
    monkeypatch.setattr(config, "ZONA_HORARIA", "UTC")
    assert "12:00" in hora_actual(instante)


def test_zona_invalida(monkeypatch):
    # RF-5: zona inexistente -> error controlado, sin excepción.
    monkeypatch.setattr(config, "ZONA_HORARIA", "Zona/Inexistente")
    texto = hora_actual(datetime(2026, 10, 13, 17, 58, tzinfo=MADRID))
    assert texto.startswith("ERROR:")
