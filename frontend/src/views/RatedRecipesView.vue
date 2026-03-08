<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";

const ratedItems = ref([]);
const localCount = ref(0);
const externalCount = ref(0);
const searchQuery = ref("");
const scoreFilter = ref("");
const isLoading = ref(false);
const error = ref("");

function quickFacts(recipe) {
  const facts = [];
  if (recipe.prep_minutes) {
    facts.push(`Cook time: ${recipe.prep_minutes} min`);
  }
  if (recipe.calories !== null && recipe.calories !== undefined) {
    facts.push(`Calories: ${recipe.calories}`);
  }
  if (Array.isArray(recipe.tags) && recipe.tags.length) {
    facts.push(`Tags: ${recipe.tags.slice(0, 3).join(", ")}`);
  }
  return facts;
}

async function loadRatedRecipes() {
  isLoading.value = true;
  error.value = "";
  try {
    const response = await api.ratedRecipes({
      query: searchQuery.value,
      score: scoreFilter.value
    });
    ratedItems.value = response.items;
    localCount.value = response.local_count;
    externalCount.value = response.external_count;
  } catch (err) {
    error.value = err.message;
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadRatedRecipes);
</script>

<template>
  <section class="grid recipes-layout">
    <article class="card stack">
      <div class="discover-header">
        <h2>Recipes You Rated</h2>
        <p class="small">Search your rated recipes and filter by score.</p>
      </div>

      <form class="search-row" @submit.prevent="loadRatedRecipes">
        <div class="search-field">
          <label for="rated-search">Search by title/cuisine</label>
          <input
            id="rated-search"
            v-model="searchQuery"
            class="search-input"
            type="text"
            placeholder="e.g. pasta or Italian"
          />
        </div>
        <div class="search-field">
          <label for="rated-score">Filter by rating</label>
          <select id="rated-score" v-model="scoreFilter" class="search-input" style="width: 160px">
            <option value="">All ratings</option>
            <option value="5">5 stars</option>
            <option value="4">4 stars</option>
            <option value="3">3 stars</option>
            <option value="2">2 stars</option>
            <option value="1">1 star</option>
          </select>
        </div>
        <button class="secondary" type="submit" :disabled="isLoading">
          {{ isLoading ? "Searching..." : "Search" }}
        </button>
      </form>

      <div class="summary">
        <span class="pill local">Local: {{ localCount }}</span>
        <span class="pill external">TheMealDB: {{ externalCount }}</span>
      </div>

      <p v-if="isLoading" class="small">Loading rated recipes...</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="!isLoading && !error && !ratedItems.length" class="small">No rated recipes found for that filter.</p>

      <ul class="list-clean" v-if="ratedItems.length">
        <li v-for="recipe in ratedItems" :key="`${recipe.source}-${recipe.id}`">
          <div class="result-row" :class="{ 'no-image': !recipe.image_url }">
            <img
              v-if="recipe.image_url"
              class="result-thumb"
              :src="recipe.image_url"
              :alt="recipe.title"
            />
            <div class="result-content">
              <RouterLink
                :to="`/recipes/cook/${recipe.source}/${recipe.source === 'themealdb' ? recipe.external_id : recipe.id}`"
              >
                {{ recipe.title }}
              </RouterLink>
              <span class="small"> ({{ recipe.cuisine }})</span>
              <div class="summary" style="margin-top: 0.35rem">
                <span class="pill" :class="recipe.source === 'local' ? 'local' : 'external'">
                  {{ recipe.source }}
                </span>
                <span class="pill quick">Your rating: {{ recipe.my_rating }}/5</span>
                <RouterLink
                  v-if="recipe.source === 'local'"
                  class="muted-link"
                  :to="`/recipes/${recipe.id}`"
                >
                  Manage
                </RouterLink>
              </div>
              <p v-if="recipe.my_comment" class="small">Comment: {{ recipe.my_comment }}</p>
              <div v-if="quickFacts(recipe).length" class="quick-facts">
                <span
                  v-for="fact in quickFacts(recipe)"
                  :key="fact"
                  class="pill quick"
                >
                  {{ fact }}
                </span>
              </div>
            </div>
          </div>
        </li>
      </ul>
    </article>
  </section>
</template>
