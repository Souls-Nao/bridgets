"""
Dashboard del tutor.

Layout:
┌──────────────────────────────────────────────────────────────┐
│ Topbar: Bridgets  —  Hola {nombre}           [Cerrar sesión] │
├───────────────────┬──────────────────────────────────────────┤
│ Sidebar clases    │ Detalle de la clase seleccionada:        │
│  [+ Nueva clase]  │  · nombre, horario, color                │
│  · Clase 1        │  · código de acceso (para compartir)     │
│  · Clase 2        │  · Anuncios (DESC) + nuevo anuncio       │
└───────────────────┴──────────────────────────────────────────┘

Decisiones:
- "Nueva clase" se abre como CTkToplevel modal para no ocupar el detalle.
- "Nuevo anuncio" es inline dentro del detalle (CTkTextbox + botón Publicar):
  el acto de publicar es frecuente y no vale el overhead de una ventana aparte.
- Todas las llamadas HTTP van en hilo; las actualizaciones de UI regresan al
  loop con after(0, ...) para no tocar widgets desde hilos worker.
- Los refrescos tras crear clase/anuncio se hacen pidiendo de nuevo al backend
  (simple y consistente; los volúmenes son bajos y evita estados inconsistentes).
"""

import re
import threading
import tkinter as tk

import customtkinter as ctk

import api_cliente
import sesion

from config import COLOR_ERROR, COLOR_OK, COLOR_TUTOR


