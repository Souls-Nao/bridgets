"""
Estado de sesión del usuario autenticado.

Persistencia:
- iniciar() guarda automáticamente a disco (%APPDATA%/bridgets/session.json
  en Windows, ~/.bridgets/session.json como fallback).
- cerrar() borra el archivo.
- cargar() rehidrata 'actual' desde el archivo (si existe y es legible).
  El splash la invoca al arrancar; si devuelve True hay sesión previa.

Se persiste la respuesta completa de UsuarioOut porque el backend no expone
GET /usuarios/{id}: si necesitáramos re-hidratar desde la red tras leer
sólo el id, no tendríamos endpoint. Si al usar la sesión el backend responde
401/404 en cualquier endpoint, el splash la invalida y manda a login.

Esto NO es un token de autenticación — el MVP no usa tokens. Es un atajo
para no pedir credenciales cada vez que se abre la app; cualquiera con
acceso al %APPDATA% del usuario puede abrir la app como él (equivalente
a la cookie de sesión de un navegador).
"""

import json
import os
import pathlib
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


# ----------------------------------------------------------------------
# Persistencia en disco.
# ----------------------------------------------------------------------


def _ruta_archivo() -> pathlib.Path:
    """
    Devuelve la ruta del archivo de sesión.

    Windows: %APPDATA%/bridgets/session.json
    Otros:  ~/.bridgets/session.json
    """
    base_appdata = os.environ.get("APPDATA")
    if base_appdata:
        directorio = pathlib.Path(base_appdata) / "bridgets"
    else:
        directorio = pathlib.Path.home() / ".bridgets"
    return directorio / "session.json"


def _guardar_disco() -> None:
    """Escribe el estado de 'actual' al archivo. Se silencian errores de IO."""
    ruta = _ruta_archivo()
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        datos = {
            "id": actual.usuario_id,
            "rol": actual.rol,
            "nombre_completo": actual.nombre_completo,
            "correo": actual.correo,
            "nombre_usuario": actual.nombre_usuario,
            "codigo_estudiante": actual.codigo_estudiante,
        }
        with ruta.open("w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
    except OSError:
        # Sin permisos o disco lleno: se pierde la persistencia pero la app sigue.
        pass


def _borrar_disco() -> None:
    """Elimina el archivo de sesión si existe."""
    try:
        _ruta_archivo().unlink(missing_ok=True)
    except OSError:
        pass


def cargar() -> bool:
    """
    Rehidrata 'actual' desde disco.

    Devuelve True si había sesión válida; False si no existía archivo o
    estaba corrupto/incompleto (en cuyo caso se limpia el archivo para
    no dejar basura).
    """
    ruta = _ruta_archivo()
    if not ruta.exists():
        return False
    try:
        with ruta.open("r", encoding="utf-8") as f:
            datos = json.load(f)
    except (OSError, ValueError):
        _borrar_disco()
        return False

    if not isinstance(datos, dict) or not datos.get("id"):
        _borrar_disco()
        return False

    # iniciar() sobrescribe campos y vuelve a guardar: no llamarlo para evitar
    # escritura redundante. Asignamos directo.
    actual.usuario_id = datos.get("id")
    actual.rol = datos.get("rol")
    actual.nombre_completo = datos.get("nombre_completo", "")
    actual.correo = datos.get("correo", "")
    actual.nombre_usuario = datos.get("nombre_usuario", "")
    actual.codigo_estudiante = datos.get("codigo_estudiante")
    actual.extra.clear()
    return True


# ----------------------------------------------------------------------
# API pública.
# ----------------------------------------------------------------------


def iniciar(datos_usuario: dict) -> None:
    """Carga en 'actual' los campos de una respuesta UsuarioOut y persiste."""
    actual.usuario_id = datos_usuario.get("id")
    actual.rol = datos_usuario.get("rol")
    actual.nombre_completo = datos_usuario.get("nombre_completo", "")
    actual.correo = datos_usuario.get("correo", "")
    actual.nombre_usuario = datos_usuario.get("nombre_usuario", "")
    actual.codigo_estudiante = datos_usuario.get("codigo_estudiante")
    actual.extra.clear()
    _guardar_disco()


def cerrar() -> None:
    """Borra los datos de sesión en memoria y en disco."""
    actual.usuario_id = None
    actual.rol = None
    actual.nombre_completo = ""
    actual.correo = ""
    actual.nombre_usuario = ""
    actual.codigo_estudiante = None
    actual.extra.clear()
    _borrar_disco()
