"""
Punto de entrada del backend de Bridgets.

Fase 1:
- Registra los modelos en Base.metadata e invoca create_all al arranque
  (idempotente; seguro con Neon porque create_all no altera tablas existentes).
- CORS abierto para permitir el cliente de escritorio (se restringe si algún
  día exponemos un frontend web por dominio concreto).
- Endpoints se agregan por batches siguiendo el orden del SPEC §5.3.
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import modelos  # noqa: F401 - la importación registra los modelos en Base.metadata.
import schemas
from conexion import Base, engine, get_db

# Idempotente: crea las tablas faltantes sin tocar las existentes.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bridgets API", version="0.3.0")

# CORS abierto: el cliente de escritorio no envía Origin típico pero facilita
# pruebas desde navegador (Swagger UI y /docs). En producción estricta se
# restringiría a un dominio concreto si hubiera frontend web.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """Health check raíz: confirma que la API está viva."""
    return {"status": "ok", "mensaje": "Bridgets API en línea"}


# ---------- Endpoints de verificación de disponibilidad ----------
# Se llaman desde el cliente en <FocusOut> durante el registro para dar
# feedback inmediato al usuario (verde/rojo en el label del campo).


@app.get("/verificar/correo/{correo}", response_model=schemas.DisponibilidadOut)
def verificar_correo(correo: str, db: Session = Depends(get_db)) -> schemas.DisponibilidadOut:
    """Indica si un correo está libre (no existe en usuarios)."""
    existe = (
        db.query(modelos.Usuario.id).filter(modelos.Usuario.correo == correo).first()
    )
    return schemas.DisponibilidadOut(disponible=existe is None)


@app.get(
    "/verificar/usuario/{nombre_usuario}",
    response_model=schemas.DisponibilidadOut,
)
def verificar_usuario(
    nombre_usuario: str, db: Session = Depends(get_db)
) -> schemas.DisponibilidadOut:
    """Indica si un nombre_usuario está libre."""
    existe = (
        db.query(modelos.Usuario.id)
        .filter(modelos.Usuario.nombre_usuario == nombre_usuario)
        .first()
    )
    return schemas.DisponibilidadOut(disponible=existe is None)


@app.get("/verificar/codigo/{codigo}", response_model=schemas.DisponibilidadOut)
def verificar_codigo(codigo: str, db: Session = Depends(get_db)) -> schemas.DisponibilidadOut:
    """
    Indica si un codigo_estudiante está libre.

    OJO: es el código de estudiante (usuarios.codigo_estudiante), distinto del
    codigo_acceso de una clase (clases.codigo_acceso).
    """
    existe = (
        db.query(modelos.Usuario.id)
        .filter(modelos.Usuario.codigo_estudiante == codigo)
        .first()
    )
    return schemas.DisponibilidadOut(disponible=existe is None)
