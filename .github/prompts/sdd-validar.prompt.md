---
name: sdd-validar
description: "Fase 7 · Validación: recorre la spec RF por RF y da un veredicto"
agent: agent
---
Valida la implementación contra la spec activa. NO cambies código.

1. Ejecuta `pytest` y guarda el resultado.
2. Recorre la spec requisito por requisito (RF-1 … RF-n). Para cada uno, indica qué test lo cubre (archivo y nombre del test) y si pasa. Si solo se puede comprobar a mano, dilo y explica cómo.
3. Revisa los criterios de finalización de la spec y marca cuáles se cumplen.
4. Señala cualquier comportamiento implementado que NO esté en la spec.
5. Da un veredicto: ¿se cumple la spec? Sí, No o Parcial, con el motivo.

Guarda el resultado como tabla en `validacion.md`, en la carpeta de la spec, siguiendo `docs/plantillas/validacion.md`, y muéstrame el resumen en el chat.
