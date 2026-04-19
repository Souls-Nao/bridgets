"""
Cliente HTTP hacia el backend de Bridgets (Render).

Placeholder de Fase 0. En Fase 2 se implementan todas las llamadas:
verificar_correo, verificar_usuario, verificar_codigo, registrar, login,
actualizar_usuario, crear_clase, listar_clases_usuario, inscribir_clase,
buscar_clases, listar_anuncios, crear_anuncio, guardar_nota, listar_notas.

Convenciones:
- timeout=15 (Render Free tiene cold start de ~50 s; el splash maneja el primer golpe).
- captura requests.exceptions.RequestException.
- devuelve (exito: bool, datos_o_mensaje: dict | str).
"""
