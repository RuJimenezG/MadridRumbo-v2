"""Contrato puro de las entradas efímeras de depuración (spec 011, T1)."""

import pytest

import config

from src.agents.base import crear_ejecutor_transversal, sesion_depuracion_activa
from src.depuracion import SesionDepuracion, sanear_valor
from src.graph import invocar_grafo


def test_entrada_completada_tiene_el_esquema_publico_y_detalle_nulo():
    """RF-2, RF-3 y RF-10: una entrada correcta tiene siete campos estables."""
    sesion = SesionDepuracion()

    entrada = sesion.registrar(
        tipo="nodo",
        nodo="supervisor",
        entrada={"mensaje": "Consulta de prueba."},
        salida={"cola_roles": ["rag"]},
    )

    assert entrada == {
        "paso": 1,
        "tipo": "nodo",
        "nodo": "supervisor",
        "entrada": {"mensaje": "Consulta de prueba."},
        "salida": {"cola_roles": ["rag"]},
        "resultado": "completado",
        "detalle": None,
    }
    assert sesion.entradas == [entrada]


def test_pasos_son_consecutivos_y_aceptan_los_tipos_y_resultados_permitidos():
    """RF-2 y RF-4: la sesión ordena todos los tipos de paso permitidos."""
    sesion = SesionDepuracion()

    nodo = sesion.registrar("nodo", "entrada", {}, {})
    tool = sesion.registrar("tool", "hora_actual", {"zona": "Europe/Madrid"}, "10:00")
    control = sesion.registrar(
        "control",
        "fachada",
        None,
        None,
        resultado="rechazado",
        detalle={"categoria": "validacion"},
    )

    assert [entrada["paso"] for entrada in sesion.entradas] == [1, 2, 3]
    assert [entrada["tipo"] for entrada in sesion.entradas] == ["nodo", "tool", "control"]
    assert [nodo["resultado"], tool["resultado"], control["resultado"]] == [
        "completado",
        "completado",
        "rechazado",
    ]


@pytest.mark.parametrize("tipo", ["especialista", "", None])
def test_rechaza_tipos_de_entrada_no_permitidos(tipo):
    """RF-4: el contrato no admite tipos fuera de nodo, tool o control."""
    with pytest.raises(ValueError, match="tipo"):
        SesionDepuracion().registrar(tipo, "x", None, None)


@pytest.mark.parametrize("resultado", ["pendiente", "", None])
def test_rechaza_resultados_no_permitidos(resultado):
    """RF-4: el contrato no admite resultados fuera de sus tres valores cerrados."""
    with pytest.raises(ValueError, match="resultado"):
        SesionDepuracion().registrar("nodo", "x", None, None, resultado=resultado)


def test_una_entrada_completada_exige_detalle_nulo():
    """RF-10: los detalles se reservan para fallos o controles, no para éxitos."""
    with pytest.raises(ValueError, match="detalle"):
        SesionDepuracion().registrar(
            "nodo",
            "x",
            {},
            {},
            detalle={"categoria": "no_corresponde"},
        )


def test_las_sesiones_son_independientes_y_exponen_una_copia_de_las_entradas():
    """RF-2: cada llamada futura podrá usar un registro efímero independiente."""
    primera = SesionDepuracion()
    primera.registrar("nodo", "entrada", {}, {})
    segunda = SesionDepuracion()

    copia = primera.entradas
    copia[0]["nodo"] = "modificado_fuera"

    assert segunda.entradas == []
    assert primera.entradas[0]["nodo"] == "entrada"


def test_sanea_recursivamente_credenciales_sin_distinguir_mayusculas():
    """RF-16 a RF-18 y RF-22: los campos de secreto nunca salen del registro."""
    centinela_token = "TOKEN-QUE-NUNCA-DEBE-SALIR"
    centinela_password = "PASSWORD-QUE-NUNCA-DEBE-SALIR"

    saneado = sanear_valor(
        {
            "Authorization": centinela_token,
            "anidado": {"PASSWORD": centinela_password, "visible": "Madrid"},
            "lista": [{"cookie": "COOKIE-SECRETA"}],
        }
    )

    assert saneado == {
        "Authorization": "[oculto por seguridad]",
        "anidado": {"PASSWORD": "[oculto por seguridad]", "visible": "Madrid"},
        "lista": [{"cookie": "[oculto por seguridad]"}],
    }
    assert centinela_token not in str(saneado)
    assert centinela_password not in str(saneado)


