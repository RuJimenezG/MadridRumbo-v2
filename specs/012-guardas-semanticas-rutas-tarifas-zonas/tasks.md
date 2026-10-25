# Tareas — Spec 012

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.

- [x] T1. Añadir primero pruebas unitarias para los pares tarifarios y los límites de la detección; después, centralizar en el catálogo los códigos de zona, los conectores admitidos, la exclusión de ruta física y la aclaración para el Supervisor. (RF-1, RF-2, RF-3, RF-4, RF-5, RF-14, RF-15)
      Hecho cuando: `python -m pytest tests/test_catalogo_roles.py` queda verde e incluye los tres formatos A–B2, la variante de mayúsculas, una única zona, una imagen válida y «¿Cómo llego desde la zona A a Sol?».

- [x] T2. Añadir primero pruebas del Supervisor para una cola LLM válida; después, corregir las apariciones incompatibles de `rutas` a `rag` y conservar orden, repeticiones y `sin_fallback`. (RF-6, RF-7, RF-8, RF-15, RF-16)
      Hecho cuando: `python -m pytest tests/test_supervisor_grafo.py tests/test_supervisor_ruta_con_extremos.py` queda verde e incluye `{"roles": ["rutas"]}` corregido para A–B2 y una ruta física Sol–Atocha con precio que conserva `rutas`.

- [x] T3. Añadir primero pruebas del contexto y del registro estructurado; después, transportar solo el contador efímero de correcciones de rutas y publicar un diagnóstico técnico seguro, separado del fallback y no persistido. (RF-9, RF-10, RF-11, RF-12)
      Hecho cuando: `python -m pytest tests/test_agent_contrato.py tests/test_depuracion.py tests/test_presentacion.py` queda verde y demuestra una entrada técnica `correccion_semantica`, sin salida LLM cruda, ausente del checkpoint y filtrada del chat de Streamlit.

- [x] T4. Añadir primero pruebas de recorrido con dobles; después, verificar que una consulta de precio entre zonas ejecuta RAG con su traza y que una ruta física con precio conserva los especialistas correspondientes. (RF-5, RF-6, RF-7, RF-13, RF-16)
      Hecho cuando: `python -m pytest tests/test_grafo_enrutamiento.py` queda verde e incluye cero llamadas a rutas y una traza `rag_ask` para A–B2, además de la no regresión Sol–Atocha.

- [x] T5. Ejecutar la validación final RF por RF y documentar el resultado. (Todos los RF)
      Hecho cuando: `python -m pytest` queda verde y `specs/012-guardas-semanticas-rutas-tarifas-zonas/validacion.md` contiene un veredicto «Sí» para RF-1 a RF-16, con las pruebas y evidencias asociadas.
