<script setup>
import { onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { useRouter } from "vue-router";
import { api } from "../services/api";

const router = useRouter();
const error = ref("");
const created = ref(null);
const successMessage = ref("");
const importUrl = ref("");
const importMessage = ref("");
const importing = ref(false);
let redirectTimer = null;
const form = ref({
  title: "",
  cuisine: "",
  prep_minutes: "",
  calories: "",
  intro: "",
  image_url: "",
  ingredients: "",
  tags: "quick",
  steps: ""
});

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed to read image file"));
    reader.readAsDataURL(file);
  });
}

async function onPhotoSelected(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  if (!file.type.startsWith("image/")) {
    error.value = "Please upload a valid image file.";
    return;
  }

  try {
    form.value.image_url = await readFileAsDataUrl(file);
  } catch (err) {
    error.value = err.message;
  }
}

async function createRecipe() {
  error.value = "";
  created.value = null;
  successMessage.value = "";

  try {
    const prepMinutesRaw = String(form.value.prep_minutes ?? "").trim();
    if (!prepMinutesRaw) {
      error.value = "Prep Minutes is required.";
      return;
    }

    const payload = {
      title: form.value.title,
      cuisine: form.value.cuisine.trim() || null,
      prep_minutes: Number(prepMinutesRaw),
      calories: String(form.value.calories ?? "").trim() ? Number(form.value.calories) : null,
      intro: form.value.intro || null,
      image_url: form.value.image_url || null,
      ingredients: form.value.ingredients
        .split("\n")
        .map((ingredient) => ingredient.trim())
        .filter(Boolean),
      tags: form.value.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      steps: form.value.steps || null
    };
    created.value = await api.createRecipe(payload);
    successMessage.value = "Recipe created successfully. Redirecting to My Recipes...";

    if (redirectTimer) {
      clearTimeout(redirectTimer);
    }

    redirectTimer = setTimeout(() => {
      router.push({
        path: "/recipes/mine",
        query: { updated: String(created.value.id || "") }
      });
    }, 1200);
  } catch (err) {
    error.value = err.message;
  }
}

async function importFromUrl() {
  error.value = "";
  importMessage.value = "";

  const normalizedUrl = importUrl.value.trim();
  if (!normalizedUrl) {
    error.value = "Please paste a recipe URL to import.";
    return;
  }

  importing.value = true;
  try {
    const preview = await api.importRecipeFromUrl(normalizedUrl);
    form.value.title = preview.title || form.value.title;
    form.value.cuisine = preview.cuisine || "";
    form.value.prep_minutes = preview.prep_minutes ?? "";
    form.value.calories = preview.calories ?? "";
    form.value.intro = preview.intro || form.value.intro;
    form.value.image_url = preview.image_url || form.value.image_url;
    form.value.ingredients = Array.isArray(preview.ingredients)
      ? preview.ingredients.join("\n")
      : form.value.ingredients;
    form.value.tags = Array.isArray(preview.tags) ? preview.tags.join(", ") : form.value.tags;
    form.value.steps = preview.steps || form.value.steps;
    importMessage.value = "Recipe details imported. Review and edit before creating.";
  } catch (err) {
    error.value = err.message;
  } finally {
    importing.value = false;
  }
}

onUnmounted(() => {
  if (redirectTimer) {
    clearTimeout(redirectTimer);
  }
});
</script>

<template>
  <section class="grid">
    <article class="card stack">
      <h2>Create Recipe</h2>
      <div class="summary">
        <RouterLink class="muted-link" to="/recipes">Back to Discover Recipes</RouterLink>
      </div>

      <label>Import From URL</label>
      <div class="button-row">
        <input v-model="importUrl" type="url" placeholder="https://example.com/recipe" />
        <button type="button" class="secondary" :disabled="importing" @click="importFromUrl">
          {{ importing ? "Importing..." : "Import Recipe" }}
        </button>
      </div>
      <p v-if="importMessage" class="small">{{ importMessage }}</p>

      <label>Title</label>
      <input v-model="form.title" type="text" />
      <label>Cuisine (optional)</label>
      <input v-model="form.cuisine" type="text" />
      <label>Prep Minutes</label>
      <input v-model="form.prep_minutes" type="number" min="1" />
      <label>Calories</label>
      <input v-model="form.calories" type="number" min="0" />
      <label>Intro (optional)</label>
      <textarea v-model="form.intro" rows="3" placeholder="Short context before instructions..." />
      <label>Recipe Photo</label>
      <input type="file" accept="image/*" @change="onPhotoSelected" />
      <img v-if="form.image_url" :src="form.image_url" alt="Recipe preview" class="image-frame" />
      <label>Ingredients (one per line)</label>
      <textarea v-model="form.ingredients" rows="6" placeholder="2 eggs&#10;1 cup flour&#10;1 tsp salt" />
      <label>Tags (comma separated)</label>
      <input v-model="form.tags" type="text" />
      <label>Steps</label>
      <textarea v-model="form.steps" rows="4" />
      <button @click="createRecipe">Create Recipe</button>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="successMessage" class="success">{{ successMessage }}</p>
    </article>
  </section>
</template>
