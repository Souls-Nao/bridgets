"""
Esquemas Pydantic v2 para request/response de la API de Bridgets.

Convenciones:
- Base -> Create -> Update -> Out: la jerarquía minimiza duplicación y deja
  explícito qué campos acepta cada operación.
- *Out usa model_config = ConfigDict(from_attributes=True) para poder
  serializarse directamente desde instancias ORM (antes orm_mode).
- UsuarioOut NUNCA incluye contrasena (es un hash, pero igual no se expone).
- contenido_formato de notas es un objeto tipado (texto + lista de tags),
  así el cliente recibe validación de estructura en vez de un dict suelto.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- Verificación de disponibilidad ----------


class DisponibilidadOut(BaseModel):
    """Respuesta de los endpoints /verificar/*."""

    disponible: bool


# ---------- Usuarios ----------


class UsuarioBase(BaseModel):
    nombre_completo: str = Field(min_length=1, max_length=120)
    correo: str = Field(min_length=3, max_length=120)
    nombre_usuario: str = Field(min_length=3, max_length=60)
    rol: Literal["estudiante", "tutor"]


class UsuarioCreate(UsuarioBase):
    contrasena: str = Field(min_length=6, max_length=128)
    # Nullable: solo lo mandan estudiantes; los tutores lo omiten.
    codigo_estudiante: str | None = Field(default=None, max_length=20)


class UsuarioUpdate(BaseModel):
    """Todos opcionales: el cliente envía solo los campos a modificar."""

    nombre_completo: str | None = Field(default=None, min_length=1, max_length=120)
    correo: str | None = Field(default=None, min_length=3, max_length=120)
    nombre_usuario: str | None = Field(default=None, min_length=3, max_length=60)
    contrasena: str | None = Field(default=None, min_length=6, max_length=128)
    codigo_estudiante: str | None = Field(default=None, max_length=20)


class UsuarioOut(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo_estudiante: str | None = None
    # Deliberadamente sin 'contrasena': ningún cliente debería recibir el hash.


# ---------- Login ----------


class LoginRequest(BaseModel):
    """Permite login por correo o por nombre_usuario, resuelto en el endpoint."""

    identificador: str = Field(min_length=3, max_length=120)
    contrasena: str = Field(min_length=1, max_length=128)


# ---------- Clases ----------


class ClaseBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = None
    horario: str | None = Field(default=None, max_length=120)
    color_hex: str = Field(default="#2B7CE9", pattern=r"^#[0-9A-Fa-f]{6}$")


class ClaseCreate(ClaseBase):
    tutor_id: int


class ClaseOut(ClaseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    # codigo_acceso lo genera el backend; siempre presente en la respuesta.
    codigo_acceso: str
    tutor_id: int


class InscripcionRequest(BaseModel):
    """Body de POST /clases/inscribir/."""

    estudiante_id: int
    codigo_acceso: str = Field(min_length=6, max_length=6)


# ---------- Anuncios ----------


class AnuncioCreate(BaseModel):
    contenido: str = Field(min_length=1)


class AnuncioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contenido: str
    fecha_creacion: datetime
    clase_id: int


# ---------- Notas ----------


class TagFormato(BaseModel):
    """Rango de formato dentro del texto de una nota."""

    inicio: int = Field(ge=0)
    fin: int = Field(ge=0)
    tipo: str  # 'color' | 'resaltado' | 'negrita' | 'cursiva' | etc.
    valor: str  # p. ej. '#ff0000' para tipo 'color'.


class ContenidoFormato(BaseModel):
    texto: str
    tags: list[TagFormato] = Field(default_factory=list)


class NotaCreate(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    contenido_formato: ContenidoFormato
    estudiante_id: int
    # Nullable: una nota puede ser personal y no vincularse a una clase.
    clase_id: int | None = None


class NotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    contenido_formato: ContenidoFormato
    fecha_creacion: datetime
    estudiante_id: int
    clase_id: int | None = None
