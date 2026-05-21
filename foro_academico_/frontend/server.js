const express = require("express");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

// Ruta de prueba
app.get("/api/mensaje", (req, res) => {
  res.json({ mensaje: "Hola desde el backend 👋" });
});

// Puerto
app.listen(3000, () => {
  console.log("Servidor corriendo en http://localhost:3000");
});