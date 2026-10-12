# Specs

Una carpeta por funcionalidad, numerada con tres dígitos:

```text
specs/
├── 000-sistema-actual/          # opcional: lo que el proyecto ya hacía (/sdd-spec-inversa)
└── 001-nombre-de-la-feature/
    ├── spec.md                  # /sdd-spec  +  /sdd-clarificar
    ├── plan.md                  # /sdd-plan
    ├── tasks.md                 # /sdd-tareas  (se marcan con /sdd-implementar)
    └── validacion.md            # /sdd-validar
```

La spec activa es la de número más alto. Si un requisito cambia, se edita primero su `spec.md` (`/sdd-cambio`).
