"""
Configuración global del cliente de Bridgets.

Incluye:
- resource_path(): resuelve rutas a assets tanto en desarrollo como dentro del .exe
  de PyInstaller (usa sys._MEIPASS, el directorio temporal donde se descomprimen
  los datos al lanzar el ejecutable).
- API_URL: endpoint del backend en Render. Se puede sobrescribir con la variable
  de entorno BRIDGETS_API_URL para apuntar a localhost durante debugging puntual.
- Paleta de colores del producto.
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    Resuelve una ruta relativa a un asset empaquetado.

    En modo desarrollo devuelve la ruta relativa al directorio del archivo.
    En el .exe generado por PyInstaller usa sys._MEIPASS (carpeta temporal
    donde el bootloader descomprime los datos al arrancar).
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# URL del backend en Render (producción por defecto).
# Sobrescribible con BRIDGETS_API_URL para pruebas locales.
API_URL: str = os.environ.get("BRIDGETS_API_URL", "https://bridgets-api.onrender.com")

# Paleta de colores de la app.
COLOR_ESTUDIANTE: str = "#2B7CE9"
COLOR_TUTOR: str = "#F59E0B"
COLOR_OK: str = "#16A34A"
COLOR_ERROR: str = "#DC2626"
COLOR_FONDO: str = "#FFFFFF"
