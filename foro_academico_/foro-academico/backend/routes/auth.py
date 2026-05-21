"""
Autenticacion y datos basicos de usuario.

Sesion Flask (cookie): login guarda user_id y rol. Registro, /api/me (GET/PATCH),
avatar en disco (static/uploads/avatars) + avatar_ext en BD, Gravatar si no hay foto.
"""
import glob
import os

import bcrypt
from flask import Blueprint, jsonify, redirect, request, send_file, session

from common import (
    build_gravatar_url,
    get_json,
    get_user_by_id,
    is_superadmin,
    normalize_role,
    resolve_avatar_url,
)
from logical_auth import (
    diagnostico_login_credenciales_invalidas,
    diagnostico_login_datos_incompletos,
    diagnostico_login_error_servidor,
    diagnostico_login_exitoso,
)
from db import get_connection

bp = Blueprint("auth", __name__)

# Raiz del backend (un nivel arriba de routes/) para rutas a static/uploads.
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AVATAR_UPLOAD_DIR = os.path.join(BACKEND_ROOT, "static", "uploads", "avatars")
AVATAR_MAX_BYTES = 2 * 1024 * 1024
MIME_BY_EXT = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def _detect_image_format(data: bytes):
    """Devuelve extension logica ('jpeg'|'png'|'webp') o None si no coincide cabecera magica."""
    if not data or len(data) < 12:
        return None
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _remove_avatar_files(user_id: int):
    """Borra archivos previos user_id.* en carpeta de avatares (antes de subir uno nuevo)."""
    pattern = os.path.join(AVATAR_UPLOAD_DIR, f"{int(user_id)}.*")
    for path in glob.glob(pattern):
        os.remove(path)


def _attach_avatar_url(user_row: dict | None) -> dict | None:
    """Quita password del dict y anade avatar_url (resolve_avatar_url: propio o Gravatar)."""
    if not user_row:
        return None
    out = {k: v for k, v in user_row.items() if k != "password"}
    ext = out.pop("avatar_ext", None)
    uid = out.get("id")
    out["avatar_url"] = resolve_avatar_url(out.get("email"), uid, ext)
    return out


@bp.route("/api/users", methods=["GET"])
def get_users():
    # Listado global: solo superadmin (pantalla de administracion).
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "No autenticado"}), 401
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    actor = get_user_by_id(cursor, uid)
    if not actor or not is_superadmin(actor):
        cursor.close()
        conn.close()
        return jsonify({"error": "Solo el administrador supremo puede listar usuarios"}), 403
    cursor.execute("SELECT id, nombre, email, rol FROM users")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/register", methods=["POST"])
