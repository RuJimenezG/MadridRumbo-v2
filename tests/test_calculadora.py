"""Tests de la tool calculadora (spec 002, RF-12 a RF-18). Son locales: sin red ni API."""
import socket

import pytest

import config
from src.tools.calculadora import calculadora


@pytest.mark.parametrize("expresion, esperado", [
    ("2+3", "5"),
    ("10-4", "6"),
    ("3*4", "12"),
    ("10/4", "2,50"),
    ("(1+2)*3", "9"),
    ("-(4+1)", "-5"),
    ("+7", "7"),
    ("10-10", "0"),
])
def test_operaciones(expresion, esperado):
    # RF-12 y RF-13: suma, resta, multiplicación, división, paréntesis y signo menos.
    assert calculadora(expresion) == esperado


def test_decimales_coma():
    # RF-13: los decimales pueden escribirse con punto o con coma.
    assert calculadora("3*2,40") == "7,20"
    assert calculadora("3*2.40") == "7,20"
    assert calculadora("3 * 2,40 + 2 * 54,60") == "116,40"


def test_formato_resultado():
    # RF-14: máximo 2 decimales, con coma; enteros sin decimales.
    assert calculadora("1/3") == "0,33"
    assert calculadora("2/3") == "0,67"
    assert calculadora("0,1+0,2") == "0,30"  # sin errores de coma flotante
    assert calculadora("2.675*1") == "2,68"  # redondeo comercial (mitad hacia arriba)


@pytest.mark.parametrize("expresion", [
    "abs(3)", "__import__('os')", "2**3", "2**9999", "a+1", "3;4", "2%3", "[1,2]", "'a'*3",
])
def test_expresion_no_permitida(expresion):
    # RF-15: letras, funciones, potencias o cualquier otro nodo -> error sin ejecutar nada.
    resultado = calculadora(expresion)
    assert resultado.startswith("ERROR:")


def test_division_cero():
    # RF-16
    assert "división entre cero" in calculadora("1/0")
    assert "división entre cero" in calculadora("5/(2-2)")


def test_expresion_vacia_o_larga():
    # RF-17: vacía, mal formada o por encima del máximo configurado.
    assert calculadora("").startswith("ERROR:")
    assert calculadora("   ").startswith("ERROR:")
    assert calculadora("2+").startswith("ERROR:")
    larga = "1+" * config.CALC_MAX_CARACTERES + "1"
    assert calculadora(larga).startswith("ERROR:")
    assert calculadora("1" * config.CALC_MAX_CARACTERES) != ""  # justo en el límite no es "larga"


def test_sin_red(monkeypatch):
    # RF-18: no usa red.
    def sin_red(*args, **kwargs):
        raise AssertionError("calculadora no debe usar la red")

    monkeypatch.setattr(socket, "socket", sin_red)
    assert calculadora("2+2") == "4"
