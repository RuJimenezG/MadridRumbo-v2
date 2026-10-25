"""Estado persistible y proyección pública del grafo multiagente."""
from src.estado import acumular_listas, crear_estado_inicial, crear_plan, proyectar_resultado
from tests.dobles_grafo import CheckpointerFalso, EjecutorFalso, LLMFalso


def test_estado_inicial_no_contiene_el_log_efimero_y_mantiene_colecciones_aisladas():
    """RF-15: el registro público no forma parte del estado persistible."""
    primero = crear_estado_inicial("Consulta uno")
    segundo = crear_estado_inicial()

    assert primero["mensaje"] == "Consulta uno"
    assert primero["historial"] == []
    assert primero["traza"] == []
    assert primero["planes_pendientes"] == []
    assert primero["hitl_pendiente"] is False
    assert primero["done"] is False
    assert "log" not in primero
    assert "log" not in segundo


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


def test_proyeccion_publica_tiene_seis_claves_log_efimero_y_traza_normalizada():
    """RF-1, RF-2 y RF-26: el log se recibe fuera del estado y traza no cambia."""
    estado = crear_estado_inicial()
    estado.update(
        {
            "respuesta": "Información disponible.",
            # Ninguna entrada estructurada persistida puede reaparecer en la proyección pública.
            "log": [{
                "paso": 1,
                "tipo": "nodo",
                "nodo": "heredado",
                "entrada": None,
                "salida": None,
                "resultado": "completado",
                "detalle": None,
            }],
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

    registro = [
        {
            "paso": 1,
            "tipo": "nodo",
            "nodo": "entrada",
            "entrada": {"mensaje": "Consulta"},
            "salida": {"mensaje": "Consulta"},
            "resultado": "completado",
            "detalle": None,
        }
    ]

    resultado = proyectar_resultado(estado, registro=registro)

    assert set(resultado) == {"respuesta", "plan", "log", "traza", "hitl_pendiente", "done"}
    assert resultado["plan"] == []
    assert resultado["log"] == registro
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
    registro[0]["nodo"] = "modificado_fuera"
    assert resultado["log"][0]["nodo"] == "entrada"


def test_proyeccion_usa_lista_vacia_si_no_recibe_registro_efimero():
    """RF-2 y RF-15: un checkpoint no aporta historial de depuración."""
    estado = crear_estado_inicial()
    estado["log"] = [{
        "paso": 1,
        "tipo": "nodo",
        "nodo": "heredado",
        "entrada": None,
        "salida": None,
        "resultado": "completado",
        "detalle": None,
    }]

    resultado = proyectar_resultado(estado)

    assert resultado["log"] == []
    assert estado["log"][0]["nodo"] == "heredado"


def test_el_checkpoint_de_un_estado_inicial_no_contiene_log():
    """RF-15: al persistir estado de conversación no se guarda el registro efímero."""
    checkpointer = CheckpointerFalso()
    checkpointer.guardar("hilo-1", crear_estado_inicial("Consulta"))

    assert "log" not in checkpointer.recuperar("hilo-1")


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
