<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { clearToken, isAuthenticated } from "./stores/auth";

const router = useRouter();
const authed = computed(() => isAuthenticated());

function logout() {
  clearToken();
  router.push("/auth/login");
}
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <h1>Meal API Console</h1>
      <nav class="nav-links">
        <RouterLink to="/health">Health</RouterLink>
        <RouterLink to="/auth/register">Register</RouterLink>
        <RouterLink to="/auth/login">Login</RouterLink>
        <RouterLink to="/auth/me">Me</RouterLink>
        <RouterLink to="/recipes">Recipes</RouterLink>
      </nav>
      <button v-if="authed" class="danger" @click="logout">Logout</button>
    </header>

    <main class="page-wrap">
      <RouterView />
    </main>
  </div>
</template>
