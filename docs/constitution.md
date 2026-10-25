# Constitución — MadridRumbo

Principios innegociables. Toda spec, plan, tarea y línea de código debe cumplirlos. Si una petición choca con alguno, el agente se detiene y lo dice.

1. **La spec manda.** No se implementa ningún comportamiento que no esté en una spec aprobada de `specs/`. Si falta una decisión, se para y se pregunta. Si cambia el comportamiento, primero se cambia la spec y después el código.
2. **RAG completo y anclado.** El RAG usa corpus curado multiformato, índice persistente y metadatos; responde solo con evidencia y se abstiene sin ella.
3. **RAG como tool.** El RAG expone una API sin UI (`rag_ask` o `responder`) y el agente la invoca como herramienta, no lo sustituye.
4. **Arquitectura modular.** Grafo, agentes, tools, RAG y UI permanecen separados; CLI y Streamlit son clientes del mismo contrato. La lógica vive en `src/`. La CLI y Streamlit son capas finas que usan la misma función principal (`responder()` / `rag_ask()`) y muestran lo mismo.
5. **Orquestación segura.** El grafo tiene supervisor, al menos dos especialistas, síntesis y aplicación; el fallback del supervisor y los límites viven en Python.
6. **Tools controladas.** Solo se ejecutan tools de una allowlist: RAG, API externa con fallback local, auxiliar determinista y multimodal; toda llamada deja traza.
7. **HITL obligatorio.** Antes de aplicar un plan, el grafo se pausa; solo una aprobación humana permite `done=True`, y el rechazo permite continuar.
8. **Estado persistente.** Se conserva el estado por `thread_id` mediante checkpointer; una nueva conversación crea otro identificador.
9. **Tests como puerta, sin API.** Cada tarea termina con `pytest` verde y dobles para LLM, APIs, embeddings, ChromaDB y tools. Los tests no llaman al LLM, a los embeddings ni a una ChromaDB real: usan dobles de prueba (`docs/tests_sin_api.md`). Prohibido avanzar con tests en rojo.
10. **Configuración y claridad.** Configuración centralizada; secretos solo en `.env`; stack documentado (Python, LangChain/LangGraph, Chroma, Gemini u otro proveedor, Streamlit); mensajes y documentación en español.
11. **Configuración en un solo sitio.** Rutas, modelos, K y límites van en `config.py`. Las claves van solo en `.env` y nunca en el código ni en el repositorio.
12. **Stack cerrado.** Python 3.10+, LangChain, LangGraph, google.genai, ChromaDB, Streamlit y pytest. No se añaden dependencias sin actualizar antes la spec y el plan.
13. **Idioma.** Preferiblemente español. Si ya existen nombres en inglés, respetarlos. Si algo queda más claro en inglés que en español, usar inglés.
14. **Comentarios.** Todo el código tiene que estar bien comentado. Sin extenderse en exceso ni comentar cosas que se puedan entender solamente leyendo el código.









