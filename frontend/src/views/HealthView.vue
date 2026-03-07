<script setup>
import { onMounted, ref } from "vue";
import { api } from "../services/api";

const health = ref(null);
const error = ref("");

onMounted(async () => {
  try {
    health.value = await api.getHealth();
  } catch (err) {
    error.value = err.message;
  }
});
</script>

<template>
  <section class="card">
    <h2>GET /health</h2>
    <p class="small">Backend liveness endpoint.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <pre v-else-if="health">{{ JSON.stringify(health, null, 2) }}</pre>
    <p v-else>Loading...</p>
  </section>
</template>