def test_sanea_prompts_y_cuerpos_externos_completos():
    """RF-19 y RF-22: el contenido bruto de proveedor no llega al log."""
    prompt = "PROMPT-INTERNO-QUE-NUNCA-DEBE-SALIR"
    cuerpo = "CUERPO-EXTERNO-QUE-NUNCA-DEBE-SALIR"

    saneado = sanear_valor({"prompt": prompt, "response_body": cuerpo, "consulta": "Sol"})

    assert saneado == {
        "prompt": "[oculto por seguridad]",
        "response_body": "[oculto por seguridad]",
        "consulta": "Sol",
    }
    assert prompt not in str(saneado)
    assert cuerpo not in str(saneado)


class ValorNoJson:
    """Centinela cuya representación cruda contiene una credencial falsa."""

    def __repr__(self) -> str:
        return "ValorNoJson(TOKEN-CRUDO-QUE-NUNCA-DEBE-SALIR)"


def test_valor_no_json_se_resume_sin_usar_su_representacion_cruda():
    """RF-21 y RF-22: el tipo se conserva, pero no se filtra el objeto original."""
    saneado = sanear_valor(ValorNoJson(), "error")

    assert saneado == {"tipo": "ValorNoJson", "resumen": "Valor no serializable omitido."}
    assert "TOKEN-CRUDO-QUE-NUNCA-DEBE-SALIR" not in str(saneado)


def test_limite_de_longitud_usa_la_representacion_json_segura():
    """RF-20: 10.000 caracteres JSON se conservan y 10.001 se resumen."""
    dentro_del_limite = "x" * (config.LOG_DEPURACION_MAX_CARACTERES - 2)
    fuera_del_limite = "x" * (config.LOG_DEPURACION_MAX_CARACTERES - 1)

    assert sanear_valor(dentro_del_limite, "texto") == dentro_del_limite
    assert sanear_valor(fuera_del_limite, "texto") == {
        "omitido": "longitud",
        "campo": "texto",
        "limite": config.LOG_DEPURACION_MAX_CARACTERES,
    }


def test_primitivos_listas_y_diccionarios_se_conservan_cuando_no_son_sensibles():
    """RF-16: el saneado mantiene los datos disponibles que no requieren ocultación."""
    valor = {"texto": "Madrid", "numero": 3, "booleano": True, "nulo": None, "lista": [1, "dos"]}

    assert sanear_valor(valor) == valor


def test_sesion_registrar_sanea_todas_las_partes_de_la_entrada():
    """RF-16 a RF-22: el registro no puede saltarse el saneado central."""
    sesion = SesionDepuracion()

    sesion.registrar(
        "nodo",
        "supervisor",
        {"token": "TOKEN-QUE-NUNCA-DEBE-SALIR"},
        {"prompt": "PROMPT-INTERNO-QUE-NUNCA-DEBE-SALIR"},
        resultado="fallido",
        detalle={"credentials": "CREDENCIAL-QUE-NUNCA-DEBE-SALIR"},
    )

    entrada = sesion.entradas[0]
    assert entrada["entrada"]["token"] == "[oculto por seguridad]"
    assert entrada["salida"]["prompt"] == "[oculto por seguridad]"
    assert entrada["detalle"]["credentials"] == "[oculto por seguridad]"


def test_ejecutor_transversal_registra_tools_en_orden_y_conserva_traza():
    """RF-6, RF-9, RF-10, RF-11 y RF-26: log seguro y traza intacta."""
    sesion = SesionDepuracion()
    traza: list[dict] = []

    def ejecutar_correctamente(nombre, args, traza_recibida):
        traza_recibida.append(
            {"tool": nombre, "args": args, "status": "ok", "preview": "Resultado disponible."}
        )
        return {"estado": "ok", "token": "TOKEN-RESULTADO-QUE-NUNCA-DEBE-SALIR"}

    def ejecutar_con_error(nombre, args, traza_recibida):
        traza_recibida.append(
            {"tool": nombre, "args": args, "status": "error", "preview": "ERROR: proveedor no disponible."}
        )
        return "ERROR: proveedor no disponible."

    exito = crear_ejecutor_transversal(ejecutar_correctamente)
    fallo = crear_ejecutor_transversal(ejecutar_con_error)
    args_exito = {"consulta": "horario", "authorization": "TOKEN-ARGS-QUE-NUNCA-DEBE-SALIR"}
    args_fallo = {"zona": "Europe/Madrid"}

    with sesion_depuracion_activa(sesion):
        assert exito("rag_ask", args_exito, traza) == {
            "estado": "ok",
            "token": "TOKEN-RESULTADO-QUE-NUNCA-DEBE-SALIR",
        }
        assert fallo("hora_actual", args_fallo, traza) == "ERROR: proveedor no disponible."

    assert sesion.entradas == [
        {
            "paso": 1,
            "tipo": "tool",
            "nodo": "rag_ask",
            "entrada": {"consulta": "horario", "authorization": "[oculto por seguridad]"},
            "salida": {"estado": "ok", "token": "[oculto por seguridad]"},
            "resultado": "completado",
            "detalle": None,
        },
        {
            "paso": 2,
            "tipo": "tool",
            "nodo": "hora_actual",
            "entrada": args_fallo,
            "salida": None,
            "resultado": "fallido",
            "detalle": {
                "categoria": "tool",
                "resumen": "La herramienta no pudo completarse.",
            },
        },
    ]
    assert "TOKEN-ARGS-QUE-NUNCA-DEBE-SALIR" not in str(sesion.entradas)
    assert "TOKEN-RESULTADO-QUE-NUNCA-DEBE-SALIR" not in str(sesion.entradas)
    assert traza == [
        {"tool": "rag_ask", "args": args_exito, "status": "ok", "preview": "Resultado disponible."},
        {"tool": "hora_actual", "args": args_fallo, "status": "error", "preview": "ERROR: proveedor no disponible."},
    ]
    assert all(set(entrada) == {"tool", "args", "status", "preview"} for entrada in traza)


