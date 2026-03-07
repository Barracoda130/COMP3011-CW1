<script setup>
import { ref } from "vue";
import { api } from "../services/api";

const form = ref({ email: "", password: "", full_name: "" });
const response = ref(null);
const error = ref("");
const fieldErrors = ref({ email: "", password: "", full_name: "" });

function resetErrors() {
  error.value = "";
  fieldErrors.value = { email: "", password: "", full_name: "" };
}

async function submit() {
  resetErrors();
  response.value = null;
  try {
    response.value = await api.register(form.value);
  } catch (err) {
    error.value = err.message;
    if (err.fieldErrors) {
      fieldErrors.value = {
        email: err.fieldErrors.email || "",
        password: err.fieldErrors.password || "",
        full_name: err.fieldErrors.full_name || ""
      };
    }
  }
}
</script>

<template>
  <section class="card stack">
    <h2>Create Account</h2>
    <p class="small">Start saving your own recipes and rating what you cook.</p>
    <form class="stack" @submit.prevent="submit">
      <label>Email</label>
      <input v-model="form.email" type="email" />
      <p v-if="fieldErrors.email" class="error small">{{ fieldErrors.email }}</p>
      <label>Password</label>
      <input v-model="form.password" type="password" />
      <p v-if="fieldErrors.password" class="error small">{{ fieldErrors.password }}</p>
      <label>Full Name</label>
      <input v-model="form.full_name" type="text" />
      <p v-if="fieldErrors.full_name" class="error small">{{ fieldErrors.full_name }}</p>
      <button type="submit">Create Account</button>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
    <pre v-if="response">{{ JSON.stringify(response, null, 2) }}</pre>
  </section>
</template>
