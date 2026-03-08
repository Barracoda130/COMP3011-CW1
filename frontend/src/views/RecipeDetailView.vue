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
const currentUser = ref(null);
const editForm = ref({ title: "", cuisine: "", prep_minutes: 20, calories: 0, image_url: "", description: "", tags: "" });
const isOwner = ref(false);

function fillEditForm(data) {
  editForm.value = {
    title: data.title,
    cuisine: data.cuisine,
    prep_minutes: data.prep_minutes,
    calories: data.calories ?? 0,
    image_url: data.image_url ?? "",
    description: data.description ?? "",
    tags: (data.tags || []).join(", ")
  };
}

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
    editForm.value.image_url = await readFileAsDataUrl(file);
  } catch (err) {
    error.value = err.message;
  }
}

async function loadRecipe() {
  error.value = "";
  message.value = "";
  try {
    const [recipeData, meData] = await Promise.all([api.getRecipe(props.id), api.me()]);
    recipe.value = recipeData;
    currentUser.value = meData;
    isOwner.value = Number(recipeData.owner_id) === Number(meData.id);
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
      image_url: editForm.value.image_url || null,
      description: editForm.value.description || null,
      tags: editForm.value.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean)
    };
    if (isOwner.value) {
      const updated = await api.updateRecipe(props.id, payload);
      router.push({ path: "/recipes/mine", query: { updated: String(updated.id) } });
    } else {
      const copied = await api.copyRecipe(props.id, payload);
      router.push({ path: "/recipes/mine", query: { updated: String(copied.id) } });
    }
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

onMounted(loadRecipe);
watch(() => props.id, loadRecipe);
</script>

<template>
  <section class="grid">
    <article class="card stack">
      <h2>{{ isOwner ? "Edit Recipe" : "Create Your Modified Copy" }}</h2>
      <p class="small">
        {{ isOwner
          ? "You own this recipe. Saving updates will modify it directly."
          : "You do not own this recipe. Saving will create a new modified copy under your account." }}
      </p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="message" class="success">{{ message }}</p>
      <label>Title</label>
      <input v-model="editForm.title" type="text" />
      <label>Cuisine</label>
      <input v-model="editForm.cuisine" type="text" />
      <label>Prep Minutes</label>
      <input v-model="editForm.prep_minutes" type="number" min="1" />
      <label>Calories</label>
      <input v-model="editForm.calories" type="number" min="0" />
      <label>Recipe Photo</label>
      <input type="file" accept="image/*" @change="onPhotoSelected" />
      <img v-if="editForm.image_url" :src="editForm.image_url" alt="Recipe preview" class="image-frame" />
      <label>Tags (comma separated)</label>
      <input v-model="editForm.tags" type="text" />
      <label>Description</label>
      <textarea v-model="editForm.description" rows="4" />
      <div class="button-row">
        <button class="secondary" @click="updateRecipe">{{ isOwner ? "Save Changes" : "Save As My Copy" }}</button>
        <button v-if="isOwner" class="danger" @click="deleteRecipe">Delete Recipe</button>
      </div>
    </article>
  </section>
</template>
