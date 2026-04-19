# Bridgets

Aplicación cliente-servidor de gestión académica entre Tutores y Estudiantes.

## Arquitectura

- **Backend**: FastAPI + SQLAlchemy sobre PostgreSQL (Neon), desplegado en Render.
- **Frontend**: Cliente de escritorio Python + customtkinter, compilado a `.exe` con PyInstaller.
- **Modelo cloud-first**: el cliente apunta a la URL pública de Render desde el día 1.

## Estructura

```
bridgets/
├── bridgets_backend/    # API FastAPI desplegada en Render
└── bridgets_client/     # Cliente de escritorio empaquetado a .exe
```

## Comandos

### Backend (desarrollo local opcional)

```bash
cd bridgets_backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Backend (producción)

`git push origin main` → Render hace auto-deploy (~2 min).

### Cliente (desarrollo)

```bash
cd bridgets_client
pip install -r requirements.txt
python app.py
```

### Cliente (compilación a .exe)

```bash
cd bridgets_client
pyinstaller build_exe.spec --clean --noconfirm
# Ejecutable en dist/bridgets.exe
```

## Verificar backend en producción

```bash
curl https://bridgets-api.onrender.com/
```

## Configuración

- `bridgets_backend/.env` — `DATABASE_URL` de Neon (gitignored).
- `bridgets_backend/.env.example` — plantilla con placeholder.
- Variables de entorno del servicio Render se configuran en el dashboard.
