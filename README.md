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
