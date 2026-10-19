# Tareas — Spec 002

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.

- [x] T1. Añadir a `config.py` `IMAGENES_DIR`, `IMAGEN_DEMO`, `IMAGEN_MAX_MB`, `EXTENSIONES_IMAGEN`, `MODELO_VISION` y `CALC_MAX_CARACTERES = 200`. (RF-3, RF-5, RF-6, RF-17)
      Hecho cuando: `python -c "import config; print(config.CALC_MAX_CARACTERES)"` imprime `200`.
- [x] T2. Escribir los tests de `describir_imagen` con cliente falso. (RF-1–8)
      Hecho cuando: los tests existen y fallan porque la función no existe.
- [x] T3. Implementar `src/tools/describir_imagen.py`. (RF-1–8)
      Hecho cuando: `pytest tests/test_describir_imagen.py` en verde.
- [x] T4. Escribir los tests de `calculadora` (operaciones, decimales con coma, formato, expresión no permitida, división entre cero, vacía o larga, sin red). (RF-12–18)
      Hecho cuando: los tests existen y fallan.
- [x] T5. Implementar `src/tools/calculadora.py` con evaluador basado en `ast`, sin `eval`. (RF-12–18)
      Hecho cuando: `pytest tests/test_calculadora.py` en verde.
- [x] T6. Escribir los tests de allowlist y traza de ambas tools. (RF-9, RF-10, RF-19, RF-20)
      Hecho cuando: los tests existen y fallan.
- [x] T7. Registrar `describir_imagen` y `calculadora` en `src/tools/__init__.py` (si ya existe por otra rama, solo añadir los registros). (RF-9, RF-10, RF-19, RF-20)
      Hecho cuando: `pytest tests/test_allowlist_multimodal.py` en verde, salvo `test_imagen_demo_existe`.
- [x] T8. Elegir y añadir `assets/imagen_demo.jpg` con importes legibles y documentar origen y fecha en el README. (RF-11)
      Hecho cuando: `pytest tests/test_allowlist_multimodal.py::test_imagen_demo_existe` en verde y las cifras se leen a simple vista.
- [x] T9. Escribir los tests del flujo imagen → calculadora con LLM y tools falsos. (RF-21–23)
      Hecho cuando: los tests existen y fallan.
- [x] T10. Añadir al prompt del especialista asignado la instrucción del flujo y comprobar que el nodo respeta allowlist y tope de pasos. (RF-21–23)
       Hecho cuando: `pytest tests/test_flujo_imagen_calculo.py` en verde.
- [x] T11. (Hecha a nivel de tools, 2026-10-14) Ejecutar una vez la demo real con la imagen y la pregunta de ejemplo y guardar el resultado para el informe. ⚠️ gasta API. (RF-1, RF-21, RF-22)
       Hecho cuando: la traza muestra `describir_imagen` y `calculadora`, y el total coincide con el cálculo a mano.
- [ ] T12. (Parcial: falta demo real) Validación final RF por RF (`/sdd-validar`). (Todos)
       Hecho cuando: `validacion.md` con veredicto «Sí».

## Cambio del 2026-10-19: reintento y causa del error

> Una tarea cada vez y con los tests primero. Se hacen antes de cerrar la T12.

- [x] T13. Añadir `IMAGEN_REINTENTO_ESPERA_S = 2.0` a `config.py`. (RF-24)
       Hecho cuando: `python -c "import config; print(config.IMAGEN_REINTENTO_ESPERA_S)"` imprime `2.0`.
- [x] T14. Escribir los tests del reintento y del registro: un 503 y después éxito, dos fallos temporales, errores no temporales (400, 403, 404) y registro de la causa sin datos sensibles. (RF-24 a RF-27)
       Hecho cuando: los tests nuevos de `tests/test_describir_imagen.py` existen y fallan.
- [x] T15. Implementar el reintento y el registro en `src/tools/describir_imagen.py`. (RF-24 a RF-27)
       Hecho cuando: `pytest tests/test_describir_imagen.py` en verde y toda la suite sigue en verde.
- [x] T16. Actualizar `validacion.md` con RF-24 a RF-27. (RF-24 a RF-27)
       Hecho cuando: las filas nuevas tienen su test citado y existente.
