<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";

const recipes = ref([]);
const localCount = ref(0);
const externalCount = ref(0);
const error = ref("");
const created = ref(null);
const searchQuery = ref("");
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
    const result = await api.discoverRecipes({
      query: searchQuery.value,
      localLimit: 100,
      externalLimit: 120
    });
    recipes.value = result.items;
    localCount.value = result.local_count;
    externalCount.value = result.external_count;
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
      <h2>GET /recipes/discover</h2>
      <p class="small">
        Shows recipes from both your database and TheMealDB.
        Local recipes are prioritized first.
      </p>
      <label>Search by title/cuisine</label>
      <input v-model="searchQuery" type="text" placeholder="e.g. pasta or Italian" />
      <button class="secondary" @click="loadRecipes">Refresh Results</button>
      <p class="small">Local: {{ localCount }} | TheMealDB: {{ externalCount }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <ul>
        <li v-for="recipe in recipes" :key="`${recipe.source}-${recipe.id}`">
          <RouterLink
            :to="`/recipes/cook/${recipe.source}/${recipe.source === 'themealdb' ? recipe.external_id : recipe.id}`"
          >
            {{ recipe.title }}
          </RouterLink>
          <span class="small"> ({{ recipe.cuisine }})</span>
          <span class="small"> [{{ recipe.source }}]</span>
          <RouterLink
            v-if="recipe.source === 'local'"
            class="small"
            :to="`/recipes/${recipe.id}`"
            style="margin-left: 0.5rem"
          >
            Manage
          </RouterLink>
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
