import { createRouter, createWebHistory } from "vue-router";
import { isAuthenticated } from "../stores/auth";

import AuthView from "../views/AuthView.vue";
import CreateRecipeView from "../views/CreateRecipeView.vue";
import HealthView from "../views/HealthView.vue";
import MeView from "../views/MeView.vue";
import MyRecipesView from "../views/MyRecipesView.vue";
import NotFoundView from "../views/NotFoundView.vue";
import RecipeCookView from "../views/RecipeCookView.vue";
import RecipeDetailView from "../views/RecipeDetailView.vue";
import RatedRecipesView from "../views/RatedRecipesView.vue";
import RecipesView from "../views/RecipesView.vue";
import SuggestedRecipesView from "../views/SuggestedRecipesView.vue";
import WeeklyPlanView from "../views/WeeklyPlanView.vue";

const routes = [
  { path: "/", redirect: "/recipes" },
  { path: "/health", name: "health", component: HealthView },
  { path: "/auth", name: "auth", component: AuthView },
  { path: "/auth/register", redirect: { path: "/auth", query: { mode: "register" } } },
  { path: "/auth/login", redirect: { path: "/auth", query: { mode: "login" } } },
  { path: "/auth/me", name: "me", component: MeView },
  { path: "/recipes", name: "recipes", component: RecipesView },
  { path: "/recipes/mine", name: "recipes-mine", component: MyRecipesView, meta: { requiresAuth: true } },
  { path: "/recipes/suggested", name: "recipes-suggested", component: SuggestedRecipesView, meta: { requiresAuth: true } },
  { path: "/recipes/rated", name: "recipes-rated", component: RatedRecipesView, meta: { requiresAuth: true } },
  { path: "/recipes/weekly-plan", name: "recipes-weekly-plan", component: WeeklyPlanView, meta: { requiresAuth: true } },
  { path: "/recipes/create", name: "recipe-create", component: CreateRecipeView, meta: { requiresAuth: true } },
  { path: "/recipes/cook/:source/:id", name: "recipe-cook", component: RecipeCookView, props: true },
  { path: "/recipes/:id", name: "recipe-detail", component: RecipeDetailView, props: true },
  { path: "/:pathMatch(.*)*", name: "not-found", component: NotFoundView }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !isAuthenticated()) {
    return {
      path: "/auth",
      query: { mode: "login", redirect: to.fullPath }
    };
  }

  return true;
});

export default router;
