# Plan técnico — Spec 002

> Basado en `spec.md` (estado: Aprobada). No añade comportamiento que no esté en la spec.

## Archivos afectados
| Archivo | Crear / Modificar | Qué cambia | RF |
|---|---|---|---|
| `src/tools/describir_imagen.py` | Crear | `describir_imagen(ruta=None, pregunta=None, cliente=None) -> str` | RF-1–8 |
| `src/tools/calculadora.py` | Crear | `calculadora(expresion) -> str` con evaluador seguro | RF-12–18 |
| `src/tools/__init__.py` | Crear o modificar (compartido) | Registra ambas tools en la allowlist con traza | RF-9, RF-10, RF-19, RF-20 |
| `src/agents/` (módulo del especialista que use las tools) | Modificar o crear | Instrucción de prompt para el flujo imagen → calculadora | RF-21–23 |
| `config.py` | Modificar | `IMAGENES_DIR`, `IMAGEN_DEMO`, `IMAGEN_MAX_MB`, `EXTENSIONES_IMAGEN`, `MODELO_VISION`, `CALC_MAX_CARACTERES`, `TOOLS_POR_ESPECIALISTA` | RF-3, RF-5, RF-6, RF-17 |
| `assets/imagen_demo.jpg` | Crear (aporte manual) | Imagen con tarifas legibles | RF-11 |
| `tests/test_describir_imagen.py` | Crear | Tests con cliente falso | RF-1–8 |
| `tests/test_calculadora.py` | Crear | Tests del evaluador | RF-12–18 |
| `tests/test_allowlist_multimodal.py` | Crear | Allowlist, traza e imagen demo | RF-9–11, RF-19, RF-20 |
| `tests/test_flujo_imagen_calculo.py` | Crear | Flujo con LLM y tools falsos | RF-21–23 |

## Contrato
```text
describir_imagen(ruta: str | None = None, pregunta: str | None = None, cliente=None) -> str
  ruta relativa a IMAGENES_DIR; None -> IMAGEN_DEMO; cliente solo para tests
  Errores: "ERROR: la imagen no existe: x.png" | "ERROR: formato no admitido (.gif)" |
           "ERROR: imagen demasiado grande (límite 4 MB)" | "ERROR: ruta no permitida" |
           "ERROR: el modelo no pudo describir la imagen" | "No hay texto legible en la imagen."

calculadora(expresion: str) -> str
  calculadora("3*2,40 + 2*54,60") -> "116,40"
  calculadora("10/0")             -> "ERROR: división entre cero"
  calculadora("__import__('os')") -> "ERROR: expresión no permitida"
  calculadora("")                 -> "ERROR: expresión vacía"
```
(Las cifras son ilustrativas.)

## Lógica clave
```text
describir_imagen: igual que en 002 (validar ruta dentro de IMAGENES_DIR, formato, tamaño; llamar al modelo; errores controlados).

calculadora(expresion):
  si vacía o len > CALC_MAX_CARACTERES: ERROR
  e = expresion.replace(",", ".")
  arbol = ast.parse(e, mode="eval")             # SyntaxError -> ERROR mal formada
  evaluar(nodo):
     Constant int/float          -> valor
     BinOp con + - * /           -> operar recursivamente
     UnaryOp con - (o +)         -> operar
     cualquier otro nodo         -> ERROR no permitida
  ZeroDivisionError -> ERROR división entre cero
  resultado -> redondeo comercial a 2 decimales -> coma decimal; enteros sin decimales ("5"), no enteros siempre con 2 ("7,20", "2,50")

Flujo (prompt del especialista):
  1. describir_imagen(pregunta="lista de importes")
  2. si hay importes -> calculadora(expresión construida con ellos)
  3. nota: "importes leídos de la imagen: ...; operación: ...; total: ..."
  4. si no hay importes -> nota "no hay importes legibles", sin calcular
```

