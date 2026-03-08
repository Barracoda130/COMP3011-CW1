<script setup>
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../services/api";
import { setToken } from "../stores/auth";

const route = useRoute();
const router = useRouter();

const loginForm = ref({ email: "", password: "" });
const registerForm = ref({ email: "", password: "", full_name: "" });

const loginError = ref("");
const registerError = ref("");
const successMessage = ref("");
const registerFieldErrors = ref({ email: "", password: "", full_name: "" });

const mode = computed(() => {
  return route.query.mode === "register" ? "register" : "login";
});

const safeRedirectPath = computed(() => {
  const candidate = route.query.redirect;
  if (typeof candidate === "string" && candidate.startsWith("/")) {
    return candidate;
  }
  return "/recipes";
});

function switchMode(nextMode) {
  successMessage.value = "";
  loginError.value = "";
  registerError.value = "";
  registerFieldErrors.value = { email: "", password: "", full_name: "" };

  router.replace({
    path: "/auth",
    query: {
      ...route.query,
      mode: nextMode
    }
  });
}

async function submitLogin() {
  loginError.value = "";
  successMessage.value = "";

  try {
    const token = await api.login(loginForm.value);
    setToken(token.access_token);
    router.push(safeRedirectPath.value);
  } catch (err) {
    loginError.value = err.message;
  }
}

async function submitRegister() {
  registerError.value = "";
  successMessage.value = "";
  registerFieldErrors.value = { email: "", password: "", full_name: "" };

  try {
    await api.register(registerForm.value);
    successMessage.value = "Account created successfully. Please sign in.";
    loginForm.value.email = registerForm.value.email;
    switchMode("login");
  } catch (err) {
    registerError.value = err.message;
    if (err.fieldErrors) {
      registerFieldErrors.value = {
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
    <div class="button-row">
      <button
        :class="mode === 'login' ? '' : 'secondary'"
        type="button"
        @click="switchMode('login')"
      >
        Login
      </button>
      <button
        :class="mode === 'register' ? '' : 'secondary'"
        type="button"
        @click="switchMode('register')"
      >
        Register
      </button>
    </div>

    <template v-if="mode === 'login'">
      <h2>Sign In</h2>
      <p class="small">Access your recipes, ratings, and personalized workflow.</p>
      <form class="stack" @submit.prevent="submitLogin">
        <label>Email (username)</label>
        <input v-model="loginForm.email" type="email" />
        <label>Password</label>
        <input v-model="loginForm.password" type="password" />
        <button type="submit">Login</button>
      </form>
      <p v-if="loginError" class="error">{{ loginError }}</p>
    </template>

    <template v-else>
      <h2>Create Account</h2>
      <p class="small">Start saving your own recipes and rating what you cook.</p>
      <form class="stack" @submit.prevent="submitRegister">
        <label>Email</label>
        <input v-model="registerForm.email" type="email" />
        <p v-if="registerFieldErrors.email" class="error small">{{ registerFieldErrors.email }}</p>

        <label>Password</label>
        <input v-model="registerForm.password" type="password" />
        <p v-if="registerFieldErrors.password" class="error small">{{ registerFieldErrors.password }}</p>

        <label>Full Name</label>
        <input v-model="registerForm.full_name" type="text" />
        <p v-if="registerFieldErrors.full_name" class="error small">{{ registerFieldErrors.full_name }}</p>

        <button type="submit">Create Account</button>
      </form>
      <p v-if="registerError" class="error">{{ registerError }}</p>
    </template>

    <p v-if="successMessage" class="success">{{ successMessage }}</p>
  </section>
</template>
