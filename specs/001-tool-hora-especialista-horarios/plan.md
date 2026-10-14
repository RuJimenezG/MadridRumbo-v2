# Plan técnico — Spec 001

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento que no esté en la spec.

## Archivos afectados
| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/tools/hora_actual.py` | Crear | Función `hora_actual(ahora=None) -> str` | RF-1–5 |
| `src/tools/__init__.py` | Crear o modificar (compartido con el equipo) | Registra `hora_actual` en la allowlist y expone `ejecutar_tool(nombre, args, traza)` | RF-6, RF-7, RF-12 |
| `src/agents/__init__.py` | Crear | Paquete de especialistas | RF-8 |
| `src/agents/horarios.py` | Crear | `PROMPT_HORARIOS` y `nodo_horarios(estado, llm, ejecutar)` | RF-8–15 |
| `src/supervisor_reglas.py` (o función en `src/graph.py`) | Crear / modificar | `PALABRAS_HORARIOS` y `elegir_rol_por_palabras(mensaje)` para el fallback | RF-16 |
| `config.py` | Modificar | `ZONA_HORARIA`, `MAX_STEPS_ESPECIALISTA`, `TOOLS_POR_ESPECIALISTA["horarios"]` | RF-4, RF-12, RF-13 |
| `requirements.txt` | Modificar | Añadir `tzdata` (necesario para `zoneinfo` en Windows) y `pytest` | RF-4 |
| `tests/test_hora_actual.py` | Crear | Tests de la tool | RF-1–5 |
| `tests/test_allowlist_horarios.py` | Crear | Allowlist y traza | RF-6, RF-7, RF-12 |
| `tests/test_especialista_horarios.py` | Crear | Especialista con LLM y tools falsos | RF-8–15 |
| `tests/test_fallback_horarios.py` | Crear | Fallback por palabras | RF-16 |

## Contrato

**Tool**
```text
hora_actual(ahora: datetime | None = None) -> str
  ahora: solo para tests; si es None se usa el reloj real en ZONA_HORARIA.

Salida: "Hoy es martes 13/10/2026, son las 17:58 (laborable, hora de Madrid)."
Error:  "ERROR: no se pudo obtener la hora (zona horaria no válida)."
```

**Ejecución y traza** (compartido con la allowlist del equipo)
```text
ejecutar_tool(nombre, args, traza) -> str
  - nombre fuera de TOOLS_PERMITIDAS -> "ERROR: tool no permitida: <nombre>" y traza con status "bloqueada"
  - traza.append({"tool": nombre, "args": args, "status": "ok|error|bloqueada", "preview": resultado[:120]})
```

**Especialista**
```text
nodo_horarios(estado: dict, llm: Callable, ejecutar: Callable) -> dict
  estado entrada: {"mensaje": str, "notas": list[str], "traza": list[dict]}
  llm(mensajes) -> {"tool": str, "args": dict}   # pide una tool
               | {"final": str}                  # nota final
  salida: {"notas": [..., "[horarios] <texto>"], "traza": [...]}
```
Ejemplo: «¿hasta qué hora hay metro hoy?» → el LLM pide `hora_actual` → pide `rag_ask` con la consulta → devuelve `final`; la traza tiene 2 entradas.

## Lógica clave
```text
nodo_horarios:
  pasos = 0; permitidas = TOOLS_POR_ESPECIALISTA["horarios"]
  historial = [PROMPT_HORARIOS, mensaje]
  mientras pasos < MAX_STEPS_ESPECIALISTA:
      resp = llm(historial)                  # try/except -> nota de error (RF-15)
      si resp tiene "final": devolver nota
      si resp no es dict válido: nota de error (RF-15)
      si resp["tool"] no está en permitidas: traza "bloqueada"; aviso al historial; pasos += 1; continuar (RF-12)
      resultado = ejecutar(resp["tool"], resp["args"], traza)
      historial += resultado; pasos += 1
  devolver nota "límite de pasos alcanzado" + lo obtenido (RF-13)
