"""
Contenido del foro: preguntas, etiquetas, comentarios, votos y traduccion.

Listado paginado (q, tag, id); historial (/api/questions/history); crear pregunta solo estudiante.
/api/translate: MyMemory Translation API (clave opcional en backend/config.py).
"""
import html
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Blueprint, jsonify, request, session

from common import can_moderate_content, get_json, get_user_by_id, is_student, resolve_avatar_url
from config import get_mymemory_api_key
from db import get_connection

bp = Blueprint("questions", __name__)

_QUESTION_SELECT = (
    "SELECT q.*, u.nombre AS autor, u.email AS autor_email, u.avatar_ext AS autor_avatar_ext, "
    "(SELECT GROUP_CONCAT(DISTINCT t2.nombre ORDER BY t2.nombre SEPARATOR ',') "
    "FROM question_tags qt2 INNER JOIN tags t2 ON t2.id=qt2.tag_id "
    "WHERE qt2.question_id=q.id) AS tags "
    "FROM questions q "
    "LEFT JOIN users u ON u.id=q.user_id "
)


def _enrich_question_rows(rows):
    for item in rows:
        item["tags"] = item["tags"].split(",") if item.get("tags") else []
        autor_email = item.pop("autor_email", None)
        ext = item.pop("autor_avatar_ext", None)
        uid = item.get("user_id")
        item["autor_avatar_url"] = resolve_avatar_url(autor_email, uid, ext)
    return rows


def _fetch_questions_page(cursor, where_sql, params, page, per_page):
    offset = (page - 1) * per_page
    cursor.execute(
        "SELECT COUNT(DISTINCT q.id) AS total FROM questions q "
        "LEFT JOIN question_tags qt ON qt.question_id=q.id "
        "LEFT JOIN tags t ON t.id=qt.tag_id "
        f"{where_sql}",
        tuple(params),
    )
    total = cursor.fetchone()["total"]

    cursor.execute(
        "SELECT q.id FROM questions q "
        "LEFT JOIN question_tags qt ON qt.question_id=q.id "
        "LEFT JOIN tags t ON t.id=qt.tag_id "
        f"{where_sql} GROUP BY q.id ORDER BY MAX(q.fecha_creacion) DESC LIMIT %s OFFSET %s",
        tuple(list(params) + [per_page, offset]),
    )
    ids = [r["id"] for r in cursor.fetchall()]
    if not ids:
        return [], total

    placeholders = ",".join(["%s"] * len(ids))
    cursor.execute(
        _QUESTION_SELECT + f"WHERE q.id IN ({placeholders}) "
        f"ORDER BY FIELD(q.id,{placeholders})",
        tuple(ids + ids),
    )
    return _enrich_question_rows(cursor.fetchall()), total