## Decisiones técnicas
| Decisión | Alternativa descartada | Por qué |
|---|---|---|
| Evaluador sobre `ast` con lista blanca de nodos | `eval()` | `eval` ejecutaría código arbitrario propuesto por el LLM (RF-15) |
| Sin potencias | Admitir `**` | Evita `2**9999` y no hace falta para importes |
| `Decimal`/redondeo a 2 decimales al formatear | `float` sin más | Importes en euros; evita colas como 0,30000000004 |
| Coma o punto decimales | Solo punto | La imagen y los usuarios escriben «54,60» |
| `describir_imagen` con `cliente` inyectable y rutas relativas | Rutas absolutas | Test sin API y sin lectura fuera de la carpeta autorizada |
| Dos tools separadas | Una tool «lee y calcula» | Cada una determinista/trazable por separado; se prueba la calculadora sin LLM |
| El flujo vive en el prompt del especialista (no en código fijo) | Función que encadena ambas | El LLM decide, pero cada paso pasa por la allowlist y el tope de pasos |
| `MODELO_VISION = "gemini-3.8-flash"`, independiente de `GENERATION_MODEL` | Reutilizar `GENERATION_MODEL` (`gemini-3.6-flash`) | En la demo real (2026-10-14) `gemini-3.6-flash` dio 503 por demanda alta y `gemini-2.5-flash` ya no está disponible; `gemini-3.8-flash` leyó bien la imagen. Así no se toca el modelo del RAG |

## Estrategia de tests
Sin API: cliente falso, LLM falso y `tmp_path` (ver `docs/tests_sin_api.md`).
- RF-1–8 y RF-11: como en 002.
- RF-12/13/14: parametrizados (`"2+3"→"5"`, `"3*2,40"→"7,20"`, `"-(4+1)"→"-5"`, `"10/4"→"2,50"`, `"1/3"→"0,33"`).
- RF-15: `"abs(3)"`, `"__import__('os')"`, `"2**3"`, `"a+1"`, `"3;4"` → `ERROR`.
- RF-16: `"1/0"`. RF-17: `""`, `"2+"`, cadena de 201 caracteres.
- RF-18: se parchea `socket` y se comprueba que no hay llamadas.
- RF-19/20: `ejecutar_tool("calculadora", ...)` deja traza ok; tool ajena bloqueada.
- RF-21/22: LLM falso con guion `describir_imagen` → `calculadora` → final; la nota contiene los importes y la operación; la traza tiene los dos pasos en ese orden.
- RF-23: cliente falso sin importes → no hay llamada a `calculadora` y la nota lo indica.
- Manual (⚠️ API): demo de la pregunta de ejemplo con la imagen real y comprobación a mano del total.

## Riesgos
- El modelo puede leer mal una cifra; la nota muestra los importes leídos para poder verificarlos.
- Imagen demo pendiente.
- Contrato del LLM/estado compartido con el grafo (igual que la spec 001).
- Dos tools nuevas en la allowlist: coordinar con quien la mantenga para no pisar el registro.

## Trazabilidad
| RF | Parte del plan | Test |
|---|---|---|
| RF-1, RF-2 | `describir_imagen.py` | `tests/test_describir_imagen.py::test_describe_imagen`, `::test_pregunta_en_prompt` |
| RF-3 | `describir_imagen.py`, `config.py` | `::test_imagen_por_defecto` |
| RF-4 | `describir_imagen.py` | `::test_no_existe`, `::test_formato_no_admitido` |
| RF-5 | `describir_imagen.py` | `::test_imagen_grande` |
| RF-6 | `describir_imagen.py` | `::test_ruta_fuera_de_carpeta` |
| RF-7 | `describir_imagen.py` | `::test_modelo_falla` |
| RF-8 | `describir_imagen.py` | `::test_sin_texto_legible` |
| RF-9, RF-10 | `src/tools/__init__.py` | `tests/test_allowlist_multimodal.py::test_imagen_en_allowlist`, `::test_traza_imagen` |
| RF-11 | `assets/` | `tests/test_allowlist_multimodal.py::test_imagen_demo_existe` + manual |
| RF-12–14 | `calculadora.py` | `tests/test_calculadora.py::test_operaciones`, `::test_decimales_coma`, `::test_formato_resultado` |
| RF-15 | `calculadora.py` | `::test_expresion_no_permitida` |
| RF-16 | `calculadora.py` | `::test_division_cero` |
| RF-17 | `calculadora.py` | `::test_expresion_vacia_o_larga` |
| RF-18 | `calculadora.py` | `::test_sin_red` |
| RF-19, RF-20 | `src/tools/__init__.py` | `tests/test_allowlist_multimodal.py::test_calculadora_en_allowlist`, `::test_traza_calculadora` |
| RF-21 | prompt del especialista | `tests/test_flujo_imagen_calculo.py::test_imagen_luego_calculo` |
| RF-22 | prompt del especialista | `::test_nota_muestra_importes_y_operacion` |
| RF-23 | prompt del especialista | `::test_sin_importes_no_calcula` |
