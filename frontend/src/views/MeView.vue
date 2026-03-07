<script setup>
import { onMounted, ref } from "vue";
import { api } from "../services/api";

const me = ref(null);
const error = ref("");

onMounted(async () => {
  try {
    me.value = await api.me();
  } catch (err) {
    error.value = err.message;
  }
});
</script>

<template>
  <section class="card">
    <h2>GET /auth/me</h2>
    <p class="small">Requires Bearer token from login.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <pre v-else-if="me">{{ JSON.stringify(me, null, 2) }}</pre>
    <p v-else>Loading...</p>
  </section>
</template>
