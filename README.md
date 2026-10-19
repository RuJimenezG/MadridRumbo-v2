# MadridRumbo
> **Project Break 2 · Sprints 11–13 | AI Engineering Bootcamp**
> **Grupo 3:** Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.

> **Estado del README.** Este documento se está completando por partes. Aquí figura la parte de **José** (tools auxiliares, multimodal y sus especialistas). Instalación general, indexado del RAG, grafo, CLI y Streamlit los completa el resto del equipo.

## Tools y especialistas (parte de José)

### Tools

Todas están en `src/tools/` y solo se ejecutan a través de `ejecutar_tool(nombre, args, traza)`, que aplica la allowlist `TOOLS_PERMITIDAS` y deja en `traza` el nombre, los argumentos, el estado (`ok`, `error` o `bloqueada`) y un extracto del resultado. El LLM propone; el código decide qué se ejecuta.

| Tool | Tipo | Qué hace |
|---|---|---|
| `hora_actual` | Auxiliar determinista | Fecha, hora, día de la semana y tipo de día (laborable, sábado o domingo) en la zona horaria configurada. Sin red ni LLM. No conoce festivos. |
| `calculadora` | Auxiliar determinista | Evalúa `+ - * /`, paréntesis y signo menos, con decimales con coma o punto. Usa `ast` y `Decimal`, sin `eval`. Resultado con 2 decimales (enteros sin decimales). |
| `describir_imagen` | Multimodal | Lee una imagen de `assets/` con Gemini y devuelve los textos y cifras visibles. Solo JPG, JPEG y PNG, máximo 4 MB, y solo dentro de `assets/`. |
| `rag_ask` | RAG | Delega en `rag.responder.rag_ask`. Se importa solo al usarla. |

Cualquier fallo (tool no permitida, error del modelo, expresión inválida…) devuelve un texto que empieza por `ERROR`, sin lanzar excepciones.

### Especialistas

Los dos comparten el bucle de `src/agents/base.py`: el LLM devuelve `{"tool", "args"}` para pedir una tool o `{"final"}` para dar su nota. El código aplica la lista de tools de cada especialista y el tope de pasos. Un especialista **nunca decide `done`**: solo devuelve `notas` y `traza`.

| Especialista | Para qué | Tools permitidas |
|---|---|---|
| `horarios` (`src/agents/horarios.py`) | Cuándo, a qué hora y hasta cuándo hay servicio | `hora_actual`, `rag_ask` |
| `tarifas` (`src/agents/tarifas.py`) | Precios y totales a partir de una imagen de tarifas | `describir_imagen`, `calculadora`, `rag_ask` |

`src/supervisor_reglas.py` contiene el fallback determinista del supervisor: `elegir_rol_por_palabras(mensaje)` devuelve `"horarios"` si el mensaje trae términos como hora, horario, ahora, hoy, noche, última, primera, abre, cierra o frecuencia; si no, devuelve `None`.

### Configuración (`config.py`)

| Constante | Valor | Para qué |
|---|---|---|
| `ZONA_HORARIA` | `Europe/Madrid` | Zona de `hora_actual` |
| `MAX_STEPS_ESPECIALISTA` | `3` | Máximo de tools por turno de un especialista |
| `TOOLS_POR_ESPECIALISTA` | dict | Allowlist de cada especialista |
| `IMAGENES_DIR`, `IMAGEN_DEMO` | `assets/`, `imagen_demo.jpg` | Carpeta autorizada e imagen por defecto |
| `IMAGEN_MAX_MB`, `EXTENSIONES_IMAGEN` | `4`, jpg/jpeg/png | Límites de `describir_imagen` |
| `MODELO_VISION` | `gemini-3.8-flash` | Modelo de la tool de imagen, independiente del modelo del RAG |
| `CALC_MAX_CARACTERES` | `200` | Longitud máxima de una expresión |

## Cómo probar mi parte

### Tests (sin API)

Con el entorno virtual activo y las dependencias instaladas (`pip install -r requirements.txt`):

```bash
python -m pytest
```

Los tests usan un LLM, un cliente de visión y unas tools falsos: no llaman a ninguna API ni gastan cuota.

### `hora_actual` y `calculadora` (locales, sin API)

```bash
python -c "from src.tools import ejecutar_tool; print(ejecutar_tool('hora_actual', {}, []))"
python -c "from src.tools import ejecutar_tool; print(ejecutar_tool('calculadora', {'expresion': '3*1,50+5,00'}, []))"
```

La segunda debe imprimir `9,50`.

### Multimodal con la API real (⚠️ gasta una llamada)

