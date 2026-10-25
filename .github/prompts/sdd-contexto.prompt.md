---
name: sdd-contexto
description: "Fase 1 · Contexto del agente: genera o actualiza AGENTS.md a partir del repo"
agent: agent
---
Vamos a preparar `AGENTS.md`, el archivo de contexto que cualquier agente de código lee antes de tocar este repositorio. NO modifiques código.

Recorre el repositorio (`README.md`, `config.py`, `main.py`, `app.py`, `src/`, `rag/`, `tests/` y `requirements.txt`), lee las instrucciones del proyecto académico en `docs/README-PB-Agentes.md` y `docs/guia_pb02_agentes.html` y genera `AGENTS.md` en español con estas secciones, en este orden:

1. **Proyecto**: qué es, en 2-3 frases (dominio, corpus, pipeline offline y online, interfaces).
2. **Mapa del código**: tabla archivo → responsabilidad, una línea por archivo.
3. **Comandos**: instalar, tests, preparar el índice, preguntar, solo retrieval y app web. Marca con ⚠️ los que gastan API.
4. **Flujo SDD**: dónde están la constitución (`docs/constitution.md`), las specs (`specs/NNN-nombre/`), las plantillas (`docs/plantillas/`) y los comandos `/sdd-*` (`.github/prompts/`).
5. **Reglas** para el agente: no escribir código fuera de la fase de implementación; una tarea cada vez y tests primero; no añadir dependencias sin spec; no ejecutar comandos ⚠️ sin pedir permiso; no leer `.env`.
6. **Al terminar cualquier tarea**: ejecutar los tests y decir qué RF cubre.

Si algo no se puede deducir del código (por ejemplo, todavía no hay tests), escribe `[COMPLETAR]` en vez de inventarlo. Si `AGENTS.md` ya existe (por ejemplo, una plantilla con `[COMPLETAR]`), propón solo los cambios necesarios y enséñame el diff antes de guardarlo.
