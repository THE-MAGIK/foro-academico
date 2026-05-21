"""
Punto de entrada de la API Flask.

Solo configura la app, CORS y registra los blueprints por dominio.
La logica de cada area esta en routes/ y helpers en common.py.
"""
import os

from flask import Flask, jsonify
from flask_cors import CORS

from db import ensure_schema, get_connection
from routes.admins import bp as admins_bp
from routes.auth import bp as auth_bp
from routes.classroom import bp as classroom_bp
from routes.professors import bp as professors_bp
from routes.superadmin import bp as superadmin_bp
from routes.questions import bp as questions_bp
from routes.students import bp as students_bp
from routes.logical import bp as logical_bp

app = Flask(__name__)
ensure_schema()
# Clave para firmar cookies de sesion (login). En produccion definir FLASK_SECRET_KEY.
app.secret_key = os.getenv("FLASK_SECRET_KEY", "foro-dev-secret-change-me")
# Permite que el front en otro puerto llame la API con cookies de sesion.
CORS(
    app,
    supports_credentials=True,
    resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:5174",
                "http://127.0.0.1:5174",
                "http://localhost:5500",
                "http://127.0.0.1:5500",
            ]
        }
    },
)


@app.route("/")
def inicio():
    """Comprobacion rapida de que el servidor esta arriba."""
    return "Servidor funcionando"


@app.route("/api/health")
def health():
    """Comprueba API (Flask) y MySQL por separado."""
    payload = {"api": True, "db": False, "servicio": "foro-academico"}
    try:
        conn = get_connection()
        conn.close()
        payload["db"] = True
    except Exception as exc:
        payload["db_error"] = str(exc)
    return jsonify(payload)


app.register_blueprint(auth_bp)
app.register_blueprint(superadmin_bp)
app.register_blueprint(classroom_bp)
app.register_blueprint(questions_bp)
app.register_blueprint(students_bp)
app.register_blueprint(professors_bp)
app.register_blueprint(admins_bp)
app.register_blueprint(logical_bp)


if __name__ == '__main__':
    # Sin reloader: al pulsar Ctrl+C no queda un Python huérfano en el puerto 3000.
    app.run(port=3000, debug=True, use_reloader=False)