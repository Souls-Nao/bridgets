"""
Dashboard del tutor (stub de Batch H, implementación completa en Batch I).

Hoy sólo muestra los datos del tutor autenticado y un botón de logout para
cerrar el ciclo básico de la Fase 2 (splash → login/registro → dashboard).
Batch I reemplaza el cuerpo por la lista de clases creadas, el formulario
de creación de clase y el panel de anuncios.
"""

import customtkinter as ctk

import sesion


class PantallaDashboardTutor(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            contenedor,
            text=f"Bienvenido, {sesion.actual.nombre_completo}",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(0, 6))
        ctk.CTkLabel(
            contenedor,
            text=f"Rol: {sesion.actual.rol}  |  Usuario: {sesion.actual.nombre_usuario}",
            font=ctk.CTkFont(size=12),
            text_color="#6B7280",
        ).pack(pady=(0, 20))
        ctk.CTkLabel(
            contenedor,
            text="Dashboard del tutor — implementación completa en Batch I.",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF",
        ).pack(pady=(0, 24))

        ctk.CTkButton(
            contenedor, text="Cerrar sesión", width=220, command=self._cerrar_sesion
        ).pack()

    def _cerrar_sesion(self) -> None:
        sesion.cerrar()
        self.app.mostrar_vista("login")
