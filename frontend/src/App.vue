<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { clearToken, isAuthenticated } from "./stores/auth";

const router = useRouter();
const authed = computed(() => isAuthenticated());

function logout() {
  clearToken();
  router.push("/auth?mode=login");
}

function goToAuth() {
  router.push("/auth?mode=login");
}
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="brand">
        <h1>Meal Planner Pro</h1>
        <p>Discover, save, and cook with confidence</p>
      </div>
      <nav class="nav-links">
        <RouterLink to="/health">Health</RouterLink>
        <RouterLink to="/auth/me">Me</RouterLink>
        <RouterLink to="/recipes">Discover</RouterLink>
        <RouterLink v-if="authed" to="/recipes/create">Create</RouterLink>
      </nav>
      <button v-if="!authed" class="secondary" @click="goToAuth">Login / Register</button>
      <button v-if="authed" class="danger" @click="logout">Logout</button>
    </header>

    <main class="page-wrap">
      <RouterView />
    </main>
  </div>
</template>
