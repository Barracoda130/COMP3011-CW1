<script setup>
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { clearToken, isAuthenticated } from "./stores/auth";

const router = useRouter();
const route = useRoute();

// Re-evaluate auth status on navigation so UI updates immediately after login/logout.
const authed = computed(() => {
  route.fullPath;
  return isAuthenticated();
});

function logout() {
  clearToken();
  router.push("/auth/login");
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
        <RouterLink to="/auth/register">Register</RouterLink>
        <RouterLink to="/auth/login">Login</RouterLink>
        <RouterLink to="/auth/me">Me</RouterLink>
        <RouterLink to="/recipes">Discover</RouterLink>
        <RouterLink v-if="authed" to="/recipes/create">Create</RouterLink>
      </nav>
      <button v-if="authed" class="danger" @click="logout">Logout</button>
    </header>

    <main class="page-wrap">
      <RouterView />
    </main>
  </div>
</template>
