-- Ejecutar en la base foro_academico si la columna rol es ENUM y no incluye 'superadmin'.
-- Si rol ya es VARCHAR, este script no es necesario.

USE foro_academico;

-- Opcion A: ampliar ENUM (MySQL 8+). Ajusta si tu ENUM ya tiene otros valores.
-- ALTER TABLE users MODIFY COLUMN rol ENUM('estudiante','profesor','admin','superadmin') NOT NULL DEFAULT 'estudiante';

-- Opcion B (recomendada si ENUM da problemas): pasar a VARCHAR
ALTER TABLE users MODIFY COLUMN rol VARCHAR(32) NOT NULL DEFAULT 'estudiante';
