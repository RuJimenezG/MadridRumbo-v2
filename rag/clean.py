"""Limpieza de texto antes del chunking"""

# Módulo estándar de Python para trabajar con expresiones regulares para detectar y sustituir determinados patrones de espacios, tabulaciones y saltos de línea.
import re
# Clase Document de langchain
from langchain_core.documents import Document


def normalizar_texto(texto: str) -> str:
    """Deja el texto listo para fragmentar: menos ruido, mismas frases."""

    # Si el texto está vacío, es None o cualquier otro valor considerado falso por Python, devolvemos directamente una cadena vacía. Así evitamos realizar operaciones posteriores sobre contenido inexistente.
    if not texto:
        return ""

    # Normaliza los saltos de línea. Dependiendo del sistema operativo o del origen del documento, un salto de línea puede aparecer como:
    # - "\r\n" → habitual en Windows (retorno de carro y salto de línea).
    # - "\r"   → formatos antiguos.
    # - "\n"   → habitual en Linux/Unix.
    # Aquí todos se convierten al mismo formato: "\n".
    t = texto.replace("\r\n", "\n").replace("\r", "\n")
    # Sustituye grupos de 3 o más saltos de línea consecutivos por exactamente 2 saltos de línea. De esta forma se eliminan espacios verticales excesivos, pero se conserva la separación entre párrafos.
    t = re.sub(r"\n{3,}", "\n\n", t)
    # Sustituye uno o más espacios o tabulaciones consecutivos por un único espacio.
    # El patrón [ \t]+ significa: espacio en blanco o tabulación (\t) repetido una o más veces (+)
    t = re.sub(r"[ \t]+", " ", t)
    # Divide el texto por saltos de línea y elimina los espacios sobrantes al principio y al final de cada línea mediante strip(). Después vuelve a unir todas las líneas utilizando "\n".
    t = "\n".join(linea.strip() for linea in t.split("\n"))
    # Elimina cualquier espacio o salto de línea sobrante al principio y al final del documento completo.
    return t.strip()


def limpiar_documentos(documentos: list[Document]) -> list[Document]:
    """Aplica normalizar_texto a cada documento; omite los que quedan vacíos."""
    # Creamos una lista vacía en la que iremos almacenando los nuevos Document una vez que su contenido haya sido limpiado.
    limpios: list[Document] = []
    # Recorremos uno a uno todos los Document recibidos.
    for doc in documentos:
        # Extraemos el texto del Document mediante page_content y se lo pasamos a normalizar_texto().
        contenido = normalizar_texto(doc.page_content)

        # Si después de la limpieza el documento se ha quedado vacío, no lo añadimos a la lista final. Esto evita que documentos sin contenido continúen hacia las siguientes fases del pipeline.
        if not contenido:
            continue

        # Creamos un nuevo objeto Document con:
        # - page_content: el texto ya normalizado.
        # - metadata: una copia de los metadatos del documento original.
        # dict(doc.metadata) crea un nuevo diccionario con los mismos datos, evitando reutilizar directamente el objeto metadata del Document original.
        limpios.append(
            Document(page_content=contenido, metadata=dict(doc.metadata))
        )

    # Devolvemos la lista con todos los documentos que han sobrevivido al proceso de limpieza.
    return limpios