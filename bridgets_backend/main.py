"""
Punto de entrada del backend de Bridgets.

Fase 1:
- Registra los modelos en Base.metadata e invoca create_all al arranque
  (idempotente; seguro con Neon porque create_all no altera tablas existentes).
- CORS abierto para permitir el cliente de escritorio (se restringe si algún
  día exponemos un frontend web por dominio concreto).
- Endpoints se agregan por batches siguiendo el orden del SPEC §5.3.
"""

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import modelos  # noqa: F401 - la importación registra los modelos en Base.metadata.
import schemas
import seguridad
from conexion import Base, engine, get_db

# Idempotente: crea las tablas faltantes sin tocar las existentes.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Bridgets API", version="0.4.0")

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


# ---------- Usuarios y autenticación ----------


@app.post(
    "/usuarios/",
    response_model=schemas.UsuarioOut,
    status_code=status.HTTP_201_CREATED,
)
def registrar_usuario(
    datos: schemas.UsuarioCreate, db: Session = Depends(get_db)
) -> modelos.Usuario:
    """Registra un usuario nuevo con contraseña hasheada con bcrypt."""
    # Regla de dominio: el código de estudiante es obligatorio para estudiantes
    # y no debe enviarse si el rol es tutor. Falla temprano para ahorrar un
    # roundtrip a la DB.
    if datos.rol == "estudiante" and not datos.codigo_estudiante:
        raise HTTPException(
            status_code=400,
            detail="codigo_estudiante es obligatorio para el rol estudiante",
        )
    if datos.rol == "tutor" and datos.codigo_estudiante:
        raise HTTPException(
            status_code=400,
            detail="codigo_estudiante no aplica al rol tutor",
        )

    # Chequeo previo de unicidad: nos permite devolver un 409 con el campo
    # exacto que colisionó (mejor UX). El try/except posterior defiende
    # contra la condición de carrera entre dos registros simultáneos.
    if db.query(modelos.Usuario.id).filter(modelos.Usuario.correo == datos.correo).first():
        raise HTTPException(status_code=409, detail="correo ya registrado")
    if (
        db.query(modelos.Usuario.id)
        .filter(modelos.Usuario.nombre_usuario == datos.nombre_usuario)
        .first()
    ):
        raise HTTPException(status_code=409, detail="nombre_usuario ya registrado")
    if datos.codigo_estudiante and (
        db.query(modelos.Usuario.id)
        .filter(modelos.Usuario.codigo_estudiante == datos.codigo_estudiante)
        .first()
    ):
        raise HTTPException(status_code=409, detail="codigo_estudiante ya registrado")

    usuario = modelos.Usuario(
        nombre_completo=datos.nombre_completo,
        codigo_estudiante=datos.codigo_estudiante,
        correo=datos.correo,
        nombre_usuario=datos.nombre_usuario,
        contrasena=seguridad.hash_password(datos.contrasena),
        rol=datos.rol,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="usuario ya existe")
    db.refresh(usuario)
    return usuario


@app.post("/login/", response_model=schemas.UsuarioOut)
def login(datos: schemas.LoginRequest, db: Session = Depends(get_db)) -> modelos.Usuario:
    """
    Autentica por correo o nombre_usuario.

    Mensaje genérico en caso de falla: no distinguimos "usuario no existe"
    de "contraseña incorrecta" para no facilitar enumeración de cuentas.
    """
    usuario = (
        db.query(modelos.Usuario)
        .filter(
            or_(
                modelos.Usuario.correo == datos.identificador,
                modelos.Usuario.nombre_usuario == datos.identificador,
            )
        )
        .first()
    )
    if usuario is None or not seguridad.verificar_password(datos.contrasena, usuario.contrasena):
        raise HTTPException(status_code=401, detail="credenciales inválidas")
    return usuario


@app.put("/usuarios/{usuario_id}", response_model=schemas.UsuarioOut)
def actualizar_usuario(
    usuario_id: int,
    datos: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
) -> modelos.Usuario:
    """
    Actualiza solo los campos presentes en el body (exclude_unset).
    Si cambia la contraseña la re-hashea con bcrypt.
    """
    usuario = db.get(modelos.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no encontrado")

    cambios = datos.model_dump(exclude_unset=True)

    # Unicidad solo para campos que cambian a un valor distinto del actual.
    if "correo" in cambios and cambios["correo"] != usuario.correo:
        if (
            db.query(modelos.Usuario.id)
            .filter(modelos.Usuario.correo == cambios["correo"])
            .first()
        ):
            raise HTTPException(status_code=409, detail="correo ya registrado")
    if "nombre_usuario" in cambios and cambios["nombre_usuario"] != usuario.nombre_usuario:
        if (
            db.query(modelos.Usuario.id)
            .filter(modelos.Usuario.nombre_usuario == cambios["nombre_usuario"])
            .first()
        ):
            raise HTTPException(status_code=409, detail="nombre_usuario ya registrado")
    if (
        "codigo_estudiante" in cambios
        and cambios["codigo_estudiante"] != usuario.codigo_estudiante
        and cambios["codigo_estudiante"] is not None
    ):
        if (
            db.query(modelos.Usuario.id)
            .filter(modelos.Usuario.codigo_estudiante == cambios["codigo_estudiante"])
            .first()
        ):
            raise HTTPException(status_code=409, detail="codigo_estudiante ya registrado")

    if "contrasena" in cambios:
        cambios["contrasena"] = seguridad.hash_password(cambios["contrasena"])

    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="violación de unicidad al actualizar")
    db.refresh(usuario)
    return usuario