@bp.route("/api/questions/history", methods=["GET"])
def get_questions_history():
    """Historial de preguntas creadas: propias (estudiante) o todas (otros roles)."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "No autenticado"}), 401

    page = max(int(request.args.get("page", 1)), 1)
    per_page = max(min(int(request.args.get("per_page", 5)), 50), 1)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    actor = get_user_by_id(cursor, uid)
    if not actor:
        cursor.close()
        conn.close()
        return jsonify({"error": "No autenticado"}), 401

    filters = []
    params = []
    scope = "all"
    if is_student(actor):
        filters.append("q.user_id = %s")
        params.append(uid)
        scope = "mine"

    where_sql = f"WHERE {' AND '.join(filters)}" if filters else ""
    data, total = _fetch_questions_page(cursor, where_sql, params, page, per_page)
    cursor.close()
    conn.close()

    return jsonify(
        {
            "items": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
            "scope": scope,
        }
    )


@bp.route("/api/questions", methods=["GET"])
def get_questions():
    # Lista con paginacion; q filtra titulo/cuerpo, tag por nombre exacto en la tabla tags.
    page = max(int(request.args.get("page", 1)), 1)
    per_page = max(min(int(request.args.get("per_page", 5)), 50), 1)
    q = (request.args.get("q") or "").strip()
    if q.startswith("#"):
        q = q[1:].strip()
    tag = (request.args.get("tag") or "").strip()
    question_id = request.args.get("id")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    filters = []
    params = []
    if question_id:
        try:
            filters.append("q.id = %s")
            params.append(int(question_id))
        except (TypeError, ValueError):
            pass
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
    data, total = _fetch_questions_page(cursor, where_sql, params, page, per_page)
    cursor.close()
    conn.close()
    return jsonify(
        {
            "items": data,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total else 0,
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

MYMEMORY_GET_URL = "https://api.mymemory.translated.net/get"
MYMEMORY_MAX_BYTES = 500
MYMEMORY_MAX_WORKERS = 8
# Idioma por defecto del foro (UI y publicaciones en español).
FORO_IDIOMA_ORIGEN = "es"


def _normalize_lang(code):
    c = (code or "").strip().lower().replace("_", "-")
    if c in ("", "auto", "autodetect"):
        return "autodetect"
    if "-" in c:
        c = c.split("-", 1)[0]
    return c


def _same_language_pair(source, target):
    """MyMemory exige dos idiomas distintos (p. ej. es|es devuelve 403)."""
    return _resolve_source_lang(source) == _normalize_lang(target)


def _resolve_source_lang(source):
    src = _normalize_lang(source)
    if src == "autodetect":
        return FORO_IDIOMA_ORIGEN
    return src


def _mymemory_langpair(source, target):
    src = _resolve_source_lang(source)
    tgt = _normalize_lang(target)
    return f"{src}|{tgt}"


def _split_for_mymemory(text, max_bytes=MYMEMORY_MAX_BYTES):
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return [text]
    parts = []
    words = text.split()
    current = []
    current_len = 0
    for word in words:
        piece = word if not current else " " + word
        piece_len = len(piece.encode("utf-8"))
        if current and current_len + piece_len > max_bytes:
            parts.append(" ".join(current))
            current = [word]
            current_len = len(word.encode("utf-8"))
        else:
            current.append(word)
            current_len += piece_len
    if current:
        parts.append(" ".join(current))
    return parts or [text]


def _mymemory_fetch_chunk(chunk, langpair, api_key, target_lang=None):
    params = {"q": chunk, "langpair": langpair, "mt": "1"}
    if api_key:
        params["key"] = api_key
    url = f"{MYMEMORY_GET_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=25) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    status = parsed.get("responseStatus")
    if status and int(status) == 403 and target_lang:
        src, _, tgt = langpair.partition("|")
        if src != FORO_IDIOMA_ORIGEN:
            fallback = f"{FORO_IDIOMA_ORIGEN}|{tgt or target_lang}"
            return _mymemory_fetch_chunk(chunk, fallback, api_key, target_lang=None)
    if status and int(status) != 200:
        detail = parsed.get("responseDetails") or parsed.get("responseData")
        raise ValueError(f"MyMemory devolvio estado {status}: {detail}")
    translated = parsed.get("responseData", {}).get("translatedText", "")
    if not translated:
        raise ValueError("MyMemory no devolvio texto traducido")
    return html.unescape(translated)


def _parallel_map(fn, items):
    if not items:
        return []
    if len(items) == 1:
        return [fn(items[0])]
    out = [None] * len(items)
    with ThreadPoolExecutor(max_workers=MYMEMORY_MAX_WORKERS) as executor:
        future_to_idx = {executor.submit(fn, item): i for i, item in enumerate(items)}
        for future in as_completed(future_to_idx):
            out[future_to_idx[future]] = future.result()
    return out


def _mymemory_translate_fragment(text, langpair, api_key, target_lang=None):
    chunks = _split_for_mymemory(text)
    translated_parts = [
        _mymemory_fetch_chunk(chunk, langpair, api_key, target_lang=target_lang) for chunk in chunks
    ]
    return " ".join(translated_parts)


@bp.route("/api/translate", methods=["POST"])
def translate_text():
    """Traduce publicaciones del foro via MyMemory Translation API (REST externa)."""
    if not session.get("user_id"):
        return jsonify({"error": "Debes iniciar sesion para traducir"}), 401

    data = get_json(request)
    target = _normalize_lang(data.get("target") or "en")
    source = _normalize_lang(data.get("source") or "auto")

    raw_texts = data.get("texts")
    if raw_texts is None and data.get("text") is not None:
        raw_texts = [data.get("text")]
    if not isinstance(raw_texts, list) or not raw_texts:
        return jsonify({"error": "Indica text o texts (lista de cadenas)"}), 400

    if len(raw_texts) > 20:
        return jsonify({"error": "Maximo 20 fragmentos por solicitud"}), 400

    # Conservar posiciones: cadenas vacias no se envian a MyMemory pero se devuelven igual.
    slots = []
    to_translate = []
    for t in raw_texts:
        s = str(t).strip() if t is not None else ""
        slots.append(s)
        if s:
            to_translate.append(s)
    if not to_translate:
        return jsonify({"error": "No hay texto para traducir"}), 400

    if _same_language_pair(source, target):
        out = {
            "translations": slots,
            "target": target,
            "provider": "mymemory",
            "skipped": True,
            "message": "Origen y destino son el mismo idioma; se devuelve el texto original.",
        }
        if len(slots) == 1:
            out["translatedText"] = slots[0]
        return jsonify(out)

    api_key = get_mymemory_api_key()
    langpair = _mymemory_langpair(source, target)

    try:
        translated_nonempty = _parallel_map(
            lambda fragment: _mymemory_translate_fragment(
                fragment, langpair, api_key, target_lang=target
            ),
            to_translate,
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return jsonify({"error": "MyMemory rechazo la solicitud", "detail": detail}), 502
    except urllib.error.URLError:
        return jsonify({"error": "No se pudo conectar con MyMemory API"}), 503
    except (json.JSONDecodeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 502

    if len(translated_nonempty) != len(to_translate):
        return jsonify({"error": "Traduccion incompleta"}), 502

    translations = []
    idx = 0
    for s in slots:
        if s:
            translations.append(translated_nonempty[idx])
            idx += 1
        else:
            translations.append("")

    out = {
        "translations": translations,
        "target": target,
        "provider": "mymemory",
        "source": _resolve_source_lang(source),
    }
    if len(translations) == 1:
        out["translatedText"] = translations[0]
    return jsonify(out)
