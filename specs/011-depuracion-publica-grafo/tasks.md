# Tareas — Spec 011 (depuración pública del grafo)

> Una tarea cada vez: `/sdd-implementar Tn`. Tests primero. Marca `[x]` al terminar.
>
> **Precondición externa:** antes de cerrar cualquier tarea de implementación, `python -m pytest` debe estar verde conforme al artículo 9 de la constitución. Los 13 fallos actuales de BiciMAD/clima los gestiona otro equipo y no forman parte de estas tareas.

- [x] T1. Crear las pruebas de contrato puro y la base efímera de las entradas estructuradas de depuración. (RF-2, RF-3, RF-4, RF-10)
      Tests primero: crear `tests/test_depuracion.py` para campos obligatorios, valores admitidos, pasos consecutivos y `detalle = null` al completar.
      Implementar después `src/depuracion.py` con los tipos y la sesión de depuración sin persistencia.
      Hecho cuando: `python -m pytest tests/test_depuracion.py -q` y `python -m pytest` están en verde.

- [x] T2. Sanear y serializar de forma segura todas las entradas de depuración. (RF-16, RF-17, RF-18, RF-19, RF-20, RF-21, RF-22)
      Tests primero: añadir a `tests/test_depuracion.py` centinelas para credenciales, cabeceras, prompts, cuerpos externos, objetos no JSON y valores de 10.000/10.001 caracteres.
      Implementar después el saneado recursivo, la representación segura y el límite centralizado en `config.py`.
      Hecho cuando: `python -m pytest tests/test_depuracion.py -q` y `python -m pytest` están en verde, sin que ninguno de los centinelas aparezca en el resultado.

- [x] T3. Adaptar la proyección pública y el estado persistente al nuevo `log` por llamada. (RF-1, RF-2, RF-15, RF-26)
      Tests primero: ampliar `tests/test_estado_grafo.py` y `tests/test_agent_contrato.py` para seis claves estables, `log` estructurado, `traza` intacta y ausencia de `log` en el checkpoint.
      Implementar después los cambios en `src/estado.py` y `src/clientes/contrato.py`; `log` deja de formar parte de `EstadoGrafo` y la proyección recibe el registro efímero.
      Hecho cuando: `python -m pytest tests/test_estado_grafo.py tests/test_agent_contrato.py -q` y `python -m pytest` están en verde.

- [x] T4. Registrar en orden las invocaciones de tools sin modificar `traza`. (RF-6, RF-9, RF-10, RF-11, RF-26)
      Tests primero: añadir a `tests/test_depuracion.py` un ejecutor falso con éxito y otro con error; comprobar argumentos, resultado saneado, fallo seguro, orden y contrato de `traza`.
      Implementar después la notificación a la sesión efímera desde `src/agents/base.py`, conservando allowlist, límites y entradas actuales de `traza`.
      Hecho cuando: `python -m pytest tests/test_depuracion.py tests/test_tool_rutas_traza.py -q` y `python -m pytest` están en verde.

- [x] T5. Instrumentar los nodos del grafo con snapshots completos antes y después de reducers. (RF-5, RF-7, RF-8, RF-11, RF-13, RF-27)
      Tests primero: añadir a `tests/test_depuracion.py` un grafo falso con varios nodos, una tool y un fallo controlado; verificar snapshots, estado combinado, orden y que no hay salida parcial pública.
      Implementar después el adaptador de eventos de LangGraph en `src/graph.py` para `values`, `updates` y `tasks`, con limpieza garantizada del contexto efímero.
      Hecho cuando: `python -m pytest tests/test_depuracion.py tests/test_supervisor_grafo.py -q` y `python -m pytest` están en verde.

- [x] T6. Entregar un log aislado por operación pública y las entradas de control de la fachada. (RF-1, RF-12, RF-13, RF-14, RF-15, RF-27)
      Tests primero: ampliar `tests/test_agent_contrato.py` y `tests/test_grafo_persistencia.py` para validaciones de entrada, plan pendiente, ausencia o selección inválida de plan, pausa HITL y reanudación con logs distintos.
      Implementar después la creación y cierre de una sesión por llamada en `src/agent.py`, incluida la reanudación; ninguna entrada llega a historial ni checkpoint.
      Hecho cuando: `python -m pytest tests/test_agent_contrato.py tests/test_grafo_persistencia.py -q` y `python -m pytest` están en verde.

