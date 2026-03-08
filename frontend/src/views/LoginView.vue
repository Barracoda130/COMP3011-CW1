<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../services/api";
import { setToken } from "../stores/auth";

const router = useRouter();
const form = ref({ email: "", password: "" });
const response = ref(null);
const error = ref("");

async function submit() {
  error.value = "";
  response.value = null;
  try {
    const token = await api.login(form.value);
    response.value = token;
    setToken(token.access_token);
    router.push("/recipes");
  } catch (err) {
    error.value = err.message;
  }
}
</script>

<template>
  <section class="card stack">
    <h2>Sign In</h2>
    <p class="small">Access your recipes, ratings, and personalized workflow.</p>
    <form class="stack" @submit.prevent="submit">
      <label>Email (username)</label>
      <input v-model="form.email" type="email" />
      <label>Password</label>
      <input v-model="form.password" type="password" />
      <button type="submit">Login</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <pre v-if="response">{{ JSON.stringify(response, null, 2) }}</pre>
  </section>
</template>
