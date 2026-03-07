import { createRouter, createWebHistory } from "vue-router";

import CreateRecipeView from "../views/CreateRecipeView.vue";
import HealthView from "../views/HealthView.vue";
import LoginView from "../views/LoginView.vue";
import MeView from "../views/MeView.vue";
import RecipeCookView from "../views/RecipeCookView.vue";
import RecipeDetailView from "../views/RecipeDetailView.vue";
import RecipesView from "../views/RecipesView.vue";
import RegisterView from "../views/RegisterView.vue";

const routes = [
  { path: "/", redirect: "/health" },
  { path: "/health", name: "health", component: HealthView },
  { path: "/auth/register", name: "register", component: RegisterView },
  { path: "/auth/login", name: "login", component: LoginView },
  { path: "/auth/me", name: "me", component: MeView },
  { path: "/recipes", name: "recipes", component: RecipesView },
  { path: "/recipes/create", name: "recipe-create", component: CreateRecipeView },
  { path: "/recipes/cook/:source/:id", name: "recipe-cook", component: RecipeCookView, props: true },
  { path: "/recipes/:id", name: "recipe-detail", component: RecipeDetailView, props: true }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
