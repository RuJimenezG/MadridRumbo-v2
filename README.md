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
| `tarifas` (`src/agents/tarifas.py`) | Lee los importes de una imagen de tarifas; la cuenta la hace el especialista `auxiliar` | `describir_imagen` |

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


Debe listar los cuatro precios de la imagen demo (1,50 €, 1,80 €, 5,00 €, 7,30 €) y la traza con estado `ok`. Si falla con `ERROR: el modelo no pudo describir la imagen`, la causa real (tipo de error y código, como `ServerError 503 UNAVAILABLE`) queda en el registro de avisos de la consola. Un error temporal (503, 429 o de red) se reintenta una vez tras 2 segundos; una clave inválida (400, 401, 403) o un modelo retirado (404) no se reintentan.

## Imagen demo multimodal

- Archivo: `assets/imagen_demo.jpg` (800 x 260 px), usado por la tool `describir_imagen`.
- Contenido: captura de la sección «Billetes de autobuses EMT» con cuatro precios: billete sencillo EMT 1,50 €, billete sencillo TransBus 1,80 €, billete Exprés Aeropuerto 5,00 € y Metrobús 10 viajes 7,30 €.
- Fuente: captura propia de [RedTransporte, precios de billetes y abonos (tarifas 2026)](https://www.redtransporte.com/madrid/precios-abonos.html), © RedTransporte. La página no indica licencia; se usa solo con fines educativos.
- Fecha de captura: 2026-10-14.
- Demo prevista: «Según assets/imagen_demo.jpg, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» (3 × 1,50 + 5,00 = 9,50 €). Resultado real de las dos tools en `entregables/informe_decisiones.md`.

## Limitaciones conocidas (parte de José)

- `hora_actual` solo distingue laborable, sábado y domingo; los festivos se tratan como laborables.
- La lectura de cifras de `describir_imagen` se ha verificado solo con la imagen demo.
- Los especialistas `horarios` y `tarifas` se probaron con un LLM falso y ahora los usa el grafo, pero `tarifas` solo se activa con una imagen aportada válida y ningún cliente puede aportarla todavía.
- `describir_imagen` reintenta una sola vez ante un error temporal y registra la causa, pero el mensaje que ve el agente sigue siendo genérico a propósito, para no filtrar detalles internos.

## Metodología

El proyecto sigue Spec-Driven Development: cada funcionalidad tiene su carpeta en `specs/NNN-nombre/` con `spec.md`, `plan.md`, `tasks.md` y `validacion.md`. Las specs de mi parte son `specs/001-tool-hora-especialista-horarios/` y `specs/002-multimodal-imagen-calculadora/`. Las reglas están en `docs/constitution.md` y `AGENTS.md`.

## Cómo usar la aplicación (CLI y Streamlit)

El CLI (`main.py`) y la web (`app.py`) son clientes del mismo grafo multiagente y muestran lo mismo ante el mismo pedido: respuesta, planes, qué especialistas actuaron y qué tools se ejecutaron. La aprobación humana (HITL) la pide el grafo cuando una consulta genera un **plan de ruta**: solo una aprobación lo cierra. Las demás consultas (horarios, RAG) se responden directamente, sin preguntar nada.

### Qué grafo se usa

Los clientes usan el grafo real de `src/agent.py` (funciones `procesar_turno` y `aprobar_plan`). Hace falta instalar las dependencias (`pip install -r requirements.txt`) y tener en el `.env` las claves que use cada tool: `GEMINI_API_KEY` para el modelo y, para planificar rutas, `GOOGLE_ROUTES_API_KEY` y `NOMINATIM_CONTACTO` (los nombres están en `.env.example`). **Con el grafo real, una ruta gasta llamadas a Gemini, Nominatim y Google.**

Para probar los clientes sin gastar API se puede activar el **modo simulado**: un grafo de pruebas con respuestas fijas que se parece al real (solo las rutas pausan, con uno o varios planes). Se activa con una variable de entorno y los clientes avisan de que están en ese modo.

PowerShell:

```powershell
$env:MADRIDRUMBO_GRAFO = "falso"
```

Bash:

```bash
export MADRIDRUMBO_GRAFO=falso
```

### Chat por terminal

```bash
python main.py
```

Escribe tu consulta y pulsa Intro. Si la consulta genera un plan de ruta, el CLI lo muestra (identificador, origen, destino, duración, tramos, zona y precio) y pregunta:

- Si hay **varios planes**, primero `¿Qué plan quieres decidir? [1-N]`: escribe el número. Con un único plan no pregunta.
- Después `¿Apruebas el plan? [s/n]`: `s` aprueba y se muestra `Terminada: sí`; `n` rechaza, y el grafo vuelve a planificar y suele proponer otro plan, que se pregunta de nuevo.
- Cualquier otra respuesta vuelve a preguntar. Con `salir` (o Ctrl+C) se termina sin aprobar nada.

El CLI muestra también el registro técnico del supervisor (líneas `Supervisor: categoria=...`), que es lo que consulta quien depura.

### Demo de tres pedidos

```bash
python main.py --demo                  # pide aprobar o rechazar el plan de la ruta a mano
python main.py --demo --auto-aprobar   # aprueba los planes automáticamente
```

La demo lanza, cada uno en su propia conversación: «¿Hasta qué hora hay metro hoy?» (horarios, sin pausa), «¿Cómo puedo ir desde la Puerta del Sol hasta la Estación de Atocha?» (ruta: genera un plan y pausa para HITL) y «¿Cuál es la capital de Francia?» (fuera de corpus, sin pausa). `--auto-aprobar` solo se puede usar junto con `--demo`, y con varios planes aprueba el primero.

### Web con Streamlit

```bash
streamlit run app.py
```

- En la barra lateral aparecen los planes pendientes con su resumen. Si hay varios, un selector permite elegir cuál decidir; los botones **Aprobar** y **Rechazar** solo están activos con un plan pendiente. Mientras lo haya, el cuadro de mensaje queda bloqueado.
- **Nueva conversación** crea un identificador nuevo y vacía el historial.
- El desplegable **Depuración** muestra el identificador, los especialistas que actuaron, la traza de tools y las banderas de plan pendiente y conversación terminada. **No muestra** los diagnósticos técnicos del supervisor: esos solo salen en el CLI.

### Cómo probar el HITL

1. Activa el modo simulado y lanza `python main.py`.
2. Escribe «¿Cómo puedo ir desde la Puerta del Sol hasta la Estación de Atocha?»: aparece un plan y la pregunta `[s/n]`.
3. Responde `n` y comprueba que no se cierra. Con el grafo real se propone otro plan; en el modo simulado no queda ninguno y puedes escribir otro mensaje.
4. Vuelve a escribir la ruta y responde `s` al plan: debe aparecer `Terminada: sí`.
5. Para ver la elección entre varios planes (solo en el modo simulado), escribe «Dame dos rutas alternativas desde la Puerta del Sol hasta la Estación de Atocha» y elige un número.

En Streamlit es lo mismo con el selector y los botones de la barra lateral.

### Limitaciones conocidas de los clientes

- **Imágenes:** los clientes no pueden aportar una imagen al grafo, así que las consultas sobre una imagen se desvían al RAG y el especialista `tarifas` no se activa desde el CLI ni desde la web. Queda pendiente de que el grafo ofrezca una forma de aportarla.
- Con el grafo real, la sesión vive en memoria: al reiniciar el proceso se pierden las conversaciones.

### Código de los clientes

Todo está en `src/clientes/`: `contrato.py` (claves del estado que devuelve el grafo), `planes.py` (resumen de planes y filtro del log), `presentacion.py` (formato común), `sesion.py` (lógica de la conversación, compartida), `cargar.py` (grafo real o simulado), `grafo_falso.py` y `cli.py`. `main.py` y `app.py` son capas finas que solo dibujan. Los tests (`python -m pytest`) no gastan API: usan el grafo simulado y el grafo real con especialistas falsos (`tests/test_clientes_grafo_real.py`). La especificación está en `specs/008-clientes-cli-streamlit/`.
