<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { RouterLink } from "vue-router";
import { api } from "../services/api";
import { formatPrepTime } from "../utils/time";
import { loadSessionPageCache, saveSessionPageCache } from "../utils/pageCache";

const WEEKLY_PLAN_STATE_KEY = "weekly-plan-page-state";

const isLoading = ref(false);
const isGenerating = ref(false);
const selectingDayIndex = ref(null);
const error = ref("");
const plan = ref(null);
const optionDetails = ref({});
const restoredScrollY = ref(0);
const restoredFromCache = ref(false);

const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const orderedItems = computed(() => {
  if (!plan.value || !Array.isArray(plan.value.items)) {
    return [];
  }

  return [...plan.value.items].sort((a, b) => a.day_index - b.day_index);
});

const dayOptions = computed(() => {
  const grouped = new Map();
  for (const item of orderedItems.value) {
    const key = item.day_index;
    if (!grouped.has(key)) {
      grouped.set(key, { dayIndex: key, plannedFor: item.planned_for, options: [] });
    }
    grouped.get(key).options.push(item);
  }

  return [...grouped.values()]
    .map((day) => ({
      ...day,
      hasSelection: day.options.some((option) => option.is_selected),
      options: [...day.options].sort((a, b) => {
        if (day.options.some((option) => option.is_selected) && a.is_selected !== b.is_selected) {
          return a.is_selected ? -1 : 1;
        }
        if (a.recipe_source === b.recipe_source) {
          return a.id - b.id;
        }
        return a.recipe_source === "local" ? -1 : 1;
      })
    }))
    .sort((a, b) => a.dayIndex - b.dayIndex);
});

function toCookPath(item) {
  if (item.recipe_source === "local" && item.recipe_id) {
    return {
      path: `/recipes/cook/local/${item.recipe_id}`,
      query: { from: "weekly-plan" }
    };
  }
  if (item.recipe_source === "themealdb" && item.external_recipe_id) {
    return {
      path: `/recipes/cook/themealdb/${item.external_recipe_id}`,
      query: { from: "weekly-plan" }
    };
  }
  return null;
}

function optionSourceId(item) {
  if (item.recipe_source === "local") {
    return item.recipe_id;
  }
  if (item.recipe_source === "themealdb") {
    return item.external_recipe_id;
  }
  return null;
}

function optionDetailKey(item) {
  const id = optionSourceId(item);
  if (id === null || id === undefined || id === "") {
    return null;
  }
  return `${item.recipe_source}:${id}`;
}

function getOptionDetails(item) {
  const key = optionDetailKey(item);
  if (!key) {
    return null;
  }
  return optionDetails.value[key] || null;
}

function optionImage(item) {
  return getOptionDetails(item)?.image_url || "";
}

function optionQuickFacts(item) {
  const details = getOptionDetails(item);
  if (!details) {
    return [];
  }

  const facts = [];
  if (details.cuisine) {
    facts.push(`Cuisine: ${details.cuisine}`);
  }
  if (details.prep_minutes !== null && details.prep_minutes !== undefined) {
    facts.push(`Cook time: ${formatPrepTime(details.prep_minutes)}`);
  }
  if (details.calories !== null && details.calories !== undefined) {
    facts.push(`Calories: ${details.calories}`);
  }
  if (Array.isArray(details.tags) && details.tags.length) {
    facts.push(`Tags: ${details.tags.slice(0, 3).join(", ")}`);
  }
  return facts;
}

function formatDate(value) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short"
  });
}

async function loadCurrentPlan() {
  isLoading.value = true;
  error.value = "";
  try {
    const response = await api.getCurrentWeeklyPlan();
    plan.value = response;
    await hydrateOptionDetails(response.items || []);
    savePageState();
  } catch (err) {
    if (err?.status === 404) {
      plan.value = null;
      return;
    }
    error.value = err.message || "Failed to load weekly plan.";
  } finally {
    isLoading.value = false;
  }
}

async function generatePlan() {
  isGenerating.value = true;
  error.value = "";
  try {
    const response = await api.generateWeeklyPlan();
    plan.value = response;
    await hydrateOptionDetails(response.items || []);
    savePageState();
  } catch (err) {
    error.value = err.message || "Failed to generate weekly plan.";
  } finally {
    isGenerating.value = false;
  }
}

async function selectOption(dayIndex, recipeSource) {
  selectingDayIndex.value = dayIndex;
  error.value = "";
  try {
    const response = await api.selectWeeklyPlanOption({ dayIndex, recipeSource });
    plan.value = response;
    await hydrateOptionDetails(response.items || []);
    savePageState();
  } catch (err) {
    error.value = err.message || "Failed to save selection.";
  } finally {
    selectingDayIndex.value = null;
  }
}

function getCurrentScrollY() {
  return window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
}

function savePageState() {
  const payload = {
    scrollY: getCurrentScrollY(),
    plan: plan.value,
    optionDetails: optionDetails.value
  };
  saveSessionPageCache(WEEKLY_PLAN_STATE_KEY, payload, { maxBytes: 1_200_000, ttlMs: 10 * 60 * 1000 });
}

