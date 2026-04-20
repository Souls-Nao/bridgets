"""
Dashboard del estudiante.

Secciones (pestañas de CTkTabview):
- "Mis clases": lista de clases inscritas, botón "+ Buscar o inscribirme" (modal
  con dos modos: por código o por búsqueda por nombre) y detalle de una clase
  con sus anuncios en modo lectura.
- "Mis notas": lista de notas propias con preview, botón "+ Nueva nota" que abre
  un editor con formato enriquecido. Las notas existentes se abren en modo
  lectura (el backend no soporta edición, son inmutables una vez creadas).

Editor enriquecido:
- tk.Text nativo soporta "tags" con rangos y estilos (weight, slant, underline,
  foreground, background) — mapeo directo a nuestro contrato
  contenido_formato = {texto, tags:[{inicio,fin,tipo,valor}]}.
- Los tags se nombran "tipo:valor" (p. ej. "color:#ff0000") para deduplicar
  configuración y poder serializar una sola vez por combinación.
- Al guardar: se recorren tag_names() y para cada uno se convierten sus
  tag_ranges() de "línea.columna" a offsets de caracter lineales.
- Al leer: se posiciona cada tag aplicando "1.0 + N chars" como índice.
"""

import threading
import tkinter as tk

import customtkinter as ctk

import api_cliente
import sesion

from config import COLOR_ERROR, COLOR_ESTUDIANTE, COLOR_OK


# Estilos disponibles en el editor: (tipo, etiqueta humana, generador de config de tag).
# Los tipos coinciden con el contrato del backend en TagFormato.
_ESTILOS_BOOLEANOS = {
    "negrita": {"font": ("Segoe UI", 13, "bold")},
    "cursiva": {"font": ("Segoe UI", 13, "italic")},
    "subrayado": {"underline": True},
}
_COLORES_TEXTO = ["#DC2626", "#2563EB", "#16A34A", "#F59E0B"]
_COLORES_RESALTADO = ["#FEF3C7", "#DBEAFE", "#DCFCE7", "#FEE2E2"]


