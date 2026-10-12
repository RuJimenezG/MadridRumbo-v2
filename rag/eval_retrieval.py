"""
eval_retrieval.py — Evaluación ligera de retrieval con ≥2 valores de K.

Ejecuta las preguntas de queries/eval_preguntas.json contra el índice ya
construido (python main.py --index debe haberse ejecutado antes) y comprueba,
para cada valor de K, si la fuente esperada aparece entre los chunks
recuperados. Pensado para generar las cifras del informe de decisiones
(sección "Retrieval: observación con 2 valores de K").

Uso:
    python eval_retrieval.py                  # usa K=(1,3) por defecto
    python eval_retrieval.py --k 1 3 5         # cualquier lista de valores de K

Requiere que el índice ya esté construido con el proveedor de embeddings que
quieras evaluar (revisa EMBEDDING_PROVIDER en tu .env antes de indexar).
"""
import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import QUERIES_DIR
from src.retrieve import retrieve


def load_eval_questions() -> list[dict]:
    path = QUERIES_DIR / "eval_preguntas.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evaluate(k_values: list[int]) -> dict:
    preguntas = load_eval_questions()
    resultados = {k: [] for k in k_values}

    for k in k_values:
        print(f"\n===== K={k} =====")
        for q in preguntas:
            chunks = retrieve(q["pregunta"], k=k)
            fuentes = [c.source for c in chunks]
            esperada = q.get("fuente_esperada")

            if esperada is None:
                # pregunta fuera de corpus: no hay "acierto" de fuente que evaluar aquí;
                # la abstención se valora en la capa de generación (--ask), no en retrieval.
                match = None
            else:
                match = esperada in fuentes

            resultados[k].append({
                "id": q["id"], "tipo": q["tipo"], "match": match, "fuentes_recuperadas": fuentes,
            })
            estado = "—" if match is None else ("✔" if match else "✘")
            print(f"{estado}  {q['id']:5} [{q['tipo']:14}] {q['pregunta'][:60]}")

    return resultados


def summarize(resultados: dict):
    print("\n===== RESUMEN =====")
    for k, filas in resultados.items():
        in_corpus = [f for f in filas if f["match"] is not None]
        aciertos = sum(1 for f in in_corpus if f["match"])
        print(f"K={k}: {aciertos}/{len(in_corpus)} preguntas in-corpus con la fuente esperada recuperada")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evalúa retrieval con distintos valores de K")
    parser.add_argument("--k", type=int, nargs="+", default=[1, 3], help="Valores de K a comparar (ej: --k 1 3 5)")
    args = parser.parse_args()

    resultados = evaluate(args.k)
    summarize(resultados)

    out_path = QUERIES_DIR / "eval_retrieval_resultados.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print(f"\nResultados detallados guardados en {out_path}")
