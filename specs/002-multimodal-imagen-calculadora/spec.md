# Spec 002 — Tool multimodal `describir_imagen` + `calculadora` 

> Estado: Aprobada · Fecha: 2026-10-14 · Responsable: José Manuel Gil Ruiz

## Contexto y objetivo

El enunciado exige una tool multimodal imagen → texto con una imagen demo de texto legible. Además, una persona que ve un cartel de tarifas suele querer una cuenta («¿cuánto cuestan 3 billetes sencillos y 2 abonos?»), y un LLM no debe calcular de cabeza. Esta opción añade a la lectura de imagen una calculadora determinista, para que el flujo imagen → importes → total sea trazable y exacto.

## Usuarios / actores

- Persona usuaria que quiere leer un cartel de transporte y calcular un coste.
- Especialista del grafo que usa las tools.
- Equipo que necesita una demo multimodal verificable.

## Historias de usuario

- H1: Como usuaria quiero que el asistente lea el cartel de tarifas de una imagen para no tener que transcribirlo.
- H2: Como usuaria quiero que el asistente calcule el total de varios billetes con exactitud.
- H3: Como equipo quiero que las tools fallen de forma controlada y no ejecuten código arbitrario.

## Requisitos funcionales

### Tool `describir_imagen`

- RF-1: CUANDO se invoca la tool `describir_imagen` con la ruta de una imagen válida, EL SISTEMA devuelve en español un texto con el contenido visible de la imagen, incluidos los textos y cifras legibles.
- RF-2: DONDE se indique una pregunta opcional sobre la imagen, EL SISTEMA orienta la descripción a esa pregunta.
- RF-3: CUANDO no se indica ruta, EL SISTEMA usa la imagen demo configurada.
- RF-4: SI el archivo no existe o su formato no es JPG, JPEG o PNG, ENTONCES EL SISTEMA devuelve un error controlado sin llamar al modelo.
- RF-5: SI el archivo supera el tamaño máximo configurado, ENTONCES EL SISTEMA devuelve un error controlado sin llamar al modelo.
- RF-6: SI la ruta está fuera de la carpeta de imágenes autorizada, ENTONCES EL SISTEMA devuelve un error controlado sin leer el archivo.
- RF-7: SI el modelo falla (red, cuota o respuesta vacía), ENTONCES EL SISTEMA devuelve un mensaje de error controlado, sin lanzar excepción y sin inventar contenido.
- RF-8: SI la imagen no contiene texto legible, ENTONCES EL SISTEMA lo indica en lugar de inventar cifras.
- RF-9: EL SISTEMA solo permite ejecutar `describir_imagen` como tool si figura en la allowlist.
- RF-10: CUANDO se ejecuta `describir_imagen`, EL SISTEMA registra en la traza nombre, argumentos, estado y un extracto del resultado.
- RF-11: EL SISTEMA incluye una imagen demo con texto legible de tarifas o información de transporte de Madrid.

### Tool `calculadora`

- RF-12: CUANDO se invoca la tool `calculadora` con una expresión aritmética, EL SISTEMA devuelve el resultado numérico en texto.
- RF-13: EL SISTEMA admite en la expresión números enteros y decimales (con punto o con coma), las operaciones suma, resta, multiplicación y división, paréntesis y el signo menos unario.
- RF-14: EL SISTEMA devuelve el resultado con un máximo de 2 decimales y coma decimal.
- RF-15: SI la expresión contiene letras, nombres, llamadas a funciones o cualquier carácter no permitido, ENTONCES EL SISTEMA devuelve un error controlado sin ejecutar nada.
- RF-16: SI la expresión implica dividir entre cero, ENTONCES EL SISTEMA devuelve un error controlado.
- RF-17: SI la expresión está vacía, está mal formada o supera 200 caracteres, ENTONCES EL SISTEMA devuelve un error controlado.
- RF-18: EL SISTEMA no usa red ni LLM para ejecutar `calculadora`.
- RF-19: EL SISTEMA solo permite ejecutar `calculadora` como tool si figura en la allowlist.
- RF-20: CUANDO se ejecuta `calculadora`, EL SISTEMA registra en la traza nombre, argumentos, estado y el resultado.

### Flujo combinado

- RF-21: CUANDO la pregunta pide un total a partir de importes de una imagen, EL SISTEMA invoca `describir_imagen` y después `calculadora`, y no estima el total por su cuenta.
- RF-22: EL SISTEMA indica en la nota que los importes proceden de la imagen y muestra la operación realizada.
- RF-23: SI `describir_imagen` no devuelve los importes necesarios, ENTONCES EL SISTEMA no calcula y lo indica.

## Requisitos no funcionales

- Coste: los tests no llaman al modelo; `calculadora` es puramente local.
- Seguridad: no se usa `eval` sobre texto del usuario o del LLM; el LLM no puede leer archivos fuera de la carpeta autorizada.
- Configuración: carpeta de imágenes, imagen demo, tamaño máximo, modelo y longitud máxima de la expresión en un único punto.
- Idioma: salidas en español.

## Casos límite

- Imagen inexistente, `.gif`, demasiado grande, ruta `../.env`, sin conexión, sin texto: RF-4 a RF-8.
- Expresión `2**9999`, `__import__('os')`, `1/0`, `""`: RF-15 a RF-17.
- Importe leído con coma («54,60»): RF-13.
- La imagen no trae precios: RF-23.

## Fuera de alcance

- Subida de imágenes desde Streamlit.
- Vídeo, audio y PDFs escaneados; OCR local sin LLM.
- Funciones avanzadas (potencias, raíces, porcentajes, conversión de divisas).
- Cálculos con IVA, descuentos o bonificaciones: esa lógica sale del RAG, no de la calculadora.
- Decidir qué especialista usa las tools (lo configura quien lleve el grafo).

## Criterios de finalización

- Todos los RF con test en verde (`pytest`), sin API.
- Demo manual: «Según la imagen, ¿cuánto cuestan 3 billetes sencillos y 2 abonos?» → la traza muestra `describir_imagen` y luego `calculadora`, y el total es correcto.

## Dudas abiertas

- [NECESITA ACLARACIÓN: ¿Qué imagen demo se usa (cartel de tarifas CRTM, plano o panel)? Debe tener importes legibles para la demo de cálculo.]
- [NECESITA ACLARACIÓN: ¿Qué especialista llama a las tools? Se asume la configuración `TOOLS_POR_ESPECIALISTA` descrita en el plan; el especialista que haga el flujo combinado lo decide quien lleve el grafo.]

## Cambios posteriores

- **2026-10-19. Superados por la spec 005:** RF-21 a RF-23 describían un único especialista que leía la imagen y calculaba. Al integrarse el grafo, `tarifas` solo lee los importes (RF-15 de la spec 005) y `auxiliar` hace la cuenta (RF-43 y RF-46). Los demás requisitos (RF-1 a RF-20, las dos tools y la allowlist) siguen vigentes.
- **2026-10-19. Spec 007:** `tarifas` solo se activa con una imagen aportada válida; hoy ningún cliente puede aportarla (ver `validacion.md`).