- [x] T7. Adaptar el formato compartido y el CLI para mostrar el registro estructurado completo. (RF-23)
      Tests primero: actualizar `tests/test_presentacion.py` y `tests/test_cli.py` con entradas de nodo, tool, control y diagnóstico de Supervisor.
      Implementar después el formato en `src/clientes/presentacion.py` y el consumo mínimo en `src/clientes/cli.py`.
      Hecho cuando: `python -m pytest tests/test_presentacion.py tests/test_cli.py -q` y `python -m pytest` están en verde; el CLI muestra las entradas ordenadas y estructuradas.

- [x] T8. Mostrar el log completo solo en el panel de depuración de Streamlit y conservar el filtro en el chat. (RF-24, RF-25)
      Tests primero: actualizar `tests/test_presentacion.py` y `tests/test_app_streamlit.py` para comprobar panel completo con diagnóstico y «Pasos seguidos» sin diagnóstico técnico.
      Implementar después el ajuste mínimo de `app.py` y la presentación compartida; comprobar que `src/clientes/sesion.py` mantiene copias profundas de cada log por respuesta.
      Hecho cuando: `python -m pytest tests/test_presentacion.py tests/test_app_streamlit.py tests/test_sesion.py -q` y `python -m pytest` están en verde.

- [x] T9. Revisar compatibilidad del contrato y actualizar los tests afectados por el paso de `list[str]` a entradas estructuradas. (RF-1, RF-2, RF-3, RF-4, RF-23 a RF-26)
      Tests primero: localizar con `rg -n 'log|Supervisor: categoria=' tests src` todos los supuestos de texto y convertirlos en aserciones del contrato estructurado.
      Ajustar solo los tests y consumidores que fijen el formato anterior, sin cambiar las seis claves públicas ni la estructura de `traza`.
      Hecho cuando: `python -m pytest tests -q` y `python -m pytest` están en verde, sin aserciones restantes que esperen `log: list[str]`.

- [x] T10. Proyectar en el log efímero el diagnóstico de un *fallback* real del Supervisor. (RF-2, RF-4, RF-10, RF-11, RF-15, RF-23 a RF-25)
      Tests primero: ampliar `tests/test_depuracion.py` y `tests/test_clientes_grafo_real.py` con un Supervisor que devuelve una decisión inválida; comprobar que, inmediatamente después del nodo `supervisor` completado, la llamada pública devuelve una única entrada `control` de `supervisor`, con `entrada` y `salida` a `null`, `resultado: "rechazado"` y un `detalle` seguro con categoría y resumen. Ampliar `tests/test_cli.py` y `tests/test_app_streamlit.py` para verificar que esa ejecución real llega íntegra a CLI y al panel de depuración, pero queda excluida de «Pasos seguidos».
      Implementar después en `src/graph.py` la proyección de `runtime.context["diagnostico_supervisor"]` exclusivamente cuando su categoría sea distinta de `sin_fallback`; no persistirla ni alterar `traza`.
      Hecho cuando: `python -m pytest tests/test_depuracion.py tests/test_clientes_grafo_real.py tests/test_cli.py tests/test_app_streamlit.py -q` y `python -m pytest` están verdes, y el checkpoint no contiene el diagnóstico ni una clave `log`.

- [x] T11. Repetir la validación final RF por RF (`/sdd-validar`). (RF-1 a RF-27)
      Hecho cuando: `specs/011-depuracion-publica-grafo/validacion.md` relaciona cada RF con evidencia y resultado, verifica explícitamente el diagnóstico de *fallback* del Supervisor en CLI, panel y filtro de chat, y el veredicto final permite cerrar la implementación.

## Cobertura de requisitos

Todos los RF aparecen al menos en una tarea:

| RF | Tarea(s) |
|---|---|
| RF-1 | T3, T6, T9, T11 |
| RF-2 a RF-4 | T1, T3, T9, T10, T11 |
| RF-5 | T5, T11 |
| RF-6 | T4, T11 |
| RF-7 y RF-8 | T5, T11 |
| RF-9 | T4, T11 |
| RF-10 | T1, T4, T10, T11 |
| RF-11 | T4, T5, T10, T11 |
| RF-12 | T6, T11 |
| RF-13 a RF-15 | T3, T5, T6, T10, T11 |
| RF-16 a RF-22 | T2, T11 |
| RF-23 | T7, T9, T10, T11 |
| RF-24 y RF-25 | T8, T9, T10, T11 |
| RF-26 | T3, T4, T9, T11 |
| RF-27 | T5, T6, T11 |
