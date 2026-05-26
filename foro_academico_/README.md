# Foro académico — instalación y arranque

Guía para montar el proyecto en **Windows** con **PowerShell**. Sustituye `C:\TuRuta\foro_academico_` por la carpeta donde descomprimiste este proyecto (si la ruta tiene espacios, déjala entre comillas).

## Requisitos

- **Python 3** instalado
- **Node.js** y npm instalados
- **MySQL** instalado y servicio en ejecución (puerto habitual: 3306)
- Navegador actualizado

**Aula (tareas):** al iniciar el backend, `ensure_schema()` crea las tablas `assignments`, `assignment_submissions` y `assignment_comments` si no existen (y columnas `fecha_entrega`, `nota`, `comentario_profesor` en bases ya creadas). Las entregas se guardan en `foro-academico/backend/static/uploads/assignments/`.

---

## 1. Primera vez: base de datos

1. Inicia el servicio **MySQL** en Windows (servicios / arranque automático).

2. Importa el script SQL (ajusta la ruta si tu carpeta no está en `C:\TuRuta\foro_academico_`):

```powershell
Get-Content "C:\TuRuta\foro_academico_\bases de datos\foro_academico.sql" -Raw -Encoding UTF8 | mysql -u root -p
```

Te pedirá la contraseña del usuario **root** de MySQL; al escribirla **no se verá nada** en pantalla (es normal).

Si aparece el error de que **`mysql` no se reconoce**, usa la ruta completa al ejecutable, por ejemplo:

```powershell
Get-Content "C:\TuRuta\foro_academico_\bases de datos\foro_academico.sql" -Raw -Encoding UTF8 | & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

(Ajusta la carpeta `MySQL Server 8.0` si tu versión es otra, o la ruta si usas XAMPP, Chocolatey, etc.)

3. Abre el archivo **`foro-academico\backend\db.py`** y comprueba que **usuario**, **contraseña** y **nombre de la base** (`foro_academico`) coincidan con tu MySQL. Si tu `root` tiene otra contraseña, cámbiala ahí.

---

## 2. Primera vez: backend (Python)

Abre PowerShell:

```powershell
cd "C:\TuRuta\foro_academico_\foro-academico\backend"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install flask flask-cors mysql-connector-python bcrypt
```

Si **PowerShell** dice que la ejecución de scripts está deshabilitada:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Luego vuelve a ejecutar `.\.venv\Scripts\Activate.ps1`.

**Alternativa** sin activar el entorno (usa el Python del venv directamente):

```powershell
cd "C:\TuRuta\foro_academico_\foro-academico\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install flask flask-cors mysql-connector-python bcrypt
```

---

## 3. Primera vez: frontend (Node)

La carpeta correcta es **`foro_academico_\frontend`** (junto a `foro-academico`, no dentro de él). No uses `foro-academico\frontend`: ahí no hay `package.json` y npm dará error ENOENT.

```powershell
cd "C:\TuRuta\foro_academico_\frontend"
npm install
```

---

## 4. Cada vez que quieras usar el proyecto

Necesitas **dos terminales** abiertas (y MySQL en marcha).

### Terminal 1 — API (Flask, puerto 3000)

```powershell
cd "C:\TuRuta\foro_academico_\foro-academico\backend"
.\.venv\Scripts\Activate.ps1
python app.py
```

O sin activar:

```powershell
cd "C:\TuRuta\foro_academico_\foro-academico\backend"
.\.venv\Scripts\python.exe app.py
```

Deja esta ventana abierta mientras uses el foro.

### Terminal 2 — interfaz web (Vite)

```powershell
cd "C:\TuRuta\foro_academico_\frontend"
npm run dev
```

En el navegador abre la URL que indique la terminal (habitualmente **http://localhost:5173**). La interfaz está configurada para hablar con la API en **http://127.0.0.1:3000**.

---

## Variables de entorno (opcional)

- **`FLASK_SECRET_KEY`**: clave para firmar cookies de sesión (login). En producción conviene definirla; si no existe, el proyecto usa un valor de desarrollo en código.
- **Traducción (MyMemory API)**: API REST externa gratuita. Opcionalmente pega tu clave en `MYMEMORY_API_KEY` dentro de `foro-academico/backend/config.py` (~10 000 palabras/día con clave; ~1 000 sin clave). Documentación: [MyMemory API](https://mymemory.translated.net/doc/spec.php). Clave gratuita: [keygen](https://mymemory.translated.net/doc/keygen.php).

---

## Resumen de carpetas

| Carpeta | Contenido |
|---------|-----------|
| `bases de datos/` | Script SQL para importar en MySQL |
| `foro-academico/backend/` | API Flask (`app.py`, `db.py`, `routes/`) |
| `frontend/` | Interfaz con Vite (`npm run dev`) |

---

## Problemas frecuentes

- **Error de conexión a MySQL**: servicio parado o datos distintos en `db.py`.
- **Nada cambia en el navegador**: recarga forzada (**Ctrl+F5**) y comprueba que entras por la URL de **Vite** (`npm run dev`), no un HTML viejo guardado en caché.
- **`mysql` no reconocido**: usar ruta completa a `mysql.exe` como en el apartado 1.
- **Detuve Flask pero el login sigue respondiendo**: en Windows, con `debug=True`, a veces queda un proceso Python en el puerto **3000**. Compruébalo con `netstat -ano | findstr :3000` y cierra el PID que aparece en LISTENING, por ejemplo `taskkill /PID 12345 /F`. El proyecto usa `use_reloader=False` en `app.py` para evitar procesos huérfanos al pulsar **Ctrl+C**.
