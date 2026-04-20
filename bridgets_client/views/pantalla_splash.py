"""
Vista inicial: ping al backend y auto-navegación.

Flujo en un solo hilo de trabajo (para no encadenar after() por red):
1. api_cliente.ping() despierta a Render si estaba frío (hasta ~75 s).
2. Si hay sesión persistida (sesion.cargar()), se valida llamando a
   listar_clases_usuario(id) — un GET liviano que 404 si el usuario
   ya no existe o fue borrado. Si falla, se cierra la sesión: mejor
   mandar al usuario al login que mostrarle un dashboard vacío.
3. Según el rol se navega al dashboard correspondiente; si no hay
   sesión, se navega al login.

En fallo de ping se mantiene la pantalla con botón Reintentar.
"""

import threading

import customtkinter as ctk

import api_cliente
import sesion


class PantallaSplash(ctk.CTkFrame):
    """Arranque: ping + carga de sesión + navegación automática."""

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            contenedor, text="Bridgets", font=ctk.CTkFont(size=34, weight="bold")
        ).pack(pady=(0, 12))

        self._estado = ctk.CTkLabel(
            contenedor,
            text="Conectando con el servidor...",
            font=ctk.CTkFont(size=14),
        )
        self._estado.pack(pady=(0, 4))

        ctk.CTkLabel(
            contenedor,
            text="Si es la primera conexión del día, puede tardar hasta 1 minuto.",
            font=ctk.CTkFont(size=11),
            text_color="#6B7280",
        ).pack(pady=(0, 20))

        # Botón oculto por defecto: sólo aparece en fallo para ofrecer reintentar.
        self._boton_reintentar = ctk.CTkButton(
            contenedor, text="Reintentar", width=200, command=self._intentar
        )

        self._intentar()

    def _intentar(self) -> None:
        """Oculta el botón y dispara el arranque en background."""
        self._estado.configure(text="Conectando con el servidor...")
        self._boton_reintentar.pack_forget()
        threading.Thread(target=self._trabajo, daemon=True).start()

    def _trabajo(self) -> None:
        """Hilo worker: ping + cargar/validar sesión."""
        exito, datos = api_cliente.ping()
        if not exito:
            self.after(0, lambda: self._on_fallo_ping(datos))
            return

        # Intentar rehidratar sesión; si falla la validación, limpiarla.
        if sesion.cargar():
            ok, _ = api_cliente.listar_clases_usuario(sesion.actual.usuario_id)
            if not ok:
                sesion.cerrar()

        self.after(0, self._navegar)

    def _on_fallo_ping(self, mensaje) -> None:
        """Deja la UI en estado de error con botón Reintentar visible."""
        self._estado.configure(text=f"No se pudo conectar: {mensaje}")
        self._boton_reintentar.pack()

    def _navegar(self) -> None:
        """Decide la vista siguiente según si hay sesión válida."""
        if sesion.actual.autenticada:
            self._estado.configure(text=f"Bienvenido de vuelta, {sesion.actual.nombre_completo}")
            destino = "dashboard_tutor" if sesion.actual.rol == "tutor" else "dashboard_estudiante"
        else:
            self._estado.configure(text="Listo")
            destino = "login"
        # Pequeña demora para que el usuario alcance a leer el mensaje.
        self.after(400, lambda: self.app.mostrar_vista(destino))
