---
name: sdd-constitucion
description: "Fase 1 · Constitución: principios innegociables del proyecto (sin código)"
agent: agent
---
Vamos a crear (o revisar) la constitución de este proyecto: los principios innegociables que deben cumplir todas las specs, planes, tareas y líneas de código. NO escribas código.

1. Lee el `README.md`, `AGENTS.md` si existe, `config.py`, `requirements.txt` y la estructura de `src/` para entender qué es el proyecto y cómo está construido.
2. Si ya existe `docs/constitution.md` (aunque sea una propuesta con huecos `[COMPLETAR]`), revísala contra el código: completa los `[COMPLETAR]` con lo que veas en el repo, dime qué principios no se cumplen hoy y qué echas en falta. Enséñame la versión propuesta y no la guardes sin mi permiso.
3. Si no existe, proponme una `docs/constitution.md` con 5-7 principios cortos y verificables (se tiene que poder comprobar si se cumplen o no). Como mínimo deben cubrir:
   - la relación entre spec y código (la spec manda; si cambia el comportamiento, primero se cambia la spec),
   - el anclaje al corpus y la abstención cuando no hay evidencia,
   - la separación entre la lógica (`src/`) y las interfaces (CLI y Streamlit),
   - la política de tests (sin llamadas reales a APIs),
   - la configuración y los secretos,
   - el stack permitido y las dependencias,
   - el idioma del código y de los mensajes.
4. Máximo 20 líneas. Muéstramela en el chat y ESPERA mi aprobación antes de crear el archivo.
