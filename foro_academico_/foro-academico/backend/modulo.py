from extensions import db

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    rol = db.Column(db.String(20))

class Pregunta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200))
    contenido = db.Column(db.Text)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

class Respuesta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.Text)
    pregunta_id = db.Column(db.Integer, db.ForeignKey('pregunta.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

class Voto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.Integer)
    usuario_id = db.Column(db.Integer)
    pregunta_id = db.Column(db.Integer, nullable=True)
    respuesta_id = db.Column(db.Integer, nullable=True)