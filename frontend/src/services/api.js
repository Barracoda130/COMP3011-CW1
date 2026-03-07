import { getToken } from "../stores/auth";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1";

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
    throw new Error(data.detail || "Request failed");
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
  createRecipe: (payload) => request("/recipes", { method: "POST", body: JSON.stringify(payload) }),
  getRecipe: (id) => request(`/recipes/${id}`),
  updateRecipe: (id, payload) => request(`/recipes/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  deleteRecipe: (id) => request(`/recipes/${id}`, { method: "DELETE" }),
  rateRecipe: (id, payload) => request(`/recipes/${id}/ratings`, { method: "POST", body: JSON.stringify(payload) })
};
