"""
Punto de entrada del cliente de escritorio de Bridgets.

Placeholder de Fase 0. En Fase 2 se implementa:
- Ventana root con customtkinter (modo light).
- Método cambiar_vista(nombre) para intercambiar frames.
- Arranque: ViewSplash -> (ping al backend) -> ViewLogin.
"""

from config import API_URL, resource_path


def main() -> None:
    """Entrada principal del cliente. Se implementa en Fase 2."""
    # Uso temporal de imports para validar empaquetado con PyInstaller.
    _ = resource_path("assets")
    _ = API_URL


if __name__ == "__main__":
    main()
