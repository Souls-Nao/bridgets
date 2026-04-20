"""
Punto de entrada del cliente de escritorio de Bridgets.

Arquitectura de navegación:
- AplicacionBridgets hereda de CTk y es la ventana única.
- Cada vista es un CTkFrame que recibe (master, app) en __init__ y se coloca
  con grid() sobre el contenedor principal.
- mostrar_vista(nombre, **kwargs) destruye la vista anterior, construye la
  nueva y le pasa kwargs al constructor (útil para navegación con contexto,
  p. ej. abrir_clase(clase_id=3)).
- Las vistas se importan perezosamente dentro de mostrar_vista para evitar
  imports circulares entre vistas y por si alguna importa recursos pesados.

El arranque lanza la vista 'splash', que hace un ping al backend de Render
(cold start ~50 s en Free) y al volver verde navega a 'login'. Si el ping
falla el splash muestra el error y ofrece reintentar.
"""

import customtkinter as ctk


class AplicacionBridgets(ctk.CTk):
    """Ventana raíz. Administra la navegación entre vistas."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Bridgets")
        self.geometry("1024x680")
        self.minsize(900, 600)

        # Contenedor que ocupa toda la ventana; cada vista se monta aquí.
        self._contenedor = ctk.CTkFrame(self, corner_radius=0)
        self._contenedor.pack(fill="both", expand=True)

        self._vista_actual: ctk.CTkFrame | None = None

    def mostrar_vista(self, nombre: str, **kwargs) -> None:
        """
        Reemplaza la vista visible por otra identificada por 'nombre'.

        Las kwargs se pasan al constructor de la vista (master=contenedor, app=self, **kwargs).
        """
        if self._vista_actual is not None:
            self._vista_actual.destroy()
            self._vista_actual = None

        clase_vista = self._resolver_vista(nombre)
        vista = clase_vista(self._contenedor, self, **kwargs)
        vista.pack(fill="both", expand=True)
        self._vista_actual = vista

    @staticmethod
    def _resolver_vista(nombre: str):
        """
        Import perezoso de la clase de vista por nombre.

        Se mantiene un mapa explícito (no introspección) para que los errores
        sean claros al equivocarse de nombre y para que PyInstaller detecte
        los imports estáticamente al empaquetar.
        """
        if nombre == "splash":
            from views.pantalla_splash import PantallaSplash
            return PantallaSplash
        if nombre == "login":
            from views.pantalla_login import PantallaLogin
            return PantallaLogin
        if nombre == "registro":
            from views.pantalla_registro import PantallaRegistro
            return PantallaRegistro
        if nombre == "dashboard_tutor":
            from views.pantalla_dashboard_tutor import PantallaDashboardTutor
            return PantallaDashboardTutor
        if nombre == "dashboard_estudiante":
            from views.pantalla_dashboard_estudiante import PantallaDashboardEstudiante
            return PantallaDashboardEstudiante
        raise ValueError(f"Vista desconocida: {nombre}")


def main() -> None:
    """Configura el tema y lanza la aplicación."""
    ctk.set_appearance_mode("light")
    # set_default_color_theme acepta archivos JSON o nombres predefinidos.
    # Usamos 'blue' como base y sobrescribimos acentos por widget en cada vista.
    ctk.set_default_color_theme("blue")

    app = AplicacionBridgets()
    # Arranca por splash (que hará ping al backend y navegará a login).
    app.mostrar_vista("splash")
    app.mainloop()


if __name__ == "__main__":
    main()
