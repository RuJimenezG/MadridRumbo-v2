# Cómo testear un RAG sin llamar a ninguna API

La constitución exige tests **sin API**: gratis, rápidos y siempre con el mismo resultado. La técnica es sustituir, solo durante el test, las funciones que llaman a servicios externos por **dobles de prueba**: funciones falsas que devuelven datos fijos y, si hace falta, cuentan cuántas veces se las llama.

## La idea en un ejemplo

Supongamos que `src/logic.py` hace esto:

```python
from .retriever import recuperar          # llama a embeddings + ChromaDB
from .generate import generar_respuesta   # llama al LLM

def responder(pregunta, top_k=None):
    chunks = recuperar(pregunta, top_k=top_k)
    ...
    return {"respuesta": generar_respuesta(prompt), ...}
```

El test sustituye `recuperar` y `generar_respuesta` **en el módulo que las usa** (`src.logic`), no en el que las define:

```python
import pytest
import src.logic as logic


@pytest.fixture
def rag_falso(monkeypatch):
    estado = {"chunks": [], "llm": 0}

    def recuperar_falso(pregunta, top_k=None):
        return estado["chunks"]

    def generar_falso(prompt):
        estado["llm"] += 1
        return "Respuesta generada"

    monkeypatch.setattr(logic, "recuperar", recuperar_falso)
    monkeypatch.setattr(logic, "generar_respuesta", generar_falso)
    return estado


def test_pregunta_vacia_no_llama_al_llm(rag_falso):
    resultado = logic.responder("   ")
    assert resultado["error"]
    assert rag_falso["llm"] == 0


def test_respuesta_normal_usa_el_llm_una_vez(rag_falso):
    rag_falso["chunks"] = [
        {"id": "c1", "text": "Texto del corpus", "metadata": {"source": "data/faq.md"}, "distance": 0.2},
    ]
    resultado = logic.responder("¿Pregunta del dominio?")
    assert rag_falso["llm"] == 1
    assert "faq.md" in resultado["fuentes"]
```

## Reglas prácticas
- **Parchea donde se usa:** `monkeypatch.setattr(logic, "recuperar", …)`. Si parcheas `src.retriever.recuperar`, `logic` seguirá usando la original, porque la importó con `from … import`.
- **Datos pequeños y a mano:** dos o tres fragmentos con la distancia y el `source` que necesites.
- **Cuenta llamadas** cuando el requisito diga "sin llamar al LLM".
- **Funciones puras siempre que puedas:** si la lógica nueva no llama a nada externo (filtrar, formatear, decidir), va en una función aparte y se testea sin dobles.
- **La salida de la CLI** se comprueba con `capsys`: `capsys.readouterr().out`.
- **Streamlit** no se testea aquí: esa parte se valida a mano y se dice así en `validacion.md`.

## Configuración
`pytest.ini` en la raíz, con `pythonpath = .` para que los tests puedan hacer `import config` e `import src.…`. Instala pytest en el entorno virtual con `pip install pytest`.
