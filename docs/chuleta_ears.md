# Chuleta de EARS

**EARS** (*Easy Approach to Requirements Syntax*, Alistair Mavin, Rolls-Royce, 2009) es una forma de escribir requisitos en lenguaje natural con palabras clave en un orden fijo. Obliga a decir **cuándo** pasa algo y **qué** hace el sistema, de forma que se pueda comprobar.

| Patrón | Plantilla | Ejemplo en el RAG de la agenda cultural |
|---|---|---|
| Ubicuo | EL SISTEMA <hará> | EL SISTEMA mostrará las fuentes usadas debajo de cada respuesta. |
| Evento | CUANDO <disparador>, EL SISTEMA <hará> | CUANDO se ejecute `--ask` con una pregunta válida, EL SISTEMA mostrará la respuesta y sus fuentes. |
| No deseado | SI <condición>, ENTONCES EL SISTEMA <hará> | SI la pregunta está vacía, ENTONCES EL SISTEMA mostrará un error sin llamar al LLM. |
| Estado | MIENTRAS <estado>, EL SISTEMA <hará> | MIENTRAS el índice esté vacío, EL SISTEMA indicará que hay que ejecutar `--index`. |
| Opcional | DONDE <característica>, EL SISTEMA <hará> | DONDE haya un umbral de relevancia configurado, EL SISTEMA descartará los fragmentos que lo superen. |

## Cómo reconocer un requisito mal escrito

| ❌ Mal | Problema | ✅ Bien |
|---|---|---|
| "El sistema debe responder bien y rápido." | Dos ideas, ningún criterio medible | RF-1: CUANDO la pregunta sea válida, EL SISTEMA responderá usando solo el contexto recuperado. |
| "Gestionar las preguntas raras." | ¿Qué es "raro"? ¿Qué es "gestionar"? | RF-2: SI la pregunta supera 2000 caracteres, ENTONCES EL SISTEMA la rechazará con un mensaje de error. |
| "Usar un umbral de 0.45 en `logic.py`." | Es implementación, no comportamiento | RF-3: EL SISTEMA dispondrá de un umbral de relevancia configurable en un único punto. |

## Reglas rápidas
1. **Un RF, una frase, un comportamiento.** Si aparece un "y" que une dos cosas, son dos RF.
2. **Verificable:** si no se te ocurre cómo comprobarlo con un test o un comando, está mal escrito.
3. **Nada de adjetivos sin número:** "rápido" → "en menos de 2 s"; "corto" → "máximo 3 frases".
4. **Numera** (RF-1, RF-2…) para poder citarlos en el plan, en las tareas y en la validación.
5. **Lo que no sepas, márcalo:** `[NECESITA ACLARACIÓN: …]`. Un hueco visible es información; una suposición silenciosa es deuda.
