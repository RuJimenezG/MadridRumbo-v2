"""
eval_generacion.py — Evaluación de la capa de generación con las preguntas
de queries/eval_preguntas.json.

Para cada pregunta, llama a responder() y comprueba:
  - si es "in-corpus": ¿ha respondido con contenido (no se ha abstenido)?
  - si es "fuera-de-corpus": ¿se ha abstenido correctamente?

Requiere que el índice ya esté construido con datos reales (python main.py --index).

Guarda el progreso pregunta a pregunta en queries/eval_generacion_resultados.json.
Si se corta a mitad (cuota agotada, error de red...), al volver a ejecutar
retoma solo las preguntas que faltan, sin repetir las ya hechas.

Uso:
    python eval_generacion.py
"""
import json
import time

from config import QUERIES_DIR
from src.responder import responder
from google.genai.errors import APIError

FRASE_ABSTENCION = "no lo sé, no está en los documentos"

# El tier gratuito de gemini-3.6-flash limita a 5 peticiones/minuto para
# generate_content. Usamos 4 (con margen) y esperamos ese tiempo entre
# preguntas; si aun así se agota la cuota o el servidor está saturado,
# se espera 60s y se reintenta.
GENERATION_RPM_LIMIT = 4

RUTA_RESULTADOS = QUERIES_DIR / "eval_generacion_resultados.json"


def cargar_preguntas() -> list[dict]:
    path = QUERIES_DIR / "eval_preguntas.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def se_abstuvo(respuesta: str) -> bool:
    return FRASE_ABSTENCION in respuesta.lower()


def _responder_con_reintento(pregunta, intentos=3):
    for intento in range(intentos):
        try:
            return responder(pregunta)
        except APIError as e:
            if getattr(e, "code", None) in (429, 503) and intento < intentos - 1:
                print("   (límite de cuota o servidor saturado, esperando 60s...)")
                time.sleep(60)
            else:
                raise


def _guardar(resultados: list[dict]) -> None:
    with open(RUTA_RESULTADOS, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)


def evaluar() -> list[dict]:
    preguntas = cargar_preguntas()

    # Si ya hay resultados de una ejecución anterior, los recuperamos y
    # solo evaluamos las preguntas que faltan.
    if RUTA_RESULTADOS.exists():
        with open(RUTA_RESULTADOS, encoding="utf-8") as f:
            resultados = json.load(f)
    else:
        resultados = []

    ids_hechos = {r["id"] for r in resultados}
    pendientes = [q for q in preguntas if q["id"] not in ids_hechos]

    if not pendientes:
        print("Todas las preguntas ya estaban evaluadas (nada pendiente).")
        return resultados

    print(f"Pendientes: {len(pendientes)} de {len(preguntas)} preguntas.")

    for i, q in enumerate(pendientes):
        r = _responder_con_reintento(q["pregunta"])
        abstuvo = se_abstuvo(r["respuesta"])

        if q["tipo"] == "fuera-de-corpus":
            correcto = abstuvo  
        else:
            correcto = not abstuvo  

        resultados.append({
            "id": q["id"],
            "tipo": q["tipo"],
            "pregunta": q["pregunta"],
            "respuesta": r["respuesta"],
            "fuentes": r["fuentes"],
            "se_abstuvo": abstuvo,
            "correcto": correcto,
        })

        estado = "✔" if correcto else "✘"
        print(f"{estado}  {q['id']:5} [{q['tipo']:15}] {q['pregunta']}")

        # Guardamos después de CADA pregunta: si se corta a mitad, no se
        # pierde el trabajo (ni la cuota gastada) de las que sí funcionaron.
        _guardar(resultados)

        if i < len(pendientes) - 1:
            time.sleep(60 / GENERATION_RPM_LIMIT)

    return resultados


def resumen(resultados: list[dict]):
    total = len(resultados)
    aciertos = sum(1 for r in resultados if r["correcto"])
    print(f"\n===== RESUMEN =====")
    print(f"{aciertos}/{total} preguntas correctas (abstención/respuesta según correspondía)")


if __name__ == "__main__":
    resultados = evaluar()
    resumen(resultados)
    print(f"\nResultados guardados en {RUTA_RESULTADOS}")