<template>
  <section class="card stack">
    <h2>Page Not Found</h2>
    <p class="small">The page you requested does not exist or may have moved.</p>
    <div class="button-row">
      <RouterLink class="action-link secondary" to="/recipes">Go to Discover</RouterLink>
      <RouterLink class="action-link secondary" to="/auth?mode=login">Go to Login</RouterLink>
    </div>
  </section>
</template>
