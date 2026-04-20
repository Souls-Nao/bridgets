"""
Pantalla de registro de usuario.

Características clave:
- Verificación en vivo contra el backend (GET /verificar/*) para correo,
  nombre_usuario y codigo_estudiante. Se aplica debounce de 500 ms: cada
  pulsación cancela el check anterior y agenda uno nuevo. Además, cada
  invocación usa un contador incremental; si al volver del hilo el contador
  ha cambiado (el usuario siguió escribiendo) el resultado se descarta para
  evitar flashes de estado viejo.
- Validaciones cliente (longitudes) reflejan las del backend. Si cambian los
  límites en el backend, actualizar también aquí.
- El botón "Crear cuenta" se activa solo cuando las verificaciones visibles
  están en verde y los campos obligatorios tienen contenido válido.
- Al registrarse con éxito, se guarda la sesión y se navega al dashboard
  correspondiente al rol elegido.
"""

import threading
from typing import Callable

import customtkinter as ctk

import api_cliente
import sesion

from config import COLOR_ERROR, COLOR_OK


# Espera tras la última pulsación antes de consultar /verificar/*.
_DEBOUNCE_MS = 500


class PantallaRegistro(ctk.CTkFrame):
    """Formulario de registro con verificación en vivo de disponibilidad."""

    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        # Contenedor scrollable: algunos temas y DPI pueden apretar los 9 campos.
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=20, pady=20)

        tarjeta = ctk.CTkFrame(self._scroll, corner_radius=12)
        tarjeta.pack(padx=40, pady=20, fill="x")

        ctk.CTkLabel(
            tarjeta, text="Crear cuenta", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(padx=28, pady=(24, 18))

        # --- Campos simples ---
        self._nombre = self._campo_simple(tarjeta, "Nombre completo")
        self._correo, self._correo_estado = self._campo_con_estado(tarjeta, "Correo")
        self._usuario, self._usuario_estado = self._campo_con_estado(
            tarjeta, "Nombre de usuario"
        )
        self._contrasena = self._campo_simple(tarjeta, "Contraseña", show="●")
        self._confirmar = self._campo_simple(tarjeta, "Confirmar contraseña", show="●")

        # --- Rol ---
        self._rol_var = ctk.StringVar(value="estudiante")
        fila_rol = ctk.CTkFrame(tarjeta, fg_color="transparent")
        fila_rol.pack(padx=28, pady=(12, 4), fill="x")
        ctk.CTkLabel(fila_rol, text="Rol:").pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(
            fila_rol, text="Estudiante", variable=self._rol_var,
            value="estudiante", command=self._on_cambio_rol,
        ).pack(side="left", padx=8)
        ctk.CTkRadioButton(
            fila_rol, text="Tutor", variable=self._rol_var,
            value="tutor", command=self._on_cambio_rol,
        ).pack(side="left", padx=8)

        # --- Código de estudiante (solo visible si rol==estudiante) ---
        self._contenedor_codigo = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self._contenedor_codigo.pack(padx=0, pady=0, fill="x")
        self._codigo, self._codigo_estado = self._campo_con_estado(
            self._contenedor_codigo, "Código de estudiante"
        )

        # --- Mensaje de error/éxito global + botones ---
        self._mensaje = ctk.CTkLabel(
            tarjeta, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR
        )
        self._mensaje.pack(padx=28, pady=(14, 2))

        self._boton_registrar = ctk.CTkButton(
            tarjeta, text="Crear cuenta", command=self._intentar_registro
        )
        self._boton_registrar.pack(padx=28, pady=(8, 6), fill="x")

        ctk.CTkButton(
            tarjeta,
            text="Volver al login",
            fg_color="transparent",
            border_width=1,
            text_color=("#1F2937", "#F3F4F6"),
            command=lambda: self.app.mostrar_vista("login"),
        ).pack(padx=28, pady=(0, 22), fill="x")

        # --- Enganches de verificación en vivo (debounce) ---
        # Estado: _checks[nombre] = (after_id, token_activo, resultado_disponible_bool_o_None)
        self._checks: dict[str, dict] = {
            "correo": {"after": None, "token": 0, "ok": None},
            "usuario": {"after": None, "token": 0, "ok": None},
            "codigo": {"after": None, "token": 0, "ok": None},
        }
        self._correo.bind(
            "<KeyRelease>",
            lambda _e: self._agendar_verificacion(
                "correo", self._correo.get().strip(),
                api_cliente.verificar_correo, self._correo_estado,
                min_len=3, max_len=120,
            ),
        )
        self._usuario.bind(
            "<KeyRelease>",
            lambda _e: self._agendar_verificacion(
                "usuario", self._usuario.get().strip(),
                api_cliente.verificar_usuario, self._usuario_estado,
                min_len=3, max_len=60,
            ),
        )
        self._codigo.bind(
            "<KeyRelease>",
            lambda _e: self._agendar_verificacion(
                "codigo", self._codigo.get().strip(),
                api_cliente.verificar_codigo, self._codigo_estado,
                min_len=1, max_len=20, opcional=True,
            ),
        )

    # ------------------------------------------------------------------
    # Helpers de UI para construir campos.
    # ------------------------------------------------------------------

    def _campo_simple(self, master, etiqueta: str, show: str | None = None) -> ctk.CTkEntry:
        """Fila con label y entry a todo el ancho, sin indicador de estado."""
        fila = ctk.CTkFrame(master, fg_color="transparent")
        fila.pack(padx=28, pady=6, fill="x")
        ctk.CTkLabel(fila, text=etiqueta, width=160, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(fila, show=show or "")
        entry.pack(side="left", fill="x", expand=True)
        return entry

    def _campo_con_estado(self, master, etiqueta: str) -> tuple[ctk.CTkEntry, ctk.CTkLabel]:
        """Fila con label, entry y label de estado (✓/✗/…) a la derecha."""
        fila = ctk.CTkFrame(master, fg_color="transparent")
        fila.pack(padx=28, pady=6, fill="x")
        ctk.CTkLabel(fila, text=etiqueta, width=160, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(fila)
        entry.pack(side="left", fill="x", expand=True)
        estado = ctk.CTkLabel(fila, text="", width=28, anchor="center")
        estado.pack(side="left", padx=(6, 0))
        return entry, estado

    # ------------------------------------------------------------------
    # Debounce + verificación en vivo.
    # ------------------------------------------------------------------

    def _agendar_verificacion(
        self,
        clave: str,
        valor: str,
        llamador: Callable[[str], tuple[bool, object]],
        label_estado: ctk.CTkLabel,
        min_len: int,
        max_len: int,
        opcional: bool = False,
    ) -> None:
        """Cancela el after previo y agenda un nuevo check a _DEBOUNCE_MS."""
        est = self._checks[clave]
        if est["after"] is not None:
            self.after_cancel(est["after"])
            est["after"] = None

        # Campo vacío opcional: no es error, simplemente sin estado.
        if not valor and opcional:
            est["ok"] = True
            label_estado.configure(text="", text_color="#6B7280")
            return

        # Validación local previa (evita pegarle al backend con basura).
        if len(valor) < min_len or len(valor) > max_len:
            est["ok"] = False
            label_estado.configure(
                text="✗" if valor else "",
                text_color=COLOR_ERROR,
            )
            return

        label_estado.configure(text="…", text_color="#6B7280")
        est["token"] += 1
        token = est["token"]
        est["after"] = self.after(
            _DEBOUNCE_MS,
            lambda: self._lanzar_verificacion(clave, valor, llamador, label_estado, token),
        )

    def _lanzar_verificacion(
        self,
        clave: str,
        valor: str,
        llamador: Callable[[str], tuple[bool, object]],
        label_estado: ctk.CTkLabel,
        token: int,
    ) -> None:
        """Ejecuta la consulta HTTP en un hilo para no bloquear la UI."""

        def trabajo() -> None:
            exito, datos = llamador(valor)
            self.after(
                0,
                lambda: self._aplicar_verificacion(
                    clave, token, exito, datos, label_estado
                ),
            )

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_verificacion(
        self,
        clave: str,
        token: int,
        exito: bool,
        datos,
        label_estado: ctk.CTkLabel,
    ) -> None:
        """Escribe el estado en la UI si el token sigue vigente."""
        est = self._checks[clave]
        if token != est["token"]:
            # El usuario siguió escribiendo: hay una verificación más reciente.
            return

        if not exito:
            est["ok"] = False
            label_estado.configure(text="!", text_color=COLOR_ERROR)
            return

        disponible = bool(datos.get("disponible")) if isinstance(datos, dict) else False
        est["ok"] = disponible
        label_estado.configure(
            text="✓" if disponible else "✗",
            text_color=COLOR_OK if disponible else COLOR_ERROR,
        )

    # ------------------------------------------------------------------
    # Cambio de rol: ocultar/mostrar el campo código.
    # ------------------------------------------------------------------

    def _on_cambio_rol(self) -> None:
        """Muestra el código sólo para estudiantes; al ser tutor, lo limpia."""
        if self._rol_var.get() == "estudiante":
            self._contenedor_codigo.pack(padx=0, pady=0, fill="x")
        else:
            self._contenedor_codigo.pack_forget()
            self._codigo.delete(0, "end")
            self._codigo_estado.configure(text="")
            self._checks["codigo"]["ok"] = True

    # ------------------------------------------------------------------
    # Envío del formulario.
    # ------------------------------------------------------------------

    def _intentar_registro(self) -> None:
        """Valida todo, construye el payload y dispara POST /usuarios/."""
        nombre = self._nombre.get().strip()
        correo = self._correo.get().strip()
        usuario = self._usuario.get().strip()
        contrasena = self._contrasena.get()
        confirmar = self._confirmar.get()
        rol = self._rol_var.get()
        codigo = self._codigo.get().strip() if rol == "estudiante" else None

        # Validación local defensiva: si el usuario hace click rápido
        # antes de que terminen las verificaciones, abortar con mensaje claro.
        if not nombre or len(nombre) > 120:
            self._mostrar_error("Ingresa tu nombre completo.")
            return
        if self._checks["correo"]["ok"] is not True:
            self._mostrar_error("Corrige el correo antes de continuar.")
            return
        if self._checks["usuario"]["ok"] is not True:
            self._mostrar_error("Corrige el nombre de usuario antes de continuar.")
            return
        if len(contrasena) < 6 or len(contrasena) > 128:
            self._mostrar_error("La contraseña debe tener entre 6 y 128 caracteres.")
            return
        if contrasena != confirmar:
            self._mostrar_error("Las contraseñas no coinciden.")
            return
        if rol == "estudiante" and codigo and self._checks["codigo"]["ok"] is not True:
            self._mostrar_error("Corrige el código de estudiante.")
            return

        payload = {
            "nombre_completo": nombre,
            "correo": correo,
            "nombre_usuario": usuario,
            "contrasena": contrasena,
            "rol": rol,
        }
        # Sólo incluir codigo_estudiante cuando aplica y no está vacío (backend lo acepta nullable).
        if rol == "estudiante" and codigo:
            payload["codigo_estudiante"] = codigo

        self._boton_registrar.configure(state="disabled", text="Creando cuenta...")
        self._mensaje.configure(text="", text_color=COLOR_ERROR)
        threading.Thread(
            target=self._trabajo_registro, args=(payload,), daemon=True
        ).start()

    def _trabajo_registro(self, payload: dict) -> None:
        """Hilo: POST /usuarios/ y, si todo sale bien, login con el mismo identificador."""
        exito, datos = api_cliente.registrar_usuario(payload)
        self.after(0, lambda: self._aplicar_registro(exito, datos))

    def _aplicar_registro(self, exito: bool, datos) -> None:
        """Navega al dashboard o muestra el error devuelto por el backend."""
        self._boton_registrar.configure(state="normal", text="Crear cuenta")
        if not exito:
            self._mostrar_error(str(datos))
            return

        sesion.iniciar(datos)
        destino = "dashboard_tutor" if sesion.actual.rol == "tutor" else "dashboard_estudiante"
        self.app.mostrar_vista(destino)

    def _mostrar_error(self, texto: str) -> None:
        self._mensaje.configure(text=texto, text_color=COLOR_ERROR)
