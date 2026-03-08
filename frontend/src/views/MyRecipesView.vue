<script setup>
import { onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { useRoute } from "vue-router";
import { api } from "../services/api";

const route = useRoute();
const items = ref([]);
const searchQuery = ref("");
const isLoading = ref(false);
const error = ref("");
const updatedRecipeId = ref(null);

function descriptionPreview(text) {
  if (!text) return "";
  const normalized = String(text).trim();
  if (normalized.length <= 140) {
    return normalized;
  }
  return `${normalized.slice(0, 140).trimEnd()}...`;
}

function syncUpdatedRecipeIdFromRoute() {
  const raw = String(route.query.updated || "").trim();
  updatedRecipeId.value = raw && /^\d+$/.test(raw) ? Number(raw) : null;
}

async function loadMyRecipes() {
  isLoading.value = true;
  error.value = "";
  try {
    items.value = await api.listMyRecipes({ query: searchQuery.value });
  } catch (err) {
    error.value = err.message;
  } finally {
    isLoading.value = false;
  }
}

async function deleteRecipe(recipeId) {
  error.value = "";
  try {
    await api.deleteRecipe(recipeId);
    await loadMyRecipes();
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(async () => {
  syncUpdatedRecipeIdFromRoute();
  await loadMyRecipes();
});

watch(() => route.query.updated, syncUpdatedRecipeIdFromRoute);
</script>

<template>
  <section class="grid recipes-layout">
    <article class="card stack">
      <div class="discover-header">
        <h2>My Recipes</h2>
        <p class="small">View, edit, and delete recipes you created.</p>
      </div>

      <form class="search-row" @submit.prevent="loadMyRecipes">
        <div class="search-field">
          <label for="my-recipes-search">Search by title/cuisine</label>
          <input
            id="my-recipes-search"
            v-model="searchQuery"
            class="search-input"
            type="text"
            placeholder="e.g. pasta or Italian"
          />
        </div>
        <button class="secondary" type="submit" :disabled="isLoading">
          {{ isLoading ? "Searching..." : "Search" }}
        </button>
      </form>

      <div class="summary">
        <span class="pill local">Total: {{ items.length }}</span>
        <RouterLink class="muted-link" to="/recipes/create">Create new recipe</RouterLink>
      </div>

      <p v-if="isLoading" class="small">Loading your recipes...</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="!isLoading && !error && !items.length" class="small">No recipes found.</p>

      <ul class="list-clean" v-if="items.length">
        <li v-for="recipe in items" :key="recipe.id">
          <div class="result-row no-image">
            <div class="result-content my-recipe-main">
              <div>
                <RouterLink
                  :to="{
                    path: `/recipes/cook/local/${recipe.id}`,
                    query: { from: 'mine' }
                  }"
                >
                  {{ recipe.title }}
                </RouterLink>
                <span class="small"> ({{ recipe.cuisine }})</span>
                <span v-if="updatedRecipeId === recipe.id" class="saved-indicator">Changes saved</span>
                <div class="summary" style="margin-top: 0.35rem">
                  <span class="pill local">local</span>
                  <span class="pill quick">Prep: {{ recipe.prep_minutes }} min</span>
                  <span v-if="recipe.calories !== null && recipe.calories !== undefined" class="pill quick">
                    Calories: {{ recipe.calories }}
                  </span>
                </div>
                <p v-if="recipe.description" class="small" style="margin-top: 0.4rem">{{ descriptionPreview(recipe.description) }}</p>
              </div>
              <div class="my-recipe-actions">
                <RouterLink class="action-link secondary" :to="`/recipes/${recipe.id}`">Edit</RouterLink>
                <button class="danger" type="button" @click="deleteRecipe(recipe.id)">Delete</button>
              </div>
            </div>
          </div>
        </li>
      </ul>
    </article>
  </section>
</template>
