"""
Módulo de depuración lógica — login contra usuarios reales en MySQL.
"""
from flask import Blueprint, jsonify, request, session

from common import get_json
from logical_auth import diagnostico_login_desde_bd

bp = Blueprint("logical", __name__)


@bp.route("/api/logical-diagnosis", methods=["POST"])
def logical_diagnosis():
    if not session.get("user_id"):
        return jsonify({"error": "No autenticado", "diagnostico": None}), 401

    data = get_json(request)
    email = (data.get("email") or data.get("usuario") or "").strip()
    password = data.get("password") or ""

    diagnostico = diagnostico_login_desde_bd(email, password)
    regla = diagnostico.get("regla")
    if regla == "validacion":
        return jsonify({"diagnostico": diagnostico, "credenciales_validas": False}), 400

    credenciales_validas = regla == "modus_ponens"
    status = 200 if credenciales_validas or regla == "modus_tollens" else 503
    return jsonify({
        "diagnostico": diagnostico,
        "credenciales_validas": credenciales_validas,
    }), status
