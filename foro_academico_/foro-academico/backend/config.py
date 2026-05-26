"""
Configuracion local del backend (proyecto academico).

Traduccion via MyMemory API (gratuita, REST externa).
"""

# MyMemory Translation API — https://mymemory.translated.net/doc/spec.php
# Opcional: sin clave ~1000 palabras/dia; con clave gratuita ~10000 palabras/dia.
# Genera una en https://mymemory.translated.net/doc/keygen.php (usuario + contrasena).
MYMEMORY_API_KEY = ""


def get_mymemory_api_key():
    return (MYMEMORY_API_KEY or "").strip()
