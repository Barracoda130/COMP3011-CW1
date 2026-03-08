<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { useRoute } from "vue-router";
import { api } from "../services/api";
import { isAuthenticated } from "../stores/auth";

const props = defineProps({
  source: { type: String, required: true },
  id: { type: [String, Number], required: true }
});
const route = useRoute();

const recipe = ref(null);
const error = ref("");
const ingredientChecks = ref({});
const ratingError = ref("");
const ratingMessage = ref("");
const ratingForm = ref({ score: null, comment: "" });
const hoverScore = ref(null);
const hasSubmittedRating = ref(false);

const sourceType = computed(() => String(props.source).toLowerCase());
const canRateCookedRecipe = computed(() => sourceType.value === "local" || sourceType.value === "themealdb");
const isLoggedIn = computed(() => isAuthenticated());
const previewedScore = computed(() => hoverScore.value ?? ratingForm.value.score ?? 0);
const backPath = computed(() => {
  const from = String(route.query.from || "").toLowerCase();
  if (from === "suggested") return "/recipes/suggested";
  if (from === "rated") return "/recipes/rated";
  if (from === "mine") return "/recipes/mine";
  return "/recipes";
});
const showDescriptionAboveSteps = computed(() => {
  const description = String(recipe.value?.description || "").trim();
  const instructions = String(recipe.value?.instructions || "").trim();
  if (!description) return false;

  // ThemealDB description is often just a one-word category (e.g., "Chicken").
  const descriptionWordCount = description.split(/\s+/).filter(Boolean).length;
  if (sourceType.value === "themealdb" && descriptionWordCount <= 2) {
    return false;
  }

  if (!instructions) return true;
  return description !== instructions;
});

function normalizeHeading(rawHeading) {
  const match = rawHeading.match(/(step|task)\s*(\d+)/i);
  if (!match) {
    return rawHeading.trim().replace(/[:.-]+$/, "");
  }

  const kind = match[1][0].toUpperCase() + match[1].slice(1).toLowerCase();
  return `${kind} ${match[2]}`;
}

function parseInstructionSteps(instructions) {
  if (!instructions || !instructions.trim()) {
    return [];
  }

  const text = instructions.replace(/\r\n/g, "\n").trim();
  const markerRegex = /(step|task)\s*\d+\s*[:.-]?/gi;
  const matches = [...text.matchAll(markerRegex)].filter((match) => typeof match.index === "number");

  if (matches.length > 0) {
    const steps = [];
    const firstMatchIndex = matches[0].index;
    const intro = text.slice(0, firstMatchIndex).trim();
    let introAppended = false;

    for (let i = 0; i < matches.length; i += 1) {
      const start = matches[i].index;
      const markerText = matches[i][0];
      const contentStart = start + markerText.length;
      const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
      let body = text.slice(contentStart, end).trim().replace(/\s+/g, " ");

      if (!introAppended && intro) {
        body = `${intro} ${body}`.trim();
        introAppended = true;
      }

      if (body) {
        steps.push({
          heading: normalizeHeading(markerText),
          text: body
        });
      }
    }

    return steps;
  }

  const lineSplit = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lineSplit.length > 1) {
    return lineSplit.map((line, index) => ({
      heading: `Step ${index + 1}`,
      text: line
    }));
  }

  return text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean)
    .map((sentence, index) => ({
      heading: `Step ${index + 1}`,
      text: sentence
    }));
}

const instructionSteps = computed(() => parseInstructionSteps(recipe.value?.instructions || ""));

function resetIngredientChecklist() {
  ingredientChecks.value = {};
}

function resetRatingState() {
  ratingError.value = "";
  ratingMessage.value = "";
  hasSubmittedRating.value = false;
  hoverScore.value = null;
  ratingForm.value = { score: null, comment: "" };
}

function selectStars(score) {
  if (hasSubmittedRating.value) {
    return;
  }
  ratingForm.value.score = score;
}

function previewStars(score) {
  if (hasSubmittedRating.value) {
    return;
  }
  hoverScore.value = score;
}

function clearPreviewStars() {
  hoverScore.value = null;
}

async function loadExistingRating() {
  if (!isLoggedIn.value || !canRateCookedRecipe.value) {
    return;
  }

  try {
    const existing =
      sourceType.value === "themealdb"
        ? await api.getMyThemealdbRating(String(props.id))
        : await api.getMyRecipeRating(props.id);

    ratingForm.value = {
      score: existing.score,
      comment: existing.comment ?? ""
    };
    hasSubmittedRating.value = true;
    ratingMessage.value = "You already rated this recipe.";
  } catch (err) {
    if (err?.status === 404) {
      return;
    }
    throw err;
  }
}

