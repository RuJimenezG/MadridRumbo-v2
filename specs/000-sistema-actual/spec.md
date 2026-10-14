# Spec 000 — Sistema RAG actual de MadridRumbo

> Estado: Aprobada · Fecha: 2026-10-12

## Contexto y objetivo

MadridRumbo implementa un RAG sobre transporte público de Madrid. Procesa un corpus CRTM en PDF, Markdown y CSV, lo indexa en ChromaDB y responde preguntas con Gemini usando los fragmentos recuperados. Esta spec documenta exclusivamente el comportamiento actual como línea base.

## Usuarios / actores

- Persona usuaria que consulta información de transporte mediante CLI o Streamlit.
- Equipo que prepara, indexa y evalúa el corpus.

## Historias de usuario

- H1: Como usuaria quiero preparar e indexar el corpus para poder consultarlo.
- H2: Como usuaria quiero formular una pregunta y ver la respuesta junto con sus fuentes.
- H3: Como equipo quiero reutilizar el RAG sin depender de una interfaz.

## Requisitos funcionales

### Ingesta y preparación

- RF-01: EL SISTEMA carga desde `data/` archivos PDF, Markdown y el CSV configurado de paradas CRTM.
- RF-02: CUANDO falta el CSV configurado de paradas, EL SISTEMA detiene la carga con `FileNotFoundError`.
- RF-03: EL SISTEMA omite archivos JSON y archivos llamados `README.md` durante la carga.
- RF-04: CUANDO `MAX_FILAS_CSV` tiene un valor distinto de `None`, EL SISTEMA limita el CSV a ese número de filas; con `None`, procesa todas las filas.
- RF-05: EL SISTEMA normaliza saltos de línea y espacios, y descarta documentos cuyo contenido quede vacío.
- RF-06: EL SISTEMA fragmenta los documentos no CSV con `CHUNK_SIZE` y `CHUNK_OVERLAP`, y añade metadatos de índice, tamaño y estrategia.
- RF-07: EL SISTEMA guarda los chunks y estadísticas de ingesta en `output/chunks.json`.

### Embeddings e índice

- RF-08: CUANDO se ejecuta la preparación, EL SISTEMA genera embeddings con el proveedor configurado y los guarda en `output/embeddings.json`.
- RF-09: EL SISTEMA indexa en ChromaDB persistente los chunks, sus embeddings y los metadatos `source` y `chunk_id`.
- RF-10: CUANDO existe un `embeddings.json` del mismo modelo y con igual número de elementos que los chunks, EL SISTEMA reutiliza sus vectores al indexar.
- RF-11: CUANDO se solicita recrear el índice, EL SISTEMA elimina la colección configurada antes de crearla de nuevo.

### Recuperación y generación

- RF-12: CUANDO se consulta una pregunta, EL SISTEMA genera su embedding, recupera los top-k chunks más cercanos y devuelve texto, fuente, identificador y distancia de cada uno.
- RF-13: SI la colección ChromaDB está vacía, ENTONCES EL SISTEMA detiene la recuperación con un error que solicita indexar primero.
- RF-14: EL SISTEMA formatea el contexto recuperado identificando cada fragmento y su fuente.
- RF-15: EL SISTEMA construye un prompt que instruye al modelo a responder únicamente con el contexto y a usar la frase exacta de abstención indicada si no hay evidencia.
- RF-16: CUANDO se invoca `responder()`, EL SISTEMA devuelve pregunta, respuesta, fuentes, k, número de chunks, tiempo y contexto; además registra la consulta en `rag.log`.
- RF-17: EL SISTEMA expone `rag_ask(consulta) -> str` como acceso simplificado al RAG.

### Interfaces

- RF-18: CUANDO se ejecuta `python -m rag.rag_cli`, EL SISTEMA ofrece `--prepare`, `--index`, `--recreate-index`, `--query`, `--ask` y `--k`.
- RF-19: CUANDO se usa `--query`, EL SISTEMA muestra el contexto y las fuentes sin llamar al generador.
- RF-20: CUANDO se usa `--ask`, EL SISTEMA muestra la respuesta y las fuentes.
- RF-21: MIENTRAS existe historial de conversación en Streamlit, EL SISTEMA muestra cada pregunta, respuesta, fuentes, contexto y métricas.

## Requisitos no funcionales

- Persistencia: ChromaDB usa la ruta configurada en `CHROMA_DIR`.
- Configuración: rutas, modelos y límites se centralizan en `config.py`; las claves se leen del entorno.
- Idioma: los mensajes, prompt e interfaces son mayoritariamente españoles.

## Casos límite

- Corpus sin `Paradas CRTM.csv`: RF-02.
- Documento vacío tras limpieza: RF-05.
- `MAX_FILAS_CSV = None`: RF-04.
- Índice vacío: RF-13.
- Sin contexto suficiente: RF-15 define la instrucción al modelo, no una comprobación determinista.
- Más chunks que `MAX_CHUNKS`: el índice conserva únicamente los primeros permitidos y avisa por consola.

## Fuera de alcance

- Grafo LangGraph, supervisor, especialistas, allowlist de tools, API externa, multimodal, HITL y persistencia por `thread_id`.
- Garantía determinista de abstención.
- Tests automatizados existentes.

## Criterios de finalización

- Esta spec describe exclusivamente código existente.
- La trazabilidad está completa y los huecos quedan registrados.

## Dudas abiertas

- [NECESITA ACLARACIÓN: ¿Qué contrato deberán compartir el futuro grafo, CLI y Streamlit?]

## Trazabilidad

| RF | Implementación | Test |
|---|---|---|
| RF-01–04 | `rag/load.py`: `cargar_documentos`, `cargar_archivo`, `cargar_paradas_csv_agrupadas` | Sin test |
| RF-05 | `rag/clean.py`: `normalizar_texto`, `limpiar_documentos` | Sin test |
| RF-06–07 | `rag/chunk.py`: `fragmentar_documentos`; `rag/pipeline.py`: `ejecutar_ingesta`, `guardar_chunks_json` | Sin test |
| RF-08 | `rag/embed.py`: `ejecutar_embeddings`, `embeddear_textos` | Sin test |
| RF-09–11 | `rag/index.py`: `index_chunks`, `get_or_create_collection`, `_cargar_embeddings_json` | Sin test |
| RF-12–14 | `rag/retrieve.py`: `retrieve`, `format_context` | Sin test |
| RF-15 | `rag/prompt.py`: `PROMPT_TEMPLATE`; `rag/generate.py`: `generate` | Sin test |
| RF-16–17 | `rag/responder.py`: `responder`, `rag_ask` | Sin test |
| RF-18–20 | `rag/rag_cli.py`: `main`, `_cmd_query`, `_cmd_ask` | Sin test |
| RF-21 | `app.py` | Sin test |


