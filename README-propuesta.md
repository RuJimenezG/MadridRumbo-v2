# MadridRumbo

> **Project Break 2 · Sprints 11–13 | AI Engineering Bootcamp**  
> **Grupo 3:** Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.

## Alcance

MadridRumbo es un asistente en español sobre transporte público de la Comunidad de Madrid. Combina un sistema RAG anclado a un corpus del CRTM con un grafo multiagente que decide qué capacidad necesita cada consulta: información documental, horarios, planificación de rutas, cálculos o lectura de la imagen demo.

El RAG no ha desaparecido: permanece como módulo independiente y se invoca como una herramienta del grafo. Sus respuestas documentales deben basarse exclusivamente en los fragmentos recuperados del corpus; cuando no hay evidencia, debe abstenerse con «No lo sé, no está en los documentos.»

**Ejemplos de preguntas dentro del alcance:**

- ¿Qué es la Tarjeta Azul y en qué medios de transporte es válida?
- ¿En qué zona tarifaria se encuentra la parada de Plaza de Castilla?
- ¿Hasta qué hora hay metro hoy?
- ¿Cómo puedo ir desde la Puerta del Sol hasta la Estación de Atocha?
- Analiza `assets/imagen_demo.jpg` e indica los precios.

**Ejemplos de preguntas fuera del alcance:**

- ¿Cuánto cuesta un billete de metro en Barcelona?
- ¿Cuál es la capital de Francia?
- Planifica una ruta en coche, bicicleta o fuera del ámbito de cobertura CRTM.

Las rutas se calculan para transporte público (metro, metro ligero/tranvía, autobús y Cercanías); los trayectos a pie solo se aceptan como parte de una ruta de transporte público. La herramienta admite `billete sencillo` y `billete de 10 viajes`; no calcula otros títulos ni abonos.

---

## Corpus documental

El RAG carga desde `data/` documentos Markdown y el CSV de paradas CRTM. El corpus procede de fuentes descargadas el 07/09/2026:

