---
name: sdd-spec
description: "Fase 2 · Especificación: entrevista y spec.md con requisitos EARS (sin código)"
agent: agent
argument-hint: "Idea de la funcionalidad en una o dos frases"
---
NO escribas código en ningún momento. Vamos a redactar la especificación de una funcionalidad nueva de este proyecto.

La idea es la que te doy en este mismo mensaje, después de estas instrucciones. Si no te he dado ninguna, pídemela y espera.

Antes de empezar, lee `docs/constitution.md`, `AGENTS.md`, las specs que ya existan en `specs/` (para no contradecirlas ni repetir número) y la plantilla `docs/plantillas/spec.md`.

Tu trabajo:

1. **Entrevístame.** Hazme preguntas de UNA en UNA (máximo 5) y espera mi respuesta antes de hacer la siguiente. Pregunta solo lo que cambie qué hay que construir: casos límite, comportamiento ante errores, qué ve la persona usuaria y qué queda fuera. No preguntes lo que tenga una respuesta obvia por defecto. No propongas soluciones técnicas: si te pregunto "¿cómo lo harías?", recuérdame que eso va en el plan.
2. **Elige el número.** El siguiente libre, con tres dígitos: `specs/NNN-nombre-en-kebab-case/spec.md`.
3. **Redacta la spec** con la plantilla, sin saltarte secciones:
   - Requisitos funcionales numerados (RF-1, RF-2…) en notación EARS en español: `CUANDO…`, `SI… ENTONCES…`, `MIENTRAS…`, `DONDE…`, o `EL SISTEMA…` para lo que siempre es cierto.
   - Un requisito = una frase = un comportamiento verificable. Si necesitas un "y" para unir dos comportamientos, son dos RF.
   - Sin adjetivos que no se puedan medir ("rápido", "robusto", "intuitivo"): pon el umbral o no lo pongas.
   - Solo el QUÉ y el POR QUÉ. Puedes nombrar lo que ve la persona usuaria (comandos de la CLI, elementos de la app), pero no la implementación: nada de nombres de archivos o funciones, algoritmos ni estructuras de datos. Eso va en el plan.
   - Incluye siempre la sección "Fuera de alcance".
   - Lo que no sepas, márcalo como `[NECESITA ACLARACIÓN: pregunta concreta]`. No rellenes huecos inventando.
4. Termina con un resumen (número de RF y dudas abiertas) y pide mi aprobación. No pases al plan.
