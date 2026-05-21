"""
Aula: tareas (assignments), comentarios en tarea, entregas con archivo.

Profesor (o superadmin como profe): crear/editar/borrar tarea, comentar, calificar entregas.
Estudiante (o superadmin como alumno): comentar, subir/reemplazar archivo; descarga con permisos.
Permisos: can_act_as_classroom_professor / _student / can_moderate_content en common.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from common import (
    can_act_as_classroom_professor,
    can_act_as_classroom_student,
    can_moderate_content,
    get_json,
    get_user_by_id,
    is_superadmin,
)
from db import get_connection

bp = Blueprint("classroom", __name__)

MAX_ASSIGNMENT_BYTES = 15 * 1024 * 1024  # 15 MB
NOTA_MIN = 0.0
NOTA_MAX = 10.0


def _upload_dir():
    """Carpeta absoluta donde se guardan los PDF/ZIP de entregas."""
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "assignments")
    )


def _parse_fecha_entrega(raw):
    """None si vacio; datetime si string ISO o datetime-local. Formato invalido -> ValueError."""
    if raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        if s.endswith("Z"):
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        return datetime.fromisoformat(s)
    return None


def _assignment_owned_by(cursor, assignment_id, professor_id):
    """True si la tarea existe y professor_id es el dueño en BD."""
    cursor.execute(
        "SELECT id FROM assignments WHERE id=%s AND professor_id=%s",
        (assignment_id, professor_id),
    )
    return cursor.fetchone() is not None


# --- Listado de tareas: alumno (for_student_id) ve JOIN con su entrega; sin param, vista general ---


@bp.route("/api/assignments", methods=["GET"])
def list_assignments():
    for_student_id = request.args.get("for_student_id", type=int)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if for_student_id:
        cursor.execute(
            "SELECT a.id, a.titulo, a.descripcion, a.professor_id, a.fecha_creacion, "
            "a.fecha_entrega, "
            "u.nombre AS profesor_nombre, "
            "s.id AS mi_submission_id, s.filename_original AS mi_archivo, "
            "s.fecha_subida AS mi_fecha, s.nota AS mi_nota, "
            "s.comentario_profesor AS mi_comentario_profesor "
            "FROM assignments a "
            "JOIN users u ON u.id = a.professor_id "
            "LEFT JOIN assignment_submissions s ON s.assignment_id = a.id "
            "AND s.student_id = %s "
            "ORDER BY a.fecha_creacion DESC",
            (for_student_id,),
        )
    else:
        cursor.execute(
            "SELECT a.id, a.titulo, a.descripcion, a.professor_id, a.fecha_creacion, "
            "a.fecha_entrega, "
            "u.nombre AS profesor_nombre, "
            "(SELECT COUNT(*) FROM assignment_submissions s "
            " WHERE s.assignment_id = a.id) AS entregas_count "
            "FROM assignments a "
            "JOIN users u ON u.id = a.professor_id "
            "ORDER BY a.fecha_creacion DESC",
        )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)


def _resolve_parent_comment(cursor, assignment_id, parent_id):
    """Valida parent_id: mismo assignment; devuelve (fila, None) o (None, mensaje error)."""
    if not parent_id:
        return None, None
    cursor.execute(
        "SELECT id, is_private, assignment_id FROM assignment_comments WHERE id=%s",
        (int(parent_id),),
    )
    row = cursor.fetchone()
    if not row or row["assignment_id"] != assignment_id:
        return None, "El comentario al que respondes no existe"
    return row, None


# --- Comentarios en una tarea (lista, alta profe/alumno con parent_id opcional) ---


@bp.route("/api/assignments/<int:assignment_id>/comments", methods=["GET"])
def list_assignment_comments(assignment_id):
    viewer_id = request.args.get("viewer_user_id", type=int)
    if not viewer_id:
        return jsonify({"error": "Indica viewer_user_id"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    actor = get_user_by_id(cursor, viewer_id)
    if not actor:
        cursor.close()
        conn.close()
        return jsonify({"error": "Usuario no encontrado"}), 404

    if can_moderate_content(actor):
        # Moderador: ve todos los comentarios (incluidos privados).
        cursor.execute(
            "SELECT c.id, c.contenido, c.fecha_creacion, c.user_id, c.parent_id, c.is_private, "
            "u.nombre AS autor_nombre "
            "FROM assignment_comments c "
            "JOIN users u ON u.id = c.user_id "
            "WHERE c.assignment_id=%s "
            "ORDER BY COALESCE(c.parent_id, c.id), c.parent_id IS NOT NULL, c.fecha_creacion ASC",
            (assignment_id,),
        )
    else:
        # Resto: solo publicos o privados donde el viewer es autor o profesor de la tarea.
        cursor.execute(
            "SELECT c.id, c.contenido, c.fecha_creacion, c.user_id, c.parent_id, c.is_private, "
            "u.nombre AS autor_nombre "
            "FROM assignment_comments c "
            "JOIN assignments a ON a.id = c.assignment_id "
            "JOIN users u ON u.id = c.user_id "
            "WHERE c.assignment_id=%s "
            "AND (c.is_private = 0 OR c.user_id = %s OR a.professor_id = %s) "
            "ORDER BY COALESCE(c.parent_id, c.id), c.parent_id IS NOT NULL, c.fecha_creacion ASC",
            (assignment_id, viewer_id, viewer_id),
        )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(rows)


@bp.route("/api/assignments/<int:assignment_id>/comments", methods=["POST"])
def create_assignment_comment(assignment_id):
    data = get_json(request)
    professor_id = data.get("professor_id")
    contenido = (data.get("contenido") or "").strip()
    parent_id = data.get("parent_id")
    if not professor_id or not contenido:
        return jsonify({"error": "professor_id y contenido son obligatorios"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    prof = get_user_by_id(cursor, int(professor_id))
    if not can_act_as_classroom_professor(prof):
        cursor.close()
        conn.close()
        return jsonify({"error": "Solo un profesor puede usar esta ruta"}), 403
    if not (
        is_superadmin(prof)
        or _assignment_owned_by(cursor, assignment_id, int(professor_id))
    ):
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada o no es tuya"}), 404

    parent_row, err = _resolve_parent_comment(cursor, assignment_id, parent_id)
    if err:
        cursor.close()
        conn.close()
        return jsonify({"error": err}), 400

    cursor.execute(
        "INSERT INTO assignment_comments "
        "(assignment_id, user_id, parent_id, is_private, contenido) "
        "VALUES (%s,%s,%s,0,%s)",
        (assignment_id, int(professor_id), parent_row["id"] if parent_row else None, contenido),
    )
    conn.commit()
    cid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Comentario publicado", "id": cid}), 201


# --- Comentario como estudiante (privado opcional; hilo bajo parent_id) ---


@bp.route("/api/students/<int:student_id>/assignments/<int:assignment_id>/comments", methods=["POST"])
def create_student_assignment_comment(student_id, assignment_id):
    data = get_json(request)
    contenido = (data.get("contenido") or "").strip()
    parent_id = data.get("parent_id")
    is_private = bool(data.get("is_private"))
    if not contenido:
        return jsonify({"error": "contenido es obligatorio"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not can_act_as_classroom_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Solo estudiantes pueden usar esta ruta"}), 403

    cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    parent_row, err = _resolve_parent_comment(cursor, assignment_id, parent_id)
    if err:
        cursor.close()
        conn.close()
        return jsonify({"error": err}), 400

    if parent_row and int(parent_row.get("is_private") or 0) == 1:
        is_private = True

    cursor.execute(
        "INSERT INTO assignment_comments "
        "(assignment_id, user_id, parent_id, is_private, contenido) "
        "VALUES (%s,%s,%s,%s,%s)",
        (
            assignment_id,
            student_id,
            parent_row["id"] if parent_row else None,
            1 if is_private else 0,
            contenido,
        ),
    )
    conn.commit()
    cid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Comentario publicado", "id": cid}), 201


# --- CRUD tarea por profesor_id (superadmin puede actuar como cualquier profe) ---


@bp.route("/api/professors/<int:professor_id>/assignments", methods=["POST"])
def create_assignment(professor_id):
    data = get_json(request)
    titulo = (data.get("titulo") or "").strip()
    descripcion = (data.get("descripcion") or "").strip()
    fecha_entrega = _parse_fecha_entrega(data.get("fecha_entrega"))
    if not titulo:
        return jsonify({"error": "El titulo es obligatorio"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    prof = get_user_by_id(cursor, professor_id)
    if not can_act_as_classroom_professor(prof):
        cursor.close()
        conn.close()
        return jsonify({"error": "Solo un profesor puede publicar tareas"}), 403

    cursor.execute(
        "INSERT INTO assignments (titulo, descripcion, professor_id, fecha_entrega) "
        "VALUES (%s,%s,%s,%s)",
        (titulo, descripcion or None, professor_id, fecha_entrega),
    )
    conn.commit()
    aid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Tarea creada", "id": aid}), 201


@bp.route("/api/professors/<int:professor_id>/assignments/<int:assignment_id>", methods=["PUT"])
def update_assignment(professor_id, assignment_id):
    data = get_json(request)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    prof = get_user_by_id(cursor, professor_id)
    if not can_act_as_classroom_professor(prof):
        cursor.close()
        conn.close()
        return jsonify({"error": "No autorizado"}), 403
    if is_superadmin(prof):
        cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    elif not _assignment_owned_by(cursor, assignment_id, professor_id):
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404
    else:
        cursor.execute(
            "SELECT id FROM assignments WHERE id=%s AND professor_id=%s",
            (assignment_id, professor_id),
        )
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

    if is_superadmin(prof):
        sql = f"UPDATE assignments SET {', '.join(fields)} WHERE id=%s"
        params.append(assignment_id)
    else:
        sql = f"UPDATE assignments SET {', '.join(fields)} WHERE id=%s AND professor_id=%s"
        params.extend([assignment_id, professor_id])
    cursor.execute(sql, tuple(params))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Tarea actualizada"})


@bp.route("/api/professors/<int:professor_id>/assignments/<int:assignment_id>", methods=["DELETE"])
def delete_assignment(professor_id, assignment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    prof = get_user_by_id(cursor, professor_id)
    if not can_act_as_classroom_professor(prof):
        cursor.close()
        conn.close()
        return jsonify({"error": "No autorizado"}), 403

    if is_superadmin(prof):
        cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    else:
        cursor.execute(
            "SELECT id FROM assignments WHERE id=%s AND professor_id=%s",
            (assignment_id, professor_id),
        )
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    cursor.execute(
        "SELECT stored_filename FROM assignment_submissions WHERE assignment_id=%s",
        (assignment_id,),
    )
    # Borrar archivos de entregas antes de eliminar filas (FK / cascada segun esquema).
    for row in cursor.fetchall():
        path = os.path.join(_upload_dir(), row["stored_filename"])
        if os.path.isfile(path):
            os.remove(path)

    cursor.execute("DELETE FROM assignments WHERE id=%s", (assignment_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Tarea eliminada"})


# --- Calificar entrega (PATCH nota y/o comentario_profesor) ---


@bp.route("/api/professors/<int:professor_id>/submissions/<int:submission_id>/grade", methods=["PATCH"])
def grade_submission(professor_id, submission_id):
    data = get_json(request)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    prof = get_user_by_id(cursor, professor_id)
    if not can_act_as_classroom_professor(prof):
        cursor.close()
        conn.close()
        return jsonify({"error": "No autorizado"}), 403

    cursor.execute(
        "SELECT s.id, a.professor_id FROM assignment_submissions s "
        "JOIN assignments a ON a.id = s.assignment_id "
        "WHERE s.id=%s",
        (submission_id,),
    )
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "Entrega no encontrada"}), 404
    if not is_superadmin(prof) and row["professor_id"] != professor_id:
        cursor.close()
        conn.close()
        return jsonify({"error": "Entrega no encontrada"}), 404

    updates = []
    params = []

    if "nota" in data:
        raw_n = data.get("nota")
        if raw_n is None or raw_n == "":
            nota_val = None
        else:
            nota_val = float(raw_n)  # no numerico -> ValueError hacia arriba
            if nota_val < NOTA_MIN or nota_val > NOTA_MAX:
                cursor.close()
                conn.close()
                return jsonify({"error": f"La nota debe estar entre {NOTA_MIN} y {NOTA_MAX}"}), 400
        updates.append("nota=%s")
        params.append(nota_val)

    if "comentario_profesor" in data:
        raw_c = data.get("comentario_profesor")
        if raw_c is None:
            comentario = None
        else:
            comentario = str(raw_c).strip() or None
        updates.append("comentario_profesor=%s")
        params.append(comentario)

    if not updates:
        cursor.close()
        conn.close()
        return jsonify({"error": "Indica nota o comentario_profesor"}), 400

    sql = "UPDATE assignment_submissions SET " + ", ".join(updates) + " WHERE id=%s"
    params.append(submission_id)
    cursor.execute(sql, tuple(params))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Calificacion guardada"})


# --- Profesor lista entregas de una tarea ---


@bp.route("/api/assignments/<int:assignment_id>/submissions", methods=["GET"])
def list_submissions(assignment_id):
    professor_id = request.args.get("professor_id", type=int)
    if not professor_id:
        return jsonify({"error": "Indica professor_id"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    prof = get_user_by_id(cursor, professor_id)
    if not can_act_as_classroom_professor(prof):
        cursor.close()
        conn.close()
        return jsonify({"error": "No autorizado"}), 403

    if is_superadmin(prof):
        cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    else:
        cursor.execute(
            "SELECT id FROM assignments WHERE id=%s AND professor_id=%s",
            (assignment_id, professor_id),
        )
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


# --- Subida o sustitucion de archivo de entrega (ON DUPLICATE KEY en submission) ---


@bp.route("/api/students/<int:student_id>/assignments/<int:assignment_id>/submit", methods=["POST"])
def submit_assignment(student_id, assignment_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    student = get_user_by_id(cursor, student_id)
    if not can_act_as_classroom_student(student):
        cursor.close()
        conn.close()
        return jsonify({"error": "Solo estudiantes pueden entregar tareas"}), 403

    cursor.execute("SELECT id FROM assignments WHERE id=%s", (assignment_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Tarea no encontrada"}), 404

    if "file" not in request.files or not request.files["file"].filename:
        cursor.close()
        conn.close()
        return jsonify({"error": "Debes adjuntar un archivo (campo file)"}), 400

    f = request.files["file"]
    raw_name = f.filename or "entrega"
    safe = secure_filename(raw_name) or "entrega"
    ext = os.path.splitext(safe)[1][:20]
    stored = f"{uuid.uuid4().hex}{ext}"
    upload_dir = _upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    dest = os.path.join(upload_dir, stored)

    raw_bytes = f.read()
    size = len(raw_bytes)
    if size > MAX_ASSIGNMENT_BYTES:
        cursor.close()
        conn.close()
        return jsonify({"error": f"Archivo demasiado grande (max {MAX_ASSIGNMENT_BYTES // (1024*1024)} MB)"}), 400

    cursor.execute(
        "SELECT id, stored_filename FROM assignment_submissions "
        "WHERE assignment_id=%s AND student_id=%s",
        (assignment_id, student_id),
    )
    prev = cursor.fetchone()
    if prev:
        old_path = os.path.join(upload_dir, prev["stored_filename"])
        if os.path.isfile(old_path):
            os.remove(old_path)

    with open(dest, "wb") as out:
        out.write(raw_bytes)

    mime = f.mimetype or None
    cursor.execute(
        "INSERT INTO assignment_submissions "
        "(assignment_id, student_id, filename_original, stored_filename, mime_type, size_bytes) "
        "VALUES (%s,%s,%s,%s,%s,%s) "
        "ON DUPLICATE KEY UPDATE "
        "filename_original=VALUES(filename_original), "
        "stored_filename=VALUES(stored_filename), "
        "mime_type=VALUES(mime_type), "
        "size_bytes=VALUES(size_bytes), "
        "fecha_subida=CURRENT_TIMESTAMP, "
        "nota=nota, "
        "comentario_profesor=comentario_profesor",
        (assignment_id, student_id, raw_name, stored, mime, size),
    )
    conn.commit()
    cursor.execute(
        "SELECT id FROM assignment_submissions WHERE assignment_id=%s AND student_id=%s",
        (assignment_id, student_id),
    )
    sid = cursor.fetchone()["id"]
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Entrega registrada", "submission_id": sid}), 201


# --- Descarga de entrega: alumno dueño, profesor de la tarea o moderador ---


@bp.route("/api/assignment-submissions/<int:submission_id>/download", methods=["GET"])
def download_submission(submission_id):
    user_id = request.args.get("user_id", type=int)
    if not user_id:
        return jsonify({"error": "Indica user_id"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    actor = get_user_by_id(cursor, user_id)
    if not actor:
        cursor.close()
        conn.close()
        return jsonify({"error": "Usuario no encontrado"}), 404

    cursor.execute(
        "SELECT s.stored_filename, s.filename_original, s.student_id, a.professor_id "
        "FROM assignment_submissions s "
        "JOIN assignments a ON a.id = s.assignment_id "
        "WHERE s.id=%s",
        (submission_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if not row:
        return jsonify({"error": "Entrega no encontrada"}), 404

    allowed = (
        row["student_id"] == user_id
        or row["professor_id"] == user_id
        or can_moderate_content(actor)
    )
    if not allowed:
        return jsonify({"error": "No autorizado"}), 403

    directory = _upload_dir()
    path = os.path.join(directory, row["stored_filename"])
    if not os.path.isfile(path):
        return jsonify({"error": "Archivo no disponible"}), 404

    return send_from_directory(
        directory,
        row["stored_filename"],
        as_attachment=True,
        download_name=row["filename_original"] or "entrega",
    )
