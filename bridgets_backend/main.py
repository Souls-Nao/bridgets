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

app = FastAPI(title="Bridgets API", version="0.6.0")

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


# ---------- Clases e inscripciones ----------


@app.post(
    "/clases/",
    response_model=schemas.ClaseOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_clase(
    datos: schemas.ClaseCreate, db: Session = Depends(get_db)
) -> modelos.Clase:
    """Crea una clase para un tutor existente. Genera codigo_acceso único."""
    tutor = db.get(modelos.Usuario, datos.tutor_id)
    if tutor is None:
        raise HTTPException(status_code=404, detail="tutor no encontrado")
    if tutor.rol != "tutor":
        raise HTTPException(
            status_code=403, detail="solo un usuario con rol tutor puede crear clases"
        )

    clase = modelos.Clase(
        nombre=datos.nombre,
        descripcion=datos.descripcion,
        horario=datos.horario,
        color_hex=datos.color_hex,
        tutor_id=datos.tutor_id,
        codigo_acceso=seguridad.generar_codigo_acceso(db),
    )
    db.add(clase)
    try:
        db.commit()
    except IntegrityError:
        # Race: otro insert tomó el mismo codigo_acceso entre generar y commit.
        db.rollback()
        raise HTTPException(
            status_code=409, detail="colisión al asignar codigo_acceso; reintenta"
        )
    db.refresh(clase)
    return clase


@app.get("/clases/usuario/{usuario_id}", response_model=list[schemas.ClaseOut])
def listar_clases_usuario(
    usuario_id: int, db: Session = Depends(get_db)
) -> list[modelos.Clase]:
    """
    Devuelve las clases asociadas al usuario según su rol:
    - tutor: clases que dicta.
    - estudiante: clases en las que está inscrito.
    """
    usuario = db.get(modelos.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no encontrado")

    if usuario.rol == "tutor":
        return (
            db.query(modelos.Clase)
            .filter(modelos.Clase.tutor_id == usuario_id)
            .order_by(modelos.Clase.id)
            .all()
        )

    # Estudiante: join con inscripciones.
    return (
        db.query(modelos.Clase)
        .join(modelos.Inscripcion, modelos.Inscripcion.clase_id == modelos.Clase.id)
        .filter(modelos.Inscripcion.estudiante_id == usuario_id)
        .order_by(modelos.Clase.id)
        .all()
    )


@app.post(
    "/clases/inscribir/",
    status_code=status.HTTP_201_CREATED,
)
def inscribir_estudiante(
    datos: schemas.InscripcionRequest, db: Session = Depends(get_db)
) -> dict:
    """
    Inscribe un estudiante en una clase usando codigo_acceso.

    El código se compara en mayúsculas por robustez ante el input del cliente.
    """
    estudiante = db.get(modelos.Usuario, datos.estudiante_id)
    if estudiante is None:
        raise HTTPException(status_code=404, detail="estudiante no encontrado")
    if estudiante.rol != "estudiante":
        raise HTTPException(
            status_code=403, detail="solo un usuario con rol estudiante puede inscribirse"
        )

    codigo_norm = datos.codigo_acceso.strip().upper()
    clase = (
        db.query(modelos.Clase)
        .filter(modelos.Clase.codigo_acceso == codigo_norm)
        .first()
    )
    if clase is None:
        raise HTTPException(status_code=404, detail="codigo_acceso inválido")

    inscripcion = modelos.Inscripcion(
        estudiante_id=datos.estudiante_id, clase_id=clase.id
    )
    db.add(inscripcion)
    try:
        db.commit()
    except IntegrityError:
        # UniqueConstraint(estudiante_id, clase_id) dispara si ya está inscrito.
        db.rollback()
        raise HTTPException(status_code=409, detail="estudiante ya inscrito en la clase")
    db.refresh(inscripcion)
    return {
        "id": inscripcion.id,
        "estudiante_id": inscripcion.estudiante_id,
        "clase_id": inscripcion.clase_id,
    }


@app.get("/clases/buscar/", response_model=list[schemas.ClaseOut])
def buscar_clases(
    q: str, estudiante_id: int, db: Session = Depends(get_db)
) -> list[modelos.Clase]:
    """
    Busca clases por nombre o descripción (ILIKE), excluyendo las que el
    estudiante ya tiene inscritas. Exige q con al menos 2 caracteres para
    evitar devolver el catálogo completo por error.
    """
    q_limpio = q.strip()
    if len(q_limpio) < 2:
        return []

    estudiante = db.get(modelos.Usuario, estudiante_id)
    if estudiante is None:
        raise HTTPException(status_code=404, detail="estudiante no encontrado")

    # Subquery: clase_ids donde el estudiante ya está inscrito.
    ya_inscritas = (
        db.query(modelos.Inscripcion.clase_id)
        .filter(modelos.Inscripcion.estudiante_id == estudiante_id)
        .subquery()
    )

    patron = f"%{q_limpio}%"
    return (
        db.query(modelos.Clase)
        .filter(
            or_(
                modelos.Clase.nombre.ilike(patron),
                modelos.Clase.descripcion.ilike(patron),
            ),
            ~modelos.Clase.id.in_(ya_inscritas.select()),
        )
        .order_by(modelos.Clase.id)
        .all()
    )


# ---------- Anuncios ----------


@app.get(
    "/clases/{clase_id}/anuncios/", response_model=list[schemas.AnuncioOut]
)
def listar_anuncios(
    clase_id: int, db: Session = Depends(get_db)
) -> list[modelos.Anuncio]:
    """Lista los anuncios de una clase, del más reciente al más antiguo."""
    clase = db.get(modelos.Clase, clase_id)
    if clase is None:
        raise HTTPException(status_code=404, detail="clase no encontrada")
    return (
        db.query(modelos.Anuncio)
        .filter(modelos.Anuncio.clase_id == clase_id)
        .order_by(modelos.Anuncio.fecha_creacion.desc())
        .all()
    )


@app.post(
    "/clases/{clase_id}/anuncios/",
    response_model=schemas.AnuncioOut,
    status_code=status.HTTP_201_CREATED,
)
def crear_anuncio(
    clase_id: int,
    datos: schemas.AnuncioCreate,
    db: Session = Depends(get_db),
) -> modelos.Anuncio:
    """
    Crea un anuncio en la clase.

    Sin restricción de rol: la UX del cliente decide quién ve el botón de
    crear. Si el producto requiere que solo el tutor publique, se agrega
    la guardia aquí.
    """
    clase = db.get(modelos.Clase, clase_id)
    if clase is None:
        raise HTTPException(status_code=404, detail="clase no encontrada")

    anuncio = modelos.Anuncio(contenido=datos.contenido, clase_id=clase_id)
    db.add(anuncio)
    db.commit()
    db.refresh(anuncio)
    return anuncio


# ---------- Notas ----------


@app.post(
    "/notas/",
    response_model=schemas.NotaOut,
    status_code=status.HTTP_201_CREATED,
)
def guardar_nota(
    datos: schemas.NotaCreate, db: Session = Depends(get_db)
) -> modelos.Nota:
    """
    Guarda una nota con contenido_formato (texto + tags de formato) en JSON.

    clase_id es opcional: una nota puede ser personal y no asociarse a una clase.
    """
    estudiante = db.get(modelos.Usuario, datos.estudiante_id)
    if estudiante is None:
        raise HTTPException(status_code=404, detail="estudiante no encontrado")

    if datos.clase_id is not None:
        clase = db.get(modelos.Clase, datos.clase_id)
        if clase is None:
            raise HTTPException(status_code=400, detail="clase_id no corresponde a ninguna clase")

    nota = modelos.Nota(
        titulo=datos.titulo,
        # Pydantic convierte ContenidoFormato a dict al serializar para SQLAlchemy.
        contenido_formato=datos.contenido_formato.model_dump(),
        estudiante_id=datos.estudiante_id,
        clase_id=datos.clase_id,
    )
    db.add(nota)
    db.commit()
    db.refresh(nota)
    return nota


@app.get("/notas/usuario/{usuario_id}", response_model=list[schemas.NotaOut])
def listar_notas_usuario(
    usuario_id: int, db: Session = Depends(get_db)
) -> list[modelos.Nota]:
    """Lista las notas de un usuario, del más reciente al más antiguo."""
    usuario = db.get(modelos.Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="usuario no encontrado")

    return (
        db.query(modelos.Nota)
        .filter(modelos.Nota.estudiante_id == usuario_id)
        .order_by(modelos.Nota.fecha_creacion.desc())
        .all()
    )
