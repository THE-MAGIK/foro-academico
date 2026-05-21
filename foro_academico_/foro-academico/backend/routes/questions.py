"""
Contenido del foro: preguntas, etiquetas, comentarios, votos y traduccion.

Listado paginado (q, tag); crear pregunta solo estudiante; votos UPSERT por usuario.
/api/translate: proxy a Google Cloud Translation (requiere GOOGLE_TRANSLATE_API_KEY).
"""
import json
import os
import urllib.parse
import urllib.request

from flask import Blueprint, jsonify, request, session

from common import can_moderate_content, get_json, get_user_by_id, is_student, resolve_avatar_url
from db import get_connection

bp = Blueprint("questions", __name__)


@bp.route("/api/questions", methods=["GET"])
def get_questions():
    # Lista con paginacion; q filtra titulo/cuerpo, tag por nombre exacto en la tabla tags.
    page = max(int(request.args.get("page", 1)), 1)
    per_page = max(min(int(request.args.get("per_page", 10)), 50), 1)
    offset = (page - 1) * per_page
    q = (request.args.get("q") or "").strip()
    if q.startswith("#"):
        q = q[1:].strip()
    tag = (request.args.get("tag") or "").strip()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    filters = []
    params = []
    if q:
        # Titulo, cuerpo o nombre de etiqueta asociada (ej. buscar "python" encuentra tag).
        filters.append(
            "(q.titulo LIKE %s OR q.contenido LIKE %s OR t.nombre LIKE %s)"
        )
        like = f"%{q}%"
        params.extend([like, like, like])
    if tag:
        filters.append("t.nombre = %s")
        params.append(tag)

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    cursor.execute(
        "SELECT COUNT(DISTINCT q.id) AS total "
        "FROM questions q "
        "LEFT JOIN question_tags qt ON qt.question_id=q.id "
        "LEFT JOIN tags t ON t.id=qt.tag_id "
        f"{where_sql}",
        tuple(params),
    )
    total = cursor.fetchone()["total"]

    # Paginar por id (GROUP BY solo q.id) y luego cargar filas completas sin q.* + GROUP BY,
    # que en MySQL con ONLY_FULL_GROUP_BY suele fallar o devolver resultados vacíos.
    cursor.execute(
        "SELECT q.id FROM questions q "
        "LEFT JOIN question_tags qt ON qt.question_id=q.id "
        "LEFT JOIN tags t ON t.id=qt.tag_id "
        f"{where_sql} GROUP BY q.id ORDER BY MAX(q.fecha_creacion) DESC LIMIT %s OFFSET %s",
        tuple(list(params) + [per_page, offset]),
    )
    id_rows = cursor.fetchall()
    ids = [r["id"] for r in id_rows]
    if not ids:
        data = []
    else:
        placeholders = ",".join(["%s"] * len(ids))
        cursor.execute(
            "SELECT q.*, u.nombre AS autor, u.email AS autor_email, u.avatar_ext AS autor_avatar_ext, "
            "(SELECT GROUP_CONCAT(DISTINCT t2.nombre ORDER BY t2.nombre SEPARATOR ',') "
            "FROM question_tags qt2 INNER JOIN tags t2 ON t2.id=qt2.tag_id "
            "WHERE qt2.question_id=q.id) AS tags "
            "FROM questions q "
            "LEFT JOIN users u ON u.id=q.user_id "
            f"WHERE q.id IN ({placeholders}) "
            f"ORDER BY FIELD(q.id,{placeholders})",
            tuple(ids + ids),
        )
        data = cursor.fetchall()
    for item in data:
        item["tags"] = item["tags"].split(",") if item.get("tags") else []
        autor_email = item.pop("autor_email", None)
        ext = item.pop("autor_avatar_ext", None)
        uid = item.get("user_id")
        item["autor_avatar_url"] = resolve_avatar_url(autor_email, uid, ext)
    cursor.close()
    conn.close()
    return jsonify(
        {
            "items": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page,
        }
    )


