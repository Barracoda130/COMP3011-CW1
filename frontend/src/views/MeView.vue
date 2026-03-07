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
  <section class="card stack">
    <h2>My Profile</h2>
    <p class="small">Authenticated account details from your current session.</p>
    <p v-if="error" class="error">{{ error }}</p>
    <pre v-else-if="me">{{ JSON.stringify(me, null, 2) }}</pre>
    <p v-else>Loading...</p>
  </section>
</template>
