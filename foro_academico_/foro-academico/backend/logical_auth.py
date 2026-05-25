"""
Diagnóstico de errores de login con razonamiento lógico (Modus Tollens / Ponens).
Solo premisas y conclusión; usado en /api/login.
"""


def _diag(regla, premisa_1, premisa_2, conclusion):
    return {
        "regla": regla,
        "premisa_1": premisa_1,
        "premisa_2": premisa_2,
        "conclusion": conclusion,
    }


def diagnostico_login_exitoso():
    return _diag(
        "modus_ponens",
        (
            "P → Q: Si el correo y la contraseña son correctos, "
            "entonces la sesión se inicia en el servidor."
        ),
        "P: Las credenciales coinciden con un usuario en la base de datos.",
        (
            "∴ Q: La sesión quedó activa (cookie de sesión). "
            "Puedes usar el foro con normalidad."
        ),
    )


def diagnostico_login_credenciales_invalidas():
    return _diag(
        "modus_tollens",
        (
            "P → Q: Si el correo y la contraseña son correctos, "
            "entonces la sesión se inicia."
        ),
        "¬Q: La sesión NO se inició (el servidor rechazó el acceso).",
        (
            "∴ ¬P: El correo o la contraseña no son válidos "
            "para ningún usuario registrado."
        ),
    )


def diagnostico_login_datos_incompletos(campos_faltantes):
    faltan = ", ".join(campos_faltantes)
    return _diag(
        "validacion",
        "Para probar P → Q hace falta enviar correo y contraseña.",
        f"¬P (entrada): Faltan campos obligatorios: {faltan}.",
        "No se puede iniciar sesión hasta completar los datos.",
    )


def diagnostico_servidor_no_disponible(detalle=None):
    extra = f" ({detalle})" if detalle else ""
    return _diag(
        "servidor_no_disponible",
        (
            "P → Q: Si el servidor de login responde, obtienes JSON "
            "(éxito o rechazo por credenciales con diagnóstico)."
        ),
        (
            "¬Q: No hubo respuesta válida del API"
            + extra
            + " — no se pudo comprobar tu correo en la base de datos."
        ),
        (
            "∴ NO es un fallo de credenciales: el problema es de infraestructura "
            "(Flask parado, error al arrancar, MySQL apagado o sin conexión)."
        ),
    )


def diagnostico_mysql_no_disponible(detalle=None):
    extra = f" ({detalle})" if detalle else ""
    return _diag(
        "servidor_no_disponible",
        (
            "P → Q: Si Flask y MySQL responden, /api/health indica db: true "
            "y el login puede validar credenciales."
        ),
        (
            "¬Q: Flask responde, pero MySQL no conecta"
            + extra
            + " — no se puede consultar la base de datos."
        ),
        (
            "∴ NO es conclusión segura sobre tu contraseña: "
            "falla la capa de datos (servicio MySQL o configuración en db.py)."
        ),
    )


def diagnostico_login_error_servidor(detalle=None):
    extra = f" Detalle: {detalle}" if detalle else ""
    return _diag(
        "servidor_no_disponible",
        (
            "P → Q: Si MySQL y Flask funcionan, el login responde con éxito o "
            "rechazo explícito por credenciales."
        ),
        "¬Q: El servidor respondió con error interno al validar el login.",
        (
            "∴ Tampoco es conclusión segura sobre tu contraseña: "
            "falló la capa de datos."
            + extra
        ),
    )
