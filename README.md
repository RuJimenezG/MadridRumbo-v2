# MadridRumbo
> **Project Break 2 · Sprints 11–13 | AI Engineering Bootcamp**
> **Grupo 3:** Rubén Jiménez Gutiérrez, Guzmán López Barceló, José Manuel Gil Ruiz.

## Imagen demo multimodal

- Archivo: `assets/imagen_demo.jpg` (800 x 260 px), usado por la tool `describir_imagen`.
- Contenido: captura de la sección «Billetes de autobuses EMT» con cuatro precios: billete sencillo EMT 1,50 €, billete sencillo TransBus 1,80 €, billete Exprés Aeropuerto 5,00 € y Metrobús 10 viajes 7,30 €.
- Fuente: captura propia de [RedTransporte, precios de billetes y abonos (tarifas 2026)](https://www.redtransporte.com/madrid/precios-abonos.html), © RedTransporte. La página no indica licencia; se usa solo con fines educativos.
- Fecha de captura: 2026-10-14.
- Demo prevista: «Según la imagen, ¿cuánto cuestan 3 billetes sencillos EMT y 1 Exprés Aeropuerto?» (3 × 1,50 + 5,00 = 9,50 €).

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
