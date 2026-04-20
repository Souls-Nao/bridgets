"""
Vista inicial: hace un ping al backend de Render y espera a que despierte.

Render Free suspende el servicio tras ~15 min de inactividad; la primera
petición puede tardar hasta 50 s. La splash absorbe esa espera con un
mensaje y un spinner textual para que el usuario no crea que la app se colgó.

Flujo:
1. Muestra "Conectando con el servidor...".
2. Lanza un Thread que llama api_cliente.ping() (bloqueante hasta 75 s).
3. En el hilo UI (vía self.after) muestra éxito o error.
4. Al éxito habilita el botón Continuar, que navega a 'login'.
5. Al fallo muestra el error y habilita un botón "Reintentar".
"""

import threading

import customtkinter as ctk

import api_cliente


class PantallaSplash(ctk.CTkFrame):
    """Carga inicial con ping al backend."""

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        # Layout: todo centrado verticalmente usando un frame interno con place.
        contenedor = ctk.CTkFrame(self, fg_color="transparent")
        contenedor.place(relx=0.5, rely=0.5, anchor="center")

        self._titulo = ctk.CTkLabel(
            contenedor, text="Bridgets", font=ctk.CTkFont(size=34, weight="bold")
        )
        self._titulo.pack(pady=(0, 12))

        self._estado = ctk.CTkLabel(
            contenedor,
            text="Conectando con el servidor...",
            font=ctk.CTkFont(size=14),
        )
        self._estado.pack(pady=(0, 4))

        self._detalle = ctk.CTkLabel(
            contenedor,
            text="Si es la primera conexión del día, puede tardar hasta 1 minuto.",
            font=ctk.CTkFont(size=11),
            text_color="#6B7280",
        )
        self._detalle.pack(pady=(0, 20))

        self._boton = ctk.CTkButton(
            contenedor,
            text="Continuar",
            width=200,
            state="disabled",
            command=self._ir_a_login,
        )
        self._boton.pack()

        # Arranca el ping en background.
        self._intentar_ping()

    def _intentar_ping(self) -> None:
        """Lanza el ping en un thread para no bloquear el loop de Tk."""
        self._estado.configure(text="Conectando con el servidor...")
        self._boton.configure(state="disabled", text="Continuar", command=self._ir_a_login)
        threading.Thread(target=self._trabajo_ping, daemon=True).start()

    def _trabajo_ping(self) -> None:
        """Ejecuta el ping y programa la actualización de UI en el hilo principal."""
        exito, datos = api_cliente.ping()
        # after(0, ...) encola en el loop de Tk: único sitio seguro para tocar widgets.
        self.after(0, lambda: self._aplicar_resultado(exito, datos))

    def _aplicar_resultado(self, exito: bool, datos) -> None:
        """Actualiza la UI según el resultado del ping."""
        if exito:
            self._estado.configure(text="Listo")
            self._boton.configure(state="normal")
            return

        self._estado.configure(text=f"No se pudo conectar: {datos}")
        self._boton.configure(
            state="normal", text="Reintentar", command=self._intentar_ping
        )

    def _ir_a_login(self) -> None:
        """Navega a la pantalla de login (disponible desde Batch H)."""
        self.app.mostrar_vista("login")
