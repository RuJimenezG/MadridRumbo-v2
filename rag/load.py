"""Carga de documentos desde data/.

Convierte los archivos del corpus en objetos Document de LangChain.

Formatos soportados:
- .txt y .md → se cargan como documentos de texto.
- .pdf → se carga mediante PyPDFLoader.
- Paradas CRTM.csv → se agrupa por tipo de transporte y zona tarifaria, generando Documents con bloques de hasta 6 paradas.
Se omiten:
- Archivos .json.
- README.md.
"""

from pathlib import Path

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

from config import (
    CSV_PARADAS,
    DATA_DIR,
    EXTENSIONES_CSV,
    EXTENSIONES_PDF,
    EXTENSIONES_TEXTO,
    MAX_FILAS_CSV,
)


def valor_celda(fila, columna: str) -> str | None:
    """Obtiene el valor de una columna de una fila del DataFrame.

    Esta función sirve para acceder de forma segura a los valores del CSV.

    Devuelve:
    - El contenido de la celda convertido a texto y sin espacios
      al principio o al final.
    - None si la columna no existe.
    - None si la celda está vacía o contiene NaN.
    """

    # Comprobamos primero que la columna exista y que su valor no sea NaN.
    if columna not in fila or pd.isna(fila[columna]):
        return None

    # Convertimos el valor a string. Esto permite tratar de la misma forma IDs, números, nombres, etc.
    texto = str(fila[columna]).strip()

    # Si después de eliminar espacios queda una cadena vacía, la consideramos como un valor inexistente.
    return texto if texto else None


def fila_parada_a_texto(fila) -> str | None:
    """Convierte una fila de Paradas CRTM.csv en texto legible.

    Cada fila del CSV representa una parada, estación o punto de transporte.

    El objetivo es transformar los campos estructurados del CSV en un texto
    comprensible que posteriormente pueda ser procesado, fragmentado,
    convertido en embeddings y utilizado por el sistema RAG.

    Devuelve None si la fila no contiene los datos mínimos necesarios
    para identificar una parada.
    """

    # stop_id es el identificador interno de la parada dentro de los datos CRTM.
    stop_id = valor_celda(fila, "stop_id")

    # stop_name contiene el nombre legible de la parada.
    nombre = valor_celda(fila, "stop_name")
    
    # Descripción de la parada (suele contener la dirección)
    descripcion = valor_celda(fila, "stop_desc")

    # Consideramos que una fila sin ID o sin nombre no representa una parada suficientemente identificable para el RAG.
    if stop_id is None or nombre is None:
        return None

    # Se construye el texto a devolver
    texto = f"- ID: {stop_id} | Nombre: {nombre}"
    if descripcion is not None:
        texto += f" | Descripción: {descripcion}"
    
    return texto


