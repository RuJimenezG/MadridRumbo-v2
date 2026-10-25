"""Punto de entrada del CLI de MadridRumbo: `python main.py`.

Es una capa fina: elige el grafo (real o simulado) y delega en `src/clientes/cli.py`.
"""
import sys

from src.clientes.cargar import GrafoNoDisponible, cargar_agente
from src.clientes.cli import ejecutar_cli


def main(argv: list[str] | None = None) -> int:
    try:
        agente, aviso = cargar_agente()
    except GrafoNoDisponible as error:
        print(error)
        return 1
    argumentos = sys.argv[1:] if argv is None else argv
    return ejecutar_cli(argumentos, agente, input, print, aviso)


if __name__ == "__main__":
    raise SystemExit(main())
