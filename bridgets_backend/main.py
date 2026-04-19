"""
Punto de entrada del backend de Bridgets.

Fase 0: endpoint mínimo para validar el despliegue en Render contra Neon.
En Fase 1 se conectará la base de datos y se agregarán los 14 endpoints.
"""

from fastapi import FastAPI

app = FastAPI(title="Bridgets API", version="0.1.0")


@app.get("/")
def root() -> dict:
    """Health check raíz: confirma que la API está viva."""
    return {"status": "ok", "mensaje": "Bridgets API en línea"}
