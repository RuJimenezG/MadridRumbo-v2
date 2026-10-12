
"""Configura GEMINI_API_KEY antes de llamar a la API."""

import getpass
import os
from dotenv import load_dotenv

_configured = False


def configurar_gemini_api_key() -> None:
    """Carga la API key una sola vez por ejecución."""
    # Indicamos que queremos modificar la variable global _configured definida fuera de la función.
    global _configured
    # Si la configuración ya se realizó anteriormente, salimos inmediatamente de la función.
    if _configured:
        return
    # Busca un archivo .env y carga sus variables de entorno. Después de ejecutar load_dotenv() podremos acceder a ella mediante os.getenv("GEMINI_API_KEY").
    load_dotenv()
    # Comprobamos si GEMINI_API_KEY existe ya como variable de entorno. Si no existe, pedimos la clave manualmente al usuario.
    if not os.getenv("GEMINI_API_KEY"):

        # getpass.getpass() solicita la clave por consola sin mostrar los caracteres introducidos. Después guardamos temporalmente esa clave en la variable de entorno GEMINI_API_KEY del proceso actual.
        os.environ["GEMINI_API_KEY"] = getpass.getpass(
            "Pega aquí tu GEMINI_API_KEY (input oculto): "
        )
    # Mostramos únicamente si la clave ha quedado configurada, pero nunca imprimimos su valor real.
    print(
        "GEMINI_API_KEY configurada:",
        "sí" if os.getenv("GEMINI_API_KEY") else "no",
    )
    # Marcamos la configuración como completada.
    _configured = True
    
def configurar_openai_api_key() -> None:
    """Carga la API key una sola vez por ejecución."""
    # Indicamos que queremos modificar la variable global _configured definida fuera de la función.
    global _configured
    # Si la configuración ya se realizó anteriormente, salimos inmediatamente de la función.
    if _configured:
        return
    # Busca un archivo .env y carga sus variables de entorno. Después de ejecutar load_dotenv() podremos acceder a ella mediante os.getenv("OPENAI_API_KEY").
    load_dotenv()
    # Comprobamos si OPENAI_API_KEY existe ya como variable de entorno. Si no existe, pedimos la clave manualmente al usuario.
    if not os.getenv("OPENAI_API_KEY"):

        # getpass.getpass() solicita la clave por consola sin mostrar los caracteres introducidos. Después guardamos temporalmente esa clave en la variable de entorno OPENAI_API_KEY del proceso actual.
        os.environ["OPENAI_API_KEY"] = getpass.getpass(
            "Pega aquí tu OPENAI_API_KEY (input oculto): "
        )
    # Mostramos únicamente si la clave ha quedado configurada, pero nunca imprimimos su valor real.
    print(
        "OPENAI_API_KEY configurada:",
        "sí" if os.getenv("OPENAI_API_KEY") else "no",
    )
    # Marcamos la configuración como completada.
    _configured = True