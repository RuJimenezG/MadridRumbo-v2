---
name: sdd-clarificar
description: "Fase 3 · Clarificación: revisa la spec como QA y detecta huecos antes de planificar"
agent: agent
argument-hint: "Carpeta de la spec (opcional; por defecto, la de número más alto)"
---
Revisa la spec activa (la que te indique o, si no, la de número más alto en `specs/`) como si fueras QA y tu trabajo fuera encontrarle fallos. Lee también `docs/constitution.md` y las specs anteriores.

NO modifiques ningún archivo todavía. Solo detecta. Devuélveme una lista numerada en cuatro bloques:

1. **Ambigüedades**: frases que dos personas podrían implementar de forma distinta.
2. **Contradicciones**: entre RF de esta spec, o con specs anteriores.
3. **Casos límite no cubiertos**: valores frontera, vacíos, datos ausentes, errores.
4. **Conflictos con la constitución.**

Para cada punto, indica el RF afectado y la pregunta concreta que tengo que responder. Máximo 10 puntos, de más a menos importante. No propongas soluciones.

Cuando te responda, actualiza `spec.md` con mis decisiones: reescribe los RF afectados, añade los casos límite, elimina los `[NECESITA ACLARACIÓN]` resueltos y enséñame el diff. Nada más.