def register():
    data = get_json(request)
    required = ["nombre", "email", "password", "rol"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Faltan campos: {', '.join(missing)}"}), 400

    role = normalize_role(data["rol"])
    if role not in {"estudiante", "profesor", "admin", "superadmin"}:
        return jsonify(
            {"error": "Rol invalido. Usa: estudiante, profesor, admin o superadmin"}
        ), 400

    conn = get_connection()
    cursor = conn.cursor()
    hashed = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cursor.execute(
        "INSERT INTO users (nombre, email, password, rol) VALUES (%s,%s,%s,%s)",
        (data["nombre"], data["email"], hashed, role),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Usuario creado"}), 201


@bp.route("/api/login", methods=["POST"])
def login():
    data = get_json(request)
    missing = [f for f in ("email", "password") if not data.get(f)]
    if missing:
        return jsonify(
            {
                "success": False,
                "error": "Email y password son obligatorios",
                "diagnostico": diagnostico_login_datos_incompletos(missing),
            }
        ), 400

    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if not user or not bcrypt.checkpw(
            password.encode("utf-8"), user["password"].encode("utf-8")
        ):
            cursor.close()
            conn.close()
            return jsonify(
                {
                    "success": False,
                    "error": "Correo o contraseña incorrectos",
                    "diagnostico": diagnostico_login_credenciales_invalidas(),
                }
            ), 401

        cursor.close()
        conn.close()
    except Exception as exc:
        return jsonify(
            {
                "success": False,
                "error": "No se pudo completar el inicio de sesión",
                "diagnostico": diagnostico_login_error_servidor(str(exc)),
            }
        ), 503

    session["user_id"] = user["id"]
    session["rol"] = user["rol"]
    avatar_url = resolve_avatar_url(
        user.get("email"), user["id"], user.get("avatar_ext")
    )
    return jsonify(
        {
            "success": True,
            "user": {
                "id": user["id"],
                "nombre": user["nombre"],
                "email": user["email"],
                "rol": user["rol"],
                "avatar_url": avatar_url,
            },
            "diagnostico": diagnostico_login_exitoso(),
        }
    )


@bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mensaje": "Sesion cerrada"})


@bp.route("/api/me", methods=["GET", "PATCH", "PUT"])
def me():
    """Usuario de la sesion: GET perfil; PATCH/PUT actualiza nombre, email o password."""
    user_id = session.get("user_id")
    if not user_id:
        if request.method == "GET":
            return jsonify({"authenticated": False}), 401
        return jsonify({"error": "No autenticado"}), 401

    if request.method == "GET":
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        user = get_user_by_id(cursor, user_id)
        cursor.close()
        conn.close()

        if not user:
            session.clear()
            return jsonify({"authenticated": False}), 401

        return jsonify({"authenticated": True, "user": _attach_avatar_url(user)})

    data = get_json(request)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, nombre, email, password, rol, avatar_ext FROM users WHERE id=%s",
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        session.clear()
        return jsonify({"error": "Usuario no encontrado"}), 401

    updates = []
    values = []

    if "nombre" in data:
        nombre = (data.get("nombre") or "").strip()
        if not nombre:
            cursor.close()
            conn.close()
            return jsonify({"error": "El nombre no puede estar vacio"}), 400
        updates.append("nombre=%s")
        values.append(nombre)

    if "email" in data:
        email = (data.get("email") or "").strip().lower()
        if not email:
            cursor.close()
            conn.close()
            return jsonify({"error": "El email no puede estar vacio"}), 400
        cursor.execute(
            "SELECT id FROM users WHERE email=%s AND id!=%s",
            (email, user_id),
        )
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "El email ya esta en uso"}), 409
        updates.append("email=%s")
        values.append(email)

    new_password = data.get("password")
    if new_password:
        if len(str(new_password)) < 6:
            cursor.close()
            conn.close()
            return jsonify({"error": "La contrasena debe tener al menos 6 caracteres"}), 400
        hashed = bcrypt.hashpw(
            str(new_password).encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        updates.append("password=%s")
        values.append(hashed)

    if not updates:
        cursor.close()
        conn.close()
        return jsonify({"error": "Nada que actualizar"}), 400

    values.append(user_id)
    cursor.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id=%s",
        tuple(values),
    )
    conn.commit()
    cursor.close()
    conn.close()

    # Leer de nuevo el usuario para devolver avatar_url resuelto (propia o Gravatar).
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, user_id)
    cursor.close()
    conn.close()
    return jsonify({"user": _attach_avatar_url(user)})


@bp.route("/api/me/avatar", methods=["POST"])
def upload_my_avatar():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "No autenticado"}), 401

    file = request.files.get("avatar")
    if not file or not file.filename:
        return jsonify({"error": "Falta el archivo (campo avatar)"}), 400

    raw = file.read()
    if len(raw) > AVATAR_MAX_BYTES:
        return jsonify({"error": "La imagen supera 2 MB"}), 400

    ext = _detect_image_format(raw)
    if not ext:
        return jsonify({"error": "Formato no permitido (usa JPEG, PNG o WebP)"}), 400

    os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)
    _remove_avatar_files(user_id)
    dest = os.path.join(AVATAR_UPLOAD_DIR, f"{int(user_id)}.{ext}")
    with open(dest, "wb") as fh:
        fh.write(raw)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET avatar_ext=%s WHERE id=%s",
        (ext, user_id),
    )
    conn.commit()
    cursor.close()
    conn.close()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, user_id)
    cursor.close()
    conn.close()
    return jsonify({"user": _attach_avatar_url(user)})


@bp.route("/api/me/avatar", methods=["DELETE"])
def delete_my_avatar():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "No autenticado"}), 401

    _remove_avatar_files(user_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET avatar_ext=NULL WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, user_id)
    cursor.close()
    conn.close()
    return jsonify({"user": _attach_avatar_url(user)})


@bp.route("/api/avatars/<int:user_id>", methods=["GET"])
def serve_avatar(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT email, avatar_ext FROM users WHERE id=%s",
        (user_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row or not row.get("avatar_ext"):
        return redirect(build_gravatar_url(row.get("email") if row else None))

    ext = row["avatar_ext"]
    if isinstance(ext, (bytes, bytearray)):
        ext = ext.decode("utf-8", errors="ignore")
    ext = str(ext).strip()
    if not ext:
        return redirect(build_gravatar_url(row.get("email")))

    path = os.path.join(AVATAR_UPLOAD_DIR, f"{user_id}.{ext}")
    if not os.path.isfile(path):
        return redirect(build_gravatar_url(row.get("email")))

    return send_file(path, mimetype=MIME_BY_EXT.get(ext, "application/octet-stream"))


@bp.route("/api/users/<int:user_id>/avatar", methods=["GET"])
def get_user_avatar(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, user_id)
    cursor.close()
    conn.close()
    if not user:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(
        {
            "avatar_url": resolve_avatar_url(
                user.get("email"), user.get("id"), user.get("avatar_ext")
            )
        }
    )
