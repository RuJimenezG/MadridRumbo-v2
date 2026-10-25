---
name: sdd-spec-inversa
description: "Proyecto existente: documenta como spec 000 lo que el sistema YA hace"
agent: agent
---
Este proyecto ya existe y no tiene specs. Vamos a documentar lo que hace HOY en `specs/000-sistema-actual/spec.md`, como línea base antes de añadir funcionalidades. NO cambies código.

1. Lee `docs/constitution.md`, `AGENTS.md`, el `README.md` y el código de `src/`, `rag/` `main.py`, `app.py`, `config.py`, `model_auth.py` y `tests/`.
2. Redacta la spec con la plantilla `docs/plantillas/spec.md`, con los RF en EARS agrupados por bloque (ingesta, índice, recuperación, generación, interfaces).
3. Describe solo comportamiento que puedas señalar en el código. Nada de deseos ni mejoras.
4. Añade una tabla de trazabilidad: RF → archivo y función que lo implementa → test que lo cubre (o "sin test").
5. Añade una sección "Huecos detectados": comportamientos frágiles, sin test o que chocan con la constitución. Son candidatos a specs futuras.

Muéstrame un resumen y pide mi aprobación.
