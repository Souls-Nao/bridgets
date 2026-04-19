"""
Punto de entrada del backend de Bridgets.

Batch A de Fase 1: importa los modelos para registrarlos en Base.metadata
y ejecuta create_all al arranque, creando las 5 tablas en Neon si aún no
existen. Los endpoints del dominio llegan en los batches siguientes.
"""

from fastapi import FastAPI

from conexion import Base, engine
import modelos  # noqa: F401 - la importación registra los modelos en Base.metadata.

# Idempotente: crea las tablas faltantes sin tocar las existentes.
# En Render (1 worker) corre una vez al boot del servicio.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bridgets API", version="0.2.0")


@app.get("/")
def root() -> dict:
    """Health check raíz: confirma que la API está viva."""
    return {"status": "ok", "mensaje": "Bridgets API en línea"}
