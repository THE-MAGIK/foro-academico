
import tkinter as tk

USUARIO_CORRECTO = "admin"
PASSWORD_CORRECTA = "12345"

def verificar_login():
    usuario = entry_usuario.get()
    password = entry_password.get()

    resultado_texto.delete("1.0", tk.END)

    if usuario == USUARIO_CORRECTO and password == PASSWORD_CORRECTA:
        resultado.config(text="ACCESO PERMITIDO", fg="#00ff88")

        analisis = """
PREMISA 1:
Si el usuario y contraseña son correctos,
entonces el acceso es permitido.

PREMISA 2:
El acceso fue permitido.

CONCLUSION:
Las credenciales son correctas.
"""
        resultado_texto.insert(tk.END, analisis)

    else:
        resultado.config(text="ACCESO DENEGADO", fg="#ff4d4d")

        analisis = """
PREMISA 1:
Si el usuario y contraseña son correctos,
entonces el acceso es permitido.

PREMISA 2:
El acceso NO fue permitido.

CONCLUSION (Modus Tollens):
Las credenciales NO fueron reconocidas correctamente.
"""
        resultado_texto.insert(tk.END, analisis)

ventana = tk.Tk()
ventana.title("Depuracion de Errores")
ventana.geometry("700x500")
ventana.config(bg="#0f172a")

titulo = tk.Label(
    ventana,
    text="RAZONAMIENTO LOGICO EN LA DEPURACION",
    font=("Arial", 18, "bold"),
    bg="#0f172a",
    fg="white"
)
titulo.pack(pady=20)

frame = tk.Frame(
    ventana,
    bg="#1e293b",
    padx=20,
    pady=20
)
frame.pack(pady=10)

label_usuario = tk.Label(
    frame,
    text="Usuario",
    font=("Arial", 12, "bold"),
    bg="#1e293b",
    fg="white"
)
label_usuario.grid(row=0, column=0, pady=10)

entry_usuario = tk.Entry(
    frame,
    width=30,
    font=("Arial", 12)
)
entry_usuario.grid(row=0, column=1, pady=10)

label_password = tk.Label(
    frame,
    text="Contrasena",
    font=("Arial", 12, "bold"),
    bg="#1e293b",
    fg="white"
)
label_password.grid(row=1, column=0, pady=10)

entry_password = tk.Entry(
    frame,
    width=30,
    font=("Arial", 12),
    show="*"
)
entry_password.grid(row=1, column=1, pady=10)

btn_login = tk.Button(
    ventana,
    text="Verificar Login",
    command=verificar_login,
    font=("Arial", 12, "bold"),
    bg="#2563eb",
    fg="white",
    padx=15,
    pady=8
)
btn_login.pack(pady=15)

resultado = tk.Label(
    ventana,
    text="",
    font=("Arial", 16, "bold"),
    bg="#0f172a"
)
resultado.pack()

resultado_texto = tk.Text(
    ventana,
    height=12,
    width=70,
    bg="#111827",
    fg="white",
    font=("Consolas", 11)
)
resultado_texto.pack(pady=15)

info = tk.Label(
    ventana,
    text="Usuario: admin | Contrasena: 12345",
    bg="#0f172a",
    fg="#94a3b8",
    font=("Arial", 10)
)
info.pack()

ventana.mainloop()
