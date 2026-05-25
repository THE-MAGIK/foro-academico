"""
Conexion a MySQL para toda la API.

Un solo lugar para host, usuario y base; el resto del codigo solo llama get_connection().
"""
import os

import mysql.connector


def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root1234",  # debe coincidir con tu servidor MySQL local
        database="foro_academico",
    )


def ensure_schema():
    """Crea columnas o carpetas necesarias si faltan (desarrollo local)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = 'users' "
        "AND column_name = 'avatar_ext'"
    )
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN avatar_ext VARCHAR(8) NULL DEFAULT NULL"
        )
        conn.commit()

    # Rol 'superadmin' (10 caracteres): ENUM antiguos o VARCHAR corto provocan
    # "Data truncated for column 'rol'". Normalizamos a VARCHAR(32).
    cursor.execute(
        "SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, COLUMN_TYPE "
        "FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = 'rol'"
    )
    rol_row = cursor.fetchone()
    if rol_row:
        dtype = (rol_row[0] or "").lower()
        maxlen = rol_row[1]
        ctype = (rol_row[2] or "").lower()
        need_rol_alter = False
        if dtype == "enum" and "superadmin" not in ctype:
            need_rol_alter = True
        elif dtype in ("varchar", "char") and maxlen is not None and int(maxlen) < 32:
            need_rol_alter = True
        if need_rol_alter:
            cursor.execute(
                "ALTER TABLE users MODIFY COLUMN rol VARCHAR(32) NOT NULL DEFAULT 'estudiante'"
            )
            conn.commit()

    cursor.execute(
        "CREATE TABLE IF NOT EXISTS assignments ("
        "id INT AUTO_INCREMENT PRIMARY KEY,"
        "titulo VARCHAR(255) NOT NULL,"
        "descripcion TEXT,"
        "professor_id INT NOT NULL,"
        "fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "fecha_entrega DATETIME NULL DEFAULT NULL,"
        "INDEX idx_assignments_professor (professor_id),"
        "CONSTRAINT fk_assignments_professor FOREIGN KEY (professor_id) "
        "REFERENCES users(id) ON DELETE CASCADE"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS assignment_submissions ("
        "id INT AUTO_INCREMENT PRIMARY KEY,"
        "assignment_id INT NOT NULL,"
        "student_id INT NOT NULL,"
        "filename_original VARCHAR(255) NOT NULL,"
        "stored_filename VARCHAR(255) NOT NULL,"
        "mime_type VARCHAR(128),"
        "size_bytes BIGINT,"
        "fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "nota DECIMAL(5,2) NULL DEFAULT NULL,"
        "comentario_profesor TEXT NULL,"
        "UNIQUE KEY uq_assignment_student (assignment_id, student_id),"
        "CONSTRAINT fk_sub_assignment FOREIGN KEY (assignment_id) "
        "REFERENCES assignments(id) ON DELETE CASCADE,"
        "CONSTRAINT fk_sub_student FOREIGN KEY (student_id) "
        "REFERENCES users(id) ON DELETE CASCADE"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS assignment_comments ("
        "id INT AUTO_INCREMENT PRIMARY KEY,"
        "assignment_id INT NOT NULL,"
        "user_id INT NOT NULL,"
        "parent_id INT NULL DEFAULT NULL,"
        "is_private TINYINT(1) NOT NULL DEFAULT 0,"
        "contenido TEXT NOT NULL,"
        "fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "INDEX idx_asgcom_assignment (assignment_id),"
        "INDEX idx_asgcom_parent (parent_id),"
        "CONSTRAINT fk_asgcom_assignment FOREIGN KEY (assignment_id) "
        "REFERENCES assignments(id) ON DELETE CASCADE,"
        "CONSTRAINT fk_asgcom_user FOREIGN KEY (user_id) "
        "REFERENCES users(id) ON DELETE CASCADE,"
        "CONSTRAINT fk_asgcom_parent FOREIGN KEY (parent_id) "
        "REFERENCES assignment_comments(id) ON DELETE CASCADE"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )
    conn.commit()

    def col_exists(table, column):
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
            (table, column),
        )
        return cursor.fetchone()[0] > 0

    if not col_exists("assignments", "fecha_entrega"):
        cursor.execute(
            "ALTER TABLE assignments ADD COLUMN fecha_entrega DATETIME NULL DEFAULT NULL"
        )
        conn.commit()
    if not col_exists("assignment_submissions", "nota"):
        cursor.execute(
            "ALTER TABLE assignment_submissions ADD COLUMN nota DECIMAL(5,2) NULL DEFAULT NULL"
        )
        conn.commit()
    if not col_exists("assignment_comments", "parent_id"):
        cursor.execute(
            "ALTER TABLE assignment_comments ADD COLUMN parent_id INT NULL DEFAULT NULL"
        )
        conn.commit()
    if not col_exists("assignment_comments", "is_private"):
        cursor.execute(
            "ALTER TABLE assignment_comments ADD COLUMN is_private TINYINT(1) NOT NULL DEFAULT 0"
        )
        conn.commit()
    if not col_exists("users", "activo"):
        cursor.execute(
            "ALTER TABLE users ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1"
        )
        conn.commit()
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
        "WHERE CONSTRAINT_SCHEMA = DATABASE() "
        "AND TABLE_NAME = 'assignment_comments' AND CONSTRAINT_NAME = 'fk_asgcom_parent'"
    )
    if cursor.fetchone()[0] == 0:
        try:
            cursor.execute(
                "ALTER TABLE assignment_comments "
                "ADD CONSTRAINT fk_asgcom_parent FOREIGN KEY (parent_id) "
                "REFERENCES assignment_comments(id) ON DELETE CASCADE"
            )
            conn.commit()
        except mysql.connector.Error:
            conn.rollback()
    conn.close()

    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__)))
    upload_dir = os.path.join(backend_root, "static", "uploads", "avatars")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(
        os.path.join(backend_root, "static", "uploads", "assignments"),
        exist_ok=True,
    )
    