<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { RouterLink } from "vue-router";
import { useRoute } from "vue-router";
import { api } from "../services/api";
import { formatPrepTime } from "../utils/time";
import { loadSessionPageCache, saveSessionPageCache } from "../utils/pageCache";

const MY_RECIPES_STATE_KEY = "my-recipes-page-state";

const route = useRoute();
const items = ref([]);
const searchQuery = ref("");
const isLoading = ref(false);
const error = ref("");
const updatedRecipeId = ref(null);
const restoredScrollY = ref(0);
const restoredFromCache = ref(false);

function stepsPreview(text) {
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

async function loadMyRecipes({ background = false } = {}) {
  if (!background) {
    isLoading.value = true;
  }
  error.value = "";
  try {
    items.value = await api.listMyRecipes({ query: searchQuery.value });
    savePageState();
  } catch (err) {
    error.value = err.message;
  } finally {
    if (!background) {
      isLoading.value = false;
    }
  }
}

function getCurrentScrollY() {
  return window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
}

function savePageState() {
  const payload = {
    query: searchQuery.value,
    scrollY: getCurrentScrollY(),
    items: items.value,
    updatedRecipeId: updatedRecipeId.value
  };
  saveSessionPageCache(MY_RECIPES_STATE_KEY, payload, { maxBytes: 1_200_000, ttlMs: 10 * 60 * 1000 });
}

function restorePageState() {
  const parsed = loadSessionPageCache(MY_RECIPES_STATE_KEY, { ttlMs: 10 * 60 * 1000 });
  if (!parsed) {
    return;
  }

  if (typeof parsed.query === "string") {
    searchQuery.value = parsed.query;
  }
  if (typeof parsed.scrollY === "number" && Number.isFinite(parsed.scrollY)) {
    restoredScrollY.value = Math.max(0, parsed.scrollY);
  }
  if (Array.isArray(parsed.items)) {
    items.value = parsed.items;
    restoredFromCache.value = true;
  }
  if (typeof parsed.updatedRecipeId === "number") {
    updatedRecipeId.value = parsed.updatedRecipeId;
  }
}

function restoreScrollPosition() {
  if (restoredScrollY.value <= 0) {
    return;
  }

  const targetY = restoredScrollY.value;
  const apply = () => {
    window.scrollTo({ top: targetY, behavior: "auto" });
  };

  apply();
  requestAnimationFrame(apply);
  setTimeout(apply, 120);
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
  restorePageState();
  syncUpdatedRecipeIdFromRoute();
  window.addEventListener("beforeunload", savePageState);

  if (!restoredFromCache.value) {
    await loadMyRecipes();
    return;
  }

  await nextTick();
  restoreScrollPosition();
  // Keep cached UI snappy but immediately refresh from server to avoid stale results.
  void loadMyRecipes({ background: true });
});

watch(() => route.query.updated, syncUpdatedRecipeIdFromRoute);
watch(searchQuery, savePageState);

onUnmounted(() => {
  savePageState();
  window.removeEventListener("beforeunload", savePageState);
});

onBeforeRouteLeave(() => {
  savePageState();
});
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
                  <span class="pill quick">Prep: {{ formatPrepTime(recipe.prep_minutes) }}</span>
                  <span v-if="recipe.calories !== null && recipe.calories !== undefined" class="pill quick">
                    Calories: {{ recipe.calories }}
                  </span>
                </div>
                <p v-if="recipe.intro || recipe.steps" class="small" style="margin-top: 0.4rem">{{ stepsPreview(recipe.intro || recipe.steps) }}</p>
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
