-- Esquema compatible con el backend Flask (tablas en ingles: users, questions, ...)
-- Importar: Get-Content "...\foro_academico.sql" -Raw -Encoding UTF8 | mysql -u root -p

CREATE DATABASE IF NOT EXISTS foro_academico
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE foro_academico;

DROP TABLE IF EXISTS assignment_comments;
DROP TABLE IF EXISTS assignment_submissions;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS votes;
DROP TABLE IF EXISTS question_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS answers;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    rol VARCHAR(32) NOT NULL DEFAULT 'estudiante',
    reputacion INT NOT NULL DEFAULT 0,
    avatar_ext VARCHAR(8) NULL DEFAULT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    contenido TEXT NOT NULL,
    user_id INT NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_questions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contenido TEXT NOT NULL,
    user_id INT NOT NULL,
    question_id INT NOT NULL,
    is_accepted TINYINT(1) NOT NULL DEFAULT 0,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_answers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_answers_question FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    contenido TEXT NOT NULL,
    user_id INT NOT NULL,
    question_id INT NULL,
    answer_id INT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_question FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_answer FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tags (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE question_tags (
    question_id INT NOT NULL,
    tag_id INT NOT NULL,
    PRIMARY KEY (question_id, tag_id),
    CONSTRAINT fk_qt_question FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    CONSTRAINT fk_qt_tag FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE votes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    question_id INT NULL,
    answer_id INT NULL,
    tipo ENUM('upvote', 'downvote') NOT NULL,
    CONSTRAINT fk_votes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_votes_question FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    CONSTRAINT fk_votes_answer FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    titulo VARCHAR(255) NOT NULL,
    descripcion TEXT,
    professor_id INT NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    fecha_entrega DATETIME NULL DEFAULT NULL,
    INDEX idx_assignments_professor (professor_id),
    CONSTRAINT fk_assignments_professor FOREIGN KEY (professor_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE assignment_submissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    student_id INT NOT NULL,
    filename_original VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(128),
    size_bytes BIGINT,
    fecha_subida DATETIME DEFAULT CURRENT_TIMESTAMP,
    nota DECIMAL(5,2) NULL DEFAULT NULL,
    comentario_profesor TEXT NULL,
    UNIQUE KEY uq_assignment_student (assignment_id, student_id),
    CONSTRAINT fk_sub_assignment FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    CONSTRAINT fk_sub_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE assignment_comments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    assignment_id INT NOT NULL,
    user_id INT NOT NULL,
    parent_id INT NULL DEFAULT NULL,
    is_private TINYINT(1) NOT NULL DEFAULT 0,
    contenido TEXT NOT NULL,
    fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_asgcom_assignment (assignment_id),
    INDEX idx_asgcom_parent (parent_id),
    CONSTRAINT fk_asgcom_assignment FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    CONSTRAINT fk_asgcom_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_asgcom_parent FOREIGN KEY (parent_id) REFERENCES assignment_comments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Usuarios de prueba (contrasena: 123456)
INSERT INTO users (nombre, email, password, rol) VALUES
('Super Admin', 'superadmin@foro.com', '$2b$12$xIMZ/qWUVRO3R20lsCsTguzd4dpyq2zoJr6XK5ISLRn9vARRZbaVC', 'superadmin'),
('Admin', 'admin@foro.com', '$2b$12$xIMZ/qWUVRO3R20lsCsTguzd4dpyq2zoJr6XK5ISLRn9vARRZbaVC', 'admin'),
('Profesor Demo', 'profesor@foro.com', '$2b$12$xIMZ/qWUVRO3R20lsCsTguzd4dpyq2zoJr6XK5ISLRn9vARRZbaVC', 'profesor'),
('Estudiante Demo', 'estudiante@foro.com', '$2b$12$xIMZ/qWUVRO3R20lsCsTguzd4dpyq2zoJr6XK5ISLRn9vARRZbaVC', 'estudiante');