1. Consigue una clave gratuita en [Google AI Studio](https://aistudio.google.com/apikey).
2. Crea un archivo `.env` 

   ```
   GEMINI_API_KEY=tu_clave
   ```


Debe listar los cuatro precios de la imagen demo (1,50 €, 1,80 €, 5,00 €, 7,30 €) y la traza con estado `ok`. Si falla con `ERROR: el modelo no pudo describir la imagen`, la causa puede ser una clave inválida, un modelo saturado (503) o no disponible (404): la tool no muestra el motivo.

## Imagen demo multimodal

- Archivo: `assets/imagen_demo.jpg` (800 x 260 px), usado por la tool `describir_imagen`.
- Contenido: captura de la sección «Billetes de autobuses EMT» con cuatro precios: billete sencillo EMT 1,50 €, billete sencillo TransBus 1,80 €, billete Exprés Aeropuerto 5,00 € y Metrobús 10 viajes 7,30 €.
- Fuente: captura propia de [RedTransporte, precios de billetes y abonos (tarifas 2026)](https://www.redtransporte.com/madrid/precios-abonos.html), © RedTransporte. La página no indica licencia; se usa solo con fines educativos.
- Fecha de captura: 2026-10-14.
- Demo prevista: «Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» (3 × 1,50 + 5,00 = 9,50 €). Resultado real de las dos tools en `entregables/informe_decisiones.md`.

## Limitaciones conocidas (parte de José)

- `hora_actual` solo distingue laborable, sábado y domingo; los festivos se tratan como laborables.
- La lectura de cifras de `describir_imagen` se ha verificado solo con la imagen demo.
- Los especialistas `horarios` y `tarifas` todavía no están conectados a un grafo: se han probado con un LLM falso.
- `describir_imagen` no reintenta ante un error temporal del modelo y no informa de la causa.

## Metodología

El proyecto sigue Spec-Driven Development: cada funcionalidad tiene su carpeta en `specs/NNN-nombre/` con `spec.md`, `plan.md`, `tasks.md` y `validacion.md`. Las specs de mi parte son `specs/001-tool-hora-especialista-horarios/` y `specs/002-multimodal-imagen-calculadora/`. Las reglas están en `docs/constitution.md` y `AGENTS.md`.

## Cómo usar la aplicación (CLI y Streamlit)

El CLI (`main.py`) y la web (`app.py`) son clientes del mismo grafo multiagente y muestran lo mismo ante el mismo pedido: respuesta, plan, qué especialistas actuaron y qué tools se ejecutaron. Antes de cualquier plan se pide la aprobación humana (HITL): solo una aprobación cierra la conversación y un rechazo permite seguir con otro mensaje.

### Qué grafo se usa

Los clientes buscan el grafo real en `src/agent.py` (funciones `procesar_turno` y `aprobar_plan`). Mientras no esté disponible, o para probar los clientes sin gastar API, se puede activar el **modo simulado**: un grafo de pruebas con respuestas fijas que reparte los pedidos entre horarios, tarifas y RAG. Se activa con una variable de entorno y los clientes avisan de que están en ese modo.

PowerShell:

```powershell
$env:MADRIDRUMBO_GRAFO = "falso"
```

Bash:

```bash
export MADRIDRUMBO_GRAFO=falso
```

Sin grafo real y sin la variable, los clientes no arrancan y explican cómo activarla.

### Chat por terminal

```bash
python main.py
```

Escribe tu consulta y pulsa Intro. Tras cada respuesta con plan, el CLI pregunta `¿Apruebas el plan? [s/n]`:

- `s` aprueba y se muestra `Terminada: sí` si el grafo da la conversación por terminada.
- `n` rechaza: el plan se descarta y puedes escribir otro mensaje en la misma conversación.
- Cualquier otra cosa vuelve a preguntar. Con `salir` (o Ctrl+C) se termina sin aprobar nada.

### Demo de tres pedidos

```bash
python main.py --demo                  # pide aprobar o rechazar cada plan a mano
python main.py --demo --auto-aprobar   # aprueba los planes automáticamente
```

La demo lanza, cada uno en su propia conversación: «¿Hasta qué hora hay metro hoy?» (horarios), «Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» (tarifas con la imagen demo) y «¿Cuál es la capital de Francia?» (fuera de corpus). `--auto-aprobar` solo se puede usar junto con `--demo`.

### Web con Streamlit

```bash
streamlit run app.py
```

- En la barra lateral aparecen el plan pendiente y los botones **Aprobar** y **Rechazar**, que solo están activos si hay un plan pendiente. Mientras lo haya, el cuadro de mensaje queda bloqueado.
- **Nueva conversación** crea un identificador nuevo y vacía el historial.
- El desplegable **Depuración** muestra el identificador de la conversación, los especialistas que actuaron, la traza de tools y las banderas de plan pendiente y conversación terminada.

### Cómo probar el HITL

1. Activa el modo simulado y lanza `python main.py`.
2. Escribe cualquier consulta: aparece un plan y la pregunta `[s/n]`.
3. Responde `n` y comprueba que no se cierra y que puedes escribir otro mensaje.
4. Escribe otra consulta y responde `s`: debe aparecer `Terminada: sí`.

En Streamlit es lo mismo con los botones de la barra lateral.

### Código de los clientes

Todo está en `src/clientes/`: `contrato.py` (claves del estado que devuelve el grafo), `presentacion.py` (formato común), `sesion.py` (lógica de la conversación, compartida), `cargar.py` (grafo real o simulado), `grafo_falso.py` y `cli.py`. `main.py` y `app.py` son capas finas que solo dibujan. Los tests (`python -m pytest`) usan el grafo simulado y no gastan API.
