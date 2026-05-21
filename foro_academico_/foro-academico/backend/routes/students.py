"""
CRUD de usuarios con rol estudiante (tabla users, rol='estudiante').

Incluye CRUD de preguntas del foro bajo /students/:id/questions (solo si user_id de la pregunta coincide).
"""
import bcrypt
from flask import Blueprint, jsonify, request

from common import get_json, get_user_by_id, is_student
from db import get_connection

bp = Blueprint("students", __name__)


# --- Listado y CRUD del usuario estudiante ---


@bp.route("/api/students", methods=["GET"])
def list_students():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT id, nombre, email, rol, reputacion, fecha_creacion "
        "FROM users WHERE rol='estudiante'"
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/students", methods=["POST"])
def create_student():
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
        (data["nombre"], data["email"], hashed, "estudiante"),
    )
    conn.commit()
    student_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Estudiante creado", "id": student_id}), 201


@bp.route("/api/students/<int:student_id>", methods=["GET"])
def get_student(student_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    cursor.close()
    conn.close()
    if not is_student(student):
        return jsonify({"error": "Estudiante no encontrado"}), 404
    return jsonify(student)


@bp.route("/api/students/<int:student_id>", methods=["PUT"])
def update_student(student_id):
    data = get_json(request)
    allowed = {k: v for k, v in data.items() if k in {"nombre", "email", "password"} and v}
    if not allowed:
        return jsonify({"error": "No hay campos para actualizar"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not is_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Estudiante no encontrado"}), 404

    cursor = conn.cursor()
    updates = []
    values = []
    if "nombre" in allowed:
        updates.append("nombre=%s")
        values.append(allowed["nombre"])
    if "email" in allowed:
        updates.append("email=%s")
        values.append(allowed["email"])
    if "password" in allowed:
        updates.append("password=%s")
        values.append(bcrypt.hashpw(allowed["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8"))
    values.append(student_id)

    cursor.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id=%s AND rol='estudiante'",
        tuple(values),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Estudiante actualizado"})


@bp.route("/api/students/<int:student_id>", methods=["DELETE"])
def delete_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s AND rol='estudiante'", (student_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Estudiante no encontrado"}), 404
    return jsonify({"mensaje": "Estudiante eliminado"})


# --- Preguntas del foro ligadas al estudiante (user_id = student_id) ---


@bp.route("/api/students/<int:student_id>/questions", methods=["GET"])
def list_student_questions(student_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not is_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Estudiante no encontrado"}), 404
    cursor.execute(
        "SELECT id, titulo, contenido, user_id, fecha_creacion "
        "FROM questions WHERE user_id=%s ORDER BY fecha_creacion DESC",
        (student_id,),
    )
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/students/<int:student_id>/questions", methods=["POST"])
def create_student_question(student_id):
    data = get_json(request)
    if not data.get("titulo") or not data.get("contenido"):
        return jsonify({"error": "titulo y contenido son obligatorios"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not is_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Estudiante no encontrado"}), 404

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO questions (titulo, contenido, user_id) VALUES (%s,%s,%s)",
        (data["titulo"], data["contenido"], student_id),
    )
    conn.commit()
    qid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Pregunta creada", "id": qid}), 201


@bp.route("/api/students/<int:student_id>/questions/<int:question_id>", methods=["PUT"])
def update_student_question(student_id, question_id):
    data = get_json(request)
    fields = {k: v for k, v in data.items() if k in {"titulo", "contenido"} and v}
    if not fields:
        return jsonify({"error": "No hay campos para actualizar"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not is_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Estudiante no encontrado"}), 404
    cursor.execute("SELECT id FROM questions WHERE id=%s AND user_id=%s", (question_id, student_id))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Pregunta no encontrada para este estudiante"}), 404

    cursor = conn.cursor()
    updates = []
    values = []
    if "titulo" in fields:
        updates.append("titulo=%s")
        values.append(fields["titulo"])
    if "contenido" in fields:
        updates.append("contenido=%s")
        values.append(fields["contenido"])
    values.extend([question_id, student_id])
    cursor.execute(f"UPDATE questions SET {', '.join(updates)} WHERE id=%s AND user_id=%s", tuple(values))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Pregunta actualizada"})


@bp.route("/api/students/<int:student_id>/questions/<int:question_id>", methods=["DELETE"])
def delete_student_question(student_id, question_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not is_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Estudiante no encontrado"}), 404
    cursor = conn.cursor()
    cursor.execute("DELETE FROM questions WHERE id=%s AND user_id=%s", (question_id, student_id))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Pregunta no encontrada para este estudiante"}), 404
    return jsonify({"mensaje": "Pregunta eliminada"})
