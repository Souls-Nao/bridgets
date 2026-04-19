"""
Modelos ORM de Bridgets (SQLAlchemy 2.x, sintaxis Mapped[]).

Esquema:
- usuarios: cuenta con rol 'estudiante' o 'tutor'. codigo_estudiante solo
  aplica para estudiantes (único pero nullable para que los tutores lo omitan).
- clases: propiedad de un tutor, identificada por un codigo_acceso único de
  6 caracteres que el estudiante usa para inscribirse.
- inscripciones: relación N:M estudiante-clase con constraint único compuesto
  para evitar que el mismo estudiante se inscriba dos veces.
- anuncios: texto libre publicado en una clase, con fecha lado-servidor.
- notas: contenido enriquecido (texto + tags de formato) serializado como JSON.
  clase_id es nullable porque una nota puede ser personal sin asociación.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from conexion import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(String(120))
    # Unique pero nullable: tutores no tienen código de estudiante.
    codigo_estudiante: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    correo: Mapped[str] = mapped_column(String(120), unique=True)
    nombre_usuario: Mapped[str] = mapped_column(String(60), unique=True)
    # Hash bcrypt (nunca texto plano). 255 cubre cualquier variante del algoritmo.
    contrasena: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))  # 'estudiante' | 'tutor'

    clases_como_tutor: Mapped[list["Clase"]] = relationship(back_populates="tutor")
    inscripciones: Mapped[list["Inscripcion"]] = relationship(back_populates="estudiante")
    notas: Mapped[list["Nota"]] = relationship(back_populates="estudiante")


class Clase(Base):
    __tablename__ = "clases"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    horario: Mapped[str | None] = mapped_column(String(120), nullable=True)
    codigo_acceso: Mapped[str] = mapped_column(String(6), unique=True)
    color_hex: Mapped[str] = mapped_column(String(7), default="#2B7CE9")
    tutor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))

    tutor: Mapped["Usuario"] = relationship(back_populates="clases_como_tutor")
    inscripciones: Mapped[list["Inscripcion"]] = relationship(
        back_populates="clase", cascade="all, delete-orphan"
    )
    anuncios: Mapped[list["Anuncio"]] = relationship(
        back_populates="clase", cascade="all, delete-orphan"
    )


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (
        UniqueConstraint("estudiante_id", "clase_id", name="uq_inscripcion_estudiante_clase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    clase_id: Mapped[int] = mapped_column(ForeignKey("clases.id"))

    estudiante: Mapped["Usuario"] = relationship(back_populates="inscripciones")
    clase: Mapped["Clase"] = relationship(back_populates="inscripciones")


class Anuncio(Base):
    __tablename__ = "anuncios"

    id: Mapped[int] = mapped_column(primary_key=True)
    contenido: Mapped[str] = mapped_column(Text)
    # server_default=func.now() delega el timestamp al motor (UTC en Neon).
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    clase_id: Mapped[int] = mapped_column(ForeignKey("clases.id"))

    clase: Mapped["Clase"] = relationship(back_populates="anuncios")


class Nota(Base):
    __tablename__ = "notas"

    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    # JSON permite almacenar {"texto": "...", "tags": [{"inicio":..,"fin":..,"tipo":..,"valor":..}]}.
    contenido_formato: Mapped[dict] = mapped_column(JSON)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    estudiante_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    # clase_id es nullable: una nota puede ser personal sin vincularse a una clase.
    clase_id: Mapped[int | None] = mapped_column(ForeignKey("clases.id"), nullable=True)

    estudiante: Mapped["Usuario"] = relationship(back_populates="notas")