def test_ejecutor_transversal_registra_el_fallo_si_la_tool_lanza():
    """RF-11: un error excepcional deja una entrada segura antes de propagarse."""
    sesion = SesionDepuracion()

    def ejecutar_roto(_nombre, _args, _traza):
        raise RuntimeError("TOKEN-ERROR-QUE-NUNCA-DEBE-SALIR")

    ejecutor = crear_ejecutor_transversal(ejecutar_roto)

    with sesion_depuracion_activa(sesion), pytest.raises(RuntimeError):
        ejecutor("hora_actual", {"cookie": "COOKIE-QUE-NUNCA-DEBE-SALIR"}, [])

    assert sesion.entradas[0]["resultado"] == "fallido"
    assert sesion.entradas[0]["salida"] is None
    assert sesion.entradas[0]["entrada"] == {"cookie": "[oculto por seguridad]"}
    assert sesion.entradas[0]["detalle"] == {
        "categoria": "tool",
        "resumen": "La herramienta no pudo completarse.",
    }
    assert "TOKEN-ERROR-QUE-NUNCA-DEBE-SALIR" not in str(sesion.entradas)


def test_invocar_grafo_registra_snapshots_de_nodos_tools_y_fallo_sin_eventos_publicos():
    """RF-5 y RF-7 a RF-11, RF-13 y RF-27: eventos locales, salida final única."""
    traza: list[dict] = []

    def ejecutar_tool_falsa(nombre, args, traza_recibida):
        traza_recibida.append(
            {"tool": nombre, "args": args, "status": "ok", "preview": "Evidencia recuperada."}
        )
        return {"evidencia": "CRTM", "secret": "TOKEN-TOOL-QUE-NUNCA-DEBE-SALIR"}

    herramienta = crear_ejecutor_transversal(ejecutar_tool_falsa)

    class GrafoEventosFalso:
        def stream(self, estado, *, config, context, stream_mode):
            assert stream_mode == ["values", "updates", "tasks"]
            assert config["configurable"]["thread_id"] == "hilo-eventos"
            assert context == {"diagnostico_supervisor": None}

            inicial = {**estado, "traza": []}
            tras_entrada = {
                **inicial,
                "historial": [{"role": "user", "content": estado["mensaje"]}],
            }
            yield ("values", inicial)
            yield ("tasks", {"id": "entrada", "name": "entrada", "input": inicial})
            yield ("updates", {"entrada": {"historial": tras_entrada["historial"]}})
            yield ("tasks", {"id": "entrada", "name": "entrada", "error": None, "result": {}})
            yield ("values", tras_entrada)

            yield ("tasks", {"id": "rag", "name": "nodo_rag", "input": tras_entrada})
            herramienta(
                "rag_ask",
                {"consulta": estado["mensaje"], "authorization": "TOKEN-ARGS-QUE-NUNCA-DEBE-SALIR"},
                traza,
            )
            tras_rag = {
                **tras_entrada,
                "traza": traza,
                "resultados": [{"especialista": "rag", "resultado": "Evidencia recuperada."}],
            }
            yield ("updates", {"nodo_rag": {"traza": traza, "resultados": tras_rag["resultados"]}})
            yield ("tasks", {"id": "rag", "name": "nodo_rag", "error": None, "result": {}})
            yield ("values", tras_rag)

            yield ("tasks", {"id": "sintesis", "name": "sintetizador", "input": tras_rag})
            yield (
                "tasks",
                {
                    "id": "sintesis",
                    "name": "sintetizador",
                    "error": RuntimeError("TOKEN-NODO-QUE-NUNCA-DEBE-SALIR"),
                },
            )

    sesion = SesionDepuracion()
    salida = invocar_grafo(
        GrafoEventosFalso(),
        {"mensaje": "Consulta CRTM", "token": "TOKEN-ESTADO-QUE-NUNCA-DEBE-SALIR"},
        "hilo-eventos",
        contexto={"diagnostico_supervisor": None},
        sesion=sesion,
    )

    entradas = sesion.entradas
    assert [entrada["tipo"] for entrada in entradas] == ["nodo", "tool", "nodo", "nodo"]
    assert [entrada["nodo"] for entrada in entradas] == ["entrada", "rag_ask", "nodo_rag", "sintetizador"]
    assert [entrada["paso"] for entrada in entradas] == [1, 2, 3, 4]
    assert entradas[0]["entrada"]["token"] == "[oculto por seguridad]"
    assert entradas[0]["salida"]["historial"] == [{"role": "user", "content": "Consulta CRTM"}]
    assert entradas[1]["entrada"]["authorization"] == "[oculto por seguridad]"
    assert entradas[1]["salida"]["secret"] == "[oculto por seguridad]"
    assert entradas[2]["entrada"]["historial"] == [{"role": "user", "content": "Consulta CRTM"}]
    assert entradas[2]["salida"]["resultados"] == [
        {"especialista": "rag", "resultado": "Evidencia recuperada."}
    ]
    assert entradas[3]["resultado"] == "fallido"
    assert entradas[3]["salida"] is None
    assert entradas[3]["detalle"] == {
        "categoria": "nodo",
        "resumen": "El nodo no pudo completarse.",
    }
    assert "TOKEN-ESTADO-QUE-NUNCA-DEBE-SALIR" not in str(entradas)
    assert "TOKEN-TOOL-QUE-NUNCA-DEBE-SALIR" not in str(entradas)
    assert "TOKEN-NODO-QUE-NUNCA-DEBE-SALIR" not in str(entradas)
    assert salida["resultados"] == [{"especialista": "rag", "resultado": "Evidencia recuperada."}]
    assert "log" not in salida

    herramienta("hora_actual", {}, traza)
    assert len(sesion.entradas) == 4


