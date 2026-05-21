"""
Funciones pequenas que se repiten en varios blueprints.

Evita copiar validaciones y consultas auxiliares en cada archivo de rutas.
"""
import hashlib

from db import get_connection


def get_json(request):
    """Lee JSON del body o devuelve dict vacio si no hay payload."""
    data = request.get_json(silent=True)
    return data if data else {}


def get_user_by_id(cursor, user_id):
    """Datos publicos del usuario por id (sin contrasena)."""
    cursor.execute(
        "SELECT id, nombre, email, rol, avatar_ext FROM users WHERE id=%s",
        (user_id,),
    )
    return cursor.fetchone()


def is_student(user):
    """True si el dict de usuario tiene rol estudiante."""
    return user and user.get("rol") == "estudiante"


def is_professor(user):
    return user and user.get("rol") == "profesor"


def is_admin(user):
    return user and user.get("rol") == "admin"


def is_superadmin(user):
    return user and user.get("rol") == "superadmin"


def can_moderate_content(user):
    """Administrador o supremo: moderacion de preguntas y respuestas."""
    return user and user.get("rol") in ("admin", "superadmin")


def can_act_as_classroom_professor(user):
    """Profesor o superadmin: rutas del aula como docente (tareas, entregas, comentarios)."""
    return bool(user and user.get("rol") in ("profesor", "superadmin"))


def can_act_as_classroom_student(user):
    """Estudiante o superadmin: entregar y comentar en el aula como alumno."""
    return bool(user and user.get("rol") in ("estudiante", "superadmin"))


def normalize_role(raw_role):
    """
    Convierte variantes del rol a los valores que usa la base de datos.
    Por ejemplo 'Administrador' o alias en ingles quedan como 'admin'.
    """
    role = str(raw_role or "").strip().lower()
    aliases = {
        "administrador": "admin",
        "administrator": "admin",
        "administrador supremo": "superadmin",
        "admin_supremo": "superadmin",
        "administrador_supremo": "superadmin",
        "super administrador": "superadmin",
    }
    return aliases.get(role, role)


def validate_admin(admin_id):
    """Comprueba que el id sea admin o superadmin (moderacion de contenido)."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    admin = get_user_by_id(cursor, admin_id)
    cursor.close()
    conn.close()
    return can_moderate_content(admin)


def build_gravatar_url(email):
    """URL publica de avatar segun email (hash MD5 como exige Gravatar)."""
    clean = (email or "").strip().lower().encode("utf-8")
    digest = hashlib.md5(clean).hexdigest()
    return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s=200"


def resolve_avatar_url(email, user_id, avatar_ext):
    """
    URL publica del avatar: ruta relativa /api/avatars/<id> (mismo origen que el front con Vite)
    o Gravatar si no hay foto subida.
    """
    ext = avatar_ext
    if isinstance(ext, (bytes, bytearray)):
        ext = ext.decode("utf-8", errors="ignore")
    if ext is not None:
        ext = str(ext).strip() or None
    if user_id and ext:
        return f"/api/avatars/{int(user_id)}"
    return build_gravatar_url(email)