_PATRON_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class PantallaDashboardTutor(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        self._clases: list[dict] = []
        self._clase_activa: dict | None = None

        self._construir_topbar()
        self._construir_cuerpo()

        self._cargar_clases()

    # ------------------------------------------------------------------
    # Construcción de la estructura estática.
    # ------------------------------------------------------------------

    def _construir_topbar(self) -> None:
        topbar = ctk.CTkFrame(self, corner_radius=0, height=52, fg_color=COLOR_TUTOR)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar,
            text="Bridgets",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="white",
        ).pack(side="left", padx=18)
        ctk.CTkLabel(
            topbar,
            text=f"Hola, {sesion.actual.nombre_completo}",
            text_color="white",
        ).pack(side="left", padx=6)
        ctk.CTkButton(
            topbar,
            text="Cerrar sesión",
            width=120,
            fg_color="transparent",
            border_width=1,
            border_color="white",
            text_color="white",
            command=self._cerrar_sesion,
        ).pack(side="right", padx=14)

    def _construir_cuerpo(self) -> None:
        cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        cuerpo.pack(fill="both", expand=True, padx=12, pady=12)

        # --- Sidebar ---
        sidebar = ctk.CTkFrame(cuerpo, width=260)
        sidebar.pack(side="left", fill="y", padx=(0, 12))
        sidebar.pack_propagate(False)

        ctk.CTkButton(
            sidebar, text="+ Nueva clase", command=self._abrir_dialogo_nueva_clase
        ).pack(padx=12, pady=12, fill="x")

        self._lista_frame = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self._lista_frame.pack(fill="both", expand=True, padx=6, pady=6)

        # --- Detalle ---
        self._detalle_frame = ctk.CTkFrame(cuerpo)
        self._detalle_frame.pack(side="left", fill="both", expand=True)
        self._mostrar_placeholder_detalle()

    # ------------------------------------------------------------------
    # Clases: carga y render de la sidebar.
    # ------------------------------------------------------------------

    def _cargar_clases(self) -> None:
        """GET /clases/usuario/{id} en hilo y repuebla la sidebar."""
        self._limpiar_lista("Cargando...")
        usuario_id = sesion.actual.usuario_id

        def trabajo() -> None:
            exito, datos = api_cliente.listar_clases_usuario(usuario_id)
            self.after(0, lambda: self._aplicar_clases(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_clases(self, exito: bool, datos) -> None:
        if not exito:
            self._limpiar_lista(f"Error: {datos}")
            return
        self._clases = list(datos) if isinstance(datos, list) else []
        self._render_lista_clases()

    def _limpiar_lista(self, mensaje: str = "") -> None:
        """Vacía la sidebar y opcionalmente muestra un mensaje en su lugar."""
        for hijo in self._lista_frame.winfo_children():
            hijo.destroy()
        if mensaje:
            ctk.CTkLabel(
                self._lista_frame,
                text=mensaje,
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
            ).pack(pady=10)

    def _render_lista_clases(self) -> None:
        self._limpiar_lista()
        if not self._clases:
            ctk.CTkLabel(
                self._lista_frame,
                text="Aún no has creado ninguna clase.",
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
                wraplength=220,
            ).pack(pady=16, padx=10)
            return

        for clase in self._clases:
            self._render_entrada_clase(clase)

    def _render_entrada_clase(self, clase: dict) -> None:
        # Botón "tarjeta" por clase: usar fg_color según color_hex para identificarla.
        boton = ctk.CTkButton(
            self._lista_frame,
            text=clase["nombre"],
            anchor="w",
            height=44,
            fg_color=clase.get("color_hex", "#2B7CE9"),
            hover_color="#1E3A8A",
            command=lambda c=clase: self._seleccionar_clase(c),
        )
        boton.pack(fill="x", pady=4, padx=4)

    # ------------------------------------------------------------------
    # Detalle de la clase seleccionada.
    # ------------------------------------------------------------------

    def _mostrar_placeholder_detalle(self) -> None:
        for hijo in self._detalle_frame.winfo_children():
            hijo.destroy()
        ctk.CTkLabel(
            self._detalle_frame,
            text="Selecciona una clase o crea una nueva.",
            font=ctk.CTkFont(size=14),
            text_color="#6B7280",
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _seleccionar_clase(self, clase: dict) -> None:
        self._clase_activa = clase
        self._render_detalle_clase()

    def _render_detalle_clase(self) -> None:
        """Pinta cabecera con datos + lista de anuncios + composer."""
        clase = self._clase_activa
        assert clase is not None
        for hijo in self._detalle_frame.winfo_children():
            hijo.destroy()

        # --- Cabecera con datos de la clase ---
        cabecera = ctk.CTkFrame(self._detalle_frame, corner_radius=10)
        cabecera.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            cabecera,
            text=clase["nombre"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 4))
        if clase.get("descripcion"):
            ctk.CTkLabel(
                cabecera,
                text=clase["descripcion"],
                font=ctk.CTkFont(size=12),
                text_color="#6B7280",
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=16)
        if clase.get("horario"):
            ctk.CTkLabel(
                cabecera,
                text=f"Horario: {clase['horario']}",
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
            ).pack(anchor="w", padx=16, pady=(2, 0))

        fila_codigo = ctk.CTkFrame(cabecera, fg_color="transparent")
        fila_codigo.pack(fill="x", padx=16, pady=(10, 12))
        ctk.CTkLabel(
            fila_codigo, text="Código de acceso:", font=ctk.CTkFont(size=11)
        ).pack(side="left")
        ctk.CTkLabel(
            fila_codigo,
            text=clase["codigo_acceso"],
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left", padx=(6, 8))
        ctk.CTkButton(
            fila_codigo,
            text="Copiar",
            width=70,
            command=lambda: self._copiar_al_portapapeles(clase["codigo_acceso"]),
        ).pack(side="left")

        # --- Panel de anuncios ---
        ctk.CTkLabel(
            self._detalle_frame,
            text="Anuncios",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(10, 4))

        # Composer inline: publicar anuncio nuevo.
        composer = ctk.CTkFrame(self._detalle_frame, corner_radius=10)
        composer.pack(fill="x", padx=16, pady=(0, 10))
        self._anuncio_textbox = ctk.CTkTextbox(composer, height=70)
        self._anuncio_textbox.pack(fill="x", padx=12, pady=(12, 6))
        fila_btn = ctk.CTkFrame(composer, fg_color="transparent")
        fila_btn.pack(fill="x", padx=12, pady=(0, 12))
        self._anuncio_estado = ctk.CTkLabel(
            fila_btn, text="", font=ctk.CTkFont(size=11), text_color=COLOR_ERROR
        )
        self._anuncio_estado.pack(side="left")
        self._boton_publicar = ctk.CTkButton(
            fila_btn, text="Publicar", width=110, command=self._publicar_anuncio
        )
        self._boton_publicar.pack(side="right")

        # Lista de anuncios (se puebla async).
        self._anuncios_scroll = ctk.CTkScrollableFrame(
            self._detalle_frame, fg_color="transparent"
        )
        self._anuncios_scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._cargar_anuncios()

    # ------------------------------------------------------------------
    # Copia de código: usa el portapapeles nativo de Tk.
    # ------------------------------------------------------------------

    def _copiar_al_portapapeles(self, texto: str) -> None:
        # clipboard_* son métodos de tk.Misc: el root es self.app.
        self.app.clipboard_clear()
        self.app.clipboard_append(texto)

    # ------------------------------------------------------------------
    # Anuncios: carga, render y publicación.
    # ------------------------------------------------------------------

    def _cargar_anuncios(self) -> None:
        clase = self._clase_activa
        assert clase is not None
        clase_id = clase["id"]

        for hijo in self._anuncios_scroll.winfo_children():
            hijo.destroy()
        ctk.CTkLabel(
            self._anuncios_scroll, text="Cargando anuncios...", text_color="#6B7280"
        ).pack(pady=8)

        def trabajo() -> None:
            exito, datos = api_cliente.listar_anuncios(clase_id)
            self.after(0, lambda: self._aplicar_anuncios(clase_id, exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_anuncios(self, clase_id: int, exito: bool, datos) -> None:
        # Si el usuario cambió de clase mientras se cargaba, descartar.
        if self._clase_activa is None or self._clase_activa["id"] != clase_id:
            return
        for hijo in self._anuncios_scroll.winfo_children():
            hijo.destroy()

        if not exito:
            ctk.CTkLabel(
                self._anuncios_scroll,
                text=f"Error al cargar anuncios: {datos}",
                text_color=COLOR_ERROR,
            ).pack(pady=8)
            return

        anuncios = list(datos) if isinstance(datos, list) else []
        if not anuncios:
            ctk.CTkLabel(
                self._anuncios_scroll,
                text="Todavía no hay anuncios en esta clase.",
                text_color="#6B7280",
            ).pack(pady=8)
            return

        for anuncio in anuncios:
            self._render_anuncio(anuncio)

    def _render_anuncio(self, anuncio: dict) -> None:
        tarjeta = ctk.CTkFrame(self._anuncios_scroll, corner_radius=8)
        tarjeta.pack(fill="x", pady=4)
        ctk.CTkLabel(
            tarjeta,
            text=anuncio.get("contenido", ""),
            wraplength=640,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(10, 2))
        fecha = anuncio.get("fecha_creacion", "")
        ctk.CTkLabel(
            tarjeta,
            text=fecha,
            font=ctk.CTkFont(size=10),
            text_color="#9CA3AF",
            anchor="w",
        ).pack(anchor="w", padx=12, pady=(0, 10))

    def _publicar_anuncio(self) -> None:
        clase = self._clase_activa
        if clase is None:
            return

        contenido = self._anuncio_textbox.get("1.0", "end").strip()
        if not contenido:
            self._anuncio_estado.configure(
                text="El anuncio no puede estar vacío.", text_color=COLOR_ERROR
            )
            return

        self._boton_publicar.configure(state="disabled", text="Publicando...")
        self._anuncio_estado.configure(text="")
        clase_id = clase["id"]

        def trabajo() -> None:
            exito, datos = api_cliente.crear_anuncio(clase_id, contenido)
            self.after(0, lambda: self._aplicar_publicacion(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_publicacion(self, exito: bool, datos) -> None:
        self._boton_publicar.configure(state="normal", text="Publicar")
        if not exito:
            self._anuncio_estado.configure(text=str(datos), text_color=COLOR_ERROR)
            return
        self._anuncio_textbox.delete("1.0", "end")
        self._anuncio_estado.configure(text="Anuncio publicado.", text_color=COLOR_OK)
        self._cargar_anuncios()

    # ------------------------------------------------------------------
    # Diálogo de nueva clase (CTkToplevel modal).
    # ------------------------------------------------------------------

    def _abrir_dialogo_nueva_clase(self) -> None:
        DialogoNuevaClase(self.app, al_crear=self._on_clase_creada)

    def _on_clase_creada(self, clase: dict) -> None:
        """Callback del diálogo: refresca la lista y selecciona la nueva clase."""
        self._cargar_clases()
        self._seleccionar_clase(clase)

    # ------------------------------------------------------------------
    # Logout.
    # ------------------------------------------------------------------

    def _cerrar_sesion(self) -> None:
        sesion.cerrar()
        self.app.mostrar_vista("login")


class DialogoNuevaClase(ctk.CTkToplevel):
    """Modal para crear una clase. Notifica vía callback cuando termina."""

    def __init__(self, master, al_crear) -> None:
        super().__init__(master)
        self.title("Nueva clase")
        self.geometry("420x440")
        self.resizable(False, False)
        # grab_set hace la ventana modal: bloquea clics en el root hasta cerrarla.
        self.transient(master)
        self.after(50, self.grab_set)

        self._al_crear = al_crear

        ctk.CTkLabel(
            self, text="Nueva clase", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(18, 14))

        self._nombre = self._fila(self, "Nombre", placeholder="Matemáticas I")
        self._descripcion = self._fila(self, "Descripción", placeholder="(opcional)")
        self._horario = self._fila(self, "Horario", placeholder="Lun/Mié 8:00–10:00")

        # Color: entry con patrón + botón de color rápido.
        fila_color = ctk.CTkFrame(self, fg_color="transparent")
        fila_color.pack(padx=20, pady=6, fill="x")
        ctk.CTkLabel(fila_color, text="Color (#RRGGBB)", width=120, anchor="w").pack(
            side="left"
        )
        self._color = ctk.CTkEntry(fila_color)
        self._color.insert(0, "#2B7CE9")
        self._color.pack(side="left", fill="x", expand=True)
        self._muestra = tk.Frame(fila_color, width=26, height=26, bg="#2B7CE9")
        self._muestra.pack(side="left", padx=(6, 0))
        self._color.bind("<KeyRelease>", self._actualizar_muestra)

        self._mensaje = ctk.CTkLabel(self, text="", text_color=COLOR_ERROR)
        self._mensaje.pack(pady=(12, 0))

        self._boton = ctk.CTkButton(self, text="Crear clase", command=self._crear)
        self._boton.pack(pady=12, padx=20, fill="x")

        ctk.CTkButton(
            self,
            text="Cancelar",
            fg_color="transparent",
            border_width=1,
            text_color=("#1F2937", "#F3F4F6"),
            command=self.destroy,
        ).pack(pady=(0, 14), padx=20, fill="x")

    def _fila(self, master, etiqueta: str, placeholder: str = "") -> ctk.CTkEntry:
        contenedor = ctk.CTkFrame(master, fg_color="transparent")
        contenedor.pack(padx=20, pady=6, fill="x")
        ctk.CTkLabel(contenedor, text=etiqueta, width=120, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(contenedor, placeholder_text=placeholder)
        entry.pack(side="left", fill="x", expand=True)
        return entry

    def _actualizar_muestra(self, _evento=None) -> None:
        """Refresca el cuadradito de color si el hex es válido."""
        valor = self._color.get().strip()
        if _PATRON_HEX.match(valor):
            try:
                self._muestra.configure(bg=valor)
            except tk.TclError:
                pass

    def _crear(self) -> None:
        nombre = self._nombre.get().strip()
        descripcion = self._descripcion.get().strip() or None
        horario = self._horario.get().strip() or None
        color = self._color.get().strip()

        if not nombre:
            self._mensaje.configure(text="El nombre es obligatorio.")
            return
        if not _PATRON_HEX.match(color):
            self._mensaje.configure(text="El color debe tener formato #RRGGBB.")
            return

        payload: dict = {
            "nombre": nombre,
            "tutor_id": sesion.actual.usuario_id,
            "color_hex": color,
        }
        if descripcion:
            payload["descripcion"] = descripcion
        if horario:
            payload["horario"] = horario

        self._boton.configure(state="disabled", text="Creando...")
        self._mensaje.configure(text="")

        def trabajo() -> None:
            exito, datos = api_cliente.crear_clase(payload)
            self.after(0, lambda: self._aplicar(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar(self, exito: bool, datos) -> None:
        self._boton.configure(state="normal", text="Crear clase")
        if not exito:
            self._mensaje.configure(text=str(datos))
            return
        # Notificar al dashboard y cerrar.
        self._al_crear(datos)
        self.destroy()
