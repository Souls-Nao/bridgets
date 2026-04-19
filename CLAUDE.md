# CLAUDE.md — Guía rápida para Bridgets

Para contexto completo consultar `SPEC.md` (local, no versionado).

## Comandos

- **Deploy backend**: `git push origin main` (Render auto-deploy ~2 min).
- **Correr cliente (dev)**: `cd bridgets_client && python app.py`.
- **Compilar .exe**: `cd bridgets_client && pyinstaller build_exe.spec --clean --noconfirm`.
- **Verificar backend**: `curl https://bridgets-api.onrender.com/`.
- **Swagger**: `https://bridgets-api.onrender.com/docs`.

## Estilo

- Python 3.10+, `snake_case`, type hints siempre, f-strings.
- Docstrings y comentarios en español.
- Mensajes de commit en español, atómicos por feature.
- Pydantic v2 con `model_config = ConfigDict(from_attributes=True)`.

## No hacer

- No usar rutas relativas sueltas en el cliente: siempre `resource_path("assets/x")`.
- No `SELECT *`: columnas explícitas.
- No commitear `.env` ni `SPEC.md` (ya en `.gitignore`).
- No `print()` en producción: usar `logging` si hace falta.
- No alucinar dependencias: antes de `import X`, agregarlo a `requirements.txt`.

## Convenciones API

- Rutas en plural y español: `/usuarios/`, `/clases/`, `/notas/`.
- Validación con Pydantic siempre (request y response).
- Códigos HTTP correctos: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 404 Not Found, 409 Conflict.
- Contraseñas con `bcrypt`, nunca texto plano.
- Nunca exponer el hash de contraseña en respuestas.

## Flujo de trabajo

- Plan antes de código en cada fase.
- Un endpoint / feature a la vez: implementar → commit → push → esperar deploy → verificar en Render → siguiente.
- Verificaciones del backend contra la URL pública de Render (no localhost).
- Usar `AskUserQuestion` ante cualquier ambigüedad.
