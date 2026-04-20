"""
Dashboard del estudiante (stub de Batch H, implementación completa en Batch J).

Placeholder para cerrar el ciclo de autenticación: muestra datos del alumno
y ofrece logout. Batch J añade lista de clases inscritas, buscador por
código, panel de anuncios y sección "Mis notas" con editor enriquecido.
"""

import customtkinter as ctk

import sesion


class PantallaDashboardEstudiante(ctk.CTkFrame):
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
        datos_detalle = (
            f"Rol: {sesion.actual.rol}  |  Usuario: {sesion.actual.nombre_usuario}"
        )
        if sesion.actual.codigo_estudiante:
            datos_detalle += f"  |  Código: {sesion.actual.codigo_estudiante}"
        ctk.CTkLabel(
            contenedor,
            text=datos_detalle,
            font=ctk.CTkFont(size=12),
            text_color="#6B7280",
        ).pack(pady=(0, 20))
        ctk.CTkLabel(
            contenedor,
            text="Dashboard del estudiante — implementación completa en Batch J.",
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF",
        ).pack(pady=(0, 24))

        ctk.CTkButton(
            contenedor, text="Cerrar sesión", width=220, command=self._cerrar_sesion
        ).pack()

    def _cerrar_sesion(self) -> None:
        sesion.cerrar()
        self.app.mostrar_vista("login")