```

## Decisiones técnicas
| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Mini-bucle con protocolo `{"tool","args"}` / `{"final"}` e inyección de `llm` | `bind_tools` de LangChain | Se testea con un LLM falso sin depender del proveedor; el enunciado permite ambas |
| `zoneinfo` + `tzdata` | `pytz`, o desfase fijo UTC+1/+2 | `zoneinfo` es estándar y gestiona CET/CEST; en Windows necesita `tzdata`. Dependencia nueva a aprobar (constitución, principio 12) |
| `ahora` opcional como parámetro | Parchear el reloj con librerías externas | Test determinista sin dependencias extra |
| Solo laborable / sábado / domingo | Calendario de festivos | Los festivos son datos variables; fuera de alcance |
| Los horarios salen del RAG | Tabla de horarios en código | Constitución: anclaje y no inventar datos |
| El especialista nunca fija `done` | Que el especialista cierre | Constitución, principio 7 |

## Estrategia de tests
Todos sin API: `pytest`, `monkeypatch` y funciones falsas (`docs/tests_sin_api.md`).
- RF-1/2/3: `hora_actual(datetime(2026,10,13,17,58,tzinfo=ZoneInfo("Europe/Madrid")))` incluye «martes», «13/10/2026», «17:58» y «laborable»; sábado y domingo con otras fechas; sin argumentos devuelve `str`; se parchea `socket` para comprobar que no abre red.
- RF-4: cambiar `config.ZONA_HORARIA` cambia la hora devuelta.
- RF-5: zona inválida → texto que empieza por `ERROR:` y sin excepción.
- RF-6/7/12: `ejecutar_tool` con nombre no permitido no llama a ninguna función y deja traza «bloqueada»; con `hora_actual` deja traza «ok».
- RF-8: `PROMPT_HORARIOS` no vacío y el nodo lo envía como primer mensaje al LLM falso.
- RF-9/10/11: LLM falso con guion (`hora_actual` → `rag_ask` → final); RAG falso sin evidencia → nota con la abstención y sin horarios inventados.
- RF-13: LLM falso que pide tools sin parar; con `MAX_STEPS_ESPECIALISTA=2` solo hay 2 ejecuciones y la nota indica el límite.
- RF-14: la salida no contiene la clave `done`.
- RF-15: LLM falso que lanza excepción y otro que devuelve basura → nota de error.
- RF-16: `elegir_rol_por_palabras("¿a qué hora cierra el metro?") == "horarios"`; un mensaje sin esas palabras no.
- Manual: demo en CLI/Streamlit cuando el grafo esté integrado (se indica en `validacion.md`).

## Riesgos
- Contrato del estado y del LLM sin acordar con quien haga el grafo (ver duda abierta de la spec).
- Dependencia nueva `tzdata`: pendiente de aprobar.
- Las palabras clave del fallback pueden solaparse con las de otros especialistas; hay que coordinar el orden.

## Trazabilidad
| RF | Parte del plan | Test |
|---|---|---|
| RF-1 | `hora_actual.py` | `tests/test_hora_actual.py::test_formato_laborable`, `::test_sabado_domingo` |
| RF-2 | `hora_actual.py` | `::test_sin_argumentos` |
| RF-3 | `hora_actual.py` | `::test_sin_red` |
| RF-4 | `config.py` | `::test_zona_horaria_configurable` |
| RF-5 | `hora_actual.py` | `::test_zona_invalida` |
| RF-6, RF-7 | `src/tools/__init__.py` | `tests/test_allowlist_horarios.py::test_hora_en_allowlist`, `::test_traza_ok` |
| RF-8 | `agents/horarios.py` | `tests/test_especialista_horarios.py::test_prompt_propio` |
| RF-9 | `agents/horarios.py` | `::test_usa_hora_actual` |
| RF-10 | `agents/horarios.py` | `::test_usa_rag` |
| RF-11 | `agents/horarios.py` | `::test_abstencion_sin_evidencia` |
| RF-12 | `src/tools/__init__.py` | `tests/test_allowlist_horarios.py::test_tool_no_permitida` |
| RF-13 | `agents/horarios.py` | `tests/test_especialista_horarios.py::test_max_steps` |
| RF-14 | `agents/horarios.py` | `::test_no_decide_done` |
| RF-15 | `agents/horarios.py` | `::test_llm_falla`, `::test_respuesta_invalida` |
| RF-16 | `supervisor_reglas.py` | `tests/test_fallback_horarios.py::test_palabras_horario` |
