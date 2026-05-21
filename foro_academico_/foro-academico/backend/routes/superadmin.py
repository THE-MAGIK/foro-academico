"""
Gestion de usuarios y roles reservada al administrador supremo (rol superadmin).

Requiere sesion iniciada; las rutas comprueban session['user_id'] en base de datos.
PATCH: actualiza nombre, email, password y rol; no deja quitar el unico superadmin.
DELETE: borra usuario; bloquea borrar el unico superadmin o borrarse a si mismo.
POST /api/superadmin/users: crea usuario con rol elegido (nombre, email, password, rol).
"""
import bcrypt
from flask import Blueprint, jsonify, request, session

from common import get_json, get_user_by_id, is_superadmin, normalize_role
from db import get_connection

bp = Blueprint("superadmin", __name__)

ROLES_VALIDOS = {"estudiante", "profesor", "admin", "superadmin"}


def _require_superadmin():
    """Devuelve (usuario, None) o (None, respuesta Flask con error)."""
    uid = session.get("user_id")
    if not uid:
        return None, (jsonify({"error": "No autenticado"}), 401)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, uid)
    cursor.close()
    conn.close()
    if not user or not is_superadmin(user):
        return None, (jsonify({"error": "Solo el administrador supremo puede usar esta accion"}), 403)
    return user, None


@bp.route("/api/superadmin/users", methods=["POST"])
def create_user_as_superadmin():
    """Alta de usuario con cualquier rol; solo superadmin autenticado."""
    _, err = _require_superadmin()
    if err:
        return err

    data = get_json(request)
    nombre = (data.get("nombre") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")
    rol_raw = data.get("rol")
    if not nombre or not email:
        return jsonify({"error": "Nombre y email son obligatorios"}), 400
    if not password or len(str(password)) < 6:
        return jsonify({"error": "La contrasena es obligatoria (minimo 6 caracteres)"}), 400

    role = normalize_role(rol_raw)
    if role not in ROLES_VALIDOS:
        return jsonify({"error": "Rol invalido"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "El email ya esta en uso"}), 409

    hashed = bcrypt.hashpw(str(password).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    ins = conn.cursor()
    ins.execute(
        "INSERT INTO users (nombre, email, password, rol) VALUES (%s,%s,%s,%s)",
        (nombre, email, hashed, role),
    )
    conn.commit()
    new_id = ins.lastrowid
    ins.close()
    cursor.execute("SELECT id, nombre, email, rol FROM users WHERE id=%s", (new_id,))
    created = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Usuario creado", "user": created}), 201


@bp.route("/api/superadmin/users/<int:user_id>", methods=["PATCH", "PUT"])
def patch_user_as_superadmin(user_id):
    _, err = _require_superadmin()
    if err:
        return err

    data = get_json(request)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre, email, password, rol FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Usuario no encontrado"}), 404

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
        # Evita duplicar email antes del UPDATE (unicidad en BD).
        cursor.execute("SELECT id FROM users WHERE email=%s AND id!=%s", (email, user_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "El email ya esta en uso"}), 409
        updates.append("email=%s")
        values.append(email)

    if "password" in data and data.get("password"):
        pwd = str(data["password"])
        if len(pwd) < 6:
            cursor.close()
            conn.close()
            return jsonify({"error": "La contrasena debe tener al menos 6 caracteres"}), 400
        hashed = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        updates.append("password=%s")
        values.append(hashed)

    if "rol" in data:
        new_rol = normalize_role(data["rol"])
        if new_rol not in ROLES_VALIDOS:
            cursor.close()
            conn.close()
            return jsonify({"error": "Rol invalido"}), 400
        # No degradar al ultimo superadmin restante.
        if row["rol"] == "superadmin" and new_rol != "superadmin":
            cursor.execute("SELECT COUNT(*) AS c FROM users WHERE rol='superadmin'")
            cnt = cursor.fetchone()["c"]
            if cnt <= 1:
                cursor.close()
                conn.close()
                return jsonify({"error": "No se puede quitar el unico administrador supremo"}), 400
        updates.append("rol=%s")
        values.append(new_rol)

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

    cursor.execute(
        "SELECT id, nombre, email, rol FROM users WHERE id=%s",
        (user_id,),
    )
    updated = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify({"user": updated})


@bp.route("/api/superadmin/users/<int:user_id>", methods=["DELETE"])
def delete_user_as_superadmin(user_id):
    _, err = _require_superadmin()
    if err:
        return err

    if user_id == session.get("user_id"):
        return jsonify({"error": "No puedes eliminar tu propia cuenta desde aqui"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, rol FROM users WHERE id=%s", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Usuario no encontrado"}), 404

    if row["rol"] == "superadmin":
        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE rol='superadmin'")
        cnt = cursor.fetchone()["c"]
        if cnt <= 1:
            cursor.close()
            conn.close()
            return jsonify({"error": "No se puede eliminar el unico administrador supremo"}), 400

    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify({"mensaje": "Usuario eliminado"})
