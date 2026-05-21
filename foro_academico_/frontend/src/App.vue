<script setup>
import { onMounted, reactive, ref } from "vue";

const API_BASE = "http://127.0.0.1:3000/api";

const loading = ref(false);
const error = ref("");
const success = ref("");

const students = ref([]);
const selectedStudent = ref(null);
const selectedQuestion = ref(null);
const studentQuestions = ref([]);

const studentForm = reactive({
  nombre: "",
  email: "",
  password: "",
});

const questionForm = reactive({
  titulo: "",
  contenido: "",
});

function resetAlerts() {
  error.value = "";
  success.value = "";
}

function resetStudentForm() {
  studentForm.nombre = "";
  studentForm.email = "";
  studentForm.password = "";
}

function resetQuestionForm() {
  questionForm.titulo = "";
  questionForm.contenido = "";
  selectedQuestion.value = null;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || "Ocurrio un error en la solicitud");
  }

  return data;
}

async function loadStudents() {
  loading.value = true;
  resetAlerts();
  try {
    students.value = await apiRequest("/students");
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function loadQuestions(studentId) {
  loading.value = true;
  resetAlerts();
  try {
    studentQuestions.value = await apiRequest(`/students/${studentId}/questions`);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function submitStudent() {
  loading.value = true;
  resetAlerts();
  try {
    if (selectedStudent.value) {
      const payload = {
        nombre: studentForm.nombre,
        email: studentForm.email,
      };
      if (studentForm.password) {
        payload.password = studentForm.password;
      }

      await apiRequest(`/students/${selectedStudent.value.id}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      success.value = "Estudiante actualizado";
    } else {
      await apiRequest("/students", {
        method: "POST",
        body: JSON.stringify({
          nombre: studentForm.nombre,
          email: studentForm.email,
          password: studentForm.password,
        }),
      });
      success.value = "Estudiante creado";
      resetStudentForm();
    }
    await loadStudents();
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

function editStudent(student) {
  selectedStudent.value = student;
  studentForm.nombre = student.nombre;
  studentForm.email = student.email;
  studentForm.password = "";
}

function cancelStudentEdit() {
  selectedStudent.value = null;
  resetStudentForm();
}

async function removeStudent(studentId) {
  if (!window.confirm("Quieres eliminar este estudiante?")) return;

  loading.value = true;
  resetAlerts();
  try {
    await apiRequest(`/students/${studentId}`, { method: "DELETE" });
    if (selectedStudent.value?.id === studentId) {
      selectedStudent.value = null;
      resetStudentForm();
    }
    if (selectedStudent.value?.id === studentId) {
      selectedStudent.value = null;
      studentQuestions.value = [];
    }
    success.value = "Estudiante eliminado";
    await loadStudents();
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function selectStudent(student) {
  selectedStudent.value = student;
  selectedQuestion.value = null;
  resetQuestionForm();
  await loadQuestions(student.id);
}

function editQuestion(question) {
  selectedQuestion.value = question;
  questionForm.titulo = question.titulo;
  questionForm.contenido = question.contenido;
}

function cancelQuestionEdit() {
  resetQuestionForm();
}

async function submitQuestion() {
  if (!selectedStudent.value) return;

  loading.value = true;
  resetAlerts();
  try {
    if (selectedQuestion.value) {
      await apiRequest(
        `/students/${selectedStudent.value.id}/questions/${selectedQuestion.value.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            titulo: questionForm.titulo,
            contenido: questionForm.contenido,
          }),
        }
      );
      success.value = "Pregunta actualizada";
    } else {
      await apiRequest(`/students/${selectedStudent.value.id}/questions`, {
        method: "POST",
        body: JSON.stringify({
          titulo: questionForm.titulo,
          contenido: questionForm.contenido,
        }),
      });
      success.value = "Pregunta creada";
    }
    resetQuestionForm();
    await loadQuestions(selectedStudent.value.id);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

async function removeQuestion(questionId) {
  if (!selectedStudent.value) return;
  if (!window.confirm("Quieres eliminar esta pregunta?")) return;

  loading.value = true;
  resetAlerts();
  try {
    await apiRequest(`/students/${selectedStudent.value.id}/questions/${questionId}`, {
      method: "DELETE",
    });
    success.value = "Pregunta eliminada";
    if (selectedQuestion.value?.id === questionId) {
      resetQuestionForm();
    }
    await loadQuestions(selectedStudent.value.id);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}

onMounted(loadStudents);
</script>

<template>
  <main class="container">
    <h1>Foro Academico - CRUD Estudiantes</h1>
    <p class="subtitle">Backend: Flask + MySQL | Frontend: Vue</p>

    <p v-if="loading" class="info">Cargando...</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success">{{ success }}</p>

    <section class="card">
      <h2>{{ selectedStudent ? "Editar estudiante" : "Crear estudiante" }}</h2>
      <form class="form-grid" @submit.prevent="submitStudent">
        <input v-model="studentForm.nombre" required placeholder="Nombre" />
        <input v-model="studentForm.email" required type="email" placeholder="Email" />
        <input
          v-model="studentForm.password"
          :required="!selectedStudent"
          type="password"
          placeholder="Password"
        />
        <div class="actions">
          <button type="submit">{{ selectedStudent ? "Actualizar" : "Crear" }}</button>
          <button v-if="selectedStudent" type="button" class="secondary" @click="cancelStudentEdit">
            Cancelar
          </button>
        </div>
      </form>
    </section>

    <section class="card">
      <h2>Estudiantes</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Nombre</th>
            <th>Email</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="student in students" :key="student.id">
            <td>{{ student.id }}</td>
            <td>{{ student.nombre }}</td>
            <td>{{ student.email }}</td>
            <td class="actions">
              <button class="secondary" @click="selectStudent(student)">Ver preguntas</button>
              <button class="secondary" @click="editStudent(student)">Editar</button>
              <button class="danger" @click="removeStudent(student.id)">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="selectedStudent" class="card">
      <h2>Preguntas de {{ selectedStudent.nombre }}</h2>
      <form class="form-grid" @submit.prevent="submitQuestion">
        <input v-model="questionForm.titulo" required placeholder="Titulo de la pregunta" />
        <textarea
          v-model="questionForm.contenido"
          required
          rows="4"
          placeholder="Contenido"
        />
        <div class="actions">
          <button type="submit">{{ selectedQuestion ? "Actualizar pregunta" : "Publicar pregunta" }}</button>
          <button v-if="selectedQuestion" type="button" class="secondary" @click="cancelQuestionEdit">
            Cancelar
          </button>
        </div>
      </form>

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Titulo</th>
            <th>Contenido</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="question in studentQuestions" :key="question.id">
            <td>{{ question.id }}</td>
            <td>{{ question.titulo }}</td>
            <td>{{ question.contenido }}</td>
            <td class="actions">
              <button class="secondary" @click="editQuestion(question)">Editar</button>
              <button class="danger" @click="removeQuestion(question.id)">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </main>
</template>