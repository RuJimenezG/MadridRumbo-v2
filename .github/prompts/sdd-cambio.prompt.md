---
name: sdd-cambio
description: "Cambio de requisitos: primero la spec, después el código"
agent: agent
argument-hint: "El cambio o requisito nuevo"
---
Hay un cambio de requisitos: el que te describo en este mismo mensaje, después de estas instrucciones. NO toques código.

1. Lee `docs/constitution.md` y la spec afectada.
2. Si el cambio amplía una funcionalidad que ya tiene spec, actualiza su `spec.md`: añade o modifica los RF necesarios (en EARS, con numeración correlativa y sin renumerar los existentes), los casos límite y "Fuera de alcance". Si es una funcionalidad nueva, dime que conviene una spec nueva con `/sdd-spec` y para.
3. Enséñame el diff de la spec y las preguntas que queden abiertas.
4. Dime qué partes del plan y de las tareas habría que revisar después, sin cambiarlas todavía.
