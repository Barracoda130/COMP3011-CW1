<script setup>
import { computed } from "vue";
import { nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { RouterLink } from "vue-router";
import { api } from "../services/api";
import { isAuthenticated } from "../stores/auth";
import { formatPrepTime } from "../utils/time";
import { loadSessionPageCache, saveSessionPageCache } from "../utils/pageCache";

const RECIPES_STATE_KEY = "recipes-page-state-v2";

const recipes = ref([]);
const localCount = ref(0);
const externalCount = ref(0);
const error = ref("");
const isLoading = ref(false);
const searchQuery = ref("");
const restoredScrollY = ref(0);
const restoredFromCache = ref(false);
const authed = computed(() => isAuthenticated());

function buildQuickFacts(recipe) {
  const facts = [];

  if (recipe.prep_minutes) {
    facts.push(`Cook time: ${formatPrepTime(recipe.prep_minutes)}`);
  }
  if (recipe.calories !== null && recipe.calories !== undefined) {
    facts.push(`Calories: ${recipe.calories}`);
  }
  if (recipe.average_rating !== null && recipe.average_rating !== undefined) {
    facts.push(`Rating: ${Number(recipe.average_rating).toFixed(1)}/5`);
  }
  if (recipe.category) {
    facts.push(`Category: ${recipe.category}`);
  }
  if (Array.isArray(recipe.tags) && recipe.tags.length) {
    facts.push(`Tags: ${recipe.tags.slice(0, 3).join(", ")}`);
  }

  return facts;
}

async function loadRecipes() {
  error.value = "";
  isLoading.value = true;
  try {
    const result = await api.discoverRecipes({
      query: searchQuery.value,
      localLimit: 100,
      externalLimit: 120
    });
    recipes.value = result.items;
    localCount.value = result.local_count;
    externalCount.value = result.external_count;
    savePageState();
  } catch (err) {
    error.value = err.message;
  } finally {
    isLoading.value = false;
  }
}

function getCurrentScrollY() {
  return window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
}

function savePageState() {
  const payload = {
    searchQuery: searchQuery.value,
    scrollY: getCurrentScrollY(),
    cachedResults: recipes.value,
    localCount: localCount.value,
    externalCount: externalCount.value,
    resultsQuery: searchQuery.value
  };
  saveSessionPageCache(RECIPES_STATE_KEY, payload, { maxBytes: 1_200_000, ttlMs: 10 * 60 * 1000 });
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
  setTimeout(apply, 320);
}

function restorePageState() {
  const parsed = loadSessionPageCache(RECIPES_STATE_KEY, { ttlMs: 10 * 60 * 1000 });
  if (!parsed) {
    return;
  }

  if (typeof parsed.searchQuery === "string") {
    searchQuery.value = parsed.searchQuery;
  }
  if (typeof parsed.scrollY === "number" && Number.isFinite(parsed.scrollY)) {
    restoredScrollY.value = Math.max(0, parsed.scrollY);
  }

  if (
    Array.isArray(parsed.cachedResults) &&
    typeof parsed.resultsQuery === "string" &&
    parsed.resultsQuery === searchQuery.value
  ) {
    recipes.value = parsed.cachedResults;
    localCount.value = typeof parsed.localCount === "number" ? parsed.localCount : 0;
    externalCount.value = typeof parsed.externalCount === "number" ? parsed.externalCount : 0;
    restoredFromCache.value = true;
  }
}

function handleScrollSave() {
  savePageState();
}

watch(searchQuery, savePageState);

onBeforeRouteLeave(() => {
  savePageState();
});

onMounted(async () => {
  restorePageState();
  window.addEventListener("scroll", handleScrollSave, { passive: true });

  if (restoredFromCache.value) {
    await nextTick();
    restoreScrollPosition();
    // Revalidate cached discover results so counts are always fresh.
    await loadRecipes();
    return;
  }

  await loadRecipes();
});

onUnmounted(() => {
  savePageState();
  window.removeEventListener("scroll", handleScrollSave);
});
</script>

<template>
  <section class="grid recipes-layout">
    <article class="card stack">
      <div class="discover-header">
        <h2>Discover Recipes</h2>
        <p class="small">
          Shows recipes from both your database and TheMealDB.
          Local recipes are prioritized first.
        </p>
      </div>
      <div class="summary">
        <RouterLink v-if="authed" class="muted-link" to="/recipes/create">Go to Create Recipe</RouterLink>
      </div>
      <form class="search-row" @submit.prevent="loadRecipes">
        <div class="search-field">
          <label for="discover-search">Search by title/cuisine</label>
          <input
            id="discover-search"
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
      <p v-if="isLoading" class="small">Searching recipes, please wait...</p>
      <div class="summary">
        <span class="pill local">Local: {{ localCount }}</span>
        <span class="pill external">TheMealDB: {{ externalCount }}</span>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <ul class="list-clean">
        <li v-for="recipe in recipes" :key="`${recipe.source}-${recipe.id}`">
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
                <RouterLink
                  v-if="recipe.source === 'local'"
                  class="muted-link"
                  :to="`/recipes/${recipe.id}`"
                >
                  Manage
                </RouterLink>
              </div>
              <div v-if="buildQuickFacts(recipe).length" class="quick-facts">
                <span
                  v-for="fact in buildQuickFacts(recipe)"
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