function restorePageState() {
  const parsed = loadSessionPageCache(WEEKLY_PLAN_STATE_KEY, { ttlMs: 10 * 60 * 1000 });
  if (!parsed) {
    return;
  }

  if (typeof parsed.scrollY === "number" && Number.isFinite(parsed.scrollY)) {
    restoredScrollY.value = Math.max(0, parsed.scrollY);
  }
  if (parsed.plan && typeof parsed.plan === "object") {
    plan.value = parsed.plan;
    restoredFromCache.value = true;
  }
  if (parsed.optionDetails && typeof parsed.optionDetails === "object") {
    optionDetails.value = parsed.optionDetails;
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

async function hydrateOptionDetails(items) {
  const pending = [];
  for (const item of items) {
    const key = optionDetailKey(item);
    const sourceId = optionSourceId(item);
    if (!key || !sourceId || optionDetails.value[key]) {
      continue;
    }

    pending.push(
      api
        .getCookRecipe(item.recipe_source, String(sourceId))
        .then((details) => ({ key, details }))
        .catch(() => ({ key, details: null }))
    );
  }

  if (!pending.length) {
    return;
  }

  const resolved = await Promise.all(pending);
  const merged = { ...optionDetails.value };
  for (const entry of resolved) {
    if (entry.details) {
      merged[entry.key] = entry.details;
    }
  }
  optionDetails.value = merged;
}

onMounted(async () => {
  restorePageState();
  window.addEventListener("beforeunload", savePageState);

  if (!restoredFromCache.value) {
    await loadCurrentPlan();
    return;
  }

  await hydrateOptionDetails(plan.value?.items || []);
  await nextTick();
  restoreScrollPosition();
});

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
        <h2>Weekly Plan</h2>
        <p class="small">Generate a 7-day plan based on your ratings and recipe preferences.</p>
      </div>

      <div class="button-row">
        <button type="button" :disabled="isGenerating" @click="generatePlan">
          {{ isGenerating ? "Generating..." : "Generate New Plan" }}
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="isLoading" class="small">Loading current weekly plan...</p>

      <p v-if="!isLoading && !error && !plan" class="small">
        No active weekly plan yet. Generate one to get started.
      </p>

      <template v-if="plan">
        <div class="summary">
          <span class="pill local">Status: {{ plan.status }}</span>
          <span class="pill quick">Week: {{ formatDate(plan.start_date) }} - {{ formatDate(plan.end_date) }}</span>
          <span class="pill">Options: {{ orderedItems.length }}</span>
        </div>

        <ul class="list-clean" v-if="dayOptions.length">
          <li v-for="day in dayOptions" :key="day.dayIndex" class="week-plan-day-block">
            <div class="week-plan-day-header">
              <div class="week-plan-day">{{ dayNames[day.dayIndex] || `Day ${day.dayIndex + 1}` }}</div>
              <span class="pill quick">{{ formatDate(day.plannedFor) }}</span>
            </div>

            <div class="week-plan-options-grid" :class="{ 'has-primary': day.hasSelection }">
              <article
                v-for="option in day.options"
                :key="option.id"
                class="week-plan-option"
                :class="{ selected: option.is_selected, 'is-primary': day.hasSelection && option.is_selected }"
              >
                <div
                  class="week-plan-option-head"
                  :class="{ 'no-image': !optionImage(option) || (day.hasSelection && !option.is_selected) }"
                >
                  <img
                    v-if="optionImage(option) && (!day.hasSelection || option.is_selected)"
                    class="week-plan-option-thumb"
                    :src="optionImage(option)"
                    :alt="option.title_snapshot"
                  />
                <div class="week-plan-main" :class="{ 'title-only': day.hasSelection && !option.is_selected }">
                  <RouterLink v-if="toCookPath(option)" :to="toCookPath(option)">
                    {{ option.title_snapshot }}
                  </RouterLink>
                  <span v-else>{{ option.title_snapshot }}</span>
                  <div v-if="!day.hasSelection || option.is_selected" class="summary" style="margin-top: 0.35rem">
                    <span class="pill" :class="option.recipe_source === 'local' ? 'local' : 'external'">
                      {{ option.recipe_source }}
                    </span>
                    <span v-if="option.is_selected" class="pill">Primary Choice</span>
                  </div>
                </div>
                </div>

                <div v-if="(!day.hasSelection || option.is_selected) && optionQuickFacts(option).length" class="quick-facts">
                  <span
                    v-for="fact in optionQuickFacts(option)"
                    :key="`${option.id}-${fact}`"
                    class="pill quick"
                  >
                    {{ fact }}
                  </span>
                </div>

                <button
                  class="secondary"
                  type="button"
                  :disabled="selectingDayIndex === day.dayIndex || option.is_selected"
                  @click="selectOption(day.dayIndex, option.recipe_source)"
                >
                  {{ option.is_selected ? "Chosen" : day.hasSelection ? "Switch To This" : "Choose This" }}
                </button>
              </article>
            </div>
          </li>
        </ul>
      </template>
    </article>
  </section>
</template>
