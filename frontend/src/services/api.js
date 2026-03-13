import { getToken } from "../stores/auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

function prettyFieldName(rawField) {
  return rawField
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatApiError(status, detail) {
  if (Array.isArray(detail)) {
    const fieldErrors = {};
    const messages = detail.map((item) => {
      const path = Array.isArray(item.loc) ? item.loc.join(".") : "field";
      const field = path.includes(".") ? path.split(".").slice(1).join(".") : path;
      if (field) {
        fieldErrors[field] = item.msg;
      }
      return `${prettyFieldName(field)}: ${item.msg}`;
    });
    return {
      message: `Please fix the following and try again: ${messages.join("; ")}`,
      fieldErrors
    };
  }

  if (typeof detail === "string" && detail.trim()) {
    if (status === 400 && detail.toLowerCase().includes("email already registered")) {
      return {
        message: "An account with this email already exists. Try logging in instead.",
        fieldErrors: { email: "This email is already registered" }
      };
    }
    if (status === 401) {
      return {
        message: "Login failed. Check your email and password and try again.",
        fieldErrors: {}
      };
    }
    return { message: detail, fieldErrors: {} };
  }

  if (status >= 500) {
    return { message: "Server error. Please try again in a moment.", fieldErrors: {} };
  }

  return { message: "Request failed. Please check your input and try again.", fieldErrors: {} };
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (response.status === 204) {
    return null;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const formatted = formatApiError(response.status, data.detail);
    const error = new Error(formatted.message);
    error.status = response.status;
    error.fieldErrors = formatted.fieldErrors;
    throw error;
  }
  return data;
}

export const api = {
  getHealth: () => request("/health"),
  register: (payload) => request("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: async ({ email, password }) => {
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    return request("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form
    });
  },
  me: () => request("/auth/me"),
  listRecipes: (skip = 0, limit = 20) => request(`/recipes?skip=${skip}&limit=${limit}`),
  listMyRecipes: ({ query = "" } = {}) => {
    const params = new URLSearchParams();
    if (query && query.trim()) {
      params.set("query", query.trim());
    }
    const suffix = params.toString();
    return request(`/recipes/mine${suffix ? `?${suffix}` : ""}`);
  },
  discoverRecipes: ({ query = "", localLimit = 50, externalLimit = 20 } = {}) => {
    const params = new URLSearchParams({
      query,
      local_limit: String(localLimit),
      external_limit: String(externalLimit)
    });
    return request(`/recipes/discover?${params.toString()}`);
  },
  suggestedRecipes: ({ localLimit = 30, externalLimit = 40 } = {}) => {
    const params = new URLSearchParams({
      local_limit: String(localLimit),
      external_limit: String(externalLimit)
    });
    return request(`/recipes/suggested?${params.toString()}`);
  },
  ratedRecipes: ({ query = "", score = "" } = {}) => {
    const params = new URLSearchParams();
    if (query && query.trim()) {
      params.set("query", query.trim());
    }
    if (score !== "" && score !== null && score !== undefined) {
      params.set("score", String(score));
    }
    const suffix = params.toString();
    return request(`/recipes/rated${suffix ? `?${suffix}` : ""}`);
  },
  importRecipeFromUrl: (url) =>
    request("/recipes/import-url", {
      method: "POST",
      body: JSON.stringify({ url })
    }),
  createRecipe: (payload) => request("/recipes", { method: "POST", body: JSON.stringify(payload) }),
  getRecipe: (id) => request(`/recipes/${id}`),
  getCookRecipe: (source, id) => request(`/recipes/cook/${source}/${id}`),
  getMyRecipeRating: (id) => request(`/recipes/${id}/ratings/me`),
  getMyThemealdbRating: (externalId) => request(`/recipes/themealdb/${externalId}/ratings/me`),
  generateWeeklyPlan: () => request("/users/me/weekly-plan/generate", { method: "POST" }),
  getCurrentWeeklyPlan: () => request("/users/me/weekly-plan/current"),
  selectWeeklyPlanOption: ({ dayIndex, recipeSource }) =>
    request("/users/me/weekly-plan/current/select", {
      method: "POST",
      body: JSON.stringify({ day_index: dayIndex, recipe_source: recipeSource })
    }),
  updateRecipe: (id, payload) => request(`/recipes/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  copyRecipe: (id, payload) => request(`/recipes/${id}/copy`, { method: "POST", body: JSON.stringify(payload) }),
  deleteRecipe: (id) => request(`/recipes/${id}`, { method: "DELETE" }),
  rateRecipe: (id, payload) => request(`/recipes/${id}/ratings`, { method: "POST", body: JSON.stringify(payload) }),
  rateThemealdbRecipe: (externalId, payload) =>
    request(`/recipes/themealdb/${externalId}/ratings`, { method: "POST", body: JSON.stringify(payload) })
};
