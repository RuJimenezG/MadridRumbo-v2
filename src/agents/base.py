"""Mini-bucle común de los especialistas: el LLM propone, el código decide qué se ejecuta.

El LLM devuelve {"tool", "args"} para pedir una tool o {"final"} para dar la nota.
Aquí se aplican la lista de tools del especialista y el tope de pasos (ambos en Python).
Un especialista nunca decide `done`; eso corresponde al grafo y al humano (HITL).
"""
import config


def ejecutar_especialista(nombre: str, prompt: str, estado: dict, llm, ejecutar) -> dict:
    """Ejecuta el especialista `nombre` y devuelve `{"notas": [...], "traza": [...]}`.

    `llm(mensajes)` devuelve {"tool", "args"} o {"final"}; `ejecutar(nombre, args, traza)`
    es la ejecución controlada de tools (normalmente `src.tools.ejecutar_tool`).
    Las tools permitidas salen de `config.TOOLS_POR_ESPECIALISTA[nombre]`.
    """
    notas = list(estado.get("notas", []))
    traza = list(estado.get("traza", []))
    permitidas = config.TOOLS_POR_ESPECIALISTA[nombre]
    mensajes = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": estado["mensaje"]},
    ]
    obtenido = []  # resultados de tools, por si se alcanza el límite de pasos

    def terminar(texto: str) -> dict:
        return {"notas": notas + [f"[{nombre}] {texto}"], "traza": traza}

    for _ in range(config.MAX_STEPS_ESPECIALISTA):
        try:
            resp = llm(mensajes)
        except Exception as exc:  # un fallo del LLM no debe tumbar el grafo
            return terminar(f"ERROR: el modelo no respondió ({exc}).")

        if not isinstance(resp, dict):
            return terminar("ERROR: respuesta del modelo no interpretable.")
        if isinstance(resp.get("final"), str):
            return terminar(resp["final"])
        tool = resp.get("tool")
        if not isinstance(tool, str):
            return terminar("ERROR: respuesta del modelo no interpretable.")

        args = resp.get("args") if isinstance(resp.get("args"), dict) else {}
        if tool not in permitidas:
            # Fuera de la lista del especialista: no se ejecuta, solo se registra.
            aviso = f"ERROR: tool no permitida: {tool}"
            traza.append({"tool": tool, "args": args, "status": "bloqueada", "preview": aviso})
            mensajes.append({"role": "tool", "content": aviso})
            continue

        resultado = ejecutar(tool, args, traza)
        obtenido.append(f"{tool}: {resultado}")
        mensajes.append({"role": "tool", "content": f"{tool}: {resultado}"})

    detalle = " | ".join(obtenido) if obtenido else "sin datos"
    return terminar(f"Se alcanzó el límite de pasos. Datos obtenidos: {detalle}")