def cargar_paradas_csv_agrupadas(ruta: Path) -> list[Document]:
    """Carga Paradas CRTM.csv agrupando por tipo y zona en bloques de hasta 6 paradas."""
    
    df = pd.read_csv(
        ruta,
        sep=";",
        encoding="utf-8",
        dtype=str,
    )

    df = df[
    [
        "stop_id",
        "stop_name",
        "stop_desc",
        "zone_id",
        "type",
    ]
    ].copy()
    
    if MAX_FILAS_CSV is not None:
        df = df.head(MAX_FILAS_CSV)

    documentos: list[Document] = []

    # Normalizamos la zona
    df["zona_normalizada"] = (
        df["zone_id"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"^Zona\s+", "", regex=True)
        .replace({"": "SIN_ZONA", "nan": "SIN_ZONA"})
    )
    # Normalizamos el tipo de transporte
    df["tipo_normalizado"] = (
        df["type"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace({"": "SIN_TIPO", "nan": "SIN_TIPO"})
    )

    for (tipo_transporte, zona), grupo in df.groupby(
    ["tipo_normalizado", "zona_normalizada"],
    sort=True,
    ):

        paradas = []

        for _, fila in grupo.iterrows():
            texto = fila_parada_a_texto(fila)

            if texto is not None:
                paradas.append(texto)

        if not paradas:
            continue

        TAM_BLOQUE = 6

        for inicio in range(0, len(paradas), TAM_BLOQUE):
            bloque = paradas[inicio:inicio + TAM_BLOQUE]
            contenido = (
                f"Tipo de transporte: {tipo_transporte}\n"
                f"Zona tarifaria: {zona}\n\n"
                + "\n".join(bloque)
            )
            documentos.append(
                Document(
                    page_content=contenido,
                    metadata={
                        "source": str(ruta),
                        "tipo": "paradas_crtm_bloque",
                        "tipo_transporte": tipo_transporte,
                        "zona": zona,
                        "num_paradas": len(bloque),
                        "bloque": (inicio // TAM_BLOQUE) + 1,
                    },
                )
            )
    
    return documentos

def cargar_archivo(ruta: Path) -> list[Document]:
    """Selecciona el loader adecuado según el tipo de archivo."""

    # Obtenemos la extensión en minúsculas. Por ejemplo:
    #   documento.PDF → ".pdf"
    #   datos.CSV     → ".csv"
    sufijo = ruta.suffix.lower()

    # Los PDF se cargan mediante PyPDFLoader.Normalmente se genera un Document por página.
    if sufijo in EXTENSIONES_PDF:
        return PyPDFLoader(str(ruta)).load()

    # Los archivos de texto (.txt, .md, etc.) se cargan completos mediante TextLoader.
    if sufijo in EXTENSIONES_TEXTO:
        return TextLoader(
            str(ruta),
            encoding="utf-8",
        ).load()

    # El CSV de paradas necesita un tratamiento específico.
    # Las paradas se agrupan por tipo de transporte y zona tarifaria, y se generan Documents con bloques de hasta 6 paradas. De este modo reducimos el número de Documents y futuros embeddings sin perder ninguna parada del corpus.    
    if sufijo in EXTENSIONES_CSV and ruta.name == CSV_PARADAS:
        return cargar_paradas_csv_agrupadas(ruta)

    # Si el archivo no pertenece a ninguno de los formatos soportados, devolvemos una lista vacía.
    return []


def cargar_documentos() -> list[Document]:
    """Recorre data/ y carga todos los documentos soportados del corpus."""

    # Antes de hacer nada comprobamos que exista la carpeta data/.
    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de datos: {DATA_DIR}"
        )

    # Construimos la ruta en la que esperamos encontrar Paradas CRTM.csv.
    csv_path = DATA_DIR / CSV_PARADAS

    # El CSV de paradas forma parte obligatoria del corpus.
    # Si no existe, detenemos la ejecución mostrando un error claro.
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Falta {CSV_PARADAS} en data/. "
            "Comprueba que el corpus está en la carpeta data/."
        )

    # Lista en la que acumularemos los Document procedentes  de todos los archivos del corpus.
    documentos: list[Document] = []

    # rglob("*") recorre de forma recursiva DATA_DIR.
    # Esto significa que también encontrará archivos almacenados dentro de subdirectorios de data/.
    # sorted() hace que el orden de procesamiento sea reproducible.
    for ruta in sorted(DATA_DIR.rglob("*")):
        # Ignoramos directorios y nos quedamos únicamente con archivos.
        if not ruta.is_file():
            continue
        # Los JSON no forman parte del corpus que queremos cargar.
        if ruta.suffix.lower() == ".json":
            continue
        # README.md contiene documentación del proyecto, no información que deba formar parte del RAG.
        if ruta.name == "README.md":
            continue

        # Delegamos en cargar_archivo() la elección del loader.
        docs = cargar_archivo(ruta)

        # Si se han generado Document, los añadimos al corpus.
        if docs:
            print(
                f"  Cargado: {ruta.name} "
                f"({len(docs)} documento(s))"
            )
            documentos.extend(docs)
        # Si el archivo tiene extensión pero no existe un loader adecuado para él, mostramos un mensaje informativo.
        elif ruta.suffix:
            print(
                f"  [omitido] archivo no soportado: {ruta.name}"
            )

    # La función devuelve una única lista con todos los Document:
    # PDF + texto + paradas CRTM.
    return documentos