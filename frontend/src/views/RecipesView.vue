<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";

const recipes = ref([]);
const error = ref("");
const created = ref(null);
const form = ref({
  title: "",
  cuisine: "",
  prep_minutes: 20,
  calories: 500,
  tags: "quick",
  description: ""
});

async function loadRecipes() {
  error.value = "";
  try {
    recipes.value = await api.listRecipes(0, 100);
  } catch (err) {
    error.value = err.message;
  }
}

async function createRecipe() {
  error.value = "";
  created.value = null;
  try {
    const payload = {
      title: form.value.title,
      cuisine: form.value.cuisine,
      prep_minutes: Number(form.value.prep_minutes),
      calories: form.value.calories ? Number(form.value.calories) : null,
      tags: form.value.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      description: form.value.description || null
    };
    created.value = await api.createRecipe(payload);
    await loadRecipes();
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(loadRecipes);
</script>

<template>
  <section class="grid">
    <article class="card">
      <h2>GET /recipes</h2>
      <p class="small">Lists all recipes currently in the API.</p>
      <p v-if="error" class="error">{{ error }}</p>
      <ul>
        <li v-for="recipe in recipes" :key="recipe.id">
          <RouterLink :to="`/recipes/${recipe.id}`">{{ recipe.title }}</RouterLink>
          <span class="small"> ({{ recipe.cuisine }})</span>
        </li>
      </ul>
    </article>

    <article class="card">
      <h2>POST /recipes</h2>
      <p class="small">Requires login token. Creates a recipe owned by current user.</p>
      <label>Title</label>
      <input v-model="form.title" type="text" />
      <label>Cuisine</label>
      <input v-model="form.cuisine" type="text" />
      <label>Prep Minutes</label>
      <input v-model="form.prep_minutes" type="number" min="1" />
      <label>Calories</label>
      <input v-model="form.calories" type="number" min="0" />
      <label>Tags (comma separated)</label>
      <input v-model="form.tags" type="text" />
      <label>Description</label>
      <textarea v-model="form.description" rows="4" />
      <button @click="createRecipe">Create Recipe</button>
      <pre v-if="created">{{ JSON.stringify(created, null, 2) }}</pre>
    </article>
  </section>
</template>
