"""Tool calculadora: evalúa expresiones aritméticas básicas de forma segura (sin eval)."""
import ast
import math
import operator
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import config

# Operaciones permitidas; cualquier otro nodo del árbol se rechaza.
OPERADORES_BINARIOS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
OPERADORES_UNARIOS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


class ExpresionNoPermitida(Exception):
    """La expresión contiene algo distinto de números y operaciones básicas."""


def _evaluar(nodo) -> Decimal:
    """Evalúa recursivamente un nodo del árbol usando Decimal para no arrastrar errores de coma flotante."""
    if isinstance(nodo, ast.Expression):
        return _evaluar(nodo.body)
    if isinstance(nodo, ast.Constant):
        valor = nodo.value
        # bool es subclase de int: se excluye junto con cadenas y complejos.
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ExpresionNoPermitida
        if isinstance(valor, float) and not math.isfinite(valor):
            raise ExpresionNoPermitida
        return Decimal(str(valor))
    if isinstance(nodo, ast.BinOp) and type(nodo.op) in OPERADORES_BINARIOS:
        return OPERADORES_BINARIOS[type(nodo.op)](_evaluar(nodo.left), _evaluar(nodo.right))
    if isinstance(nodo, ast.UnaryOp) and type(nodo.op) in OPERADORES_UNARIOS:
        return OPERADORES_UNARIOS[type(nodo.op)](_evaluar(nodo.operand))
    raise ExpresionNoPermitida


def _formatear(valor: Decimal) -> str:
    """Enteros sin decimales; el resto con 2 decimales y coma (importes en euros)."""
    if valor == valor.to_integral_value():
        return str(int(valor))
    redondeado = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if redondeado == 0:
        redondeado = abs(redondeado)  # evita "-0,00"
    return f"{redondeado:.2f}".replace(".", ",")


def calculadora(expresion: str) -> str:
    """Devuelve el resultado de la expresión como texto, o "ERROR: ..." si no es válida."""
    if not isinstance(expresion, str) or not expresion.strip():
        return "ERROR: expresión vacía"
    if len(expresion) > config.CALC_MAX_CARACTERES:
        return f"ERROR: expresión demasiado larga (máximo {config.CALC_MAX_CARACTERES} caracteres)"

    try:
        # La coma decimal se normaliza a punto antes de analizar la expresión.
        arbol = ast.parse(expresion.strip().replace(",", "."), mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return "ERROR: expresión mal formada"

    try:
        return _formatear(_evaluar(arbol))
    except ExpresionNoPermitida:
        return "ERROR: expresión no permitida"
    except (ZeroDivisionError, InvalidOperation):
        return "ERROR: división entre cero"
    except (ArithmeticError, RecursionError):
        return "ERROR: no se pudo calcular la expresión"
