---
name: sdd-implementar
description: "Fase 6 · Implementación: SOLO una tarea, tests primero, y parar"
agent: agent
argument-hint: "Identificador de la tarea, p. ej. T2"
---
Implementa SOLO la tarea de `tasks.md` (spec activa) que te indico en este mensaje, por ejemplo T2. Si no te indico ninguna, coge la primera sin marcar y dime cuál es antes de empezar.

1. Lee antes `docs/constitution.md`, la spec, el plan y la tarea.
2. **Tests primero.** Escribe o amplía los tests de la tarea, ejecútalos y enséñame que fallan antes de escribir el código. Los tests no pueden llamar a ninguna API: usa dobles de prueba.
3. Escribe el código mínimo para que pasen, siguiendo el plan. No toques nada que la tarea no pida. No añadas dependencias.
4. Ejecuta toda la suite (`pytest`) y enséñame el resumen. Si algo falla, arréglalo dentro de esta tarea. Si no puedes, para y explícamelo.
5. Si la tarea se verifica a mano (por ejemplo, la app web), dime exactamente qué comando ejecutar y qué debo ver.
6. Marca la tarea como hecha (`- [x]`) en `tasks.md`.
7. Termina con: archivos tocados, RF cubiertos y resultado de los tests. Y PÁRATE: no empieces la siguiente tarea.

Si durante la tarea descubres que la spec o el plan no cuadran con el código, no improvises: para y dímelo.
