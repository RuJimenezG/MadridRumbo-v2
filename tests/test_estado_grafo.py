"""Estado y dobles del grafo multiagente (spec 005, T2)."""
from src.estado import acumular_listas, crear_estado_inicial, crear_plan, proyectar_resultado
from tests.dobles_grafo import CheckpointerFalso, EjecutorFalso, LLMFalso


def test_estado_inicial_tiene_colecciones_independientes_y_valores_seguros():
    """RF-25 y RF-35: el estado inicial no comparte auditoría entre conversaciones."""
    primero = crear_estado_inicial("Consulta uno")
    segundo = crear_estado_inicial()

    assert primero["mensaje"] == "Consulta uno"
    assert primero["historial"] == []
    assert primero["traza"] == []
    assert primero["planes_pendientes"] == []
    assert primero["hitl_pendiente"] is False
    assert primero["done"] is False

    primero["log"].append("evento")
    assert segundo["log"] == []


def test_reducer_de_auditoria_acumula_sin_mutar_las_entradas():
    """RF-35: los reducers conservan la auditoría al actualizar el estado."""
    anterior = [{"tool": "hora_actual"}]
    nuevo = [{"tool": "rag_ask"}]

    combinado = acumular_listas(anterior, nuevo)

    assert combinado == [{"tool": "hora_actual"}, {"tool": "rag_ask"}]
    assert anterior == [{"tool": "hora_actual"}]
    assert nuevo == [{"tool": "rag_ask"}]


def test_plan_identificado_conserva_id_y_oculta_argumentos_internos():
    """RF-47: la proyección permite seleccionar un plan sin exponer su control interno."""
    plan = crear_plan(
        "ruta-1",
        {"estado": "ok", "ruta": {"duracion": "12 min"}},
        {"origen": "Atocha", "destino": "Sol"},
    )
    estado = crear_estado_inicial()
    estado["planes_pendientes"] = [plan]

    resultado = proyectar_resultado(estado)

    assert resultado["plan"] == [
        {"id": "ruta-1", "resultado": {"estado": "ok", "ruta": {"duracion": "12 min"}}}
    ]
    assert plan["id"] == "ruta-1"
    assert plan["args"] == {"origen": "Atocha", "destino": "Sol"}


def test_proyeccion_publica_tiene_solo_las_seis_claves_y_traza_normalizada():
    """RF-25 a RF-27: la fachada podrá devolver una estructura pública uniforme."""
    estado = crear_estado_inicial()
    estado.update(
        {
            "respuesta": "Información disponible.",
            "log": ["nodo_rag completado"],
            "traza": [
                {
                    "tool": "rag_ask",
                    "args": {"consulta": "zonas"},
                    "status": "ok",
                    "preview": "Zona A",
                    "interno": "no público",
                }
            ],
            "hitl_pendiente": True,
            "done": False,
        }
    )

    resultado = proyectar_resultado(estado)

    assert set(resultado) == {"respuesta", "plan", "log", "traza", "hitl_pendiente", "done"}
    assert resultado["plan"] == []
    assert resultado["log"] == ["nodo_rag completado"]
    assert resultado["traza"] == [
        {
            "tool": "rag_ask",
            "args": {"consulta": "zonas"},
            "status": "ok",
            "preview": "Zona A",
        }
    ]
    assert isinstance(resultado["hitl_pendiente"], bool)
    assert isinstance(resultado["done"], bool)


def test_proyeccion_anade_diagnostico_canonico_sin_mutar_estado_ni_filtrar_texto():
    """RF-10 a RF-14: el diagnóstico se añade solo a la copia pública de log."""
    estado = crear_estado_inicial()
    estado["log"] = ["nodo_rag completado"]
    diagnostico = {
        "categoria": "proveedor",
        "resumen": "TOKEN_DE_PRUEBA_NO_EXPOSABLE",
    }

    resultado = proyectar_resultado(estado, diagnostico_supervisor=diagnostico)

    assert set(resultado) == {"respuesta", "plan", "log", "traza", "hitl_pendiente", "done"}
    assert resultado["log"] == [
        "nodo_rag completado",
        "Supervisor: categoria=proveedor; resumen=El proveedor no entregó una respuesta utilizable.",
    ]
    assert estado["log"] == ["nodo_rag completado"]
    assert "TOKEN_DE_PRUEBA_NO_EXPOSABLE" not in str(resultado)
    assert resultado["traza"] == []


def test_proyeccion_anade_indicador_de_correccion_semantica_seguro_y_separado():
    """RF-14 a RF-17: la corrección no es una categoría de fallback ni persiste."""
    estado = crear_estado_inicial()
    estado["log"] = ["nodo_rag completado"]
    diagnostico = {
        "categoria": "sin_fallback",
        "resumen": "RESPUESTA_CRUDA_TOKEN_DE_PRUEBA",
    }

    resultado = proyectar_resultado(
        estado,
        diagnostico_supervisor=diagnostico,
        correcciones_tarifas=2,
    )

    assert resultado["log"] == [
        "nodo_rag completado",
        "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada.",
        "Supervisor: correccion_semantica=aplicada; resumen=Se redirigieron 2 derivaciones incompatibles de tarifas a rag.",
    ]
    assert set(resultado) == {"respuesta", "plan", "log", "traza", "hitl_pendiente", "done"}
    assert estado["log"] == ["nodo_rag completado"]
    assert "RESPUESTA_CRUDA_TOKEN_DE_PRUEBA" not in str(resultado)


def test_proyeccion_ignora_contadores_de_correccion_no_seguros_o_nulos():
    """RF-16 y RF-17: solo un entero positivo alimenta el resumen canónico."""
    estado = crear_estado_inicial()
    diagnostico = {"categoria": "sin_fallback", "resumen": "texto no fiable"}

    for contador in (None, 0, -1, True, "2"):
        resultado = proyectar_resultado(
            estado,
            diagnostico_supervisor=diagnostico,
            correcciones_tarifas=contador,
        )
        assert resultado["log"] == [
            "Supervisor: categoria=sin_fallback; resumen=Decisión estructurada validada."
        ]


def test_dobles_comunes_registran_llamadas_y_aislan_snapshots():
    """Los dobles de T2 no necesitan red ni comparten estado mutable."""
    llm = LLMFalso([{"final": "respuesta fija"}])
    ejecutor = EjecutorFalso({"hora_actual": "10:00"})
    traza = []
    checkpointer = CheckpointerFalso()

    assert llm([{"role": "user", "content": "hola"}]) == {"final": "respuesta fija"}
    assert ejecutor("hora_actual", {}, traza) == "10:00"
    assert traza[0] == {
        "tool": "hora_actual",
        "args": {},
        "status": "ok",
        "preview": "10:00",
    }

    checkpointer.guardar("hilo-1", {"historial": ["mensaje"]})
    snapshot = checkpointer.recuperar("hilo-1")
    snapshot["historial"].append("modificado")
    assert checkpointer.recuperar("hilo-1") == {"historial": ["mensaje"]}
