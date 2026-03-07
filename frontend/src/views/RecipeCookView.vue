<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";

const props = defineProps({
  source: { type: String, required: true },
  id: { type: [String, Number], required: true }
});

const recipe = ref(null);
const error = ref("");
const ingredientChecks = ref({});

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
    if (intro) {
      steps.push(intro);
    }

    for (let i = 0; i < matches.length; i += 1) {
      const start = matches[i].index;
      const end = i + 1 < matches.length ? matches[i + 1].index : text.length;
      const chunk = text.slice(start, end).trim();
      if (chunk) {
        steps.push(chunk.replace(/\s+/g, " "));
      }
    }

    return steps;
  }

  const lineSplit = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lineSplit.length > 1) {
    return lineSplit;
  }

  return text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

const instructionSteps = computed(() => parseInstructionSteps(recipe.value?.instructions || ""));

function resetIngredientChecklist() {
  ingredientChecks.value = {};
}

async function loadCookRecipe() {
  error.value = "";
  recipe.value = null;
  resetIngredientChecklist();
  try {
    recipe.value = await api.getCookRecipe(props.source, props.id);
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(loadCookRecipe);
watch(() => `${props.source}:${props.id}`, loadCookRecipe);
</script>

<template>
  <section class="card stack">
    <RouterLink to="/recipes">← Back to recipes</RouterLink>
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
          </article>
        </div>

        <article class="card">
          <h3>How to cook</h3>
          <p class="small" v-if="recipe.description">{{ recipe.description }}</p>
          <ol v-if="instructionSteps.length" class="instruction-list">
            <li v-for="(step, idx) in instructionSteps" :key="idx">{{ step }}</li>
          </ol>
          <p v-else class="small">No instructions available.</p>
        </article>
      </section>
    </template>
  </section>
</template>
