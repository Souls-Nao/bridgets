# -*- mode: python ; coding: utf-8 -*-
"""
Spec de PyInstaller para Bridgets.

- Modo onefile + windowed: genera un único bridgets.exe sin consola.
- hiddenimports explícitos para las vistas: app.py las importa perezosamente
  dentro de _resolver_vista, así que PyInstaller no siempre las detecta al
  escanear el grafo estático. Listarlas garantiza que estén en el bundle.
- collect_data_files('customtkinter') empaqueta los temas y assets internos
  del framework; sin esto CTk falla al buscar su tema default al iniciar.
- El directorio assets/ se incluye aunque hoy esté vacío: config.resource_path()
  ya lo espera y así futuras adiciones (iconos, imágenes) funcionarán sin
  tocar el spec.

Compilar desde bridgets_client/:
    pyinstaller build_exe.spec --clean --noconfirm

El .exe resultante queda en bridgets_client/dist/bridgets.exe.
"""

from PyInstaller.utils.hooks import collect_data_files

# Vistas cargadas perezosamente por views/__init__.py → hacerlas explícitas.
hiddenimports = [
    "views.pantalla_splash",
    "views.pantalla_login",
    "views.pantalla_registro",
    "views.pantalla_dashboard_tutor",
    "views.pantalla_dashboard_estudiante",
]

# Assets propios del cliente (hoy vacío; listo para iconos/imágenes).
datas = [("assets", "assets")]
# Datos internos de customtkinter (themes/*.json, fonts, etc.).
datas += collect_data_files("customtkinter")


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="bridgets",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
