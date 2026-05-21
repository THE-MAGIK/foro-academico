"""
CRUD de profesores (users con rol='profesor') y respuestas en el foro.

Rutas /api/questions/:id/answers: respuestas de una pregunta (cualquier autor).
Rutas /api/professors/:id/answers*: respuestas creadas por ese profesor.
"""
import bcrypt
from flask import Blueprint, jsonify, request

from common import get_json, get_user_by_id, is_professor, resolve_avatar_url
from db import get_connection

bp = Blueprint("professors", __name__)


# --- Listado y CRUD del usuario profesor ---


@bp.route("/api/professors", methods=["GET"])
def list_professors():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, nombre, email, rol, reputacion, fecha_creacion "
        "FROM users WHERE rol='profesor'"
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/professors", methods=["POST"])
def create_professor():
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
        (data["nombre"], data["email"], hashed, "profesor"),
    )
    conn.commit()
    pid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Profesor creado", "id": pid}), 201


@bp.route("/api/professors/<int:professor_id>", methods=["GET"])
def get_professor(professor_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    professor = get_user_by_id(cursor, professor_id)
    cursor.close()
    conn.close()
    if not is_professor(professor):
        return jsonify({"error": "Profesor no encontrado"}), 404
    return jsonify(professor)


@bp.route("/api/professors/<int:professor_id>", methods=["PUT"])
def update_professor(professor_id):
    data = get_json(request)
    fields = {k: v for k, v in data.items() if k in {"nombre", "email", "password"} and v}
    if not fields:
        return jsonify({"error": "No hay campos para actualizar"}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    professor = get_user_by_id(cursor, professor_id)
    if not is_professor(professor):
        cursor.close()
        conn.close()
        return jsonify({"error": "Profesor no encontrado"}), 404
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
    values.append(professor_id)
    cursor.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=%s AND rol='profesor'", tuple(values))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Profesor actualizado"})


@bp.route("/api/professors/<int:professor_id>", methods=["DELETE"])
def delete_professor(professor_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s AND rol='profesor'", (professor_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Profesor no encontrado"}), 404
    return jsonify({"mensaje": "Profesor eliminado"})


# --- Respuestas: por pregunta (publico) o por profesor (propiedad user_id) ---


@bp.route("/api/questions/<int:question_id>/answers", methods=["GET"])
def list_question_answers(question_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM questions WHERE id=%s", (question_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404
    cursor.execute(
        "SELECT a.id, a.contenido, a.user_id, a.question_id, a.is_accepted, a.fecha_creacion, "
        "u.nombre AS autor, u.email AS autor_email, u.avatar_ext AS autor_avatar_ext "
        "FROM answers a "
        "LEFT JOIN users u ON u.id=a.user_id "
        "WHERE a.question_id=%s ORDER BY a.fecha_creacion DESC",
        (question_id,),
    )
    data = cursor.fetchall()
    for row in data:
        autor_email = row.pop("autor_email", None)
        ext = row.pop("autor_avatar_ext", None)
        uid = row.get("user_id")
        # URL de foto: archivo propio o Gravatar segun email.
        row["autor_avatar_url"] = resolve_avatar_url(autor_email, uid, ext)
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/professors/<int:professor_id>/answers", methods=["GET"])
def list_professor_answers(professor_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    professor = get_user_by_id(cursor, professor_id)
    if not is_professor(professor):
        cursor.close()
        conn.close()
        return jsonify({"error": "Profesor no encontrado"}), 404
    cursor.execute(
        "SELECT id, contenido, user_id, question_id, is_accepted, fecha_creacion "
        "FROM answers WHERE user_id=%s ORDER BY fecha_creacion DESC",
        (professor_id,),
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/professors/<int:professor_id>/answers", methods=["POST"])
def create_professor_answer(professor_id):
    data = get_json(request)
    if not data.get("question_id") or not data.get("contenido"):
        return jsonify({"error": "question_id y contenido son obligatorios"}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    professor = get_user_by_id(cursor, professor_id)
    if not is_professor(professor):
        cursor.close()
        conn.close()
        return jsonify({"error": "Profesor no encontrado"}), 404
    cursor.execute("SELECT id FROM questions WHERE id=%s", (data["question_id"],))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Pregunta no encontrada"}), 404
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO answers (contenido, user_id, question_id) VALUES (%s,%s,%s)",
        (data["contenido"], professor_id, data["question_id"]),
    )
    conn.commit()
    aid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Respuesta creada", "id": aid}), 201


@bp.route("/api/professors/<int:professor_id>/answers/<int:answer_id>", methods=["PUT"])
def update_professor_answer(professor_id, answer_id):
    data = get_json(request)
    if not data.get("contenido"):
        return jsonify({"error": "contenido es obligatorio"}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    professor = get_user_by_id(cursor, professor_id)
    if not is_professor(professor):
        cursor.close()
        conn.close()
        return jsonify({"error": "Profesor no encontrado"}), 404
    cursor.execute("SELECT id FROM answers WHERE id=%s AND user_id=%s", (answer_id, professor_id))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Respuesta no encontrada para este profesor"}), 404
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE answers SET contenido=%s WHERE id=%s AND user_id=%s",
        (data["contenido"], answer_id, professor_id),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Respuesta actualizada"})


@bp.route("/api/professors/<int:professor_id>/answers/<int:answer_id>", methods=["DELETE"])
def delete_professor_answer(professor_id, answer_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    professor = get_user_by_id(cursor, professor_id)
    if not is_professor(professor):
        cursor.close()
        conn.close()
        return jsonify({"error": "Profesor no encontrado"}), 404
    cursor = conn.cursor()
    cursor.execute("DELETE FROM answers WHERE id=%s AND user_id=%s", (answer_id, professor_id))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Respuesta no encontrada para este profesor"}), 404
    return jsonify({"mensaje": "Respuesta eliminada"})
