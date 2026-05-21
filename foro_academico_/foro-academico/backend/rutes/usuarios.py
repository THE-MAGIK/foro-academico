from flask import Blueprint, request, jsonify
from models import Usuario
from extensions import db

usuarios_bp = Blueprint('usuarios', __name__)

# CREATE
@usuarios_bp.route("/", methods=["POST"])
def crear_usuario():
    data = request.json
    user = Usuario(**data)
    db.session.add(user)
    db.session.commit()
    return jsonify({"msg": "Usuario creado"})

# READ
@usuarios_bp.route("/", methods=["GET"])
def listar():
    usuarios = Usuario.query.all()
    return jsonify([{"id": u.id, "nombre": u.nombre, "email": u.email} for u in usuarios])

# READ ONE
@usuarios_bp.route("/<int:id>", methods=["GET"])
def obtener(id):
    u = Usuario.query.get(id)
    return jsonify({"id": u.id, "nombre": u.nombre, "email": u.email})

# UPDATE
@usuarios_bp.route("/<int:id>", methods=["PUT"])
def actualizar(id):
    u = Usuario.query.get(id)
    data = request.json
    u.nombre = data.get("nombre", u.nombre)
    u.email = data.get("email", u.email)
    db.session.commit()
    return jsonify({"msg": "Actualizado"})

# DELETE
@usuarios_bp.route("/<int:id>", methods=["DELETE"])
def eliminar(id):
    u = Usuario.query.get(id)
    db.session.delete(u)
    db.session.commit()
    return jsonify({"msg": "Eliminado"})