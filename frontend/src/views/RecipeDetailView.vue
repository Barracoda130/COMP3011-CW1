<script setup>
import { onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { api } from "../services/api";

const props = defineProps({
  id: { type: [String, Number], required: true }
});

const router = useRouter();
const recipe = ref(null);
const error = ref("");
const message = ref("");
const editForm = ref({ title: "", cuisine: "", prep_minutes: 20, calories: 0, description: "", tags: "" });
const rateForm = ref({ score: 5, comment: "" });
const ratingResult = ref(null);

function fillEditForm(data) {
  editForm.value = {
    title: data.title,
    cuisine: data.cuisine,
    prep_minutes: data.prep_minutes,
    calories: data.calories ?? 0,
    description: data.description ?? "",
    tags: (data.tags || []).join(", ")
  };
}

async function loadRecipe() {
  error.value = "";
  message.value = "";
  try {
    recipe.value = await api.getRecipe(props.id);
    fillEditForm(recipe.value);
  } catch (err) {
    error.value = err.message;
  }
}

async function updateRecipe() {
  error.value = "";
  message.value = "";
  try {
    const payload = {
      title: editForm.value.title,
      cuisine: editForm.value.cuisine,
      prep_minutes: Number(editForm.value.prep_minutes),
      calories: editForm.value.calories ? Number(editForm.value.calories) : null,
      description: editForm.value.description || null,
      tags: editForm.value.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean)
    };
    recipe.value = await api.updateRecipe(props.id, payload);
    fillEditForm(recipe.value);
    message.value = "Recipe updated";
  } catch (err) {
    error.value = err.message;
  }
}

async function deleteRecipe() {
  error.value = "";
  message.value = "";
  try {
    await api.deleteRecipe(props.id);
    router.push("/recipes");
  } catch (err) {
    error.value = err.message;
  }
}

async function rateRecipe() {
  error.value = "";
  message.value = "";
  ratingResult.value = null;
  try {
    ratingResult.value = await api.rateRecipe(props.id, {
      score: Number(rateForm.value.score),
      comment: rateForm.value.comment || null
    });
    await loadRecipe();
    message.value = "Rating saved";
  } catch (err) {
    error.value = err.message;
  }
}

onMounted(loadRecipe);
watch(() => props.id, loadRecipe);
</script>

<template>
  <section class="grid">
    <article class="card stack">
      <h2>Recipe Overview</h2>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="message" class="success">{{ message }}</p>
      <pre v-if="recipe">{{ JSON.stringify(recipe, null, 2) }}</pre>
    </article>

    <article class="card stack">
      <h2>Edit Recipe</h2>
      <p class="small">Only the recipe owner can edit or delete this record.</p>
      <label>Title</label>
      <input v-model="editForm.title" type="text" />
      <label>Cuisine</label>
      <input v-model="editForm.cuisine" type="text" />
      <label>Prep Minutes</label>
      <input v-model="editForm.prep_minutes" type="number" min="1" />
      <label>Calories</label>
      <input v-model="editForm.calories" type="number" min="0" />
      <label>Tags (comma separated)</label>
      <input v-model="editForm.tags" type="text" />
      <label>Description</label>
      <textarea v-model="editForm.description" rows="3" />
      <div class="button-row">
        <button class="secondary" @click="updateRecipe">Save Changes</button>
        <button class="danger" @click="deleteRecipe">Delete Recipe</button>
      </div>
    </article>

    <article class="card stack">
      <h2>Rate Recipe</h2>
      <label>Score (1-5)</label>
      <input v-model="rateForm.score" type="number" min="1" max="5" />
      <label>Comment</label>
      <textarea v-model="rateForm.comment" rows="3" />
      <button @click="rateRecipe">Submit Rating</button>
      <pre v-if="ratingResult">{{ JSON.stringify(ratingResult, null, 2) }}</pre>
    </article>
  </section>
</template>
