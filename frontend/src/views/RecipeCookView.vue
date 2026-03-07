<script setup>
import { onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { api } from "../services/api";

const props = defineProps({
  source: { type: String, required: true },
  id: { type: [String, Number], required: true }
});

const recipe = ref(null);
const error = ref("");

async function loadCookRecipe() {
  error.value = "";
  recipe.value = null;
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
  <section class="card">
    <RouterLink to="/recipes">← Back to recipes</RouterLink>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="recipe">
      <h2>{{ recipe.title }}</h2>
      <p class="small">Source: {{ recipe.source }} | Cuisine: {{ recipe.cuisine }}</p>
      <img
        v-if="recipe.image_url"
        :src="recipe.image_url"
        :alt="recipe.title"
        style="max-width: 100%; border-radius: 10px; margin-bottom: 1rem"
      />

      <section class="grid" style="grid-template-columns: 1fr 2fr">
        <article class="card">
          <h3>Ingredients</h3>
          <ul v-if="recipe.ingredients?.length">
            <li v-for="(ingredient, idx) in recipe.ingredients" :key="idx">
              {{ ingredient.name }}
              <span v-if="ingredient.measure" class="small"> - {{ ingredient.measure }}</span>
            </li>
          </ul>
          <p v-else class="small">No ingredient list available for this recipe.</p>

          <h3 style="margin-top: 1rem">Tags</h3>
          <p class="small">{{ recipe.tags?.length ? recipe.tags.join(", ") : "No tags" }}</p>

          <h3 style="margin-top: 1rem">Quick info</h3>
          <p class="small">Prep: {{ recipe.prep_minutes ?? "N/A" }} mins</p>
          <p class="small">Calories: {{ recipe.calories ?? "N/A" }}</p>
        </article>

        <article class="card">
          <h3>How to cook</h3>
          <p class="small" v-if="recipe.description">{{ recipe.description }}</p>
          <pre style="white-space: pre-wrap; line-height: 1.5">{{ recipe.instructions || "No instructions available." }}</pre>
        </article>
      </section>
    </template>
  </section>
</template>
