"""
Utilidades de seguridad: hashing de contraseñas y códigos de acceso.

- bcrypt se usa directamente (sin passlib) para reducir superficie de
  dependencias. bcrypt.gensalt() aplica 12 rondas por defecto: suficiente
  para una API de escritorio sin comprometer latencia.
- generar_codigo_acceso verifica unicidad en DB antes de devolver el código.
  Con 36^6 ≈ 2.2B combinaciones las colisiones son prácticamente nulas,
  pero el reintento defiende contra la condición que sí podría ocurrir.
"""

import secrets
import string

import bcrypt
from sqlalchemy.orm import Session

# Mayúsculas + dígitos: evita ambigüedades visuales del usuario al teclear.
_ALFABETO_CODIGO = string.ascii_uppercase + string.digits
_LONGITUD_CODIGO = 6
_MAX_INTENTOS_CODIGO = 10


def hash_password(plano: str) -> str:
    """Hashea una contraseña en texto plano con bcrypt. Devuelve el hash en UTF-8."""
    return bcrypt.hashpw(plano.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(plano: str, hash_guardado: str) -> bool:
    """Compara una contraseña plana contra el hash bcrypt almacenado."""
    try:
        return bcrypt.checkpw(plano.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        # Hash malformado (dato corrupto). Nunca validar como True por seguridad.
        return False


def generar_codigo_acceso(db: Session) -> str:
    """
    Genera un código de acceso único de 6 caracteres alfanuméricos mayúsculas.

    Consulta la tabla clases para garantizar unicidad; reintenta hasta
    _MAX_INTENTOS_CODIGO veces antes de abortar (escenario prácticamente imposible
    con este espacio de combinaciones, pero defendemos contra rarezas).
    """
    # Import local para evitar import circular en el arranque (modelos usa Base).
    from modelos import Clase

    for _ in range(_MAX_INTENTOS_CODIGO):
        codigo = "".join(secrets.choice(_ALFABETO_CODIGO) for _ in range(_LONGITUD_CODIGO))
        existe = db.query(Clase).filter(Clase.codigo_acceso == codigo).first()
        if existe is None:
            return codigo

    raise RuntimeError(
        f"No se pudo generar un codigo_acceso único tras {_MAX_INTENTOS_CODIGO} intentos."
    )