def test_fallback_del_supervisor_se_proyecta_como_control_efimero():
    """RF-10, RF-11 y RF-15: el diagnóstico real no altera el nodo completado ni el estado."""

    class GrafoConFallbackSupervisor:
        def stream(self, estado, *, config, context, stream_mode):
            assert stream_mode == ["values", "updates", "tasks"]
            inicial = dict(estado)
            salida = {**inicial, "cola_roles": ["auxiliar"]}
            yield ("values", inicial)
            yield ("tasks", {"id": "supervisor", "name": "supervisor", "input": inicial})
            context["diagnostico_supervisor"] = {
                "categoria": "json_invalido",
                "resumen": "La decisión no contiene JSON válido; se aplicó el fallback.",
            }
            yield ("updates", {"supervisor": {"cola_roles": ["auxiliar"]}})
            yield ("tasks", {"id": "supervisor", "name": "supervisor", "error": None, "result": {}})
            yield ("values", salida)

    contexto = {"diagnostico_supervisor": None}
    sesion = SesionDepuracion()
    salida = invocar_grafo(
        GrafoConFallbackSupervisor(),
        {"mensaje": "¿Qué hora es?"},
        "hilo-fallback",
        contexto=contexto,
        sesion=sesion,
    )

    assert salida == {"mensaje": "¿Qué hora es?", "cola_roles": ["auxiliar"]}
    assert sesion.entradas == [
        {
            "paso": 1,
            "tipo": "nodo",
            "nodo": "supervisor",
            "entrada": {"mensaje": "¿Qué hora es?"},
            "salida": {"mensaje": "¿Qué hora es?", "cola_roles": ["auxiliar"]},
            "resultado": "completado",
            "detalle": None,
        },
        {
            "paso": 2,
            "tipo": "control",
            "nodo": "supervisor",
            "entrada": None,
            "salida": None,
            "resultado": "rechazado",
            "detalle": {
                "categoria": "json_invalido",
                "resumen": "La decisión no contiene JSON válido; se aplicó el fallback.",
            },
        },
    ]
