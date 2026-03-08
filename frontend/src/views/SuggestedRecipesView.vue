<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";

const items = ref([]);
const localCount = ref(0);
const externalCount = ref(0);
const formula = ref("");
const error = ref("");
const isLoading = ref(false);

function quickFacts(recipe) {
  const facts = [];
  if (recipe.prep_minutes) {
    facts.push(`Cook time: ${recipe.prep_minutes} min`);
  }
  if (recipe.calories !== null && recipe.calories !== undefined) {
    facts.push(`Calories: ${recipe.calories}`);
  }
  if (recipe.category) {
    facts.push(`Category: ${recipe.category}`);
  }
  if (Array.isArray(recipe.key_ingredients) && recipe.key_ingredients.length) {
    facts.push(`Key ingredients: ${recipe.key_ingredients.slice(0, 3).join(", ")}`);
  }
  if (Array.isArray(recipe.tags) && recipe.tags.length) {
    facts.push(`Tags: ${recipe.tags.slice(0, 3).join(", ")}`);
  }
  return facts;
}

async function loadSuggestions() {
  isLoading.value = true;
  error.value = "";
  try {
    const response = await api.suggestedRecipes({ localLimit: 50, externalLimit: 70 });
    items.value = response.items;
    localCount.value = response.local_count;
    externalCount.value = response.external_count;
    formula.value = response.formula;
  } catch (err) {
    error.value = err.message;
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadSuggestions);
</script>

<template>
  <section class="grid recipes-layout">
    <article class="card stack">
      <div class="discover-header">
        <h2>Suggested Recipes For You</h2>
        <p class="small">
          Suggestions are based on ingredients and tags from recipes you rated highly, while reducing matches to
          patterns from recipes you rated low.
        </p>
      </div>

      <button class="secondary" type="button" :disabled="isLoading" @click="loadSuggestions">
        {{ isLoading ? "Refreshing..." : "Refresh Suggestions" }}
      </button>

      <p v-if="formula" class="small">
        <strong>Scoring formula:</strong> {{ formula }}
      </p>

      <div class="summary">
        <span class="pill local">Local: {{ localCount }}</span>
        <span class="pill external">TheMealDB: {{ externalCount }}</span>
      </div>

      <p v-if="isLoading" class="small">Building your suggestions...</p>
      <p v-if="error" class="error">{{ error }}</p>

      <p v-if="!isLoading && !error && !items.length" class="small">
        No suggestions yet. Rate a few recipes first to build your preference profile.
      </p>

      <ul class="list-clean" v-if="items.length">
        <li v-for="recipe in items" :key="`${recipe.source}-${recipe.id}`">
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
                <span class="pill quick">Match: {{ Number(recipe.recommendation_score || 0).toFixed(3) }}</span>
                <RouterLink
                  v-if="recipe.source === 'local'"
                  class="muted-link"
                  :to="`/recipes/${recipe.id}`"
                >
                  Manage
                </RouterLink>
              </div>
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
