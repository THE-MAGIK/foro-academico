"""
Configuracion local del backend (proyecto academico).

Pega aqui la API key de Google Cloud Translation.
"""

# Google Cloud Translation API — https://console.cloud.google.com/apis/credentials
GOOGLE_TRANSLATE_API_KEY = ""


def get_google_translate_api_key():
    return (GOOGLE_TRANSLATE_API_KEY or "").strip()
