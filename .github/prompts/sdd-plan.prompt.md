---
name: sdd-plan
description: "Fase 4 · Plan técnico: archivos, contrato, decisiones y tests (sin código)"
agent: agent
---
Lee `docs/constitution.md`, `AGENTS.md`, la spec activa (la de número más alto en `specs/`, salvo que te indique otra) y el código que se vaya a ver afectado. NO escribas código.

Si la spec aún tiene algún `[NECESITA ACLARACIÓN]`, para y dímelo: no se planifica sobre dudas abiertas.

Genera `plan.md` en la misma carpeta que la spec, con la plantilla `docs/plantillas/plan.md`:

1. **Archivos afectados**: qué se crea y qué se modifica, y qué RF cubre cada uno.
2. **Contrato**: cómo cambia lo que reciben o devuelven las funciones públicas y los comandos. Incluye un ejemplo de entrada y salida.
3. **Lógica clave** en pseudocódigo corto.
4. **Decisiones técnicas** justificadas, cada una con la alternativa descartada y el motivo.
5. **Estrategia de tests**: qué test cubre cada RF y qué dobles de prueba se usan para no llamar a ninguna API. Si un RF solo se puede comprobar a mano, dilo y explica cómo.
6. **Riesgos.**

Todo debe respetar la constitución y cubrir todos los RF. Termina con la tabla de trazabilidad RF → parte del plan → test, y pide mi aprobación antes de pasar a tareas.
