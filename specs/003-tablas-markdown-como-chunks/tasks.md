# Tareas — Spec 003

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.

- [x] T1. Añadir primero las pruebas de una tabla Markdown válida y, después, implementar su detección y emisión como un chunk indivisible con título, metadatos de estrategia y exclusión de esa misma ocurrencia de los fragmentos ordinarios. Debe incluir una tabla que supere el límite ordinario y dos tablas consecutivas con título repetido. (RF-1, RF-2, RF-3, RF-4)
      Hecho cuando: `python -m pytest tests/test_chunk_tablas_markdown.py -k "valida or titulo_y_filas_completas or mayor_que_limite or titulo_repetido or no_se_duplican"` termina en verde y `python -m pytest` también termina en verde.

- [x] T2. Añadir primero las pruebas de formatos no válidos, texto Markdown fuera de tablas y formatos no Markdown; después, completar la ruta de fragmentación para que solo preserve como indivisibles las tablas Markdown válidas y mantenga los comportamientos existentes en los demás casos. (RF-5, RF-6, RF-7)
      Hecho cuando: `python -m pytest tests/test_chunk_tablas_markdown.py -k "sin_titulo or separador_invalido or sin_encabezado or alrededor_de_tabla or no_markdown or bloque_csv"` termina en verde y `python -m pytest` también termina en verde.

- [x] T3. Validación final RF por RF (`/sdd-validar`). (Todos)
      Hecho cuando: `validacion.md` registra un veredicto «Sí» para RF-1 a RF-7 y `python -m pytest` termina en verde.

Cobertura: RF-1, RF-2, RF-3 y RF-4 están en T1; RF-5, RF-6 y RF-7 están en T2; T3 valida todos los RF. No falta ninguno.
