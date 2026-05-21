"""
Administradores: CRUD de usuarios admin/superadmin y moderacion global.

CRUD /api/admins: crear admin solo superadmin; editar propio perfil o cualquier admin si eres superadmin.
/moderation/*: admin_id en URL debe ser admin real (validate_admin). Foro: preguntas y respuestas.
Aula: editar/borrar tareas, listar entregas, editar/borrar comentarios de tarea.
"""
import os

import bcrypt
from flask import Blueprint, jsonify, request, session

from common import can_moderate_content, get_json, get_user_by_id, is_superadmin, validate_admin
from db import get_connection
from routes.classroom import _parse_fecha_entrega, _upload_dir

bp = Blueprint("admins", __name__)


def _usuario_sesion():
    """Usuario actual desde session['user_id'] o None."""
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, uid)
    cursor.close()
    conn.close()
    return user


# --- Listado y CRUD de filas users con rol admin o superadmin ---


@bp.route("/api/admins", methods=["GET"])
def list_admins():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, nombre, email, rol, reputacion, fecha_creacion "
        "FROM users WHERE rol IN ('admin','superadmin')"
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/admins", methods=["POST"])
def create_admin():
    actor = _usuario_sesion()
    if not actor or not is_superadmin(actor):
        return jsonify({"error": "Solo el administrador supremo puede crear administradores"}), 403
    data = get_json(request)
    required = ["nombre", "email", "password"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Faltan campos: {', '.join(missing)}"}), 400
    conn = get_connection()
    cursor = conn.cursor()
    hashed = bcrypt.hashpw(data["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cursor.execute(
        "INSERT INTO users (nombre, email, password, rol) VALUES (%s,%s,%s,%s)",
        (data["nombre"], data["email"], hashed, "admin"),
    )
    conn.commit()
    aid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Administrador creado", "id": aid}), 201


@bp.route("/api/admins/<int:admin_id>", methods=["GET"])
def get_admin(admin_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    admin = get_user_by_id(cursor, admin_id)
    cursor.close()
    conn.close()
    if not can_moderate_content(admin):
        return jsonify({"error": "Administrador no encontrado"}), 404
    return jsonify(admin)


@bp.route("/api/admins/<int:admin_id>", methods=["PUT"])
def update_admin(admin_id):
    actor = _usuario_sesion()
    if not actor:
        return jsonify({"error": "No autenticado"}), 401
    if actor["id"] != admin_id and not is_superadmin(actor):
        return jsonify({"error": "Solo el administrador supremo puede editar otros administradores"}), 403
    data = get_json(request)
    fields = {k: v for k, v in data.items() if k in {"nombre", "email", "password"} and v}
    if not fields:
        return jsonify({"error": "No hay campos para actualizar"}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    admin = get_user_by_id(cursor, admin_id)
    if not can_moderate_content(admin):
        cursor.close()
        conn.close()
        return jsonify({"error": "Administrador no encontrado"}), 404
    cursor = conn.cursor()
    updates = []
    values = []
    if "nombre" in fields:
        updates.append("nombre=%s")
        values.append(fields["nombre"])
    if "email" in fields:
        updates.append("email=%s")
        values.append(fields["email"])
    if "password" in fields:
        updates.append("password=%s")
        values.append(bcrypt.hashpw(fields["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8"))
    values.append(admin_id)
    cursor.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id=%s AND rol IN ('admin','superadmin')",
        tuple(values),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Administrador actualizado"})


@bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
def delete_admin(admin_id):
    actor = _usuario_sesion()
    if not actor or not is_superadmin(actor):
        return jsonify({"error": "Solo el administrador supremo puede eliminar administradores"}), 403
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, rol FROM users WHERE id=%s", (admin_id,))
    target = cursor.fetchone()
    if not target or target["rol"] not in ("admin", "superadmin"):
        cursor.close()
        conn.close()
        return jsonify({"error": "Administrador no encontrado"}), 404
    if target["rol"] == "superadmin":
        cursor.execute("SELECT COUNT(*) AS c FROM users WHERE rol='superadmin'")
        if cursor.fetchone()["c"] <= 1:
            cursor.close()
            conn.close()
            return jsonify({"error": "No se puede eliminar el unico administrador supremo"}), 400
    cursor.close()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM users WHERE id=%s AND rol IN ('admin','superadmin')",
        (admin_id,),
    )
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Administrador no encontrado"}), 404
    return jsonify({"mensaje": "Administrador eliminado"})


# --- Moderacion foro: preguntas y respuestas (sin ser autor) ---


@bp.route("/api/admins/<int:admin_id>/moderation/questions", methods=["GET"])
def admin_list_questions(admin_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT q.id, q.titulo, q.contenido, q.user_id, u.nombre AS autor, q.fecha_creacion "
        "FROM questions q LEFT JOIN users u ON q.user_id=u.id "
        "ORDER BY q.fecha_creacion DESC"
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/admins/<int:admin_id>/moderation/questions/<int:question_id>", methods=["PUT"])
def admin_update_question(admin_id, question_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    data = get_json(request)
    fields = {k: v for k, v in data.items() if k in {"titulo", "contenido"} and v}
    if not fields:
        return jsonify({"error": "No hay campos para actualizar"}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM questions WHERE id=%s", (question_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404
    cursor = conn.cursor()
    updates = []
    values = []
    if "titulo" in fields:
        updates.append("titulo=%s")
        values.append(fields["titulo"])
    if "contenido" in fields:
        updates.append("contenido=%s")
        values.append(fields["contenido"])
    values.append(question_id)
    cursor.execute(f"UPDATE questions SET {', '.join(updates)} WHERE id=%s", tuple(values))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Pregunta moderada/actualizada"})


@bp.route("/api/admins/<int:admin_id>/moderation/questions/<int:question_id>", methods=["DELETE"])
def admin_delete_question(admin_id, question_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id=%s", (question_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Pregunta no encontrada"}), 404
    return jsonify({"mensaje": "Pregunta eliminada por moderacion"})


@bp.route("/api/admins/<int:admin_id>/moderation/answers", methods=["GET"])
def admin_list_answers(admin_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT a.id, a.contenido, a.user_id, u.nombre AS autor, a.question_id, a.fecha_creacion "
        "FROM answers a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.fecha_creacion DESC"
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/admins/<int:admin_id>/moderation/answers/<int:answer_id>", methods=["PUT"])
def admin_update_answer(admin_id, answer_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    data = get_json(request)
    if not data.get("contenido"):
        return jsonify({"error": "contenido es obligatorio"}), 400
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE answers SET contenido=%s WHERE id=%s", (data["contenido"], answer_id))
    conn.commit()
    updated = cursor.rowcount
    cursor.close()
    conn.close()
    if updated == 0:
        return jsonify({"error": "Respuesta no encontrada"}), 404
    return jsonify({"mensaje": "Respuesta moderada/actualizada"})


@bp.route("/api/admins/<int:admin_id>/moderation/answers/<int:answer_id>", methods=["DELETE"])
def admin_delete_answer(admin_id, answer_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM answers WHERE id=%s", (answer_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Respuesta no encontrada"}), 404
    return jsonify({"mensaje": "Respuesta eliminada por moderacion"})


# --- Moderacion aula: assignments, ficheros de entregas, comentarios ---


@bp.route(
    "/api/admins/<int:admin_id>/moderation/assignments/<int:assignment_id>",
    methods=["PUT"],
)
def admin_moderation_update_assignment(admin_id, assignment_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    data = get_json(request)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    fields = []
    params = []
    if "titulo" in data:
        t = (data.get("titulo") or "").strip()
        if not t:
            cursor.close()
            conn.close()
            return jsonify({"error": "El titulo no puede quedar vacio"}), 400
        fields.append("titulo=%s")
        params.append(t)
    if "descripcion" in data:
        fields.append("descripcion=%s")
        params.append((data.get("descripcion") or "").strip() or None)
    if "fecha_entrega" in data:
        fields.append("fecha_entrega=%s")
        params.append(_parse_fecha_entrega(data.get("fecha_entrega")))

    if not fields:
        cursor.close()
        conn.close()
        return jsonify({"error": "No hay campos para actualizar"}), 400

    sql = f"UPDATE assignments SET {', '.join(fields)} WHERE id=%s"
    params.append(assignment_id)
    cursor.execute(sql, tuple(params))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Tarea actualizada por moderacion"})


@bp.route(
    "/api/admins/<int:admin_id>/moderation/assignments/<int:assignment_id>",
    methods=["DELETE"],
)
def admin_moderation_delete_assignment(admin_id, assignment_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    cursor.execute(
        "SELECT stored_filename FROM assignment_submissions WHERE assignment_id=%s",
        (assignment_id,),
    )
    upload_dir = _upload_dir()
    for row in cursor.fetchall():
        path = os.path.join(upload_dir, row["stored_filename"])
        if os.path.isfile(path):
            # Borrar ficheros en disco antes de CASCADE/DELETE de la tarea.
            os.remove(path)

    cursor.execute("DELETE FROM assignments WHERE id=%s", (assignment_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Tarea no encontrada"}), 404
    return jsonify({"mensaje": "Tarea eliminada por moderacion"})


@bp.route(
    "/api/admins/<int:admin_id>/moderation/assignments/<int:assignment_id>/submissions",
    methods=["GET"],
)
def admin_moderation_list_submissions(admin_id, assignment_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    cursor.execute(
        "SELECT s.id, s.student_id, s.filename_original, s.fecha_subida, s.size_bytes, "
        "s.nota, s.comentario_profesor, "
        "u.nombre AS estudiante_nombre "
        "FROM assignment_submissions s "
        "JOIN users u ON u.id = s.student_id "
        "WHERE s.assignment_id=%s ORDER BY s.fecha_subida DESC",
        (assignment_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)


@bp.route(
    "/api/admins/<int:admin_id>/moderation/assignment-comments/<int:comment_id>",
    methods=["PUT"],
)
def admin_moderation_update_assignment_comment(admin_id, comment_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    data = get_json(request)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id FROM assignment_comments WHERE id=%s",
        (comment_id,),
    )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Comentario no encontrado"}), 404

    fields = []
    params = []
    if "contenido" in data:
        contenido = (data.get("contenido") or "").strip()
        if not contenido:
            cursor.close()
            conn.close()
            return jsonify({"error": "El contenido no puede quedar vacio"}), 400
        fields.append("contenido=%s")
        params.append(contenido)
    if "is_private" in data:
        fields.append("is_private=%s")
        params.append(1 if bool(data.get("is_private")) else 0)

    if not fields:
        cursor.close()
        conn.close()
        return jsonify({"error": "No hay campos para actualizar"}), 400

    sql = f"UPDATE assignment_comments SET {', '.join(fields)} WHERE id=%s"
    params.append(comment_id)
    cursor.execute(sql, tuple(params))
    conn.commit()
    updated = cursor.rowcount
    cursor.close()
    conn.close()
    if updated == 0:
        return jsonify({"error": "Comentario no encontrado"}), 404
    return jsonify({"mensaje": "Comentario actualizado por moderacion"})


@bp.route(
    "/api/admins/<int:admin_id>/moderation/assignment-comments/<int:comment_id>",
    methods=["DELETE"],
)
def admin_moderation_delete_assignment_comment(admin_id, comment_id):
    if not validate_admin(admin_id):
        return jsonify({"error": "Administrador no autorizado"}), 403
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM assignment_comments WHERE id=%s", (comment_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Comentario no encontrado"}), 404
    return jsonify({"mensaje": "Comentario eliminado por moderacion"})
