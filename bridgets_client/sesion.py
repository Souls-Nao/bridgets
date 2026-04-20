"""
Estado de sesión del usuario autenticado (solo memoria).

No persiste a disco en Fase 2 — en Batch K se agregará una capa opcional
para recordar el usuario_id en %APPDATA%/bridgets/session.json.

Uso:
    import sesion
    sesion.iniciar(respuesta_login)     # tras un POST /login/ exitoso
    sesion.actual.rol                   # 'estudiante' | 'tutor' | None
    sesion.cerrar()                     # al hacer logout
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Sesion:
    """Datos del usuario actualmente autenticado. Vacío cuando no hay sesión."""

    usuario_id: int | None = None
    rol: str | None = None  # 'estudiante' | 'tutor'
    nombre_completo: str = ""
    correo: str = ""
    nombre_usuario: str = ""
    codigo_estudiante: str | None = None
    # Espacio libre para que las vistas guarden estado derivado sin ensuciar globals.
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def autenticada(self) -> bool:
        """True si hay un usuario activo (usuario_id definido)."""
        return self.usuario_id is not None


# Instancia única consultada por todas las vistas.
actual: Sesion = Sesion()


def iniciar(datos_usuario: dict) -> None:
    """Carga en 'actual' los campos de una respuesta UsuarioOut del backend."""
    actual.usuario_id = datos_usuario.get("id")
    actual.rol = datos_usuario.get("rol")
    actual.nombre_completo = datos_usuario.get("nombre_completo", "")
    actual.correo = datos_usuario.get("correo", "")
    actual.nombre_usuario = datos_usuario.get("nombre_usuario", "")
    actual.codigo_estudiante = datos_usuario.get("codigo_estudiante")
    actual.extra.clear()


def cerrar() -> None:
    """Borra todos los datos de sesión. Llamar al hacer logout."""
    actual.usuario_id = None
    actual.rol = None
    actual.nombre_completo = ""
    actual.correo = ""
    actual.nombre_usuario = ""
    actual.codigo_estudiante = None
    actual.extra.clear()