@bp.route("/api/questions", methods=["POST"])
def create_question():
    # Crea fila en questions y opcionalmente enlaza etiquetas en tags / question_tags.
    data = get_json(request)
    required = ["titulo", "descripcion", "user_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Faltan campos: {', '.join(missing)}"}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, data["user_id"])
    if not is_student(user):
        cursor.close()
        conn.close()
        return jsonify({"error": "Solo estudiantes pueden publicar preguntas"}), 403

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO questions (titulo, contenido, user_id) VALUES (%s,%s,%s)",
        (data["titulo"], data["descripcion"], data["user_id"]),
    )
    conn.commit()
    qid = cursor.lastrowid
    tags = data.get("tags", [])
    if isinstance(tags, list):
        for tag_name in tags:
            clean = str(tag_name).strip().lower()
            if not clean:
                continue
            cursor.execute("INSERT IGNORE INTO tags (nombre) VALUES (%s)", (clean,))
            cursor.execute("SELECT id FROM tags WHERE nombre=%s", (clean,))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "INSERT IGNORE INTO question_tags (question_id, tag_id) VALUES (%s,%s)",
                    (qid, row[0]),
                )
        conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Pregunta creada", "id": qid}), 201


# --- Comentarios (tabla comments; puede ir ligado a pregunta o a respuesta)

@bp.route("/api/questions/<int:question_id>/comments", methods=["GET"])
def list_question_comments(question_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT c.id, c.contenido, c.user_id, u.nombre AS autor, u.email AS autor_email, "
        "u.avatar_ext AS autor_avatar_ext, "
        "c.fecha_creacion "
        "FROM comments c LEFT JOIN users u ON c.user_id=u.id "
        "WHERE c.question_id=%s ORDER BY c.fecha_creacion ASC",
        (question_id,),
    )
    data = cursor.fetchall()
    for row in data:
        autor_email = row.pop("autor_email", None)
        ext = row.pop("autor_avatar_ext", None)
        uid = row.get("user_id")
        row["avatar_url"] = resolve_avatar_url(autor_email, uid, ext)
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/questions/<int:question_id>/comments", methods=["POST"])
def create_question_comment(question_id):
    data = get_json(request)
    if not data.get("user_id") or not data.get("contenido"):
        return jsonify({"error": "user_id y contenido son obligatorios"}), 400
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (contenido, user_id, question_id) VALUES (%s,%s,%s)",
        (data["contenido"], data["user_id"], question_id),
    )
    conn.commit()
    cid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Comentario creado", "id": cid}), 201


@bp.route("/api/answers/<int:answer_id>/comments", methods=["GET"])
def list_answer_comments(answer_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT c.id, c.contenido, c.user_id, u.nombre AS autor, u.email AS autor_email, "
        "u.avatar_ext AS autor_avatar_ext, "
        "c.fecha_creacion "
        "FROM comments c LEFT JOIN users u ON c.user_id=u.id "
        "WHERE c.answer_id=%s ORDER BY c.fecha_creacion ASC",
        (answer_id,),
    )
    data = cursor.fetchall()
    for row in data:
        autor_email = row.pop("autor_email", None)
        ext = row.pop("autor_avatar_ext", None)
        uid = row.get("user_id")
        row["avatar_url"] = resolve_avatar_url(autor_email, uid, ext)
    cursor.close()
    conn.close()
    return jsonify(data)


@bp.route("/api/answers/<int:answer_id>/comments", methods=["POST"])
def create_answer_comment(answer_id):
    data = get_json(request)
    if not data.get("user_id") or not data.get("contenido"):
        return jsonify({"error": "user_id y contenido son obligatorios"}), 400
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO comments (contenido, user_id, answer_id) VALUES (%s,%s,%s)",
        (data["contenido"], data["user_id"], answer_id),
    )
    conn.commit()
    cid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Comentario creado", "id": cid}), 201


# --- Votos (tabla votes; una fila por usuario y pregunta o respuesta)

