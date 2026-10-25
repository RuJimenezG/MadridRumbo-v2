---
name: sdd-tareas
description: "Fase 5 · Tareas: divide el plan en pasos pequeños y verificables (sin código)"
agent: agent
---
A partir de la spec y el plan activos, genera `tasks.md` en la misma carpeta, con la plantilla `docs/plantillas/tasks.md`. NO escribas código.

- Tareas pequeñas (20-30 minutos como máximo), en orden de dependencia.
- Cada tarea lleva checkbox `- [ ]`, un identificador (T1, T2…), los RF que cubre y una línea **"Hecho cuando:"** verificable: un test concreto en verde o una comprobación manual precisa (comando y resultado esperado).
- En toda tarea que toque lógica, los tests van primero.
- La última tarea es siempre la validación RF por RF.

Al final, comprueba que todos los RF aparecen en al menos una tarea y dime si falta alguno.