- `Paradas CRTM.csv`
  - Reúne las paradas de Metro, Metro Ligero, Cercanías, EMT, autobuses interurbanos y autobuses urbanos.
  - Se construye a partir de las colecciones GTFS del [portal de datos del CRTM](https://datos.crtm.es/search?type=CSV%2520Collection): se conservan `stop_id`, `stop_name`, `stop_desc`, `zone_id` y un campo `type` con el modo de transporte.
  - Durante la carga, las paradas se agrupan por tipo y zona tarifaria, en bloques de hasta seis paradas.
- `crtm_billetes_tarifas.md`
  - Información relevante de [Billetes y tarifas del CRTM](https://www.crtm.es/billetes-y-tarifas/).
- `crtm_faq.md`
  - Información procedente de las [preguntas frecuentes de billetes y tarifas](https://www.crtm.es/billetes-y-tarifas/preguntas-frecuentes/).
- `bocm-20251231-tarifas_transporte.md` y `bocm-20251231-precios_transporte.md`
  - Versiones textuales de los documentos de tarifas y precios publicados por el CRTM: [tarifas](https://www.crtm.es/media/sjqj4ggj/bocm-20251231-tarifas_transporte.pdf) y [precios](https://www.crtm.es/media/s1qi0nmo/bocm-20251231-precios_transporte.pdf).

Los archivos Markdown con tablas válidas conservan cada tabla completa —incluido su título y encabezados— en un único chunk. Así se evita separar precios o condiciones que solo tienen sentido juntos.

---

## Arquitectura

El sistema separa la preparación offline del corpus de la conversación online. La configuración centralizada en `config.py` reúne rutas, modelos, límites, allowlists y parámetros operativos; las claves se leen exclusivamente desde `.env`.

```text
                         PREPARACIÓN DEL CORPUS

 PDF / Markdown / CSV CRTM
             ↓
 carga → limpieza → chunking semántico → embeddings → ChromaDB persistente
             ↓                                      ↑
 output/chunks.json · output/embeddings.json ───────┘

                         CONSULTA Y CONVERSACIÓN

 CLI / Streamlit
        ↓
 src.agent (fachada pública)
        ↓
 LangGraph: Supervisor → especialistas → Sintetizador
        │                    │
        │                    ├─ rag        → rag_ask → ChromaDB + Gemini
        │                    ├─ horarios   → hora_actual / rag_ask
        │                    ├─ rutas      → Nominatim + Google Routes + RAG
        │                    ├─ auxiliar   → hora_actual / calculadora
        │                    └─ tarifas    → describir_imagen
        ↓
 respuesta, planes, log, traza, HITL y estado por thread_id
```

El supervisor pide al modelo una lista JSON de roles válidos y aplica las reglas de seguridad en Python. Si la respuesta del proveedor falla, no es JSON válido o contiene roles incorrectos, se usa un fallback determinista y se conserva un diagnóstico técnico seguro. Las consultas textuales sobre tarifas se redirigen al RAG si no aportan una imagen válida; una mención a una foto o cartel no basta.

### Grafo multiagente

| Componente | Responsabilidad |
| --- | --- |
| Supervisor | Decide y ordena los roles necesarios; valida su decisión, aplica fallback y guardas semánticas. |
| `rag` | Responde sobre normativa, tarifas, títulos, zonas y documentos del CRTM usando evidencia recuperada. |
| `horarios` | Combina la hora actual de Madrid y el RAG para preguntas de servicio, frecuencias o «hoy / ahora». |
| `rutas` | Solicita una ruta entre origen y destino; la tool consulta geocodificación, Google Routes y el RAG para zona y precio. |
| `auxiliar` | Obtiene la hora actual y ejecuta cálculos aritméticos deterministas. |
| `tarifas` | Extrae textos e importes visibles de una imagen válida; no calcula importes por sí mismo. |
| Sintetizador | Produce una respuesta sencilla en español a partir de las notas de los especialistas, sin añadir datos no obtenidos. |

Cada conversación se conserva en memoria con un `thread_id`. Las operaciones públicas del grafo son `src.agent.procesar_turno(estado, mensaje, thread_id)` y `src.agent.aprobar_plan(estado, thread_id, aprobado)`. Ambas devuelven las mismas seis claves: `respuesta`, `plan`, `log`, `traza`, `hitl_pendiente` y `done`.

Los límites de turnos y de invocaciones de tools se aplican en Python. Las tools solo se ejecutan mediante `ejecutar_tool(nombre, args, traza)`, que aplica una allowlist y registra el nombre, argumentos, estado y vista previa del resultado.

### Tools disponibles

| Tool | Tipo | Qué hace |
| --- | --- | --- |
| `rag_ask` | RAG | Delega en `rag.responder.rag_ask` para responder con el corpus CRTM. |
| `hora_actual` | Auxiliar determinista | Devuelve fecha, hora, día y tipo de día en `Europe/Madrid`; no usa red ni LLM. No distingue festivos. |
| `calculadora` | Auxiliar determinista | Evalúa `+`, `-`, `*`, `/`, paréntesis y signo menos con `ast` y `Decimal`, sin `eval`; acepta coma o punto decimal. |
| `planificar_ruta` | API externa + RAG | Geocodifica con Nominatim, calcula con Google Routes y consulta internamente el RAG para zona y precio. |
| `describir_imagen` | Multimodal | Lee texto y cifras de JPG, JPEG o PNG dentro de `assets/`, con un tamaño máximo de 4 MB. |

Un fallo de tool se convierte en un texto controlado que comienza por `ERROR`, sin propagar excepciones al chat. La tool de imagen reintenta una sola vez ante errores temporales (por ejemplo 503, 429 o red); no reintenta errores de clave, petición o modelo.

### Aprobación humana de rutas (HITL)

Las rutas son los únicos resultados que se pausan para aprobación. Cuando el grafo devuelve uno o varios planes, los clientes muestran su identificador, origen, destino, duración, tramos, zona y precio disponibles. La persona elige un plan si hay varios y después lo aprueba o lo rechaza.

```text
consulta de ruta → plan pendiente → elegir plan (si hay varios) → aprobar / rechazar
                                      │                              │
                                      └───────── aprobar ────────────┘ → done=True
                                                                     
                                                       rechazar → replanificación o continuar
```

Mientras haya un plan pendiente, los clientes bloquean mensajes nuevos. Un rechazo no cierra la conversación: el grafo puede proponer una alternativa o permitir continuar en el mismo `thread_id`.

### Estructura del proyecto

```text
MadridRumbo/
├── main.py                         # Cliente CLI del grafo
├── app.py                          # Cliente web Streamlit del mismo grafo
├── config.py                       # Configuración centralizada
├── model_auth.py                   # Lectura/solicitud de claves de modelos
├── requirements.txt
├── .env.example                    # Plantilla de variables de entorno
├── rag/                            # Módulo RAG reutilizable
│   ├── load.py · clean.py · chunk.py · pipeline.py
│   ├── embed.py · index.py · retrieve.py
│   ├── prompt.py · generate.py · responder.py
│   ├── rag_cli.py                  # CLI de preparación, índice y consulta RAG
│   └── eval_retrieval.py · eval_generacion.py
├── src/
│   ├── agent.py · graph.py · estado.py
│   ├── supervisor.py · supervisor_reglas.py · catalogo_roles.py
│   ├── sintetizador.py · modelos.py · reloj.py
│   ├── agents/                     # rag, horarios, rutas, auxiliar y tarifas
│   ├── tools/                      # allowlist y herramientas del grafo
│   └── clientes/                   # contrato, sesión, CLI, presentación y modo simulado
├── data/                           # Corpus CRTM
├── assets/                         # Icono e imagen demo
├── output/                         # Artefactos generados (esta propuesta está en la raíz: README-propuesta.md)
├── chroma/                         # Índice vectorial persistente, generado localmente
├── specs/                          # Especificaciones, planes, tareas y validaciones SDD
├── docs/                           # Constitución, plantillas y guía de tests
└── tests/                          # Suite sin llamadas a servicios reales
```

---

## Preparación del entorno

Se recomienda Python 3.10 o superior.

### 1. Crear y activar un entorno virtual

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

El stack utiliza Python, LangChain, LangGraph, ChromaDB, `google-genai`, Streamlit y pytest, entre otras dependencias indicadas en `requirements.txt`.

### 3. Configurar las variables de entorno

Crea `.env` a partir de `.env.example` y completa únicamente las claves que vaya a usar el flujo elegido:

```env
GEMINI_API_KEY=tu_clave_de_google_ai_studio
OPENAI_API_KEY=tu_clave_de_openai
GOOGLE_ROUTES_API_KEY=tu_clave_de_google_routes
NOMINATIM_CONTACTO=tu_email_o_contacto
```

`GEMINI_API_KEY` es necesaria para generación, embeddings Gemini, el supervisor/especialistas y la visión. `OPENAI_API_KEY` solo es necesaria si se cambia el proveedor de embeddings en `config.py`. Las rutas reales requieren además `GOOGLE_ROUTES_API_KEY` y un contacto para identificar la aplicación ante Nominatim.

> No incluyas claves en el código, en documentación ni en el repositorio.

---

## Preparación e indexado del RAG

El RAG separa el tratamiento del corpus de la creación del índice. Sus comandos son independientes del chat multiagente.

```text
Documentos → carga → limpieza → fragmentación → embeddings → ChromaDB
```

### Preparar corpus y embeddings

```bash
python -m rag.rag_cli --prepare
```

Genera `output/chunks.json` y `output/embeddings.json`. ⚠️ Puede consumir llamadas al proveedor de embeddings.

### Crear o actualizar el índice

```bash
python -m rag.rag_cli --index
```

Indexa los chunks en la colección persistente de ChromaDB y reutiliza `output/embeddings.json` si corresponde al mismo modelo y al mismo número de chunks. Si no existe `chunks.json`, realiza antes la ingesta.

Para eliminar y reconstruir la colección configurada:

```bash
python -m rag.rag_cli --index --recreate-index
```

### Consultar solo el retrieval o pedir una respuesta RAG

```bash
python -m rag.rag_cli --query "¿En qué zona está Plaza de Castilla?" --k 4
python -m rag.rag_cli --ask "¿Qué es la Tarjeta Azul?" --k 4
```

`--query` muestra los chunks recuperados y sus fuentes sin llamar al generador, aunque puede requerir el embedding de la consulta. `--ask` ejecuta retrieval y generación, muestra respuesta y fuentes, y puede consumir una llamada de Gemini. El valor de `k` controla el número de chunks recuperados; el predeterminado es 4.

---

## Uso de la aplicación

Los clientes `main.py` y `app.py` consumen el mismo contrato de `src.agent`; no llaman al RAG directamente. Con el grafo real, una consulta puede usar Gemini, el RAG, Nominatim o Google Routes según el caso.

### Modo simulado, sin APIs

Para recorrer CLI, Streamlit y el flujo HITL sin claves ni coste, activa el grafo de pruebas:

PowerShell:

```powershell
$env:MADRIDRUMBO_GRAFO = "falso"
```

Bash:

```bash
export MADRIDRUMBO_GRAFO=falso
```

Los clientes avisan visiblemente de que están en modo simulado. Sus respuestas son fijas, pero los planes conservan el formato del grafo real, incluidos los casos con varias alternativas.

### Chat por terminal

```bash
python main.py
```

Escribe una consulta y pulsa Intro. El CLI muestra la respuesta, el `thread_id`, las notas del log y la traza de tools. También muestra los diagnósticos técnicos seguros del supervisor, útiles para depuración.

Si la consulta genera planes:

- Con varios planes pregunta `¿Qué plan quieres decidir? [1-N]`; admite el número o el identificador.
- Después pregunta `¿Apruebas el plan? [s/n]`.
- `s` aprueba el plan y solo muestra «Terminada: sí» si el grafo lo confirma.
- `n` rechaza el plan; el grafo puede proponer otra alternativa o el chat puede continuar.
- Una respuesta distinta vuelve a preguntar; `salir`, `Ctrl+C` o fin de entrada terminan sin aprobar nada.

### Demo de tres consultas

```bash
python main.py --demo
python main.py --demo --auto-aprobar
```

La demo usa conversaciones independientes para tres pedidos: horarios («¿Hasta qué hora hay metro hoy?»), ruta («¿Cómo puedo ir desde la Puerta del Sol hasta la Estación de Atocha?»), y una pregunta fuera de corpus («¿Cuál es la capital de Francia?»). La opción `--auto-aprobar` solo es válida junto con `--demo`; cuando hay varias rutas, aprueba la primera.

### Interfaz web con Streamlit

```bash
streamlit run app.py
```

La aplicación conserva el historial y el `thread_id` en la sesión del navegador. La barra lateral incluye los planes pendientes, selector cuando hay más de uno, botones **Aprobar** y **Rechazar**, **Nueva conversación** y un panel de depuración. Al existir un plan pendiente, el campo de chat queda desactivado hasta decidirlo.

El panel web oculta los diagnósticos técnicos del supervisor; el CLI sí los muestra. Al reiniciar el proceso se pierde el estado, porque el checkpointer actual está en memoria.

### Imagen demo multimodal

La única imagen seleccionable desde los clientes es la referencia literal `assets/imagen_demo.jpg`; no hay subida de archivos ni se permiten rutas arbitrarias. Escríbela como parte de la consulta, por ejemplo:

```text
Analiza assets/imagen_demo.jpg e indica los precios.
```

El grafo valida que sea el archivo demo permitido en `assets/` y solo durante ese turno. La imagen contiene una captura de «Billetes de autobuses EMT» con cuatro importes: billete sencillo EMT (1,50 €), TransBus (1,80 €), Exprés Aeropuerto (5,00 €) y Metrobús de 10 viajes (7,30 €).

Fuente: captura propia de [RedTransporte, precios de billetes y abonos (tarifas 2026)](https://www.redtransporte.com/madrid/precios-abonos.html), © RedTransporte; se utiliza únicamente con fines educativos. Fecha de captura: 2026-10-14.

La consulta «Según assets/imagen_demo.jpg, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» (la ruta literal activa el contexto de imagen, spec 007) debe seguir el flujo visión → cálculo y producir `9,50 €` cuando se use el grafo real con una API disponible.

---

## Pruebas y evaluación

La suite automatizada usa dobles para LLM, APIs, embeddings, ChromaDB y tools. No debe llamar a proveedores reales ni requerir claves:

```bash
python -m pytest -q
```

Las especificaciones cubren el RAG base, la preservación de tablas Markdown, las tools de hora/visión/cálculo, la planificación de rutas, el grafo LangGraph, la robustez del supervisor, las guardas de tarifas y los clientes CLI/Streamlit. Las validaciones disponibles documentan pruebas con grafo simulado y con el grafo real inyectando dobles, incluido el HITL, varios planes, el aislamiento por `thread_id`, la traza de tools y el filtrado de diagnósticos en la web.

El módulo RAG también incluye los puntos de entrada `rag/eval_retrieval.py` y `rag/eval_generacion.py` para evaluar la recuperación con distintos valores de `k` y las respuestas/anulaciones del generador.

---

## Limitaciones conocidas

- Las demostraciones manuales pendientes con Gemini, Nominatim y Google Routes no deben considerarse evidencia automatizada: consumen cuota y requieren las claves correspondientes.
- El checkpointer del grafo es en memoria. Al reiniciar el proceso no se conserva una conversación ni los planes pendientes.
- `hora_actual` diferencia laborable, sábado y domingo, pero no conoce festivos nacionales ni locales.
- Solo se admite la imagen demo por su referencia literal; no hay selector, subida de archivos, vídeo, audio ni rutas arbitrarias.
- La lectura visual se ha validado con la imagen demo; depende de la disponibilidad del modelo Gemini Vision.
- Las rutas no admiten hora de llegada, otros modos de desplazamiento ni títulos distintos de los dos configurados. La cobertura se limita al ámbito CRTM configurado.
- El RAG se ancla al corpus disponible y no garantiza una abstención determinista fuera de él; la instrucción de abstención se aplica en el prompt.

---

## Metodología

El proyecto sigue Spec-Driven Development (SDD). Cada funcionalidad vive en `specs/NNN-nombre/` con `spec.md`, `plan.md`, `tasks.md` y `validacion.md`. La constitución del proyecto se encuentra en `docs/constitution.md` y establece, entre otros principios, RAG anclado, separación modular, tools controladas, HITL, persistencia por conversación, configuración centralizada y pruebas sin APIs como puerta de calidad.

Las specs vigentes documentan esta evolución: desde el RAG inicial (000), la hora y horarios (001), visión/cálculo (002), tablas Markdown (003), rutas (004), grafo multiagente (005), robustez del supervisor (006), guardas para tarifas textuales (007) y clientes CLI/Streamlit (008).
