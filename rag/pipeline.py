"""Orquestación del pipeline de ingesta.

Flujo: load → clean → chunk → guardar chunks.json
"""

# Módulo estándar para convertir estructuras de Python a JSON.
import json

# Counter permite contar fácilmente cuántas veces aparece cada elemento. Aquí se usa para contar documentos y chunks agrupados por fuente.
from collections import Counter

# Path permite trabajar con rutas y nombres de archivos de forma portable.
from pathlib import Path

# Clase Document de LangChain.Cada Document contiene principalmente:
# - page_content: el texto del documento.
# - metadata: información adicional sobre ese documento.
from langchain_core.documents import Document

# Importamos la configuración general del proyecto:
# - CHUNK_OVERLAP: solapamiento entre chunks consecutivos.
# - CHUNK_SIZE: tamaño máximo configurado para los chunks.
# - CHUNKS_JSON: ruta donde se guardará el resultado de la ingesta.
# - DATA_DIR: directorio donde están los documentos originales.
from config import CHUNK_SIZE, CHUNK_OVERLAP, CHUNKS_JSON, DATA_DIR

# Función encargada de cargar los documentos originales desde DATA_DIR.
from .load import cargar_documentos

# Función encargada de limpiar y normalizar los documentos cargados.
from .clean import limpiar_documentos

# Función encargada de dividir los documentos limpios en chunks.
from .chunk import fragmentar_documentos



# Convierte la fuente a Path y devuelve únicamente el nombre final del archivo, eliminando el resto de la ruta.
# Ejemplo: "/data/Paradas CRTM.csv" -> "Paradas CRTM.csv"
def _nombre_fuente(metadata: dict) -> str:
    # Obtiene del metadata la ruta/origen del documento.
    # Si no existe la clave "source", utiliza "desconocido".
    source = metadata.get("source", "desconocido")

    return Path(str(source)).name

# Construye y devuelve un diccionario con estadísticas sobre las distintas fases del proceso de ingesta.
def calcular_stats_ingesta(
    crudos: list[Document],
    limpios: list[Document],
    chunks: list[Document],
) -> dict:

    return {
        # Número de documentos obtenidos inicialmente durante la carga.
        "documentos_cargados": len(crudos),

        # Número de documentos que permanecen después de la limpieza.
        "documentos_tras_limpieza": len(limpios),

        # Número total de chunks generados tras la fragmentación.
        "chunks_generados": len(chunks),

        # Cuenta cuántos documentos originales proceden de cada fuente.
        #
        # Para cada documento:
        # 1. Obtiene su metadata.
        # 2. Extrae el nombre de la fuente con _nombre_fuente().
        # 3. Counter cuenta cuántas veces aparece cada fuente.
        # 4. dict() convierte el Counter en un diccionario normal.
        "documentos_por_fuente": dict(
            Counter(_nombre_fuente(d.metadata) for d in crudos)
        ),

        # Hace el mismo conteo, pero sobre los chunks generados.
        # Permite saber cuántos chunks ha producido cada fuente.
        "chunks_por_fuente": dict(
            Counter(_nombre_fuente(c.metadata) for c in chunks)
        ),
    }

# Convierte una lista de objetos Document de LangChain en una lista de diccionarios normales.
# Esto es necesario porque los objetos Document no se pueden serializar directamente a JSON de forma sencilla.
def documentos_a_dicts(documentos: list[Document]) -> list[dict]:

    return [
        {
            # Guarda el contenido textual del documento.
            "text": doc.page_content,

            # Copia los metadatos del documento como un diccionario normal.
            "metadata": dict(doc.metadata)
        }
        for doc in documentos
    ]

# Crea el directorio padre donde se guardará el JSON si todavía no existe y guarda el json.
def guardar_chunks_json(chunks: list[Document], ruta: Path, stats: dict) -> Path:
    # parents=True:
    # crea también directorios intermedios si fueran necesarios.
    # exist_ok=True:
    # evita error si el directorio ya existe.
    ruta.parent.mkdir(parents=True, exist_ok=True)

    # Construye la estructura completa que se guardará en el archivo JSON.
    payload = {
        # Guarda también la configuración utilizada para generar los chunks.
        # Esto permite saber posteriormente con qué parámetros se creó el fichero.
        "chunk_size_config": {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
        },

        # Número total de chunks incluidos en el archivo.
        "total_chunks": len(chunks),

        # Estadísticas calculadas sobre el proceso de ingesta.
        "ingesta_stats": stats,

        # Convierte los Document de LangChain en diccionarios
        # serializables a JSON.
        "chunks": documentos_a_dicts(chunks),
    }

    # Convierte el payload a texto JSON y lo escribe en la ruta indicada.
    ruta.write_text(
        json.dumps(
            payload,

            # Evita convertir caracteres como ñ o tildes en secuencias Unicode del tipo \u00f1.
            ensure_ascii=False,

            # Formatea el JSON con sangría para que sea legible.
            indent=2
        ),

        # Guarda el archivo utilizando codificación UTF-8.
        encoding="utf-8",
    )

    # Devuelve la ruta del archivo creado.
    return ruta