class PantallaDashboardEstudiante(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master)
        self.app = app

        self._clases: list[dict] = []
        self._notas: list[dict] = []
        self._clase_activa: dict | None = None
        self._panel_nota: ctk.CTkFrame | None = None

        self._construir_topbar()
        self._construir_tabs()

        self._cargar_clases()
        self._cargar_notas()

    # ------------------------------------------------------------------
    # Estructura: topbar + pestañas.
    # ------------------------------------------------------------------

    def _construir_topbar(self) -> None:
        topbar = ctk.CTkFrame(self, corner_radius=0, height=52, fg_color=COLOR_ESTUDIANTE)
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

    def _construir_tabs(self) -> None:
        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=12, pady=12)

        self._tab_clases = self._tabs.add("Mis clases")
        self._tab_notas = self._tabs.add("Mis notas")

        self._construir_tab_clases()
        self._construir_tab_notas()

    # ==================================================================
    # TAB MIS CLASES
    # ==================================================================

    def _construir_tab_clases(self) -> None:
        # Columna izquierda: sidebar con lista + botón inscribirse.
        # Columna derecha: detalle de la clase seleccionada.
        izq = ctk.CTkFrame(self._tab_clases, width=240)
        izq.pack(side="left", fill="y", padx=(0, 10))
        izq.pack_propagate(False)

        ctk.CTkButton(
            izq,
            text="+ Buscar o inscribirme",
            command=self._abrir_dialogo_inscripcion,
        ).pack(padx=8, pady=8, fill="x")

        self._lista_clases_frame = ctk.CTkScrollableFrame(izq, fg_color="transparent")
        self._lista_clases_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self._detalle_clase_frame = ctk.CTkFrame(self._tab_clases)
        self._detalle_clase_frame.pack(side="left", fill="both", expand=True)
        self._mostrar_placeholder_clase()

    def _mostrar_placeholder_clase(self) -> None:
        for hijo in self._detalle_clase_frame.winfo_children():
            hijo.destroy()
        ctk.CTkLabel(
            self._detalle_clase_frame,
            text="Selecciona una clase o inscríbete en una nueva.",
            font=ctk.CTkFont(size=14),
            text_color="#6B7280",
        ).place(relx=0.5, rely=0.5, anchor="center")

    def _cargar_clases(self) -> None:
        self._limpiar_clases("Cargando...")
        usuario_id = sesion.actual.usuario_id

        def trabajo() -> None:
            exito, datos = api_cliente.listar_clases_usuario(usuario_id)
            self.after(0, lambda: self._aplicar_clases(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_clases(self, exito: bool, datos) -> None:
        if not exito:
            self._limpiar_clases(f"Error: {datos}")
            return
        self._clases = list(datos) if isinstance(datos, list) else []
        self._render_lista_clases()

    def _limpiar_clases(self, mensaje: str = "") -> None:
        for hijo in self._lista_clases_frame.winfo_children():
            hijo.destroy()
        if mensaje:
            ctk.CTkLabel(
                self._lista_clases_frame,
                text=mensaje,
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
            ).pack(pady=10)

    def _render_lista_clases(self) -> None:
        self._limpiar_clases()
        if not self._clases:
            ctk.CTkLabel(
                self._lista_clases_frame,
                text="Aún no estás inscrito en ninguna clase.",
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
                wraplength=210,
            ).pack(pady=16, padx=10)
            return

        for clase in self._clases:
            ctk.CTkButton(
                self._lista_clases_frame,
                text=clase["nombre"],
                anchor="w",
                height=40,
                fg_color=clase.get("color_hex", "#2B7CE9"),
                hover_color="#1E3A8A",
                command=lambda c=clase: self._seleccionar_clase(c),
            ).pack(fill="x", pady=3, padx=4)

    def _seleccionar_clase(self, clase: dict) -> None:
        self._clase_activa = clase
        self._render_detalle_clase()

    def _render_detalle_clase(self) -> None:
        clase = self._clase_activa
        assert clase is not None
        for hijo in self._detalle_clase_frame.winfo_children():
            hijo.destroy()

        cabecera = ctk.CTkFrame(self._detalle_clase_frame, corner_radius=10)
        cabecera.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            cabecera,
            text=clase["nombre"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 4))
        if clase.get("descripcion"):
            ctk.CTkLabel(
                cabecera,
                text=clase["descripcion"],
                font=ctk.CTkFont(size=12),
                text_color="#6B7280",
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=14)
        if clase.get("horario"):
            ctk.CTkLabel(
                cabecera,
                text=f"Horario: {clase['horario']}",
                font=ctk.CTkFont(size=11),
                text_color="#6B7280",
            ).pack(anchor="w", padx=14, pady=(2, 10))

        ctk.CTkLabel(
            self._detalle_clase_frame,
            text="Anuncios",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(4, 4))

        self._anuncios_scroll = ctk.CTkScrollableFrame(
            self._detalle_clase_frame, fg_color="transparent"
        )
        self._anuncios_scroll.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        self._cargar_anuncios()

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
        # Si el estudiante cambió de clase mientras cargaba, descartar.
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
            tarjeta = ctk.CTkFrame(self._anuncios_scroll, corner_radius=8)
            tarjeta.pack(fill="x", pady=4)
            ctk.CTkLabel(
                tarjeta,
                text=anuncio.get("contenido", ""),
                wraplength=640,
                justify="left",
                anchor="w",
            ).pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                tarjeta,
                text=anuncio.get("fecha_creacion", ""),
                font=ctk.CTkFont(size=10),
                text_color="#9CA3AF",
            ).pack(anchor="w", padx=12, pady=(0, 10))

    def _abrir_dialogo_inscripcion(self) -> None:
        DialogoInscripcion(self.app, al_inscribir=self._on_inscripcion_exitosa)

    def _on_inscripcion_exitosa(self, clase: dict) -> None:
        self._cargar_clases()
        self._seleccionar_clase(clase)

    # ==================================================================
    # TAB MIS NOTAS
    # ==================================================================

    def _construir_tab_notas(self) -> None:
        barra = ctk.CTkFrame(self._tab_notas, fg_color="transparent")
        barra.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(
            barra, text="+ Nueva nota", command=self._nueva_nota
        ).pack(side="left", padx=4)
        self._notas_estado = ctk.CTkLabel(
            barra, text="", font=ctk.CTkFont(size=11), text_color="#6B7280"
        )
        self._notas_estado.pack(side="left", padx=12)

        # Contenedor que alterna entre "lista" y "panel editor/visor".
        self._notas_contenedor = ctk.CTkFrame(self._tab_notas, fg_color="transparent")
        self._notas_contenedor.pack(fill="both", expand=True)

        self._notas_lista = ctk.CTkScrollableFrame(self._notas_contenedor, fg_color="transparent")
        self._notas_lista.pack(fill="both", expand=True)

    def _cargar_notas(self) -> None:
        self._notas_estado.configure(text="Cargando notas...")
        usuario_id = sesion.actual.usuario_id

        def trabajo() -> None:
            exito, datos = api_cliente.listar_notas(usuario_id)
            self.after(0, lambda: self._aplicar_notas(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_notas(self, exito: bool, datos) -> None:
        if not exito:
            self._notas_estado.configure(text=f"Error: {datos}", text_color=COLOR_ERROR)
            return
        self._notas = list(datos) if isinstance(datos, list) else []
        self._notas_estado.configure(text="", text_color="#6B7280")
        self._render_lista_notas()

    def _render_lista_notas(self) -> None:
        # Cerrar un eventual panel de edición antes de mostrar la lista.
        if self._panel_nota is not None:
            self._panel_nota.destroy()
            self._panel_nota = None
        self._notas_lista.pack(fill="both", expand=True)

        for hijo in self._notas_lista.winfo_children():
            hijo.destroy()

        if not self._notas:
            ctk.CTkLabel(
                self._notas_lista,
                text="Todavía no has creado notas. Usa \"+ Nueva nota\" para empezar.",
                text_color="#6B7280",
            ).pack(pady=16)
            return

        for nota in self._notas:
            self._render_tarjeta_nota(nota)

    def _render_tarjeta_nota(self, nota: dict) -> None:
        contenido = nota.get("contenido_formato") or {}
        texto = contenido.get("texto", "") if isinstance(contenido, dict) else ""
        preview = (texto[:120] + "…") if len(texto) > 120 else texto

        tarjeta = ctk.CTkFrame(self._notas_lista, corner_radius=8)
        tarjeta.pack(fill="x", pady=5)

        encabezado = ctk.CTkFrame(tarjeta, fg_color="transparent")
        encabezado.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            encabezado,
            text=nota.get("titulo", ""),
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            encabezado,
            text="Abrir",
            width=70,
            command=lambda n=nota: self._abrir_nota(n),
        ).pack(side="right")

        if preview:
            ctk.CTkLabel(
                tarjeta,
                text=preview,
                wraplength=680,
                justify="left",
                anchor="w",
                text_color="#374151",
            ).pack(anchor="w", padx=12)
        ctk.CTkLabel(
            tarjeta,
            text=nota.get("fecha_creacion", ""),
            font=ctk.CTkFont(size=10),
            text_color="#9CA3AF",
        ).pack(anchor="w", padx=12, pady=(2, 10))

    def _nueva_nota(self) -> None:
        self._abrir_panel_nota(nota=None, modo="edicion")

    def _abrir_nota(self, nota: dict) -> None:
        self._abrir_panel_nota(nota=nota, modo="lectura")

    def _abrir_panel_nota(self, nota: dict | None, modo: str) -> None:
        """Oculta la lista y coloca un PanelNota ocupando el área de notas."""
        self._notas_lista.pack_forget()
        if self._panel_nota is not None:
            self._panel_nota.destroy()

        self._panel_nota = PanelNota(
            self._notas_contenedor,
            clases_inscritas=self._clases,
            nota=nota,
            modo=modo,
            al_guardar=self._on_nota_guardada,
            al_cerrar=self._render_lista_notas,
        )
        self._panel_nota.pack(fill="both", expand=True)

    def _on_nota_guardada(self, _nota: dict) -> None:
        self._cargar_notas()

    # ------------------------------------------------------------------
    # Logout.
    # ------------------------------------------------------------------

    def _cerrar_sesion(self) -> None:
        sesion.cerrar()
        self.app.mostrar_vista("login")


# ======================================================================
# Diálogo de inscripción (por código y/o búsqueda por nombre).
# ======================================================================


class DialogoInscripcion(ctk.CTkToplevel):
    """Modal con dos modos: inscripción por código directo o búsqueda por nombre."""

    def __init__(self, master, al_inscribir) -> None:
        super().__init__(master)
        self.title("Inscribirme en una clase")
        self.geometry("520x520")
        self.resizable(False, False)
        self.transient(master)
        self.after(50, self.grab_set)

        self._al_inscribir = al_inscribir

        ctk.CTkLabel(
            self, text="Inscribirme en una clase", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(pady=(18, 12))

        # Modo 1: código directo.
        caja_codigo = ctk.CTkFrame(self, corner_radius=10)
        caja_codigo.pack(padx=18, pady=6, fill="x")
        ctk.CTkLabel(
            caja_codigo, text="¿Tienes el código?", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 2))
        fila = ctk.CTkFrame(caja_codigo, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(0, 10))
        self._codigo = ctk.CTkEntry(fila, placeholder_text="ABC123")
        self._codigo.pack(side="left", fill="x", expand=True)
        self._boton_codigo = ctk.CTkButton(
            fila, text="Inscribirme", width=120, command=self._inscribir_por_codigo
        )
        self._boton_codigo.pack(side="left", padx=(8, 0))

        # Modo 2: búsqueda por nombre.
        caja_buscar = ctk.CTkFrame(self, corner_radius=10)
        caja_buscar.pack(padx=18, pady=6, fill="both", expand=True)
        ctk.CTkLabel(
            caja_buscar, text="O busca por nombre:", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 2))
        fila2 = ctk.CTkFrame(caja_buscar, fg_color="transparent")
        fila2.pack(fill="x", padx=12, pady=(0, 6))
        self._buscar = ctk.CTkEntry(fila2, placeholder_text="nombre de la clase")
        self._buscar.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(fila2, text="Buscar", width=90, command=self._buscar_clases).pack(
            side="left", padx=(8, 0)
        )
        self._resultados = ctk.CTkScrollableFrame(caja_buscar, fg_color="transparent", height=200)
        self._resultados.pack(fill="both", expand=True, padx=6, pady=6)

        self._mensaje = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self._mensaje.pack(pady=(6, 2))

        ctk.CTkButton(
            self,
            text="Cancelar",
            fg_color="transparent",
            border_width=1,
            text_color=("#1F2937", "#F3F4F6"),
            command=self.destroy,
        ).pack(padx=18, pady=(0, 14), fill="x")

    def _inscribir_por_codigo(self) -> None:
        codigo = self._codigo.get().strip().upper()
        if len(codigo) != 6:
            self._mensaje.configure(text="El código debe tener 6 caracteres.", text_color=COLOR_ERROR)
            return
        self._boton_codigo.configure(state="disabled", text="Inscribiendo...")
        estudiante_id = sesion.actual.usuario_id

        def trabajo() -> None:
            exito, datos = api_cliente.inscribir_clase(estudiante_id, codigo)
            self.after(0, lambda: self._aplicar_inscripcion(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_inscripcion(self, exito: bool, datos) -> None:
        self._boton_codigo.configure(state="normal", text="Inscribirme")
        if not exito:
            self._mensaje.configure(text=str(datos), text_color=COLOR_ERROR)
            return
        self._al_inscribir(datos)
        self.destroy()

    def _buscar_clases(self) -> None:
        q = self._buscar.get().strip()
        if len(q) < 2:
            self._mensaje.configure(
                text="Escribe al menos 2 caracteres para buscar.", text_color=COLOR_ERROR
            )
            return
        self._mensaje.configure(text="Buscando...", text_color="#6B7280")
        for hijo in self._resultados.winfo_children():
            hijo.destroy()
        estudiante_id = sesion.actual.usuario_id

        def trabajo() -> None:
            exito, datos = api_cliente.buscar_clases(estudiante_id, q)
            self.after(0, lambda: self._aplicar_busqueda(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_busqueda(self, exito: bool, datos) -> None:
        if not exito:
            self._mensaje.configure(text=str(datos), text_color=COLOR_ERROR)
            return
        self._mensaje.configure(text="", text_color="#6B7280")
        resultados = list(datos) if isinstance(datos, list) else []
        if not resultados:
            ctk.CTkLabel(
                self._resultados, text="Sin resultados.", text_color="#6B7280"
            ).pack(pady=8)
            return
        for clase in resultados:
            fila = ctk.CTkFrame(self._resultados, corner_radius=6)
            fila.pack(fill="x", pady=3)
            ctk.CTkLabel(
                fila, text=clase["nombre"], anchor="w"
            ).pack(side="left", padx=10, pady=6)
            ctk.CTkButton(
                fila,
                text="Inscribirme",
                width=110,
                command=lambda c=clase: self._inscribir_por_codigo_auto(c["codigo_acceso"]),
            ).pack(side="right", padx=10, pady=6)

    def _inscribir_por_codigo_auto(self, codigo: str) -> None:
        """Autocompleta el campo de código y dispara la inscripción."""
        self._codigo.delete(0, "end")
        self._codigo.insert(0, codigo)
        self._inscribir_por_codigo()


# ======================================================================
# Panel de edición/lectura de notas con formato enriquecido.
# ======================================================================


class PanelNota(ctk.CTkFrame):
    """
    Panel que alterna entre edición (nota=None) y lectura (nota con datos).

    En modo edición expone toolbar de formato y botón Guardar.
    En modo lectura deshabilita la edición y sólo ofrece Volver.
    """

    def __init__(
        self,
        master,
        clases_inscritas: list[dict],
        nota: dict | None,
        modo: str,
        al_guardar,
        al_cerrar,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._clases = clases_inscritas
        self._nota = nota
        self._modo = modo
        self._al_guardar = al_guardar
        self._al_cerrar = al_cerrar

        self._construir()
        if nota is not None:
            self._cargar_contenido(nota)
        if modo == "lectura":
            self._bloquear_edicion()

    # ------------------------------------------------------------------
    # Construcción de UI.
    # ------------------------------------------------------------------

    def _construir(self) -> None:
        encabezado = ctk.CTkFrame(self, fg_color="transparent")
        encabezado.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(
            encabezado,
            text="← Volver",
            width=90,
            fg_color="transparent",
            border_width=1,
            text_color=("#1F2937", "#F3F4F6"),
            command=self._al_cerrar,
        ).pack(side="left")
        self._titulo_texto = ctk.CTkLabel(
            encabezado,
            text="Nueva nota" if self._modo == "edicion" else "Nota",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._titulo_texto.pack(side="left", padx=14)

        # Título.
        fila_titulo = ctk.CTkFrame(self, fg_color="transparent")
        fila_titulo.pack(fill="x", pady=4)
        ctk.CTkLabel(fila_titulo, text="Título", width=80, anchor="w").pack(side="left")
        self._titulo = ctk.CTkEntry(fila_titulo, placeholder_text="Título de la nota")
        self._titulo.pack(side="left", fill="x", expand=True)

        # Clase (dropdown con "Personal" = None).
        fila_clase = ctk.CTkFrame(self, fg_color="transparent")
        fila_clase.pack(fill="x", pady=4)
        ctk.CTkLabel(fila_clase, text="Clase", width=80, anchor="w").pack(side="left")
        opciones = ["Personal"] + [c["nombre"] for c in self._clases]
        self._opcion_clase = ctk.CTkOptionMenu(fila_clase, values=opciones)
        self._opcion_clase.pack(side="left")
        self._opcion_clase.set("Personal")

        # Toolbar de formato.
        self._toolbar = ctk.CTkFrame(self, fg_color="transparent")
        self._toolbar.pack(fill="x", pady=(10, 4))

        ctk.CTkButton(
            self._toolbar, text="B", width=32,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._toggle_estilo("negrita", "1"),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            self._toolbar, text="I", width=32,
            font=ctk.CTkFont(size=14, slant="italic"),
            command=lambda: self._toggle_estilo("cursiva", "1"),
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            self._toolbar, text="U", width=32, font=ctk.CTkFont(size=14, underline=True),
            command=lambda: self._toggle_estilo("subrayado", "1"),
        ).pack(side="left", padx=2)

        ctk.CTkLabel(self._toolbar, text="  color:").pack(side="left")
        for color in _COLORES_TEXTO:
            self._boton_color(self._toolbar, color, "color")
        ctk.CTkLabel(self._toolbar, text="  resaltado:").pack(side="left")
        for color in _COLORES_RESALTADO:
            self._boton_color(self._toolbar, color, "resaltado")
        ctk.CTkButton(
            self._toolbar, text="Limpiar", width=70, command=self._limpiar_formato
        ).pack(side="left", padx=(12, 2))

        # Editor: tk.Text directo (CTkTextbox prohíbe 'font' en tag_config por
        # escalado, y aquí necesitamos cambiar el font para negrita/cursiva).
        editor_frame = ctk.CTkFrame(self, corner_radius=8)
        editor_frame.pack(fill="both", expand=True, pady=(4, 8))
        self._textbox = tk.Text(
            editor_frame, font=("Segoe UI", 13), wrap="word",
            relief="flat", borderwidth=0, padx=10, pady=10,
        )
        barra = ctk.CTkScrollbar(editor_frame, command=self._textbox.yview)
        barra.pack(side="right", fill="y")
        self._textbox.configure(yscrollcommand=barra.set)
        self._textbox.pack(side="left", fill="both", expand=True)

        # Pre-configurar tags de los tipos booleanos para que estén disponibles al aplicar.
        for tipo, config in _ESTILOS_BOOLEANOS.items():
            self._textbox.tag_config(f"{tipo}:1", **config)

        # Pie: estado + botón guardar (sólo edición).
        pie = ctk.CTkFrame(self, fg_color="transparent")
        pie.pack(fill="x")
        self._mensaje = ctk.CTkLabel(pie, text="", font=ctk.CTkFont(size=11))
        self._mensaje.pack(side="left")
        self._boton_guardar = ctk.CTkButton(
            pie, text="Guardar", width=140, command=self._guardar
        )
        self._boton_guardar.pack(side="right")

    def _boton_color(self, master, color: str, tipo: str) -> None:
        """Botón de muestra de color: aplica tag tipo:color al rango seleccionado."""
        ctk.CTkButton(
            master,
            text="",
            width=24,
            height=24,
            fg_color=color,
            hover_color=color,
            command=lambda: self._toggle_estilo(tipo, color),
        ).pack(side="left", padx=1)

    # ------------------------------------------------------------------
    # Lógica de formato (aplicar/quitar tags al rango seleccionado).
    # ------------------------------------------------------------------

    def _rango_seleccionado(self) -> tuple[str, str] | None:
        """Devuelve ('sel.first','sel.last') o None si no hay selección activa."""
        try:
            inicio = self._textbox.index("sel.first")
            fin = self._textbox.index("sel.last")
            return inicio, fin
        except Exception:
            return None

    def _toggle_estilo(self, tipo: str, valor: str) -> None:
        """
        Aplica o quita el tag 'tipo:valor' sobre el rango seleccionado.

        Si alguna parte del rango ya tiene el tag, se retira; si no, se aplica.
        Para estilos excluyentes (color, resaltado) se retira cualquier otro
        valor del mismo tipo antes de aplicar el nuevo, para evitar estilos
        apilados que no tengan sentido (un carácter con dos colores a la vez).
        """
        rango = self._rango_seleccionado()
        if rango is None:
            self._mensaje.configure(
                text="Selecciona texto para aplicar formato.", text_color=COLOR_ERROR
            )
            return
        self._mensaje.configure(text="")
        inicio, fin = rango
        tag = f"{tipo}:{valor}"

        # Registrar el tag si aún no existe (sobre todo para color/resaltado dinámicos).
        self._asegurar_tag(tipo, valor)

        tags_existentes = self._textbox.tag_names(inicio)
        if tag in tags_existentes:
            # Toggle off.
            self._textbox.tag_remove(tag, inicio, fin)
            return

        # Estilos excluyentes: limpiar cualquier otro valor del mismo tipo dentro del rango.
        if tipo in ("color", "resaltado"):
            for otro in self._textbox.tag_names():
                if otro.startswith(f"{tipo}:"):
                    self._textbox.tag_remove(otro, inicio, fin)

        self._textbox.tag_add(tag, inicio, fin)

    def _asegurar_tag(self, tipo: str, valor: str) -> None:
        """Configura un tag en tk.Text si no está registrado aún."""
        tag = f"{tipo}:{valor}"
        if tag in self._textbox.tag_names():
            return
        if tipo == "color":
            self._textbox.tag_config(tag, foreground=valor)
        elif tipo == "resaltado":
            self._textbox.tag_config(tag, background=valor)
        elif tipo in _ESTILOS_BOOLEANOS:
            self._textbox.tag_config(tag, **_ESTILOS_BOOLEANOS[tipo])

    def _limpiar_formato(self) -> None:
        """Quita todos los tags de nuestra familia en el rango seleccionado."""
        rango = self._rango_seleccionado()
        if rango is None:
            return
        inicio, fin = rango
        for tag in self._textbox.tag_names():
            if ":" in tag:
                self._textbox.tag_remove(tag, inicio, fin)

    # ------------------------------------------------------------------
    # Serialización: tk.Text tags -> contenido_formato.
    # ------------------------------------------------------------------

    def _offset_lineal(self, index: str) -> int:
        """Convierte un índice tk ('línea.col') a offset de carácter desde '1.0'."""
        # CTkTextbox delega vía __getattr__ a tk.Text, por eso count() funciona directo.
        conteo = self._textbox.count("1.0", index, "chars")
        if conteo is None:
            return 0
        # tk.Text.count con una sola opción retorna una tupla de longitud 1.
        if isinstance(conteo, tuple):
            return int(conteo[0])
        return int(conteo)

    def _serializar_contenido(self) -> dict:
        """Devuelve {texto, tags} listo para enviar al backend."""
        texto = self._textbox.get("1.0", "end-1c")
        tags_salida: list[dict] = []
        for nombre_tag in self._textbox.tag_names():
            if ":" not in nombre_tag:
                # Tags internos de tk (sel, etc.).
                continue
            tipo, _, valor = nombre_tag.partition(":")
            rangos = self._textbox.tag_ranges(nombre_tag)
            # tag_ranges retorna una secuencia plana [inicio1, fin1, inicio2, fin2, ...].
            for i in range(0, len(rangos), 2):
                ini = self._offset_lineal(str(rangos[i]))
                fin = self._offset_lineal(str(rangos[i + 1]))
                if fin > ini:
                    tags_salida.append(
                        {"inicio": ini, "fin": fin, "tipo": tipo, "valor": valor}
                    )
        return {"texto": texto, "tags": tags_salida}

    # ------------------------------------------------------------------
    # Carga: contenido_formato -> tk.Text con tags.
    # ------------------------------------------------------------------

    def _cargar_contenido(self, nota: dict) -> None:
        self._titulo.delete(0, "end")
        self._titulo.insert(0, nota.get("titulo", ""))

        contenido = nota.get("contenido_formato") or {}
        texto = contenido.get("texto", "") if isinstance(contenido, dict) else ""
        tags = contenido.get("tags", []) if isinstance(contenido, dict) else []

        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", texto)

        for tag in tags:
            tipo = tag.get("tipo", "")
            valor = tag.get("valor", "")
            ini = int(tag.get("inicio", 0))
            fin = int(tag.get("fin", 0))
            if not tipo or fin <= ini:
                continue
            self._asegurar_tag(tipo, valor)
            self._textbox.tag_add(
                f"{tipo}:{valor}", f"1.0+{ini}c", f"1.0+{fin}c"
            )

        # Preseleccionar clase si la nota pertenece a una.
        clase_id = nota.get("clase_id")
        if clase_id is not None:
            for clase in self._clases:
                if clase["id"] == clase_id:
                    self._opcion_clase.set(clase["nombre"])
                    break

    def _bloquear_edicion(self) -> None:
        """Pone el editor en modo lectura: desactiva toolbar, título y guardar."""
        self._titulo_texto.configure(text="Nota (lectura)")
        self._titulo.configure(state="disabled")
        self._opcion_clase.configure(state="disabled")
        self._textbox.configure(state="disabled")
        self._boton_guardar.pack_forget()
        for hijo in self._toolbar.winfo_children():
            try:
                hijo.configure(state="disabled")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Guardar.
    # ------------------------------------------------------------------

    def _guardar(self) -> None:
        titulo = self._titulo.get().strip()
        contenido = self._serializar_contenido()
        texto = contenido["texto"].strip()

        if not titulo:
            self._mensaje.configure(text="El título es obligatorio.", text_color=COLOR_ERROR)
            return
        if not texto:
            self._mensaje.configure(text="La nota no puede estar vacía.", text_color=COLOR_ERROR)
            return

        clase_nombre = self._opcion_clase.get()
        clase_id: int | None = None
        if clase_nombre != "Personal":
            for clase in self._clases:
                if clase["nombre"] == clase_nombre:
                    clase_id = clase["id"]
                    break

        payload = {
            "titulo": titulo,
            "contenido_formato": contenido,
            "estudiante_id": sesion.actual.usuario_id,
            "clase_id": clase_id,
        }

        self._boton_guardar.configure(state="disabled", text="Guardando...")
        self._mensaje.configure(text="")

        def trabajo() -> None:
            exito, datos = api_cliente.guardar_nota(payload)
            self.after(0, lambda: self._aplicar_guardado(exito, datos))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar_guardado(self, exito: bool, datos) -> None:
        self._boton_guardar.configure(state="normal", text="Guardar")
        if not exito:
            self._mensaje.configure(text=str(datos), text_color=COLOR_ERROR)
            return
        self._mensaje.configure(text="Nota guardada.", text_color=COLOR_OK)
        self._al_guardar(datos)
        # Volver a la lista tras un pequeño delay para que el usuario vea el ok.
        self.after(600, self._al_cerrar)
