"""
Pantalla de inicio de sesión.

El backend acepta correo o nombre_usuario en el mismo campo 'identificador',
así que aquí solo se presenta un campo único con etiqueta explicativa. El login
se ejecuta en un hilo para no congelar la UI durante el round-trip a Render.
"""

import threading

import customtkinter as ctk

import api_cliente
import sesion

from config import COLOR_ERROR, COLOR_OK


class PantallaLogin(ctk.CTkFrame):
    """Formulario de login con validación mínima y navegación al registro."""

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        tarjeta = ctk.CTkFrame(self, corner_radius=12, width=400)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            tarjeta, text="Iniciar sesión", font=ctk.CTkFont(size=24, weight="bold")
        ).pack(padx=32, pady=(28, 4))

        ctk.CTkLabel(
            tarjeta,
            text="Usa tu correo o nombre de usuario",
            font=ctk.CTkFont(size=11),
            text_color="#6B7280",
        ).pack(padx=32, pady=(0, 20))

        self._identificador = ctk.CTkEntry(
            tarjeta, placeholder_text="correo o usuario", width=320
        )
        self._identificador.pack(padx=32, pady=6)

        self._contrasena = ctk.CTkEntry(
            tarjeta, placeholder_text="contraseña", width=320, show="●"
        )
        self._contrasena.pack(padx=32, pady=6)
        # Enter en el campo de contraseña dispara el login.
        self._contrasena.bind("<Return>", lambda _e: self._intentar_login())

        self._mensaje = ctk.CTkLabel(
            tarjeta, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR
        )
        self._mensaje.pack(padx=32, pady=(10, 0))

        self._boton_ingresar = ctk.CTkButton(
            tarjeta, text="Ingresar", width=320, command=self._intentar_login
        )
        self._boton_ingresar.pack(padx=32, pady=(10, 8))

        ctk.CTkButton(
            tarjeta,
            text="Crear cuenta",
            width=320,
            fg_color="transparent",
            border_width=1,
            text_color=("#1F2937", "#F3F4F6"),
            command=lambda: self.app.mostrar_vista("registro"),
        ).pack(padx=32, pady=(0, 28))

    def _intentar_login(self) -> None:
        """Valida campos, deshabilita el botón y lanza el login en un hilo."""
        identificador = self._identificador.get().strip()
        contrasena = self._contrasena.get()

        if not identificador or not contrasena:
            self._mostrar_error("Ingresa usuario/correo y contraseña.")
            return

        self._boton_ingresar.configure(state="disabled", text="Ingresando...")
        self._mensaje.configure(text="", text_color=COLOR_ERROR)
        threading.Thread(
            target=self._trabajo_login,
            args=(identificador, contrasena),
            daemon=True,
        ).start()

    def _trabajo_login(self, identificador: str, contrasena: str) -> None:
        """Ejecuta el login y programa la actualización de UI en el hilo principal."""
        exito, datos = api_cliente.login(identificador, contrasena)
        self.after(0, lambda: self._aplicar_resultado(exito, datos))

    def _aplicar_resultado(self, exito: bool, datos) -> None:
        """Navega al dashboard correspondiente o muestra el error devuelto."""
        self._boton_ingresar.configure(state="normal", text="Ingresar")
        if not exito:
            self._mostrar_error(str(datos))
            return

        sesion.iniciar(datos)
        self._mensaje.configure(text="Sesión iniciada", text_color=COLOR_OK)
        destino = "dashboard_tutor" if sesion.actual.rol == "tutor" else "dashboard_estudiante"
        self.app.mostrar_vista(destino)

    def _mostrar_error(self, texto: str) -> None:
        self._mensaje.configure(text=texto, text_color=COLOR_ERROR)
