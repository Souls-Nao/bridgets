"""
Conexión a la base de datos PostgreSQL (Neon) vía SQLAlchemy.

- Carga DATABASE_URL desde variables de entorno (en Render se inyecta desde
  el dashboard; en local se lee del archivo .env vía python-dotenv).
- pool_pre_ping=True es obligatorio con Neon: la base cierra conexiones
  inactivas y sin pre-ping cada reinicio de pool falla con OperationalError.
- Expone Base (declarativa), SessionLocal (factory de sesiones) y la
  dependencia get_db() que se usa en los endpoints de FastAPI con Depends.
"""

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Carga .env solo si existe (en Render no hay archivo, la var ya está inyectada).
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no está definida. En local agrega un .env al lado de "
        "conexion.py; en Render configúrala en Environment del servicio."
    )

# pool_pre_ping reemite un SELECT 1 antes de entregar la conexión del pool,
# evitando fallos cuando Neon ya la cerró por inactividad.
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autoflush=False, autocommit=False, bind=engine)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM de Bridgets."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: abre una sesión por request y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
