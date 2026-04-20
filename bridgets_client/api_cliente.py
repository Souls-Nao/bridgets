"""
Cliente HTTP hacia el backend de Bridgets (Render).

Cada función devuelve una tupla (exito: bool, datos: Any):
- exito=True  -> datos es el JSON parseado (dict o list).
- exito=False -> datos es un string con el mensaje de error para mostrar al usuario.

El timeout es generoso (75 s) porque Render Free suspende el servicio tras
15 min de inactividad y el cold start ronda los 50 s. El splash de la app
absorbe ese primer golpe con un ping; las llamadas subsecuentes serán rápidas.

Errores comunes:
- requests.Timeout: el servidor tardó demasiado (cold start extremo o caído).
- requests.ConnectionError: sin red o DNS roto.
- response != 2xx: se extrae 'detail' del JSON de FastAPI cuando está disponible.
"""

from typing import Any
from urllib.parse import quote

import requests

from config import API_URL

_TIMEOUT_S = 75


def _url(path: str) -> str:
    """Concatena API_URL y una ruta asegurando que haya exactamente una '/'."""
    return f"{API_URL.rstrip('/')}/{path.lstrip('/')}"


def _manejar_respuesta(resp: requests.Response) -> tuple[bool, Any]:
    """
    Normaliza la respuesta de requests en el contrato (exito, datos).

    2xx -> (True, json). Si el body no es JSON se devuelve texto crudo.
    4xx/5xx -> (False, detalle). FastAPI expone el error en el campo 'detail';
    si falta, se usa el texto del response o el código HTTP como último recurso.
    """
    if 200 <= resp.status_code < 300:
        try:
            return True, resp.json()
        except ValueError:
            return True, resp.text

    # Error: intentar extraer FastAPI 'detail', si no, usar texto o código.
    try:
        cuerpo = resp.json()
        detalle = cuerpo.get("detail") if isinstance(cuerpo, dict) else None
        if detalle:
            return False, str(detalle)
    except ValueError:
        pass
    return False, resp.text or f"Error HTTP {resp.status_code}"


def _request(metodo: str, path: str, **kwargs) -> tuple[bool, Any]:
    """Envoltorio único para requests: inyecta timeout y atrapa excepciones de red."""
    try:
        resp = requests.request(metodo, _url(path), timeout=_TIMEOUT_S, **kwargs)
    except requests.Timeout:
        return False, "El servidor tardó demasiado en responder. Intenta de nuevo."
    except requests.ConnectionError:
        return False, "No se pudo conectar con el servidor. Revisa tu conexión."
    except requests.RequestException as exc:
        return False, f"Error de red: {exc}"
    return _manejar_respuesta(resp)


# ---------- Health ----------


def ping() -> tuple[bool, Any]:
    """GET /. Útil para despertar el servicio de Render al arrancar la app."""
    return _request("GET", "/")


# ---------- Verificación de disponibilidad ----------


def verificar_correo(correo: str) -> tuple[bool, Any]:
    """GET /verificar/correo/{correo}. True/False en disponible."""
    return _request("GET", f"/verificar/correo/{quote(correo, safe='')}")


def verificar_usuario(nombre_usuario: str) -> tuple[bool, Any]:
    """GET /verificar/usuario/{nombre_usuario}."""
    return _request("GET", f"/verificar/usuario/{quote(nombre_usuario, safe='')}")


def verificar_codigo(codigo: str) -> tuple[bool, Any]:
    """GET /verificar/codigo/{codigo}. Disponibilidad de codigo_estudiante."""
    return _request("GET", f"/verificar/codigo/{quote(codigo, safe='')}")


# ---------- Usuarios ----------


def registrar_usuario(datos: dict) -> tuple[bool, Any]:
    """
    POST /usuarios/.

    datos debe incluir: nombre_completo, correo, nombre_usuario, contrasena, rol,
    y codigo_estudiante si rol == 'estudiante'.
    """
    return _request("POST", "/usuarios/", json=datos)


def login(identificador: str, contrasena: str) -> tuple[bool, Any]:
    """POST /login/. identificador acepta correo o nombre_usuario."""
    return _request(
        "POST",
        "/login/",
        json={"identificador": identificador, "contrasena": contrasena},
    )


def actualizar_usuario(usuario_id: int, cambios: dict) -> tuple[bool, Any]:
    """PUT /usuarios/{usuario_id}. Solo los campos presentes se actualizan."""
    return _request("PUT", f"/usuarios/{usuario_id}", json=cambios)


# ---------- Clases ----------


def crear_clase(datos: dict) -> tuple[bool, Any]:
    """POST /clases/. Requiere nombre y tutor_id; color_hex opcional."""
    return _request("POST", "/clases/", json=datos)


def listar_clases_usuario(usuario_id: int) -> tuple[bool, Any]:
    """GET /clases/usuario/{usuario_id}. Devuelve clases según el rol del usuario."""
    return _request("GET", f"/clases/usuario/{usuario_id}")


def inscribir_clase(estudiante_id: int, codigo_acceso: str) -> tuple[bool, Any]:
    """POST /clases/inscribir/. Inscribe a un estudiante por código de acceso."""
    return _request(
        "POST",
        "/clases/inscribir/",
        json={"estudiante_id": estudiante_id, "codigo_acceso": codigo_acceso},
    )


def buscar_clases(estudiante_id: int, q: str) -> tuple[bool, Any]:
    """GET /clases/buscar/?q=...&estudiante_id=.... Excluye las ya inscritas."""
    return _request(
        "GET",
        "/clases/buscar/",
        params={"q": q, "estudiante_id": estudiante_id},
    )


# ---------- Anuncios ----------


def listar_anuncios(clase_id: int) -> tuple[bool, Any]:
    """GET /clases/{clase_id}/anuncios/. Devuelve anuncios en orden DESC por fecha."""
    return _request("GET", f"/clases/{clase_id}/anuncios/")


def crear_anuncio(clase_id: int, contenido: str) -> tuple[bool, Any]:
    """POST /clases/{clase_id}/anuncios/."""
    return _request(
        "POST",
        f"/clases/{clase_id}/anuncios/",
        json={"contenido": contenido},
    )


# ---------- Notas ----------


def guardar_nota(datos: dict) -> tuple[bool, Any]:
    """
    POST /notas/.

    datos debe incluir titulo, contenido_formato ({texto, tags}), estudiante_id
    y opcionalmente clase_id (None para nota personal).
    """
    return _request("POST", "/notas/", json=datos)


def listar_notas(usuario_id: int) -> tuple[bool, Any]:
    """GET /notas/usuario/{usuario_id}. Notas del estudiante en orden DESC."""
    return _request("GET", f"/notas/usuario/{usuario_id}")