def vote_entity(user_id, tipo, question_id=None, answer_id=None):
    # Un voto por usuario y pregunta/respuesta; no se puede cambiar despues.
    if tipo not in {"upvote", "downvote"}:
        return {"error": "tipo invalido, usa upvote/downvote"}, 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    if question_id is not None:
        cursor.execute(
            "SELECT id FROM votes WHERE user_id=%s AND question_id=%s",
            (user_id, question_id),
        )
    else:
        cursor.execute(
            "SELECT id FROM votes WHERE user_id=%s AND answer_id=%s",
            (user_id, answer_id),
        )
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return {"error": "Solo puedes votar una vez; el voto no se puede cambiar"}, 409
    cursor.close()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO votes (user_id, question_id, answer_id, tipo) VALUES (%s,%s,%s,%s)",
        (user_id, question_id, answer_id, tipo),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return {"mensaje": "Voto registrado"}, 200


@bp.route("/api/questions/<int:question_id>/votes", methods=["POST"])
def vote_question(question_id):
    data = get_json(request)
    if not data.get("user_id") or not data.get("tipo"):
        return jsonify({"error": "user_id y tipo son obligatorios"}), 400
    payload, code = vote_entity(data["user_id"], data["tipo"], question_id=question_id)
    return jsonify(payload), code


@bp.route("/api/answers/<int:answer_id>/votes", methods=["POST"])
def vote_answer(answer_id):
    data = get_json(request)
    if not data.get("user_id") or not data.get("tipo"):
        return jsonify({"error": "user_id y tipo son obligatorios"}), 400
    payload, code = vote_entity(data["user_id"], data["tipo"], answer_id=answer_id)
    return jsonify(payload), code


@bp.route("/api/questions/<int:question_id>/votes", methods=["GET"])
def get_question_votes(question_id):
    user_id = request.args.get("user_id", type=int)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT "
        "SUM(CASE WHEN tipo='upvote' THEN 1 ELSE 0 END) AS upvotes, "
        "SUM(CASE WHEN tipo='downvote' THEN 1 ELSE 0 END) AS downvotes "
        "FROM votes WHERE question_id=%s",
        (question_id,),
    )
    data = cursor.fetchone()
    mi_voto = None
    if user_id:
        cursor.execute(
            "SELECT tipo FROM votes WHERE question_id=%s AND user_id=%s",
            (question_id, user_id),
        )
        row = cursor.fetchone()
        if row:
            mi_voto = row["tipo"]
    cursor.close()
    conn.close()
    upvotes = int(data["upvotes"] or 0)
    downvotes = int(data["downvotes"] or 0)
    return jsonify(
        {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "score": upvotes - downvotes,
            "mi_voto": mi_voto,
        }
    )


@bp.route("/api/answers/<int:answer_id>/votes", methods=["GET"])
def get_answer_votes(answer_id):
    user_id = request.args.get("user_id", type=int)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT "
        "SUM(CASE WHEN tipo='upvote' THEN 1 ELSE 0 END) AS upvotes, "
        "SUM(CASE WHEN tipo='downvote' THEN 1 ELSE 0 END) AS downvotes "
        "FROM votes WHERE answer_id=%s",
        (answer_id,),
    )
    data = cursor.fetchone()
    mi_voto = None
    if user_id:
        cursor.execute(
            "SELECT tipo FROM votes WHERE answer_id=%s AND user_id=%s",
            (answer_id, user_id),
        )
        row = cursor.fetchone()
        if row:
            mi_voto = row["tipo"]
    cursor.close()
    conn.close()
    upvotes = int(data["upvotes"] or 0)
    downvotes = int(data["downvotes"] or 0)
    return jsonify(
        {
            "upvotes": upvotes,
            "downvotes": downvotes,
            "score": upvotes - downvotes,
            "mi_voto": mi_voto,
        }
    )


# --- Listado de etiquetas para autocompletar o filtros en el front

@bp.route("/api/tags", methods=["GET"])
def list_tags():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, nombre FROM tags ORDER BY nombre ASC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(data)


