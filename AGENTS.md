# AGENTS.md — MadridRumbo

## Proyecto
MadridRumbo es un asistente sobre transporte público de Madrid cuyo módulo RAG usa un corpus CRTM en PDF, Markdown y CSV de paradas. Su flujo offline carga, limpia, fragmenta, genera embeddings y persiste el índice en ChromaDB; el online recupera top-k, construye el prompt y genera una respuesta anclada al contexto.

En la iteración actual, MadridRumbo evoluciona hacia un sistema multiagente con LangGraph: supervisor, especialistas, síntesis, HITL y persistencia. El sistema podrá invocar el RAG de `rag/` como tool, además de una API externa y herramientas auxiliares/multimodales pendientes de desarrollar; CLI y Streamlit serán clientes del mismo grafo.

## Mapa del código
| Archivo | Responsabilidad |
|---|---|
| `config.py` | Rutas, corpus, parámetros de chunking, embeddings, retrieval y generación. |
| `main.py` | Vacío; `[COMPLETAR]` como punto de entrada CLI raíz. |
| `app.py` | Chat Streamlit, historial, contexto recuperado y métricas; importa `rag.responder` |
| `model_auth.py` | Carga o solicita de forma oculta claves de Gemini y OpenAI. |
| `rag/load.py` | Carga PDF, Markdown y CSV; agrupa paradas CRTM. |
| `rag/clean.py` | Normaliza texto y descarta documentos vacíos. |
| `rag/chunk.py` | Fragmenta documentos y añade metadatos de chunks. |
| `rag/pipeline.py` | Orquesta la ingesta y guarda `output/chunks.json`. |
| `rag/embed.py` | Genera embeddings Gemini/OpenAI y guarda `output/embeddings.json`. |
| `rag/index.py` | Persiste y consulta la colección ChromaDB. |
| `rag/retrieve.py` | Recupera top-k y formatea el contexto. |
| `rag/prompt.py` | Define el prompt con anclaje y abstención. |
| `rag/generate.py` | Genera la respuesta Gemini desde pregunta y contexto. |
| `rag/responder.py` | Expone `responder()` y `rag_ask()` para reutilizar el RAG sin UI. |
| `rag/main.py` | Declara CLI de preparación, indexado, retrieval y consulta del módulo RAG reutilizable. |
| `rag/eval_retrieval.py` | Evalúa retrieval con varios valores de K. |
| `rag/eval_generacion.py` | Evalúa respuestas y abstención. |
| `src/` | Vacío; ubicación prevista para estado, grafo, orquestación y tools del sistema multiagente PB2. |
| `tests/` | `[COMPLETAR]` no existe actualmente. |

## Comandos
- Instalar: `pip install -r requirements.txt`
- Tests: `python -m pytest` (sin API; `[COMPLETAR]` instalar `pytest` y crear tests).
- Preparar: `python -m rag.rag_cli --prepare --> genera chunks y embeddings a partir del corpus en data/` ⚠️ gasta API.
- Indexar: `python -m rag.rag_cli --index --> genera la base de datos y el índice de ChromaDB, reutiliza embeddings locales si existen` ⚠️ puede gastar API.
- Preguntar: `python -m rag.rag_cli --ask "pregunta" --k 4 --> responde una pregunta basada en los documentos` ⚠️ gasta API.
- Solo retrieval: `python -m rag.rag_cli --query "pregunta" --k 4 --> comprueba el contexto recuperado sin responder a la pregunta` ⚠️ puede gastar API si debe embeber la consulta.
- Web: `streamlit run app.py` ⚠️ gasta API.

## Flujo SDD de este repositorio
- Constitución: `docs/constitution.md`. Léela siempre.
- Specs: `specs/NNN-nombre/` con `spec.md`, `plan.md`, `tasks.md` y `validacion.md`. La spec activa es la de número más alto, salvo que se indique otra.
- Plantillas: `docs/plantillas/`. Chuleta de EARS: `docs/chuleta_ears.md`. Cómo testear sin API: `docs/tests_sin_api.md`.
- Comandos por fase: `.github/prompts/` (`/sdd-contexto`, `/sdd-constitucion`, `/sdd-spec`, `/sdd-clarificar`, `/sdd-plan`, `/sdd-tareas`, `/sdd-implementar`, `/sdd-validar`, `/sdd-cambio`, `/sdd-spec-inversa`).

## Reglas
- Lee `docs/constitution.md` y la spec activa antes de tocar nada.
- Respeta la fase en la que estamos. En spec, clarificación, plan y tareas NO se escribe código.
- En implementación: una sola tarea de `tasks.md` cada vez, tests primero, y te paras al terminarla.
- No modifiques `specs/` salvo que la fase lo pida.
- No añadas dependencias ni cambies el contrato de la función principal (p. ej. `responder()` o `rag_ask()`) si la spec no lo dice.
- No ejecutes comandos marcados con ⚠️ salvo que te lo pida: cuestan dinero y tiempo. Para verificar, usa `pytest`.
- Nunca leas ni muestres el contenido de `.env`.

## Al terminar cualquier tarea
- Ejecuta `pytest` y pega el resumen del resultado.
- Indica qué RF de la spec cubre lo que has hecho.
