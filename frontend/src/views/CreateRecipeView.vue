<script setup>
import { onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { useRouter } from "vue-router";
import { api } from "../services/api";

const router = useRouter();
const error = ref("");
const created = ref(null);
const successMessage = ref("");
let redirectTimer = null;
const form = ref({
  title: "",
  cuisine: "",
  prep_minutes: 20,
  calories: 500,
  image_url: "",
  tags: "quick",
  description: ""
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
    const payload = {
      title: form.value.title,
      cuisine: form.value.cuisine.trim() || null,
      prep_minutes: Number(form.value.prep_minutes),
      calories: form.value.calories ? Number(form.value.calories) : null,
      image_url: form.value.image_url || null,
      tags: form.value.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      description: form.value.description || null
    };
    created.value = await api.createRecipe(payload);
    successMessage.value = "Recipe created successfully. Redirecting to Discover...";

    if (redirectTimer) {
      clearTimeout(redirectTimer);
    }

    redirectTimer = setTimeout(() => {
      router.push("/recipes");
    }, 1200);
  } catch (err) {
    error.value = err.message;
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

      <label>Title</label>
      <input v-model="form.title" type="text" />
      <label>Cuisine (optional)</label>
      <input v-model="form.cuisine" type="text" />
      <label>Prep Minutes</label>
      <input v-model="form.prep_minutes" type="number" min="1" />
      <label>Calories</label>
      <input v-model="form.calories" type="number" min="0" />
      <label>Recipe Photo</label>
      <input type="file" accept="image/*" @change="onPhotoSelected" />
      <img v-if="form.image_url" :src="form.image_url" alt="Recipe preview" class="image-frame" />
      <label>Tags (comma separated)</label>
      <input v-model="form.tags" type="text" />
      <label>Description</label>
      <textarea v-model="form.description" rows="4" />
      <button @click="createRecipe">Create Recipe</button>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="successMessage" class="success">{{ successMessage }}</p>
    </article>
  </section>
</template>