def _require_moderator_session():
    """Solo admin o superadmin (sesion)."""
    uid = session.get("user_id")
    if not uid:
        return None, (jsonify({"error": "No autenticado"}), 401)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    user = get_user_by_id(cursor, uid)
    cursor.close()
    conn.close()
    if not user or not can_moderate_content(user):
        return None, (jsonify({"error": "Solo administradores pueden gestionar etiquetas"}), 403)
    return user, None


def _normalize_tag_nombre(raw):
    """Nombre unico en minusculas; evita comas y caracteres problematicos."""
    s = (raw or "").strip().lower()
    if not s or len(s) > 64:
        return None, "La etiqueta debe tener entre 1 y 64 caracteres"
    for ch in s:
        if ch in ",;<>\"'\\":
            return None, "Caracteres no permitidos en la etiqueta"
    return s, None


@bp.route("/api/tags", methods=["POST"])
def create_tag_moderation():
    """Crear etiqueta en el catalogo (moderacion)."""
    _, err = _require_moderator_session()
    if err:
        return err
    data = get_json(request)
    nombre, msg = _normalize_tag_nombre(data.get("nombre"))
    if not nombre:
        return jsonify({"error": msg}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM tags WHERE nombre=%s", (nombre,))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Ya existe esa etiqueta"}), 409
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tags (nombre) VALUES (%s)", (nombre,))
    conn.commit()
    tid = cursor.lastrowid
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Etiqueta creada", "tag": {"id": tid, "nombre": nombre}}), 201


@bp.route("/api/tags/<int:tag_id>", methods=["PATCH", "PUT"])
def update_tag_moderation(tag_id):
    """Renombrar etiqueta (moderacion)."""
    _, err = _require_moderator_session()
    if err:
        return err
    data = get_json(request)
    nombre, msg = _normalize_tag_nombre(data.get("nombre"))
    if not nombre:
        return jsonify({"error": msg}), 400
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM tags WHERE id=%s", (tag_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Etiqueta no encontrada"}), 404
    cursor.execute("SELECT id FROM tags WHERE nombre=%s AND id!=%s", (nombre, tag_id))
    if cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Ya existe otra etiqueta con ese nombre"}), 409
    cursor = conn.cursor()
    cursor.execute("UPDATE tags SET nombre=%s WHERE id=%s", (nombre, tag_id))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({"mensaje": "Etiqueta actualizada", "tag": {"id": tag_id, "nombre": nombre}})


@bp.route("/api/tags/<int:tag_id>", methods=["DELETE"])
def delete_tag_moderation(tag_id):
    """Eliminar etiqueta y enlaces en preguntas (moderacion)."""
    _, err = _require_moderator_session()
    if err:
        return err
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM tags WHERE id=%s", (tag_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return jsonify({"error": "Etiqueta no encontrada"}), 404
    cursor.close()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM question_tags WHERE tag_id=%s", (tag_id,))
    cursor.execute("DELETE FROM tags WHERE id=%s", (tag_id,))
    conn.commit()
    deleted = cursor.rowcount
    cursor.close()
    conn.close()
    if deleted == 0:
        return jsonify({"error": "Etiqueta no encontrada"}), 404
    return jsonify({"mensaje": "Etiqueta eliminada"})

@bp.route("/api/translate", methods=["POST"])
def translate_text():
    # POST a Google; fallos de red o JSON invalido propagan excepcion (502 no forzado aqui).
    data = get_json(request)
    text = data.get("text")
    target = data.get("target", "en")
    source = data.get("source", "es")
    if not text:
        return jsonify({"error": "text es obligatorio"}), 400
    api_key = os.getenv("GOOGLE_TRANSLATE_API_KEY")
    if not api_key:
        return jsonify({"error": "Falta GOOGLE_TRANSLATE_API_KEY para usar Google Translate API"}), 400

    endpoint = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
    payload = urllib.parse.urlencode({"q": text, "target": target, "source": source}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    translated = parsed["data"]["translations"][0]["translatedText"]
    return jsonify({"translatedText": translated})