async function submitRating() {
  ratingError.value = "";
  ratingMessage.value = "";

  if (!canRateCookedRecipe.value) {
    ratingError.value = "This recipe source cannot be rated right now.";
    return;
  }

  if (!ratingForm.value.score) {
    ratingError.value = "Please select a star rating first.";
    return;
  }

  try {
    const payload = {
      score: Number(ratingForm.value.score),
      comment: ratingForm.value.comment || null
    };

    if (sourceType.value === "themealdb") {
      await api.rateThemealdbRecipe(String(props.id), payload);
    } else {
      await api.rateRecipe(props.id, payload);
    }

    hasSubmittedRating.value = true;
    ratingMessage.value = "Rating submitted. You have already rated this recipe.";
  } catch (err) {
    ratingError.value = err.message;

    if (typeof err.message === "string" && err.message.toLowerCase().includes("already rated")) {
      hasSubmittedRating.value = true;
      ratingMessage.value = "You have already rated this recipe.";
      ratingError.value = "";
    }
  }
}

async function loadCookRecipe() {
  error.value = "";
  recipe.value = null;
  resetIngredientChecklist();
  resetRatingState();
  try {
    recipe.value = await api.getCookRecipe(props.source, props.id);
    await loadExistingRating();
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(loadCookRecipe);
watch(() => `${props.source}:${props.id}`, loadCookRecipe);
</script>

<template>
  <section class="card stack">
    <RouterLink :to="backPath">← Back to recipes</RouterLink>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="recipe">
      <h2>{{ recipe.title }}</h2>
      <p class="small">Source: {{ recipe.source }} | Cuisine: {{ recipe.cuisine }}</p>
      <img
        v-if="recipe.image_url"
        :src="recipe.image_url"
        :alt="recipe.title"
        class="image-frame"
      />

      <section class="grid cols-1-2">
        <div class="stack">
          <article class="card">
            <h3>Ingredients</h3>
            <ul v-if="recipe.ingredients?.length" class="checklist">
              <li v-for="(ingredient, idx) in recipe.ingredients" :key="idx">
                <label class="check-item">
                  <input v-model="ingredientChecks[idx]" type="checkbox" />
                  <span class="check-text" :class="{ done: ingredientChecks[idx] }">
                    {{ ingredient.name }}
                    <span v-if="ingredient.measure" class="small"> - {{ ingredient.measure }}</span>
                  </span>
                </label>
              </li>
            </ul>
            <p v-else class="small">No ingredient list available for this recipe.</p>
          </article>

          <article class="card">
            <h3>Recipe info</h3>
            <p class="small"><strong>Tags:</strong> {{ recipe.tags?.length ? recipe.tags.join(", ") : "No tags" }}</p>
            <p class="small">Prep: {{ recipe.prep_minutes ?? "N/A" }} mins</p>
            <p class="small">Calories: {{ recipe.calories ?? "N/A" }}</p>
            <details v-if="recipe.estimated_cost_debug" class="stack" style="margin-top: 0.4rem">
              <summary class="small">Cost Debug</summary>
              <pre>{{ JSON.stringify(recipe.estimated_cost_debug, null, 2) }}</pre>
            </details>
          </article>
        </div>

        <article class="card">
          <h3>How to cook</h3>
          <p class="small" v-if="showDescriptionAboveSteps">{{ recipe.description }}</p>
          <div v-if="instructionSteps.length" class="instruction-list">
            <article v-for="(step, idx) in instructionSteps" :key="idx" class="instruction-card">
              <h4>{{ step.heading }}</h4>
              <p>{{ step.text }}</p>
            </article>
          </div>
          <p v-else class="small">No instructions available.</p>
        </article>

        <article v-if="canRateCookedRecipe" class="card stack">
          <h3>Rate After Cooking</h3>
          <p v-if="!isLoggedIn" class="small">
            Log in to submit your rating.
            <RouterLink to="/auth">Go to login</RouterLink>
          </p>
          <template v-else>
            <label>Score</label>
            <div
              class="star-row"
              role="radiogroup"
              aria-label="Rate this recipe from 1 to 5 stars"
              @mouseleave="clearPreviewStars"
            >
              <button
                v-for="score in 5"
                :key="score"
                type="button"
                class="star-btn"
                :class="{ active: score <= (ratingForm.score ?? 0), preview: hoverScore !== null && score <= previewedScore }"
                :disabled="hasSubmittedRating"
                :aria-label="`${score} star${score > 1 ? 's' : ''}`"
                @click="selectStars(score)"
                @mouseenter="previewStars(score)"
              >
                ★
              </button>
            </div>
            <p class="small">Selected: {{ ratingForm.score ?? 0 }}/5</p>
            <label>{{ hasSubmittedRating ? "Comment" : "Comment" }}</label>
            <textarea v-if="!hasSubmittedRating" v-model="ratingForm.comment" rows="3" />
            <p v-else class="readonly-comment">{{ ratingForm.comment || "No comment provided." }}</p>
            <button v-if="!hasSubmittedRating" @click="submitRating">Submit Rating</button>
            <p v-if="ratingError" class="error">{{ ratingError }}</p>
            <p v-if="ratingMessage" class="success rating-success">{{ ratingMessage }}</p>
          </template>
        </article>
      </section>
    </template>
  </section>
</template>