def _mostrar_chunk_ejemplo(titulo: str, chunk: Document) -> None:
    # Imprime un encabezado para identificar el tipo de muestra.
    print(f"\n--- {titulo} ---")

    # Muestra únicamente los primeros 350 caracteres del chunk.
    print(chunk.page_content[:350].strip(), "...")

    # Muestra los metadatos asociados al chunk.
    print("Metadata:", chunk.metadata)


def imprimir_resumen_consola(chunks: list[Document], stats: dict) -> None:
    # Imprime un resumen general del proceso de ingesta.
    print("\n--- Resumen ingesta ---")

    # Muestra cuántos documentos fueron cargados originalmente.
    print(f"  Documentos cargados:      {stats['documentos_cargados']}")

    # Muestra cuántos documentos permanecieron después de la limpieza.
    print(f"  Tras limpieza:            {stats['documentos_tras_limpieza']}")

    # Muestra el número total de chunks generados.
    print(f"  Chunks generados:         {stats['chunks_generados']}")

    # Encabezado para mostrar los chunks agrupados por fuente.
    print("  Chunks por fuente:")

    # Recorre las fuentes ordenadas alfabéticamente.
    # stats["chunks_por_fuente"] tiene una estructura similar a:
    # {
    #     "archivo1.csv": 120,
    #     "archivo2.pdf": 45,
    # }
    # .items() devuelve pares (fuente, cantidad).
    # sorted() los ordena por el nombre de la fuente.
    for fuente, n in sorted(stats["chunks_por_fuente"].items()):
        # Muestra cuántos chunks ha producido cada fuente.
        print(f"    {fuente}: {n}")

    # Si no se ha generado ningún chunk, termina aquí. Esto evita intentar acceder posteriormente a chunks[0].
    if not chunks:
        return

    # Muestra como ejemplo el primer chunk generado.
    _mostrar_chunk_ejemplo("Muestra: primer chunk", chunks[0])

    # Busca el primer chunk cuyo metadata indique que es una parada del CRTM procedente del CSV.
    for chunk in chunks:
        if chunk.metadata.get("tipo") == "parada_crtm":
            # Cuando lo encuentra, muestra su contenido y metadata.
            _mostrar_chunk_ejemplo("Muestra: parada CRTM", chunk)

            # Solo se quiere mostrar un ejemplo,
            # así que se detiene el bucle tras encontrar el primero.
            break


def ejecutar_ingesta() -> tuple[list[Document], Path, dict]:
    # Informa del inicio de la ingesta y del directorio desde el que se cargarán los datos.
    print(f"Ingesta: cargando documentos desde {DATA_DIR} ...")

    # FASE 1: LOAD
    # Carga los documentos originales desde las fuentes configuradas.
    crudos = cargar_documentos()

    # Muestra cuántos documentos se han cargado.
    print(f"  Documentos cargados: {len(crudos)}")

    # FASE 2: CLEAN
    # Limpia y normaliza los documentos cargados.
    limpios = limpiar_documentos(crudos)

    # Muestra cuántos documentos quedan después de la limpieza.
    print(f"  Tras limpieza: {len(limpios)}")

    # FASE 3: CHUNK
    # Divide los documentos limpios en fragmentos más pequeños que posteriormente podrán utilizarse en el sistema RAG.
    chunks = fragmentar_documentos(limpios)

    # Muestra cuántos chunks se han generado.
    print(f"  Chunks generados: {len(chunks)}")

    # Calcula estadísticas globales sobre las tres fases: documentos originales, documentos limpios y chunks.
    stats = calcular_stats_ingesta(crudos, limpios, chunks)

    # FASE 4: GUARDADO
    # Guarda los chunks, su metadata, la configuración de chunking y las estadísticas en el archivo JSON configurado.
    ruta = guardar_chunks_json(chunks, CHUNKS_JSON, stats)

    # Informa de la ubicación final del archivo generado.
    print(f"  Guardado: {ruta}")

    # Imprime en consola un resumen de la ingesta y algunos chunks de ejemplo para comprobar el resultado.
    imprimir_resumen_consola(chunks, stats)

    # Devuelve:
    # 1. La lista de chunks generados.
    # 2. La ruta del archivo JSON creado.
    # 3. Las estadísticas de la ingesta.
    return chunks, ruta, stats