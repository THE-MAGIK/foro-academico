<script setup>
import { onMounted, ref } from "vue";
import axios from "axios";

const mensaje = ref("");

onMounted(async () => {
  try {
    const response = await axios.get("http://localhost:3000/api/mensaje");
    mensaje.value = response.data.mensaje;
  } catch (error) {
    console.error(error);
  }
});
</script>


<template>
  <h1>{{ mensaje }}</h1>
</template>