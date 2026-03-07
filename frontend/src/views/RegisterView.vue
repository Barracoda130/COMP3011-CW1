<script setup>
import { ref } from "vue";
import { api } from "../services/api";

const form = ref({ email: "", password: "", full_name: "" });
const response = ref(null);
const error = ref("");

async function submit() {
  error.value = "";
  response.value = null;
  try {
    response.value = await api.register(form.value);
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <section class="card">
    <h2>POST /auth/register</h2>
    <label>Email</label>
    <input v-model="form.email" type="email" />
    <label>Password</label>
    <input v-model="form.password" type="password" />
    <label>Full Name</label>
    <input v-model="form.full_name" type="text" />
    <button @click="submit">Register</button>
    <p v-if="error" class="error">{{ error }}</p>
    <pre v-if="response">{{ JSON.stringify(response, null, 2) }}</pre>
  </section>
</template>
